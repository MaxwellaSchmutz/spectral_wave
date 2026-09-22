// Module worker that hosts the Python runtime (contract section 5).
//
// All numerics happen in Python: this file loads Pyodide from the pinned CDN
// URL, installs NumPy, unpacks the checksummed spectral/ archive and calls the
// bridge (spectral.browser). It never computes physics itself; it only moves
// JSON in and a copied float64 buffer out.
import type { PyodideInterface } from "pyodide";
import type { PyProxy } from "pyodide/ffi";
import { assetUrl, buildInfo } from "../buildInfo";
import type { FromWorker, ToWorker } from "../types";

interface WorkerScope {
  postMessage(message: unknown, options?: { transfer?: Transferable[] }): void;
  onmessage: ((ev: MessageEvent<ToWorker>) => void) | null;
}
const scope = self as unknown as WorkerScope;

function post(msg: FromWorker, transfer: Transferable[] = []): void {
  scope.postMessage(msg, { transfer });
}

/** Error that already carries a user-facing message. */
class RuntimeFailure extends Error {}

let py: PyodideInterface | null = null;
let bridge: PyProxy | null = null;
let readyPromise: Promise<void> | null = null;
let initFailure: string | null = null;

async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function loadRuntime(): Promise<void> {
  const { indexURL } = buildInfo.pyodide;
  post({ type: "stage", stage: "runtime", detail: "Starting Python runtime (first time only)" });

  let loadPyodide: (typeof import("pyodide"))["loadPyodide"];
  try {
    // Loaded from the pinned CDN at run time; Vite must not bundle Pyodide.
    const mod = (await import(/* @vite-ignore */ `${indexURL}pyodide.mjs`)) as typeof import("pyodide");
    loadPyodide = mod.loadPyodide;
  } catch (err) {
    throw new RuntimeFailure(
      "Could not download the Python runtime (Pyodide) from the CDN. " +
        "Check your internet connection and reload the page.",
    );
  }

  try {
    py = await loadPyodide({
      indexURL,
      stdout: (line: string) => console.log("[python]", line),
      stderr: (line: string) => console.warn("[python]", line),
    });
  } catch (err) {
    throw new RuntimeFailure(
      `The Python runtime failed to start (${errorText(err)}). ` +
        "Reload the page; a recent browser (Chrome, Edge, Firefox or Safari) is required.",
    );
  }

  post({ type: "stage", stage: "packages", detail: "Loading NumPy" });
  try {
    await py.loadPackage("numpy", { messageCallback: () => {}, errorCallback: (m: string) => console.warn(m) });
  } catch (err) {
    throw new RuntimeFailure(
      `NumPy could not be loaded (${errorText(err)}). Check your internet connection and reload the page.`,
    );
  }

  post({ type: "stage", stage: "code", detail: "Loading the spectral_wave Python code" });
  // archive.file is relative to web/public ("py/spectral-<sha12>.zip"); accept a bare name too.
  const file = buildInfo.archive.file.replace(/^\/+/, "");
  const url = assetUrl(file.includes("/") ? file : `py/${file}`);
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-cache" });
  } catch (err) {
    throw new RuntimeFailure(
      "The spectral_wave Python code could not be downloaded. Check your internet connection and reload the page.",
    );
  }
  // Static hosts may answer a missing file with an HTML page and status 200.
  if (!response.ok || (response.headers.get("content-type") ?? "").includes("text/html")) {
    throw new RuntimeFailure(
      `The spectral_wave Python code could not be downloaded (HTTP ${response.ok ? 404 : response.status}). ` +
        "The site may have been updated since this page was opened; reload the page.",
    );
  }
  const archive = await response.arrayBuffer();
  const digest = await sha256Hex(archive);
  if (digest !== buildInfo.archive.sha256) {
    throw new RuntimeFailure(
      "The downloaded Python code does not match this page (checksum mismatch). " +
        "The site may have been updated; reload the page.",
    );
  }

  try {
    py.unpackArchive(archive, "zip", { extractDir: "/home/pyodide" });
    py.runPython("import sys\nif '/home/pyodide' not in sys.path:\n    sys.path.insert(0, '/home/pyodide')");
    bridge = py.pyimport("spectral.browser") as PyProxy;
  } catch (err) {
    throw new RuntimeFailure(`The spectral_wave Python code failed to import (${errorText(err)}).`);
  }

  const versions = py.runPython(
    "import json, sys, numpy\njson.dumps({'python': sys.version.split()[0], 'numpy': numpy.__version__})",
  ) as string;
  const { python, numpy } = JSON.parse(versions) as { python: string; numpy: string };
  const sourceRevision = String((bridge as unknown as { SOURCE_REVISION: string }).SOURCE_REVISION);
  post({ type: "ready", runtime: { pyodide: py.version, python, numpy }, sourceRevision });
}

function errorText(err: unknown): string {
  const text = err instanceof Error ? err.message : String(err);
  // Keep Python tracebacks out of the UI: the last line is the useful one.
  const lines = text.trim().split("\n");
  return lines[lines.length - 1].slice(0, 300);
}

function ensureReady(): Promise<void> {
  if (!readyPromise) {
    readyPromise = loadRuntime().catch((err: unknown) => {
      initFailure =
        err instanceof RuntimeFailure ? err.message : `The Python runtime failed to start (${errorText(err)}).`;
      post({ type: "error", kind: "runtime", message: initFailure });
    });
  }
  return readyPromise;
}

type BridgeFns = {
  run(params: string, cached: string | null, onStage: (stage: string, detail: string) => void): PyProxy;
  estimate_json(params: string): string;
};

function handleRun(msg: Extract<ToWorker, { type: "run" }>): void {
  const fns = bridge as unknown as BridgeFns;
  const onStage = (stage: string, detail: string): void => {
    post({ type: "stage", id: msg.id, stage: String(stage), detail: String(detail ?? "") });
  };
  let res: PyProxy | null = null;
  let psiProxy: PyProxy | null = null;
  try {
    const cached = msg.cachedValidation ? JSON.stringify(msg.cachedValidation) : null;
    res = fns.run(JSON.stringify(msg.params), cached, onStage);
    const metaJson = res.get(0) as string;
    const meta = JSON.parse(metaJson);
    const second = res.get(1) as PyProxy | undefined | null;
    psiProxy = second ?? null;
    let psi: ArrayBuffer | null = null;
    if (psiProxy) {
      const buf = psiProxy.getBuffer("f64");
      try {
        // Own the memory: never hand out a view into the wasm heap.
        psi = (buf.data as Float64Array).slice().buffer;
      } finally {
        buf.release();
      }
    }
    post({ type: "result", id: msg.id, meta, psi }, psi ? [psi] : []);
  } catch (err) {
    post({ type: "error", id: msg.id, kind: "internal", message: `Unexpected error in the Python bridge: ${errorText(err)}` });
  } finally {
    psiProxy?.destroy();
    res?.destroy();
  }
}

function handleEstimate(msg: Extract<ToWorker, { type: "estimate" }>): void {
  const fns = bridge as unknown as BridgeFns;
  try {
    const result = JSON.parse(fns.estimate_json(JSON.stringify(msg.params)));
    post({ type: "estimate", id: msg.id, result });
  } catch (err) {
    post({ type: "error", id: msg.id, kind: "internal", message: `Cost estimate failed: ${errorText(err)}` });
  }
}

async function handle(msg: ToWorker): Promise<void> {
  await ensureReady();
  if (msg.type === "init") return;
  if (initFailure || !bridge) {
    post({ type: "error", id: msg.id, kind: "runtime", message: initFailure ?? "The Python runtime is not available." });
    return;
  }
  if (msg.type === "run") handleRun(msg);
  else if (msg.type === "estimate") handleEstimate(msg);
}

// Handle messages strictly in arrival order (init is asynchronous).
let chain: Promise<void> = Promise.resolve();
scope.onmessage = (ev: MessageEvent<ToWorker>) => {
  const msg = ev.data;
  chain = chain.then(() => handle(msg)).catch((err: unknown) => {
    post({ type: "error", kind: "internal", message: `Worker error: ${errorText(err)}` });
  });
};
