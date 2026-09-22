// Main-thread client for the Python worker.
//
// One job at a time. Every request carries an id; replies for anything but the
// current job are ignored. Cancel terminates the worker (Python cannot be
// interrupted mid-computation) and immediately starts a fresh one. A crashed
// worker is replaced the same way. Between runs the worker stays alive, so
// only the first run of a page session pays the runtime start-up.
//
// A crash is only recovered automatically when the crashed worker had fully
// started and crashes are rare (at most 2 in 10 s). A worker that dies while
// starting (e.g. its script is gone after a redeploy, or the user is offline)
// puts the client in state "failed"; the next Compute is then the one retry.
import type {
  ErrorKind,
  Estimate,
  FromWorker,
  Meta,
  Params,
  QuadratureRecord,
  RuntimeInfo,
  ToWorker,
} from "./types";

export interface RunOutcome {
  meta: Meta;
  psi: Float64Array | null;
  /** Wall-clock time from request to reply, in ms. */
  wallMs: number;
}

export class JobError extends Error {
  constructor(
    public kind: ErrorKind | "cancelled" | "busy",
    message: string,
    public field: string | null = null,
  ) {
    super(message);
  }
}

export type WorkerState = "starting" | "ready" | "failed";

/** Shown when the worker cannot be (re)started; Compute retries once per click. */
export const WORKER_FAILED_MESSAGE =
  "The Python worker could not be loaded — the site may have been updated or you are offline. Reload the page.";

const CRASH_WINDOW_MS = 10_000;
const MAX_CRASHES_IN_WINDOW = 2;

export interface ClientEvents {
  stage(stage: string, detail: string, jobId: number | null): void;
  state(state: WorkerState, info: { runtime?: RuntimeInfo; sourceRevision?: string; message?: string }): void;
}

interface Pending<T> {
  id: number;
  resolve(value: T): void;
  reject(err: JobError): void;
  started: number;
}

export class WorkerClient {
  private worker: Worker | null = null;
  private nextId = 1;
  private job: Pending<RunOutcome> | null = null;
  private estimateJob: Pending<Estimate> | null = null;
  private readyResolve: ((info: RuntimeInfo) => void) | null = null;
  private readyReject: ((err: JobError) => void) | null = null;
  private generation = 0;
  /** Whether the current worker has sent "ready". */
  private reachedReady = false;
  private crashTimes: number[] = [];

  ready: Promise<RuntimeInfo> = Promise.resolve({ pyodide: "", python: "", numpy: "" });
  state: WorkerState = "starting";
  runtime: RuntimeInfo | null = null;
  sourceRevision: string | null = null;
  failureMessage: string | null = null;

  constructor(private events: ClientEvents) {
    this.start();
  }

  get busy(): boolean {
    return this.job !== null;
  }

  /** Create a worker and ask it to load Python right away. */
  private start(): void {
    this.generation += 1;
    const generation = this.generation;
    this.state = "starting";
    this.reachedReady = false;
    this.failureMessage = null;
    this.ready = new Promise<RuntimeInfo>((resolve, reject) => {
      this.readyResolve = resolve;
      this.readyReject = reject;
    });
    // Swallow unhandled rejections; callers that care await `ready` themselves.
    this.ready.catch(() => {});
    const worker = new Worker(new URL("./worker/pyworker.ts", import.meta.url), {
      type: "module",
      name: "spectral-python",
    });
    worker.onmessage = (ev: MessageEvent<FromWorker>) => {
      if (generation === this.generation) this.onMessage(ev.data);
    };
    worker.onerror = (ev: ErrorEvent) => {
      ev.preventDefault();
      if (generation === this.generation) this.onCrash(ev.message || "");
    };
    worker.onmessageerror = () => {
      if (generation === this.generation) this.onCrash("a message from the Python worker could not be read");
    };
    this.worker = worker;
    this.events.state("starting", {});
    this.send({ type: "init" });
  }

  private send(msg: ToWorker, transfer: Transferable[] = []): void {
    this.worker?.postMessage(msg, transfer);
  }

  private onMessage(msg: FromWorker): void {
    switch (msg.type) {
      case "ready":
        this.state = "ready";
        this.reachedReady = true;
        this.runtime = msg.runtime;
        this.sourceRevision = msg.sourceRevision;
        this.readyResolve?.(msg.runtime);
        this.events.state("ready", { runtime: msg.runtime, sourceRevision: msg.sourceRevision });
        return;
      case "stage":
        if (msg.id === undefined || msg.id === this.job?.id) {
          this.events.stage(msg.stage, msg.detail, msg.id ?? null);
        }
        return;
      case "result": {
        const job = this.job;
        if (!job || job.id !== msg.id) return; // stale reply
        this.job = null;
        const psi = msg.psi ? new Float64Array(msg.psi) : null;
        job.resolve({ meta: msg.meta, psi, wallMs: performance.now() - job.started });
        return;
      }
      case "estimate": {
        const est = this.estimateJob;
        if (!est || est.id !== msg.id) return;
        this.estimateJob = null;
        est.resolve(msg.result);
        return;
      }
      case "error": {
        if (msg.kind === "runtime" && this.state !== "ready") {
          this.state = "failed";
          this.failureMessage = msg.message;
          this.readyReject?.(new JobError("runtime", msg.message));
          this.events.state("failed", { message: msg.message });
        }
        const err = new JobError(msg.kind, msg.message, msg.field ?? null);
        if (msg.id === undefined) {
          // Not tied to a request: fail whatever is outstanding.
          this.failJob(err);
          this.failEstimate(err);
        } else if (this.job?.id === msg.id) {
          this.failJob(err);
        } else if (this.estimateJob?.id === msg.id) {
          this.failEstimate(err);
        }
        return;
      }
    }
  }

  private failJob(err: JobError): void {
    const job = this.job;
    this.job = null;
    job?.reject(err);
  }

  private failEstimate(err: JobError): void {
    const est = this.estimateJob;
    this.estimateJob = null;
    est?.reject(err);
  }

  private onCrash(reason: string): void {
    const now = performance.now();
    this.crashTimes = this.crashTimes.filter((t) => now - t < CRASH_WINDOW_MS);
    this.crashTimes.push(now);
    const restart = this.reachedReady && this.crashTimes.length <= MAX_CRASHES_IN_WINDOW;
    this.worker?.terminate();
    this.worker = null;
    if (!restart) {
      this.fail(WORKER_FAILED_MESSAGE);
      return;
    }
    const why = reason ? ` (${reason})` : "";
    const err = new JobError(
      "runtime",
      `The Python worker stopped unexpectedly${why}. It has been restarted; press Compute to try again.`,
    );
    this.readyReject?.(err);
    this.failJob(err);
    this.failEstimate(err);
    this.start();
  }

  /** Give up on the current worker until the user presses Compute again. */
  private fail(message: string): void {
    this.state = "failed";
    this.failureMessage = message;
    const err = new JobError("runtime", message);
    this.readyReject?.(err);
    this.failJob(err);
    this.failEstimate(err);
    this.events.state("failed", { message });
  }

  /** Start a computation. Rejects with kind "busy" if one is already running. */
  run(params: Params, cachedValidation?: Record<string, QuadratureRecord>): Promise<RunOutcome> {
    if (this.job) return Promise.reject(new JobError("busy", "A computation is already running."));
    if (this.state === "failed") {
      // The previous runtime could not start (e.g. offline): this click is the one retry.
      this.worker?.terminate();
      this.crashTimes = [];
      this.start();
    }
    const id = this.nextId++;
    return new Promise<RunOutcome>((resolve, reject) => {
      this.job = { id, resolve, reject, started: performance.now() };
      this.send({ type: "run", id, params, cachedValidation });
    });
  }

  /**
   * Cost preview. Only sent while the runtime is ready and idle (Python runs
   * one call at a time, so a queued estimate would wait behind a compute).
   * A newer estimate supersedes an older one.
   */
  estimate(params: Params): Promise<Estimate | null> {
    if (this.state !== "ready" || this.job) return Promise.resolve(null);
    if (this.estimateJob) this.failEstimate(new JobError("cancelled", "superseded"));
    const id = this.nextId++;
    return new Promise<Estimate>((resolve, reject) => {
      this.estimateJob = { id, resolve, reject, started: performance.now() };
      this.send({ type: "estimate", id, params });
    }).catch((err: JobError) => {
      if (err.kind === "cancelled") return null;
      throw err;
    });
  }

  /** Abort the running job: terminate the worker and start a fresh one. */
  cancel(): void {
    if (!this.job) return;
    this.worker?.terminate();
    this.worker = null;
    this.readyReject?.(new JobError("cancelled", "Cancelled"));
    this.failJob(new JobError("cancelled", "Computation cancelled."));
    this.failEstimate(new JobError("cancelled", "Cancelled"));
    this.start();
  }
}
