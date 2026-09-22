// spectral_wave in the browser: page wiring.
//
// The calculation is spectral.maxwell.compute_psi, running unchanged in a
// Pyodide worker. This file builds the interface, sends canonical params to
// the worker, and plays back / plots / exports the stored psi(n, t) array.
import "./style.css";
import { buildInfo } from "./buildInfo";
import { JobError, WORKER_FAILED_MESSAGE, WorkerClient, type RunOutcome } from "./client";
import { h, setText } from "./dom";
import { buildCsv, buildNpz, buildPng, downloadBlob, slug } from "./exports";
import {
  buildForm,
  clearErrors,
  fillForm,
  readForm,
  showErrors,
  slotForPythonField,
  type FormEls,
} from "./form";
import { buildHeatImage, drawDensity, drawEmpty, drawHeatmap, prepareCanvas, type PlotData } from "./plots";
import { linspace } from "./times";
import type { Params, Preset, QuadratureRecord, SuccessMeta } from "./types";

// ---- state -----------------------------------------------------------------

interface Result {
  params: Params;
  /** stableJson(params), compared with the form to flag a stale picture. */
  paramsKey: string;
  meta: SuccessMeta;
  data: PlotData;
  heat: HTMLCanvasElement;
  presetName: string;
  modified: boolean;
  wallMs: number;
  runtime: { pyodide: string; python: string; numpy: string };
  finishedAt: Date;
}

const SPEEDS = [0.25, 0.5, 1, 2, 4];
const BASE_FPS = 30; // frames per second at 1x (the desktop timer is 33 ms)

const presets: Preset[] = buildInfo.presets;
let presetIndex = 0;
let modified = false;
let result: Result | null = null;
let frame = 0;
let playing = false;
let speed = 1;
let lastError: { kind: string; message: string; field: string | null } | null = null;
let computeStartedAt = 0;
let elapsedTimer: number | null = null;
let currentStage = "";
const sessionValidation: Record<string, QuadratureRecord> = {};

// ---- DOM -------------------------------------------------------------------

const app = document.getElementById("app")!;
const form: FormEls = buildForm();

const presetSelect = h("select", { id: "preset", testid: "preset-select", "aria-describedby": "preset-desc" });
presets.forEach((p, k) => presetSelect.append(h("option", { value: String(k) }, p.name)));
const presetDesc = h("p", { class: "preset-desc", id: "preset-desc", testid: "preset-description" });
const modifiedBadge = h("p", { class: "modified", testid: "preset-modified", "aria-live": "polite", hidden: true });

const computeBtn = h("button", { type: "button", class: "primary", testid: "compute-button" }, "Compute");
const cancelBtn = h("button", { type: "button", testid: "cancel-button", disabled: true }, "Cancel");
const estimateEl = h("p", { class: "estimate", testid: "estimate", "aria-live": "polite" });
const generalError = h("p", { class: "field-error general", testid: "error-general", "aria-live": "polite" });

const statusEl = h("p", { class: "status", testid: "status", role: "status", "aria-live": "polite" });
const elapsedEl = h("span", { class: "elapsed", testid: "elapsed" });
const warningsEl = h("ul", { class: "warnings", testid: "warnings" });

const densCanvas = h("canvas", { testid: "plot-density", role: "img", "aria-label": "Density ψ(n, t) against site n at the current time" });
const heatCanvas = h("canvas", { testid: "plot-heatmap", role: "img", "aria-label": "Heatmap of ψ(n, t): site n across, time t upward" });

const playBtn = h("button", { type: "button", testid: "play-button", "aria-label": "Play", disabled: true }, "Play");
const restartBtn = h("button", { type: "button", testid: "restart-button", disabled: true }, "Restart");
const scrub = h("input", { type: "range", min: 0, max: 0, step: 1, value: 0, testid: "scrubber", "aria-label": "Frame", disabled: true });
const frameLabel = h("span", { class: "frame-label", testid: "frame-label" }, "–");
const speedSel = h("select", { testid: "speed-select", "aria-label": "Playback speed" });
SPEEDS.forEach((s) => speedSel.append(h("option", { value: String(s) }, `${s}×`)));
speedSel.value = "1";

const readTime = h("output", { testid: "readout-time" }, "–");
const readPeak = h("output", { testid: "readout-peak" }, "–");
const readMass = h("output", { testid: "readout-mass" }, "–");

const dlParams = h("button", { type: "button", testid: "download-params", disabled: true }, "Parameters (.json)");
const dlNpz = h("button", { type: "button", testid: "download-npz", disabled: true }, "Results (.npz)");
const dlCsv = h("button", { type: "button", testid: "download-csv", disabled: true }, "Results (.csv)");
const dlPng = h("button", { type: "button", testid: "download-png", disabled: true }, "Plots (.png)");

const staleBanner = h("p", { class: "stale-banner", testid: "stale-banner", role: "status", hidden: true });
const resultCaption = h("p", { class: "result-caption", testid: "result-caption" }, "No result yet.");
const plotsBox = h("div", { class: "plots", testid: "plots" },
  h("figure", { class: "plot plot-density" }, densCanvas,
    h("figcaption", {}, "ψ(n, t) at the current time. Fixed vertical scale: the maximum over all frames. " +
      "Dashed orange lines mark potential sites.")),
  h("figure", { class: "plot plot-heatmap" }, heatCanvas,
    h("figcaption", {}, "All frames: site n across, time t upward; the white line is the current time.")));

const infoList = h("dl", { class: "info", testid: "result-info" });
const aboutList = h("dl", { class: "info", testid: "about-info" });

function build(): void {
  const header = h("header", { class: "topbar" },
    h("h1", {}, "spectral_wave"),
    h("p", { class: "tagline" },
      "A wave packet on a lattice with L channels meets a matrix potential. " +
      "The Python algorithm runs unchanged in your browser; nothing is sent to a server."));

  const presetBox = h("section", { class: "group preset", "aria-labelledby": "preset-label" },
    h("label", { for: "preset", id: "preset-label", class: "label strong" }, "Preset"),
    presetSelect, presetDesc, modifiedBadge);

  // The estimate and general error sit above the buttons: this box sticks to the
  // bottom of the panel, so text changing above the buttons cannot move them.
  const actions = h("div", { class: "actions" },
    estimateEl, generalError,
    h("div", { class: "buttons" }, computeBtn, cancelBtn),
    h("p", { class: "help" },
      "Press Enter in any field (Ctrl+Enter in the potential box) to compute. Cancel stops Python and restarts it."));

  const controls = h("aside", { class: "controls", "aria-label": "Parameters" }, presetBox, form.root, actions);

  const transport = h("div", { class: "transport", role: "group", "aria-label": "Playback" },
    playBtn, restartBtn, scrub, frameLabel,
    h("label", { class: "speed" }, "Speed ", speedSel));

  const readouts = h("div", { class: "readouts", testid: "readouts" },
    h("div", { class: "readout" }, h("span", { class: "rlabel" }, "Time t"), readTime),
    h("div", { class: "readout" }, h("span", { class: "rlabel" }, "Peak density (site)"), readPeak),
    h("div", { class: "readout wide" },
      h("span", { class: "rlabel" }, "Probability in displayed frame  Σₙ ψ(n, t) over n in [N, M]"),
      readMass,
      h("span", { class: "rnote" },
        "Not renormalized: it falls below 1 when part of the packet has left the frame [N, M].")));

  const downloads = h("section", { class: "downloads", "aria-label": "Downloads" },
    h("h2", {}, "Download"),
    h("div", { class: "buttons" }, dlParams, dlNpz, dlCsv, dlPng),
    h("p", { class: "help" },
      "Files describe the result on screen. Animated video export is available in the desktop app only."));

  const about = h("details", { class: "about", testid: "about" },
    h("summary", {}, "About this result"),
    h("h3", {}, "Quadrature check"), infoList,
    h("h3", {}, "Software"), aboutList);

  const viewer = h("main", { class: "viewer" },
    h("div", { class: "status-row" }, statusEl, elapsedEl),
    warningsEl,
    staleBanner,
    resultCaption,
    plotsBox,
    transport, readouts,
    h("div", { class: "lower" }, downloads, about));

  app.append(header, h("div", { class: "layout" }, controls, viewer));
}

// ---- presets and form --------------------------------------------------------

function applyPreset(k: number): void {
  presetIndex = k;
  const p = presets[k];
  fillForm(form, p.params, p.form_gaussian);
  setText(presetDesc, p.description);
  setModified(false);
  clearErrors(form);
  setText(generalError, "");
  syncModeUI();
  scheduleEstimate();
  updateStale();
}

function setModified(value: boolean): void {
  modified = value;
  modifiedBadge.hidden = !value;
  setText(modifiedBadge, value ? `Modified from “${presets[presetIndex].name}”` : "");
}

function syncModeUI(): void {
  const windowMode = form.inputs.amplitude_mode.value === "schober_window";
  form.windowNote.hidden = !windowMode;
  form.gaussianBox.classList.toggle("disabled", windowMode);
  for (const key of ["E0", "sigma_E", "direction", "n_init"]) {
    const el = form.inputs[key];
    el.disabled = windowMode;
    el.title = windowMode ? "Not used in Schober-window mode" : "";
  }
}

/** The value each field had at its last "input" event. */
const seenOnInput = new WeakMap<EventTarget, string>();

function onFieldEdited(ev: Event): void {
  const target = ev.target as HTMLElement;
  if (!target.matches("input, select, textarea")) return;
  const value = (target as HTMLInputElement).value;
  // "change" fires on blur, i.e. at mousedown on Compute. If "input" already
  // handled this value, do nothing: no text may change under the pointer.
  if (ev.type === "change" && seenOnInput.get(target) === value) return;
  if (ev.type === "input") seenOnInput.set(target, value);
  if (!modified) setModified(true);
  if (target === form.inputs.amplitude_mode) syncModeUI();
  // Clear the message of the field being edited; others stay until the next run.
  const slot = target.closest(".field")?.getAttribute("data-slot");
  if (slot) {
    const err = form.errors[slot as keyof FormEls["errors"]];
    if (err) {
      setText(err, "");
      err.closest(".field")?.classList.remove("invalid");
    }
  }
  scheduleEstimate();
  updateStale();
}

// ---- displayed result vs form ------------------------------------------------

/** JSON with object keys sorted at every level, so equal params compare equal. */
function stableJson(value: unknown): string {
  return JSON.stringify(value, (_key, v: unknown) => {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const src = v as Record<string, unknown>;
      return Object.fromEntries(Object.keys(src).sort().map((k) => [k, src[k]]));
    }
    return v;
  });
}

/** Form params, or null when the form does not parse (never throws). */
function formParams(): Params | null {
  try {
    return readForm(form).params;
  } catch {
    return null;
  }
}

let resultMatchesForm = false;

function resultLabel(r: Result): string {
  return `“${r.presetName}”${r.modified ? " (modified)" : ""}`;
}

/** Banner, dimming and status when the plots no longer describe the form. */
function updateStale(): void {
  if (!result) {
    resultMatchesForm = false;
    staleBanner.hidden = true;
    plotsBox.classList.remove("stale");
    setText(resultCaption, "No result yet.");
    return;
  }
  const p = formParams();
  resultMatchesForm = p !== null && stableJson(p) === result.paramsKey;
  setText(resultCaption, `Showing ${resultLabel(result)}${resultMatchesForm ? "" : " — not the current form"}`);
  staleBanner.hidden = resultMatchesForm;
  setText(staleBanner, resultMatchesForm ? ""
    : `The plots show ${resultLabel(result)} as last computed; the form has changed — press Compute to update.`);
  plotsBox.classList.toggle("stale", !resultMatchesForm);
  if (statusEl.dataset.done === "true") {
    setText(statusEl, resultMatchesForm ? doneText : "Form changed since the last result. Press Compute to update the plots.");
    statusEl.dataset.kind = resultMatchesForm ? "ok" : "info";
  }
}

// ---- status ------------------------------------------------------------------

/** Set after Cancel (or a crash) while the fresh worker starts. */
let restartNote = "";

const STAGE_TEXT: Record<string, string> = {
  runtime: "Starting Python runtime (first time only)",
  packages: "Loading NumPy (first time only)",
  code: "Loading the spectral_wave Python code",
  validating: "Checking the parameters",
  computing: "Computing ψ(n, t)",
  checking: "Checking the quadrature",
  refining: "Refining the quadrature",
  done: "Finishing",
};

/** The "Done: …" line of the result on screen, restored when the form matches it again. */
let doneText = "";

function setStatus(text: string, kind: "info" | "busy" | "ok" | "error" | "warn" = "info"): void {
  setText(statusEl, text);
  statusEl.dataset.kind = kind;
  delete statusEl.dataset.done;
}

function stageLine(stage: string, detail: string): string {
  const base = STAGE_TEXT[stage] ?? stage;
  return detail && detail !== base ? `${base}: ${detail}` : base;
}

function startElapsed(): void {
  computeStartedAt = performance.now();
  const tick = () => setText(elapsedEl, `${((performance.now() - computeStartedAt) / 1000).toFixed(1)} s`);
  tick();
  elapsedTimer = window.setInterval(tick, 100);
}

function stopElapsed(): void {
  if (elapsedTimer !== null) window.clearInterval(elapsedTimer);
  elapsedTimer = null;
  setText(elapsedEl, "");
}

function setBusy(busy: boolean): void {
  computeBtn.disabled = busy;
  cancelBtn.disabled = !busy;
  computeBtn.setAttribute("aria-busy", String(busy));
  document.body.classList.toggle("busy", busy);
}

// ---- worker ------------------------------------------------------------------

const client = new WorkerClient({
  stage(stage, detail, jobId) {
    currentStage = stage;
    if (jobId !== null || client.busy) setStatus(`${stageLine(stage, detail)} …`, "busy");
    else if (restartNote) setStatus(`${restartNote} Restarting Python …`, "warn");
    else setStatus(`${stageLine(stage, detail)} … You can already edit the parameters.`, "busy");
  },
  state(state, info) {
    if (state === "ready") {
      if (!client.busy) {
        setStatus(restartNote ? `${restartNote} Python is ready again.`
          : result ? "Ready." : "Ready. Pick a preset and press Compute.", restartNote ? "warn" : "info");
      }
      restartNote = "";
      if (!result) render();
      scheduleEstimate();
      renderAbout();
    } else if (state === "failed") {
      restartNote = "";
      setText(estimateEl, "");
      delete estimateEl.dataset.pending;
      setStatus(info.message ?? WORKER_FAILED_MESSAGE, "error");
      if (!result) render();
    }
  },
});

// ---- estimate (live cost preview) ------------------------------------------

let estimateTimer: number | null = null;
function scheduleEstimate(): void {
  if (estimateTimer !== null) window.clearTimeout(estimateTimer);
  // The old estimate stays (dimmed, marked pending) until the new one replaces
  // it: emptying it here would shift the layout under a click in progress.
  if (estimateEl.textContent) estimateEl.dataset.pending = "true";
  estimateTimer = window.setTimeout(() => void runEstimate(), 350);
}

function showEstimate(text: string, kind: "info" | "warn" = "info"): void {
  estimateEl.dataset.kind = kind;
  delete estimateEl.dataset.pending;
  setText(estimateEl, text);
}

function mb(bytes: number): string {
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(2)} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
}

async function runEstimate(): Promise<void> {
  estimateTimer = null;
  let params: Params | null;
  try {
    params = readForm(form).params;
  } catch (err) {
    showEstimate(`No cost estimate: the form could not be read (${errorText(err)}).`, "warn");
    return;
  }
  if (!params) {
    showEstimate("");
    return;
  }
  if (client.state !== "ready" || client.busy) return;
  try {
    const est = await client.estimate(params);
    if (!est) return;
    if (est.ok) {
      const values = params.times.n_t * (params.M - params.N + 1);
      showEstimate(`Estimated working memory ≈ ${mb(est.bytes_peak ?? 0)} · result ${values.toLocaleString("en-US")} values`);
    } else if (est.error) {
      showEstimate(est.error.message, est.error.kind === "over_budget" ? "warn" : "info");
    }
  } catch {
    showEstimate("");
  }
}

/** End a message with a full stop so a following sentence reads correctly. */
function sentence(text: string): string {
  const t = text.trim();
  return /[.!?)]$/.test(t) ? t : `${t}.`;
}

/** Plain text for an unexpected exception (never HTML, never a stack). */
function errorText(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.slice(0, 300) || "unknown error";
}

// ---- compute -------------------------------------------------------------------

function cachedValidation(): Record<string, QuadratureRecord> {
  return { ...buildInfo.presetValidation, ...sessionValidation };
}

function presetLabel(): string {
  return presets[presetIndex]?.name ?? "custom";
}

/** Check psi before it may replace what is on screen. */
function checkResult(params: Params, meta: SuccessMeta, psi: Float64Array | null): string | null {
  const nSites = params.M - params.N + 1;
  const nT = params.times.n_t;
  if (!psi) return "Python returned no data.";
  if (!meta.shape || meta.shape[0] !== nT || meta.shape[1] !== nSites) {
    return `Python returned shape ${JSON.stringify(meta.shape)}, expected [${nT}, ${nSites}].`;
  }
  if (psi.length !== nT * nSites) return `Python returned ${psi.length} values, expected ${nT * nSites}.`;
  for (let i = 0; i < psi.length; i++) if (!Number.isFinite(psi[i])) return "The result contains non-finite values.";
  if (!Array.isArray(meta.mass_in_frame) || meta.mass_in_frame.length !== nT) return "Python returned no per-frame probability.";
  return null;
}

const ERROR_TITLE: Record<string, string> = {
  invalid_input: "Check the input",
  over_budget: "Too large to compute in the browser",
  unresolved: "The energy integral did not converge",
  nonfinite: "The result was not finite",
  internal: "Internal error",
  runtime: "Python runtime problem",
};

interface ExecOptions {
  presetName: string;
  modified: boolean;
}

/** The one path every computation takes (button, Enter and the test hook). */
async function execute(params: Params, opts: ExecOptions): Promise<RunOutcome> {
  if (client.busy) throw new JobError("busy", "A computation is already running.");
  lastError = null;
  setBusy(true);
  startElapsed();
  setStatus(client.state === "ready" ? `${STAGE_TEXT.validating} …` : `${STAGE_TEXT.runtime} …`, "busy");
  setText(warningsEl, "");
  try {
    const outcome = await client.run(params, cachedValidation());
    const { meta, psi } = outcome;
    const elapsed = outcome.wallMs;
    if (!meta.ok) {
      lastError = { kind: meta.error.kind, message: meta.error.message, field: meta.error.field };
      const slot = slotForPythonField(meta.error.field);
      if (slot) showErrors(form, { [slot]: meta.error.message });
      else setText(generalError, meta.error.message);
      setStatus(`${ERROR_TITLE[meta.error.kind] ?? "Not computed"}: ${sentence(meta.error.message)}` +
        (result ? " The previous result is still shown." : ""), "error");
      return outcome;
    }
    const problem = checkResult(params, meta, psi);
    if (problem) {
      lastError = { kind: "invalid_result", message: problem, field: null };
      setStatus(`The result was rejected: ${problem}` + (result ? " The previous result is still shown." : ""), "error");
      return outcome;
    }
    showResult(params, meta, psi!, opts, elapsed);
    return outcome;
  } catch (err) {
    const e = err instanceof JobError ? err : new JobError("internal", String(err));
    lastError = { kind: e.kind, message: e.message, field: e.field };
    if (e.kind === "cancelled") {
      restartNote = "Cancelled." + (result ? " The previous result is still shown." : "");
      setStatus(`${restartNote} Restarting Python …`, "warn");
    } else if (e.kind === "runtime" && client.state === "failed") {
      setStatus(client.failureMessage ?? e.message, "error");
    } else if (e.kind === "runtime" && client.state === "starting") {
      restartNote = `${e.message}`;
      setStatus(e.message, "error");
    } else {
      setStatus(`${ERROR_TITLE[e.kind] ?? "Error"}: ${e.message}`, "error");
    }
    throw e;
  } finally {
    stopElapsed();
    setBusy(false);
    scheduleEstimate();
  }
}

async function computeFromForm(): Promise<void> {
  if (client.busy) return; // no stacking
  clearErrors(form);
  setText(generalError, "");
  let read: ReturnType<typeof readForm>;
  try {
    read = readForm(form);
  } catch (err) {
    setText(generalError, `The form could not be read: ${errorText(err)}. Check the fields and try again.`);
    setStatus("Not computed: the form could not be read.", "error");
    return;
  }
  const { params, errors } = read;
  if (!params) {
    showErrors(form, errors);
    setStatus("Not computed: fix the highlighted field(s).", "error");
    const first = Object.keys(errors)[0];
    if (first) (form.errors[first as keyof FormEls["errors"]].closest(".field")?.querySelector("input, textarea, select") as HTMLElement | null)?.focus();
    return;
  }
  try {
    await execute(params, { presetName: presetLabel(), modified });
  } catch {
    /* already reported in the status line */
  }
}

function showResult(params: Params, meta: SuccessMeta, psi: Float64Array, opts: ExecOptions, wallMs: number): void {
  const nT = meta.shape[0];
  const nSites = meta.shape[1];
  let globalMax = 0;
  for (let i = 0; i < psi.length; i++) if (psi[i] > globalMax) globalMax = psi[i];
  const data: PlotData = {
    psi, nT, nSites,
    N: params.N, M: params.M,
    times: linspace(params.times.t_min, params.times.t_max, nT),
    globalMax,
    jSites: params.j_sites.slice(),
  };
  const runtime = client.runtime ?? { pyodide: "", python: meta.runtime.python, numpy: meta.runtime.numpy };
  result = {
    params, paramsKey: stableJson(params), meta, data, heat: buildHeatImage(data),
    presetName: opts.presetName, modified: opts.modified, wallMs, runtime, finishedAt: new Date(),
  };
  const q = meta.quadrature;
  sessionValidation[meta.config_key] = {
    source_revision: meta.source_revision,
    requested_n_quad: q.requested_n_quad,
    used_n_quad: q.used_n_quad,
    check_n_quad: q.check_n_quad,
    discrepancy_rel_peak: q.discrepancy_rel_peak,
    tolerance: q.tolerance,
    status: q.status,
  };

  scrub.max = String(nT - 1);
  for (const el of [playBtn, restartBtn, scrub, dlParams, dlNpz, dlCsv, dlPng]) el.disabled = false;
  setFrame(0);
  renderInfo();
  const pyMs = Object.values(meta.timing_ms ?? {}).reduce((a, b) => a + (Number(b) || 0), 0);
  doneText = `Done: ${nT} frames × ${nSites} sites in ${(wallMs / 1000).toFixed(2)} s ` +
    `(Python ${(pyMs / 1000).toFixed(2)} s). Quadrature ${q.status}.`;
  setStatus(doneText, "ok");
  statusEl.dataset.done = "true";
  warningsEl.replaceChildren(...(meta.warnings ?? []).map((w) => h("li", {}, w)));
  updateStale();
  play();
}

// ---- playback -------------------------------------------------------------------

let rafId: number | null = null;
let lastTick = 0;
let frameFloat = 0;

function setFrame(k: number): void {
  if (!result) return;
  frame = Math.max(0, Math.min(result.data.nT - 1, Math.round(k)));
  frameFloat = frame;
  scrub.value = String(frame);
  render();
}

function play(): void {
  if (!result) return;
  if (frame >= result.data.nT - 1) setFrame(0);
  playing = true;
  playBtn.textContent = "Pause";
  playBtn.setAttribute("aria-label", "Pause");
  lastTick = performance.now();
  if (rafId === null) rafId = requestAnimationFrame(tick);
}

function pause(): void {
  playing = false;
  playBtn.textContent = "Play";
  playBtn.setAttribute("aria-label", "Play");
  if (rafId !== null) cancelAnimationFrame(rafId);
  rafId = null;
}

function tick(now: number): void {
  rafId = null;
  if (!playing || !result) return;
  // The rAF timestamp can precede the performance.now() taken in play().
  const dt = Math.max(0, Math.min(250, now - lastTick));
  lastTick = Math.max(lastTick, now);
  frameFloat += (dt / 1000) * BASE_FPS * speed;
  const last = result.data.nT - 1;
  if (frameFloat >= last) {
    frame = last;
    scrub.value = String(frame);
    render();
    pause();
    return;
  }
  const k = Math.max(0, Math.floor(frameFloat));
  if (k !== frame) {
    frame = k;
    scrub.value = String(frame);
    render();
  }
  rafId = requestAnimationFrame(tick);
}

function togglePlay(): void {
  if (playing) pause();
  else play();
}

// ---- rendering ------------------------------------------------------------------

function fmt(x: number, digits = 4): string {
  if (x === 0) return "0";
  const a = Math.abs(x);
  if (a >= 1e4 || a < 1e-3) return x.toExponential(digits - 1);
  return x.toPrecision(digits);
}

function render(): void {
  if (!result) {
    drawEmpty(densCanvas, client.state === "ready" ? "Press Compute to run the selected preset"
      : client.state === "failed" ? "Python could not be loaded. Reload the page." : "Python is starting …");
    drawEmpty(heatCanvas, "The time/site heatmap appears here");
    return;
  }
  const d = result.data;
  frame = Math.max(0, Math.min(d.nT - 1, frame));
  const pd = prepareCanvas(densCanvas);
  if (pd) drawDensity(pd.ctx, pd.w, pd.h, d, frame);
  const ph = prepareCanvas(heatCanvas);
  if (ph) drawHeatmap(ph.ctx, ph.w, ph.h, d, frame, result.heat);

  const base = frame * d.nSites;
  let peak = -1;
  let at = 0;
  for (let k = 0; k < d.nSites; k++) {
    if (d.psi[base + k] > peak) {
      peak = d.psi[base + k];
      at = d.N + k;
    }
  }
  setText(frameLabel, `frame ${frame + 1} / ${d.nT}`);
  scrub.setAttribute("aria-valuetext", `frame ${frame + 1} of ${d.nT}, t = ${fmt(d.times[frame])}`);
  setText(readTime, fmt(d.times[frame], 5));
  setText(readPeak, `${fmt(peak)}  (n = ${at})`);
  setText(readMass, result.meta.mass_in_frame[frame].toFixed(6));
}

function row(dl: HTMLElement, key: string, value: string, testid?: string): void {
  dl.append(h("dt", {}, key), h("dd", { testid }, value));
}

function renderInfo(): void {
  infoList.replaceChildren();
  if (!result) return;
  const { meta } = result;
  const q = meta.quadrature;
  const statusText: Record<string, string> = {
    verified: "verified: the requested nodes agree with a run at twice as many",
    refined: "refined: the requested nodes were not enough; more nodes were used and checked",
    cached: "cached: this exact configuration was verified before (same code revision); computed once",
  };
  row(infoList, "Status", statusText[q.status] ?? q.status, "info-status");
  row(infoList, "Nodes used / requested", `${q.used_n_quad} / ${q.requested_n_quad}`, "info-nodes");
  row(infoList, "Check nodes", q.check_n_quad === null ? "—" : String(q.check_n_quad), "info-check");
  row(infoList, "Discrepancy / tolerance",
    `${q.discrepancy_rel_peak === null ? "—" : q.discrepancy_rel_peak.toExponential(2)} / ${q.tolerance.toExponential(0)}` +
      "  (max |Δψ| relative to peak)", "info-discrepancy");
  row(infoList, "Energy segments",
    q.segments ? q.segments.map(([a, b]) => `[${a}, ${b}]`).join(", ") : `single interval [${q.interval_used.join(", ")}]`,
    "info-segments");
  row(infoList, "Compute time",
    `${(result.wallMs / 1000).toFixed(2)} s wall clock; Python ` +
      Object.entries(meta.timing_ms ?? {}).map(([k, v]) => `${k} ${(Number(v) / 1000).toFixed(2)} s`).join(", "),
    "info-time");
  row(infoList, "Source", `${result.presetName}${result.modified ? " (modified)" : ""}`, "info-preset");
  renderAbout();
}

function renderAbout(): void {
  aboutList.replaceChildren();
  const rt = result?.runtime ?? client.runtime;
  row(aboutList, "Python", result?.meta.runtime.python ?? rt?.python ?? "not loaded yet", "about-python");
  row(aboutList, "NumPy", result?.meta.runtime.numpy ?? rt?.numpy ?? "not loaded yet", "about-numpy");
  row(aboutList, "Pyodide", rt?.pyodide || buildInfo.pyodide.version, "about-pyodide");
  row(aboutList, "Source revision", result?.meta.source_revision ?? client.sourceRevision ?? buildInfo.sourceRevision, "about-revision");
  row(aboutList, "Algorithm", "spectral.maxwell.compute_psi (unchanged desktop code)", "about-algorithm");
}

// ---- downloads --------------------------------------------------------------------

function baseName(): string {
  if (!result) return "spectral_wave";
  const stamp = result.finishedAt.toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return `spectral_wave-${slug(result.presetName)}${result.modified ? "-modified" : ""}-${stamp}`;
}

function describe(): Record<string, unknown> {
  const r = result!;
  return {
    preset: r.presetName,
    modified_from_preset: r.modified,
    params: r.params,
    quadrature: r.meta.quadrature,
    source_revision: r.meta.source_revision,
    runtime: { pyodide: r.runtime.pyodide, python: r.meta.runtime.python, numpy: r.meta.runtime.numpy },
    config_key: r.meta.config_key,
    timing_ms: r.meta.timing_ms,
    warnings: r.meta.warnings ?? [],
    computed_at: r.finishedAt.toISOString(),
  };
}

function downloadParams(): void {
  if (!result) return;
  const body = { format: "spectral_wave parameters", ...describe() };
  downloadBlob(new Blob([JSON.stringify(body, null, 2) + "\n"], { type: "application/json" }), `${baseName()}-params.json`);
}

function downloadNpz(): void {
  if (!result) return;
  const d = result.data;
  const metadata = {
    format: "spectral_wave result",
    arrays: {
      psi: {
        shape: [d.nT, d.nSites], dims: ["time", "site"], dtype: "float64",
        meaning: "probability density psi(n, t) on lattice site n at time times[i], as computed by " +
          "spectral.maxwell.compute_psi (not renormalized)",
        units: "dimensionless probability per site",
      },
      times: {
        shape: [d.nT], dtype: "float64",
        meaning: "time of each psi row: numpy.linspace(t_min, t_max, n_t)",
        units: "lattice time (hbar = 1; the energy scale is set by the hoppings a)",
      },
      sites: { shape: [d.nSites], dtype: "int64", meaning: "lattice site index n of each psi column (N..M)" },
      mass_in_frame: {
        shape: [d.nT], dtype: "float64",
        meaning: "sum over n in [N, M] of psi(n, t) for each time (not renormalized; falls below 1 when the packet leaves the frame)",
      },
    },
    dimensions: { n_t: d.nT, n_sites: d.nSites, N: d.N, M: d.M },
    ...describe(),
  };
  downloadBlob(buildNpz({ data: d, massInFrame: result.meta.mass_in_frame, metadata }), `${baseName()}.npz`);
}

function downloadCsv(): void {
  if (!result) return;
  downloadBlob(buildCsv(result.data), `${baseName()}-psi.csv`);
}

async function downloadPng(): Promise<void> {
  if (!result) return;
  const r = result;
  const title = `spectral_wave — ${r.presetName}${r.modified ? " (modified)" : ""}`;
  const sub = `t = ${fmt(r.data.times[frame], 5)}  (frame ${frame + 1} of ${r.data.nT})   ·   L = ${r.params.L}, ` +
    `a = [${r.params.a.join(", ")}], sites ${r.params.N}..${r.params.M}, outer branch ${r.params.outer_sign > 0 ? "+1" : "−1"}, ` +
    `quadrature ${r.meta.quadrature.status} (${r.meta.quadrature.used_n_quad} nodes)`;
  try {
    const blob = await buildPng(r.data, frame, r.heat, title, sub);
    downloadBlob(blob, `${baseName()}-t${String(frame).padStart(4, "0")}.png`);
  } catch (err) {
    setStatus(`PNG export failed: ${String(err)}`, "error");
  }
}

// ---- events -------------------------------------------------------------------------

function wire(): void {
  presetSelect.addEventListener("change", () => applyPreset(Number(presetSelect.value)));
  form.root.addEventListener("input", onFieldEdited);
  form.root.addEventListener("change", onFieldEdited);
  form.root.addEventListener("keydown", (ev) => {
    const t = ev.target as HTMLElement;
    if (ev.key !== "Enter") return;
    if (t instanceof HTMLTextAreaElement && !(ev.ctrlKey || ev.metaKey)) return;
    if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) {
      ev.preventDefault();
      void computeFromForm();
    }
  });
  computeBtn.addEventListener("click", () => void computeFromForm());
  cancelBtn.addEventListener("click", () => client.cancel());

  playBtn.addEventListener("click", togglePlay);
  restartBtn.addEventListener("click", () => {
    setFrame(0);
    play();
  });
  scrub.addEventListener("input", () => {
    pause();
    setFrame(Number(scrub.value));
  });
  speedSel.addEventListener("change", () => {
    speed = Number(speedSel.value);
  });

  document.addEventListener("keydown", (ev) => {
    const t = ev.target as HTMLElement;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (t.closest("input:not([type=range]), textarea, select, button, summary")) return;
    if (!result) return;
    if (ev.key === " " || ev.key === "k") {
      ev.preventDefault();
      togglePlay();
    } else if (t === scrub) {
      return; // the slider handles its own arrow keys
    } else if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
      ev.preventDefault();
      pause();
      setFrame(frame + (ev.key === "ArrowRight" ? 1 : -1));
    } else if (ev.key === "Home") {
      ev.preventDefault();
      pause();
      setFrame(0);
    } else if (ev.key === "End") {
      ev.preventDefault();
      pause();
      setFrame(result.data.nT - 1);
    }
  });

  dlParams.addEventListener("click", downloadParams);
  dlNpz.addEventListener("click", downloadNpz);
  dlCsv.addEventListener("click", downloadCsv);
  dlPng.addEventListener("click", () => void downloadPng());

  // Redraw on any size change, including while paused.
  const ro = new ResizeObserver(() => render());
  ro.observe(densCanvas);
  ro.observe(heatCanvas);
  window.matchMedia?.(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener?.("change", () => render());
}

// ---- test hooks -----------------------------------------------------------------------

declare global {
  interface Window {
    __spectralWave: {
      readonly ready: Promise<unknown>;
      run(params: Params): Promise<{ meta: unknown; psi: number[] }>;
      state(): Record<string, unknown>;
      presets: Preset[];
    };
  }
}

window.__spectralWave = {
  get ready() {
    return client.ready;
  },
  async run(params: Params) {
    const outcome = await execute(params, { presetName: "test run", modified: true });
    return { meta: outcome.meta, psi: outcome.psi ? Array.from(outcome.psi) : [] };
  },
  state() {
    return {
      ...(result?.meta ?? {}),
      meta: result?.meta ?? null,
      params: result?.params ?? null,
      frameIndex: frame,
      nFrames: result?.data.nT ?? 0,
      playing,
      speed,
      busy: client.busy,
      workerState: client.state,
      stage: currentStage,
      preset: presets[presetIndex]?.name ?? null,
      presetId: presets[presetIndex]?.id ?? null,
      modified,
      amplitudeMode: form.inputs.amplitude_mode.value,
      resultPreset: result?.presetName ?? null,
      resultModified: result?.modified ?? null,
      resultMatchesForm,
      staleShown: !staleBanner.hidden,
      lastError,
    };
  },
  presets,
};

// ---- start --------------------------------------------------------------------------

build();
wire();
applyPreset(0);
render();
renderAbout();
if (client.state === "starting") setStatus(`${STAGE_TEXT.runtime} … You can already edit the parameters.`, "busy");
