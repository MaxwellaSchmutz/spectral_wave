// 5. Downloads: parameters (.json), results (.npz, .csv) and plots (.png) are
// parsed in node and checked against the result the page computed.
import { test, expect, type Page } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  WEB_DIR, appState, hookRun, linspace, openApp, pngSize, presets, readNpy, readZip, testLog, type App,
} from "./support";

test.describe.configure({ mode: "serial" });

let app: App;
let params: any;
let meta: any;
let psi: Float64Array;

test.beforeAll(async ({ browser }) => {
  app = await openApp(browser, { acceptDownloads: true });
  params = structuredClone((await presets(app.page)).find((p) => p.id === "two-channel-coupled")!.params);
  params.times = { t_min: -2.5, t_max: 30, n_t: 37 };
  params.outer_sign = -1;
  const r = await hookRun(app.page, params);
  expect(r.meta.ok).toBe(true);
  meta = r.meta;
  psi = r.psi;
  const s = await appState(app.page);
  expect(s.meta.config_key, "the hook result is the one on screen").toBe(meta.config_key);
  await app.page.getByTestId("play-button").click(); // pause for a stable frame
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

async function download(page: Page, testid: string, testInfo: any): Promise<{ name: string; buf: Buffer }> {
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId(testid).click()]);
  const name = dl.suggestedFilename();
  const path = testInfo.outputPath(name);
  await dl.saveAs(path);
  expect(await dl.failure()).toBeNull();
  return { name, buf: readFileSync(path) };
}

test("downloads: parameters .json (source revision, runtime versions, actual quadrature)", async ({}, testInfo) => {
  const { name, buf } = await download(app.page, "download-params", testInfo);
  expect(name).toMatch(/^spectral_wave-.*-params\.json$/);
  const j = JSON.parse(buf.toString("utf-8"));
  const ready = (await testLog(app.page)).received.find((r) => r.type === "ready")!;
  expect(j.format).toBe("spectral_wave parameters");
  expect(j.source_revision).toBe(meta.source_revision);
  expect(j.source_revision).toBe(ready.sourceRevision);
  expect(j.runtime).toEqual({ pyodide: "314.0.7", python: "3.14.2", numpy: "2.4.6" });
  expect(ready.runtime).toEqual(j.runtime);
  expect(j.quadrature.used_n_quad).toBe(meta.quadrature.used_n_quad);
  expect(j.quadrature.check_n_quad).toBe(meta.quadrature.check_n_quad);
  expect(j.quadrature.status).toBe(meta.quadrature.status);
  expect(j.quadrature.discrepancy_rel_peak).toBe(meta.quadrature.discrepancy_rel_peak);
  expect(j.params).toEqual(params);
  expect(j.config_key).toBe(meta.config_key);
});

test("downloads: results .npz (psi/times/sites/mass_in_frame + metadata.json)", async ({}, testInfo) => {
  const { name, buf } = await download(app.page, "download-npz", testInfo);
  expect(name).toMatch(/^spectral_wave-.*\.npz$/);
  const zip = readZip(buf);
  expect([...zip.keys()].sort()).toEqual(["mass_in_frame.npy", "metadata.json", "psi.npy", "sites.npy", "times.npy"]);
  const [nT, nS] = meta.shape;

  const p = readNpy(zip.get("psi.npy")!);
  expect(p.descr).toBe("<f8");
  expect(p.fortran).toBe(false);
  expect(p.shape).toEqual([nT, nS]);
  const pd = p.data as Float64Array;
  let mismatches = 0;
  for (let i = 0; i < psi.length; i++) if (!Object.is(pd[i], psi[i])) mismatches++;
  expect(mismatches, "psi.npy equals the in-page result bit for bit").toBe(0);
  for (const i of [0, 1, nS + 3, Math.floor(psi.length / 2), psi.length - 1]) expect(pd[i]).toBe(psi[i]);

  const t = readNpy(zip.get("times.npy")!);
  expect(t.shape).toEqual([nT]);
  expect(Array.from(t.data as Float64Array)).toEqual(linspace(params.times.t_min, params.times.t_max, nT));
  const s = readNpy(zip.get("sites.npy")!);
  expect(s.descr).toBe("<i8");
  expect(Array.from(s.data as BigInt64Array, Number)).toEqual(Array.from({ length: nS }, (_, k) => params.N + k));
  const m = readNpy(zip.get("mass_in_frame.npy")!);
  expect(m.shape).toEqual([nT]);
  expect(Array.from(m.data as Float64Array)).toEqual(meta.mass_in_frame);

  const md = JSON.parse(zip.get("metadata.json")!.toString("utf-8"));
  expect(md.format).toBe("spectral_wave result");
  expect(md.arrays.psi.shape).toEqual([nT, nS]);
  expect(md.arrays.psi.dtype).toBe("float64");
  expect(md.dimensions).toEqual({ n_t: nT, n_sites: nS, N: params.N, M: params.M });
  expect(md.source_revision).toBe(meta.source_revision);
  expect(md.runtime.python).toBe("3.14.2");
  expect(md.runtime.numpy).toBe("2.4.6");
  expect(md.quadrature.used_n_quad).toBe(meta.quadrature.used_n_quad);
  expect(md.params).toEqual(params);

  // Cross-check with real NumPy when the repo venv is available (skipped otherwise).
  const py = resolve(WEB_DIR, "..", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  if (existsSync(py)) {
    const path = testInfo.outputPath(name);
    const code = "import sys, json, numpy as np\nz = np.load(sys.argv[1])\n" +
      "out = {k: [list(z[k].shape), str(z[k].dtype)] for k in ('psi', 'times', 'sites', 'mass_in_frame')}\n" +
      "out['psi_sum'] = float(z['psi'].sum())\nprint(json.dumps(out))";
    const r = spawnSync(py, ["-c", code, path], { encoding: "utf-8", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } });
    expect(r.status, r.stderr).toBe(0);
    const out = JSON.parse(r.stdout);
    expect(out.psi).toEqual([[nT, nS], "float64"]);
    expect(out.sites).toEqual([[nS], "int64"]);
    expect(out.times).toEqual([[nT], "float64"]);
    expect(out.mass_in_frame).toEqual([[nT], "float64"]);
    let sum = 0;
    for (const v of psi) sum += v;
    expect(Math.abs(out.psi_sum - sum)).toBeLessThan(1e-9 * Math.abs(sum));
  }
});

test("downloads: results .csv (dimensions and values)", async ({}, testInfo) => {
  const { name, buf } = await download(app.page, "download-csv", testInfo);
  expect(name).toMatch(/^spectral_wave-.*-psi\.csv$/);
  const lines = buf.toString("utf-8").trimEnd().split("\n");
  const [nT, nS] = meta.shape;
  expect(lines.length).toBe(nT + 1);
  const header = lines[0].split(",");
  expect(header.length).toBe(nS + 1);
  expect(header.slice(1).map(Number)).toEqual(Array.from({ length: nS }, (_, k) => params.N + k));
  const times = linspace(params.times.t_min, params.times.t_max, nT);
  for (const i of [0, 5, nT - 1]) {
    const row = lines[i + 1].split(",").map(Number);
    expect(row.length).toBe(nS + 1);
    expect(row[0]).toBe(times[i]);
    for (const k of [0, 17, Math.floor(nS / 2), nS - 1]) expect(row[k + 1], `psi[${i}, ${k}]`).toBe(psi[i * nS + k]);
  }
});

test("downloads: plots .png (signature and dimensions)", async ({}, testInfo) => {
  const { name, buf } = await download(app.page, "download-png", testInfo);
  expect(name).toMatch(/^spectral_wave-.*-t\d{4}\.png$/);
  const { width, height } = pngSize(buf);
  await testInfo.attach("png.json", { body: JSON.stringify({ name, width, height, bytes: buf.length }), contentType: "application/json" });
  expect(width).toBeGreaterThanOrEqual(1000);
  expect(height).toBeGreaterThanOrEqual(800);
  expect(width).toBeLessThanOrEqual(8192);
  expect(height).toBeLessThanOrEqual(8192);
  expect(buf.length).toBeGreaterThan(20_000); // a real picture, not an empty canvas
});
