// Shared helpers for the spectral_wave browser harness.
//
// - openApp(): one page per spec file (Pyodide cold start is expensive), with a
//   Worker wrapper injected before the app loads so tests can see every
//   message sent to / received from the Python worker and every worker's
//   lifetime. The wrapper never changes messages, except that a test may set
//   window.__swTestStripCache = true to drop cachedValidation from run requests
//   (forcing the browser to do its own n vs 2n convergence check).
// - Health: console errors/warnings, page errors, failed requests and HTTP >= 400
//   responses are collected for the whole page session and checked after every
//   test (the only tolerated entry is Firefox's wasm "try instruction is
//   deprecated" warning from Pyodide).
// - Small readers for .npz (stored zip), .npy and PNG headers.
import { expect, type Browser, type BrowserContext, type Page, type TestInfo } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";

export const WEB_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const REF_DIR = resolve(WEB_DIR, "tests", ".ref");
export const LIVE = !!process.env.SW_BASE_URL;
export const PYODIDE_INDEX = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

// ---------------------------------------------------------------- types ----

export type Params = Record<string, any>;

export interface Health {
  console: { type: string; text: string; where: string }[];
  pageErrors: string[];
  failedRequests: { url: string; failure: string }[];
  badResponses: { url: string; status: number }[];
  requests: { url: string; status?: number; fromWorker?: boolean }[];
  /** Entries matching these are tolerated (with a reason). */
  allowed: { pattern: RegExp; reason: string }[];
}

export interface App {
  context: BrowserContext;
  page: Page;
  health: Health;
  /** ms from navigation start to window.__spectralWave.ready resolving */
  coldStartMs: number;
  /** Health check of everything collected during the test; call from test.afterEach. */
  afterEach(testInfo: TestInfo): Promise<void>;
  close(): Promise<void>;
}

// ------------------------------------------------------ instrumentation ----

const INIT_SCRIPT = `(() => {
  const Orig = window.Worker;
  const log = { workers: [], sent: [], received: [] };
  window.__swTest = log;
  window.__swTestStripCache = false;
  class InstrumentedWorker extends Orig {
    constructor(url, opts) {
      super(url, opts);
      const rec = { idx: log.workers.length, url: String(url), alive: true, created: performance.now(), terminated: null };
      log.workers.push(rec);
      this.__rec = rec;
      this.addEventListener("message", (e) => {
        const d = e.data || {};
        const r = { w: rec.idx, type: d.type, id: d.id, stage: d.stage, t: performance.now() };
        if (d.type === "ready") { r.sourceRevision = d.sourceRevision; r.runtime = d.runtime; }
        if (d.type === "result") { r.ok = d.meta && d.meta.ok; }
        log.received.push(r);
      });
    }
    postMessage(msg, transfer) {
      let m = msg;
      if (m && m.type === "run" && window.__swTestStripCache) { m = Object.assign({}, m); delete m.cachedValidation; }
      log.sent.push({ w: this.__rec.idx, type: m && m.type, id: m && m.id, hasCache: !!(m && m.cachedValidation), t: performance.now() });
      return super.postMessage(m, transfer);
    }
    terminate() { this.__rec.alive = false; this.__rec.terminated = performance.now(); return super.terminate(); }
  }
  window.Worker = InstrumentedWorker;
})();`;

const FIREFOX_WASM_TRY = /WebAssembly exception handling 'try' instruction is deprecated/;

export async function openApp(browser: Browser, opts: { acceptDownloads?: boolean; viewport?: { width: number; height: number } } = {}): Promise<App> {
  const context = await browser.newContext({
    acceptDownloads: opts.acceptDownloads ?? true,
    viewport: opts.viewport ?? { width: 1400, height: 1000 },
  });
  await context.addInitScript({ content: INIT_SCRIPT });
  const page = await context.newPage();
  const health: Health = {
    console: [], pageErrors: [], failedRequests: [], badResponses: [], requests: [],
    allowed: browser.browserType().name() === "firefox"
      ? [{ pattern: FIREFOX_WASM_TRY, reason: "Pyodide wasm 'try instruction is deprecated' (Firefox)" }]
      : [],
  };
  const onConsole = (where: string) => (msg: { type(): string; text(): string }) => {
    const type = msg.type();
    if (type === "error" || type === "warning" || type === "assert") health.console.push({ type, text: msg.text(), where });
  };
  page.on("console", onConsole("page"));
  page.on("worker", (w) => {
    // Worker console events exist on recent Playwright; page "console" may also relay them.
    (w as any).on?.("console", onConsole(`worker ${w.url()}`));
  });
  page.on("pageerror", (err) => health.pageErrors.push(String(err?.stack || err)));
  context.on("requestfailed", (req) => health.failedRequests.push({ url: req.url(), failure: req.failure()?.errorText ?? "?" }));
  context.on("response", (res) => {
    health.requests.push({ url: res.url(), status: res.status() });
    if (res.status() >= 400) health.badResponses.push({ url: res.url(), status: res.status() });
  });
  context.on("request", (req) => {
    if (!health.requests.some((r) => r.url === req.url())) health.requests.push({ url: req.url() });
  });

  // Playwright's trace / screenshot-on-failure settings also cover this manual context.
  const t0 = Date.now();
  const resp = await page.goto("./", { waitUntil: "domcontentloaded" });
  try {
    await page.waitForFunction(() => !!(window as any).__spectralWave, undefined, { timeout: 30_000 });
  } catch {
    throw new Error(
      `${page.url()} (HTTP ${resp?.status()}, title "${await page.title()}") is not the spectral_wave web app: ` +
      "window.__spectralWave never appeared. Is the site deployed / was web/dist built?",
    );
  }
  await page.evaluate(() => (window as any).__spectralWave.ready);
  const coldStartMs = Date.now() - t0;
  const app: App = {
    context, page, health, coldStartMs,
    async afterEach(testInfo: TestInfo) {
      await expectHealthy(app, testInfo);
    },
    async close() {
      await context.close();
    },
  };
  return app;
}

/** Problems collected since the last call (and clears them). */
export function takeHealthProblems(h: Health): string[] {
  const out: string[] = [];
  const ok = (text: string) => h.allowed.some((a) => a.pattern.test(text));
  for (const c of h.console) if (!ok(c.text)) out.push(`console ${c.type} (${c.where}): ${c.text}`);
  for (const e of h.pageErrors) if (!ok(e)) out.push(`page error: ${e}`);
  for (const f of h.failedRequests) if (!ok(`${f.failure} ${f.url}`)) out.push(`request failed: ${f.url} (${f.failure})`);
  for (const b of h.badResponses) if (!ok(`${b.status} ${b.url}`)) out.push(`HTTP ${b.status}: ${b.url}`);
  h.console.length = 0;
  h.pageErrors.length = 0;
  h.failedRequests.length = 0;
  h.badResponses.length = 0;
  return out;
}

export async function expectHealthy(app: App, testInfo: TestInfo): Promise<void> {
  const problems = takeHealthProblems(app.health);
  if (problems.length) await testInfo.attach("health-problems.txt", { body: problems.join("\n"), contentType: "text/plain" });
  expect(problems, "console errors / failed requests during this test").toEqual([]);
}

// ---------------------------------------------------------------- app ops --

export interface TestLog {
  workers: { idx: number; url: string; alive: boolean; created: number; terminated: number | null }[];
  sent: { w: number; type: string; id?: number; hasCache: boolean; t: number }[];
  received: { w: number; type: string; id?: number; stage?: string; t: number; ok?: boolean; sourceRevision?: string; runtime?: any }[];
}

export function testLog(page: Page): Promise<TestLog> {
  return page.evaluate(() => (window as any).__swTest);
}

export function appState(page: Page): Promise<Record<string, any>> {
  return page.evaluate(() => (window as any).__spectralWave.state());
}

/** Run canonical params through the page's test hook; psi comes back as a Float64Array. */
export async function hookRun(page: Page, params: Params): Promise<{ meta: any; psi: Float64Array; wallMs: number }> {
  const r = await page.evaluate(async (p) => {
    const t0 = performance.now();
    const out = await (window as any).__spectralWave.run(p);
    const wallMs = performance.now() - t0;
    const f = Float64Array.from(out.psi as number[]);
    const bytes = new Uint8Array(f.buffer);
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return { meta: out.meta, b64: btoa(bin), wallMs };
  }, params);
  const buf = Buffer.from(r.b64, "base64");
  const psi = new Float64Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  return { meta: r.meta, psi, wallMs: r.wallMs };
}

export async function waitIdle(page: Page, timeout = 240_000): Promise<void> {
  await page.waitForFunction(() => {
    const s = (window as any).__spectralWave.state();
    return !s.busy && s.workerState === "ready";
  }, undefined, { timeout, polling: 50 });
}

export function presets(page: Page): Promise<{ id: string; name: string; params: Params }[]> {
  return page.evaluate(() => (window as any).__spectralWave.presets);
}

export async function selectPreset(page: Page, id: string): Promise<void> {
  const list = await presets(page);
  const k = list.findIndex((p) => p.id === id);
  expect(k, `preset ${id}`).toBeGreaterThanOrEqual(0);
  const sel = page.getByTestId("preset-select");
  // Always produce a real change event, even when re-selecting the current preset.
  await sel.selectOption(String((k + 1) % list.length));
  await sel.selectOption(String(k));
}

/**
 * Commit the focused field (blur -> "change") and let the debounced cost estimate
 * go out and come back, so the Compute button is not moving when it is clicked.
 * (Clicking straight after an edit can lose the click: see the dedicated
 * layout-shift test in jobs.spec.ts.)
 */
export async function settleForm(page: Page): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.waitForTimeout(450);
  await page.waitForFunction(() => {
    const log = (window as any).__swTest;
    const answered = new Set(log.received.filter((r: any) => r.type === "estimate").map((r: any) => r.id));
    return log.sent
      .filter((s: any) => s.type === "estimate" && log.workers[s.w].alive)
      .every((s: any) => answered.has(s.id));
  }, undefined, { timeout: 30_000 });
  await page.waitForTimeout(50);
}

/** Click Compute and wait until the job has finished (success or error). */
export async function computeViaUi(page: Page): Promise<void> {
  await settleForm(page);
  await page.getByTestId("compute-button").click();
  await waitIdle(page);
}

// ------------------------------------------------------------------ refs ---

export interface RefCase {
  id: string;
  params: Params;
  meta: string;
  ok: boolean;
  bin: string | null;
  status?: string;
  used_n_quad?: number;
  error_kind?: string;
}

export interface RefIndex {
  sourceRevision: string;
  runtime: { python: string; numpy: string };
  cases: RefCase[];
}

export function loadRefIndex(): RefIndex {
  const p = resolve(REF_DIR, "index.json");
  if (!existsSync(p)) throw new Error(`missing ${p}: run "python web/scripts/native_reference.py" from the repo root`);
  return JSON.parse(readFileSync(p, "utf-8"));
}

export function loadRefMeta(c: RefCase): any {
  return JSON.parse(readFileSync(resolve(REF_DIR, c.meta), "utf-8"));
}

export function loadRefPsi(c: RefCase): Float64Array {
  const buf = readFileSync(resolve(REF_DIR, c.bin!));
  // .bin is little-endian float64; decode explicitly (independent of host endianness).
  const out = new Float64Array(buf.length / 8);
  for (let i = 0; i < out.length; i++) out[i] = buf.readDoubleLE(i * 8);
  return out;
}

/** Local build-info (undefined when testing a live URL, which may be a different build). */
export function localBuildInfo(): any | undefined {
  const p = resolve(WEB_DIR, "src", "generated", "build-info.json");
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf-8")) : undefined;
}

// ------------------------------------------------------- file formats ------

/** Entries of a ZIP (STORED or deflate) read via the central directory. */
export function readZip(buf: Buffer): Map<string, Buffer> {
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("zip: no end-of-central-directory record");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const out = new Map<string, Buffer>();
  for (let k = 0; k < count; k++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Error("zip: bad central directory entry");
    const method = buf.readUInt16LE(p + 10);
    const csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28);
    const xlen = buf.readUInt16LE(p + 30);
    const clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf-8", p + 46, p + 46 + nlen);
    if (buf.readUInt32LE(local) !== 0x04034b50) throw new Error(`zip: bad local header for ${name}`);
    const lnlen = buf.readUInt16LE(local + 26);
    const lxlen = buf.readUInt16LE(local + 28);
    const start = local + 30 + lnlen + lxlen;
    const raw = buf.subarray(start, start + csize);
    out.set(name, method === 0 ? Buffer.from(raw) : inflateRawSync(raw));
    p += 46 + nlen + xlen + clen;
  }
  return out;
}

export interface Npy {
  descr: string;
  fortran: boolean;
  shape: number[];
  data: Float64Array | BigInt64Array;
}

export function readNpy(buf: Buffer): Npy {
  if (buf.readUInt8(0) !== 0x93 || buf.toString("latin1", 1, 6) !== "NUMPY") throw new Error("npy: bad magic");
  const major = buf.readUInt8(6);
  const hlen = major === 1 ? buf.readUInt16LE(8) : buf.readUInt32LE(8);
  const hstart = major === 1 ? 10 : 12;
  const header = buf.toString("latin1", hstart, hstart + hlen);
  const descr = /'descr':\s*'([^']+)'/.exec(header)?.[1] ?? "?";
  const fortran = /'fortran_order':\s*True/.test(header);
  const shapeText = /'shape':\s*\(([^)]*)\)/.exec(header)?.[1] ?? "";
  const shape = shapeText.split(",").map((s) => s.trim()).filter(Boolean).map(Number);
  const off = hstart + hlen;
  if (off % 64 !== 0) throw new Error(`npy: data offset ${off} not 64-aligned`);
  const n = shape.reduce((a, b) => a * b, 1);
  let data: Float64Array | BigInt64Array;
  if (descr === "<f8") {
    data = new Float64Array(n);
    for (let i = 0; i < n; i++) data[i] = buf.readDoubleLE(off + 8 * i);
  } else if (descr === "<i8") {
    data = new BigInt64Array(n);
    for (let i = 0; i < n; i++) data[i] = buf.readBigInt64LE(off + 8 * i);
  } else throw new Error(`npy: unsupported dtype ${descr}`);
  if (buf.length !== off + 8 * n) throw new Error(`npy: ${buf.length - off} data bytes for ${n} values`);
  return { descr, fortran, shape, data };
}

export function pngSize(buf: Buffer): { width: number; height: number } {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (!buf.subarray(0, 8).equals(sig)) throw new Error("png: bad signature");
  if (buf.toString("latin1", 12, 16) !== "IHDR") throw new Error("png: IHDR is not the first chunk");
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

// ------------------------------------------------------------- canvases ----

export interface CanvasPixels {
  width: number;
  height: number;
  cssWidth: number;
  cssHeight: number;
  dpr: number;
  /** RGBA bytes, base64 */
  b64: string;
}

export async function canvasPixels(page: Page, testid: string): Promise<CanvasPixels> {
  return page.evaluate((id) => {
    const c = document.querySelector(`[data-testid="${id}"]`) as HTMLCanvasElement;
    // Copy into a scratch canvas made for readback, so the app's own canvas is only drawn from
    // (reading it directly makes Chrome warn about willReadFrequently).
    const scratch = document.createElement("canvas");
    scratch.width = c.width;
    scratch.height = c.height;
    const ctx = scratch.getContext("2d", { willReadFrequently: true })!;
    ctx.drawImage(c, 0, 0);
    const img = ctx.getImageData(0, 0, c.width, c.height);
    let bin = "";
    for (let i = 0; i < img.data.length; i += 0x8000) bin += String.fromCharCode(...img.data.subarray(i, i + 0x8000));
    const r = c.getBoundingClientRect();
    return { width: c.width, height: c.height, cssWidth: r.width, cssHeight: r.height, dpr: window.devicePixelRatio || 1, b64: btoa(bin) };
  }, testid);
}

export function rgba(p: CanvasPixels): Buffer {
  return Buffer.from(p.b64, "base64");
}

/** numpy.linspace(start, stop, num) exactly as web/src/times.ts documents it. */
export function linspace(start: number, stop: number, num: number): number[] {
  const out: number[] = [];
  const div = num - 1;
  const step = (stop - start) / div;
  for (let i = 0; i < num; i++) out.push(i * step + start);
  out[num - 1] = stop;
  return out;
}
