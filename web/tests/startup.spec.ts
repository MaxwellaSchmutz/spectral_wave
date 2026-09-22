// 6. Startup and health: cold start (navigation -> ready), warm compute times
// for three presets, where the runtime and the Python code came from, and a
// clean console / network log (checked after every test in every spec file by
// App.afterEach; this file additionally checks origins and the archive hash).
import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
import {
  LIVE, PYODIDE_INDEX, appState, localBuildInfo, openApp, selectPreset, settleForm, testLog, waitIdle, type App,
} from "./support";

test.describe.configure({ mode: "serial" });

let app: App;
const timings: Record<string, unknown> = {};

test.beforeAll(async ({ browser }) => {
  app = await openApp(browser); // fresh context: empty HTTP cache, so this is a true cold start
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

test("startup: cold start, runtime versions and where code was loaded from", async ({ baseURL }, testInfo) => {
  const page = app.page;
  const log = await testLog(page);
  const stage = (name: string) => log.received.find((r) => r.type === "stage" && r.stage === name)?.t;
  const ready = log.received.find((r) => r.type === "ready")!;
  const nav = await page.evaluate(() => {
    const n = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    return { responseEnd: n.responseEnd, domContentLoaded: n.domContentLoadedEventEnd };
  });
  Object.assign(timings, {
    browser: testInfo.project.name,
    baseURL,
    cold_start_ms_navigation_to_ready: app.coldStartMs,
    in_page_ms: {
      document_response_end: Math.round(nav.responseEnd),
      dom_content_loaded: Math.round(nav.domContentLoaded),
      stage_runtime: Math.round(stage("runtime") ?? NaN),
      stage_packages: Math.round(stage("packages") ?? NaN),
      stage_code: Math.round(stage("code") ?? NaN),
      ready: Math.round(ready.t),
    },
    runtime: ready.runtime,
    source_revision: ready.sourceRevision,
  });
  console.log(`  [${testInfo.project.name}] cold start ${app.coldStartMs} ms (ready at ${Math.round(ready.t)} ms in-page)`);
  expect(ready.runtime).toEqual({ pyodide: "314.0.7", python: "3.14.2", numpy: "2.4.6" });
  await expect(page.getByTestId("status")).toHaveText(/Ready/);
  await expect(page.getByTestId("about")).toContainText("314.0.7");

  // Pyodide from the pinned CDN path.
  const reqs = app.health.requests;
  const mjs = reqs.find((r) => r.url === `${PYODIDE_INDEX}pyodide.mjs`);
  expect(mjs, `pyodide.mjs requested from ${PYODIDE_INDEX}`).toBeTruthy();
  expect(reqs.some((r) => r.url.startsWith(PYODIDE_INDEX) && /pyodide\.asm\.wasm$/.test(r.url))).toBe(true);
  expect(reqs.some((r) => r.url.startsWith(PYODIDE_INDEX) && /numpy.*\.(whl|zip)$/.test(r.url)), "numpy wheel from the CDN").toBe(true);

  // The Python archive from <base>py/, its name carrying its own sha256 prefix.
  const archives = [...new Set(reqs.map((r) => r.url).filter((u) => /\/py\/spectral-[0-9a-f]{12}\.zip$/.test(u)))];
  expect(archives.length, `archive requests: ${archives.join(", ")}`).toBe(1);
  const archiveUrl = archives[0];
  expect(archiveUrl.startsWith(`${baseURL}py/`), `${archiveUrl} under ${baseURL}py/`).toBe(true);
  const body = await (await app.context.request.get(archiveUrl)).body();
  const sha = createHash("sha256").update(body).digest("hex");
  expect(archiveUrl.endsWith(`spectral-${sha.slice(0, 12)}.zip`), "archive name = sha256 prefix of its bytes").toBe(true);
  const info = localBuildInfo();
  if (!LIVE && info) {
    expect(archiveUrl).toBe(`${baseURL}${info.archive.file}`);
    expect(sha).toBe(info.archive.sha256);
    expect(body.length).toBe(info.archive.bytes);
    expect(ready.sourceRevision).toBe(info.sourceRevision);
  }
  Object.assign(timings, { archive: { url: archiveUrl, sha256: sha, bytes: body.length } });

  // Nothing is loaded from anywhere else.
  const origin = new URL(baseURL!).origin;
  const foreign = reqs.map((r) => r.url).filter((u) => !u.startsWith(origin) && !u.startsWith(PYODIDE_INDEX) && !/^(data|blob):/.test(u));
  expect(foreign, "requests outside the site and the pinned Pyodide path").toEqual([]);
});

test("startup: warm compute times for three presets", async ({}, testInfo) => {
  const page = app.page;
  const runs: any[] = [];
  for (const id of ["free-gaussian", "two-channel-coupled", "schober-2"]) {
    await selectPreset(page, id);
    await settleForm(page);
    const t0 = Date.now();
    await page.getByTestId("compute-button").click();
    await waitIdle(page);
    const wall = Date.now() - t0; // click -> result on screen (Python has been warm since the cold start)
    const s = await appState(page);
    expect(s.meta?.ok, id).toBe(true);
    runs.push({ preset: id, wall_ms: wall, python_ms: s.meta.timing_ms, status: s.meta.quadrature.status, used_n_quad: s.meta.quadrature.used_n_quad, shape: s.meta.shape });
    await expect(page.getByTestId("status")).toHaveText(/^Done:/);
  }
  timings.warm_compute = runs;
  console.log(`  [${testInfo.project.name}] warm computes: ${runs.map((r) => `${r.preset} ${r.wall_ms} ms (${r.status})`).join(", ")}`);
  await testInfo.attach("timings.json", { body: JSON.stringify(timings, null, 1), contentType: "application/json" });
  for (const r of runs) expect(r.wall_ms, `${r.preset} warm compute`).toBeLessThan(60_000);
});
