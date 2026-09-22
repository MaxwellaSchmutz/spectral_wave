// 1. Parity: every native reference case (web/tests/.ref, written by
// web/scripts/native_reference.py through spectral.browser.run under native
// CPython) is run in the browser through window.__spectralWave.run and compared
// element-wise: |b - n| <= atol + rtol * |n| with rtol = 1e-9, atol = 1e-11.
import { test, expect } from "@playwright/test";
import {
  LIVE, hookRun, loadRefIndex, loadRefMeta, loadRefPsi, openApp, testLog, type App, type RefCase,
} from "./support";

const RTOL = 1e-9;
const ATOL = 1e-11;

test.describe.configure({ mode: "serial" });

let app: App;
test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

interface CaseReport {
  id: string;
  compared: boolean;
  skipped?: string;
  shape?: [number, number];
  status?: { browser: string; native: string };
  used_n_quad?: { browser: number; native: number };
  check_n_quad?: { browser: number | null; native: number | null };
  max_abs_diff?: number;
  max_diff_over_peak?: number;
  worst_ratio_to_tolerance?: number;
  violations?: number;
  browser_wall_ms?: number;
  problems: string[];
}

function compare(c: RefCase, meta: any, psi: Float64Array, ref: any, refPsi: Float64Array | null, report: CaseReport): void {
  const p = report.problems;
  if (!c.ok) {
    if (meta.ok) p.push(`native returned error ${ref.error?.kind} but browser succeeded`);
    else if (meta.error.kind !== ref.error.kind) p.push(`error kind ${meta.error.kind} != native ${ref.error.kind}`);
    else if (meta.error.field !== ref.error.field) p.push(`error field ${meta.error.field} != native ${ref.error.field}`);
    return;
  }
  if (!meta.ok) {
    p.push(`browser error ${meta.error.kind}: ${meta.error.message}`);
    return;
  }
  const eq = (what: string, a: unknown, b: unknown) => {
    if (JSON.stringify(a) !== JSON.stringify(b)) p.push(`${what}: browser ${JSON.stringify(a)} != native ${JSON.stringify(b)}`);
  };
  eq("shape", meta.shape, ref.shape);
  eq("dtype", meta.dtype, ref.dtype);
  eq("sites", meta.sites, ref.sites);
  eq("times", meta.times, ref.times);
  eq("quadrature.status", meta.quadrature.status, ref.quadrature.status);
  eq("quadrature.used_n_quad", meta.quadrature.used_n_quad, ref.quadrature.used_n_quad);
  eq("quadrature.check_n_quad", meta.quadrature.check_n_quad, ref.quadrature.check_n_quad);
  eq("quadrature.requested_n_quad", meta.quadrature.requested_n_quad, ref.quadrature.requested_n_quad);
  eq("quadrature.segments", meta.quadrature.segments, ref.quadrature.segments);
  eq("config_key", meta.config_key, ref.config_key);
  eq("source_revision", meta.source_revision, ref.source_revision);
  eq("dtype", meta.dtype, "float64");
  report.shape = meta.shape;
  report.status = { browser: meta.quadrature.status, native: ref.quadrature.status };
  report.used_n_quad = { browser: meta.quadrature.used_n_quad, native: ref.quadrature.used_n_quad };
  report.check_n_quad = { browser: meta.quadrature.check_n_quad, native: ref.quadrature.check_n_quad };
  const n = refPsi!;
  if (psi.length !== n.length || n.length !== ref.shape[0] * ref.shape[1]) {
    p.push(`psi length ${psi.length} != native ${n.length} (shape ${ref.shape})`);
    return;
  }
  let maxAbs = 0;
  let peak = 0;
  let worst = 0;
  let bad = 0;
  for (let i = 0; i < n.length; i++) {
    const d = Math.abs(psi[i] - n[i]);
    if (!(d <= ATOL + RTOL * Math.abs(n[i]))) bad++;
    if (!(d <= maxAbs)) maxAbs = d; // NaN-propagating
    peak = Math.max(peak, Math.abs(n[i]));
    worst = Math.max(worst, d / (ATOL + RTOL * Math.abs(n[i])));
  }
  report.max_abs_diff = maxAbs;
  report.max_diff_over_peak = peak > 0 ? maxAbs / peak : NaN;
  report.worst_ratio_to_tolerance = worst;
  report.violations = bad;
  if (bad) p.push(`${bad} of ${n.length} values outside rtol=${RTOL}, atol=${ATOL} (max abs diff ${maxAbs.toExponential(3)})`);
  // mass_in_frame is Python's own psi.sum(axis=1); check it with the same tolerance.
  for (let i = 0; i < ref.mass_in_frame.length; i++) {
    const a = meta.mass_in_frame[i];
    const b = ref.mass_in_frame[i];
    if (!(Math.abs(a - b) <= ATOL + RTOL * Math.abs(b))) {
      p.push(`mass_in_frame[${i}] ${a} vs native ${b}`);
      break;
    }
  }
}

async function deployedRevision(): Promise<string | undefined> {
  const log = await testLog(app.page);
  return log.received.find((r) => r.type === "ready")?.sourceRevision;
}

test("parity: presets through the shipped build-time validation cache (status 'cached', one compute)", async ({}, testInfo) => {
  const index = loadRefIndex();
  const deployed = await deployedRevision();
  if (deployed !== index.sourceRevision) {
    const why = `SKIPPED: native refs are for ${index.sourceRevision}, page runs ${deployed}`;
    testInfo.annotations.push({ type: "skipped-cases", description: why });
    test.skip(true, why);
  }
  const rows: any[] = [];
  for (const c of index.cases.filter((k) => k.id.startsWith("preset-"))) {
    const ref = loadRefMeta(c);
    const refPsi = loadRefPsi(c);
    const { meta, psi, wallMs } = await hookRun(app.page, c.params);
    const problems: string[] = [];
    if (!meta.ok) problems.push(`error ${meta.error.kind}: ${meta.error.message}`);
    else {
      // A config verified earlier in this page (previous test) is also "cached"; either way one compute.
      if (meta.quadrature.status !== "cached") problems.push(`status ${meta.quadrature.status}, expected cached`);
      if (meta.quadrature.used_n_quad !== ref.quadrature.used_n_quad) problems.push(`used ${meta.quadrature.used_n_quad} != ${ref.quadrature.used_n_quad}`);
      if (meta.quadrature.check_n_quad !== ref.quadrature.check_n_quad) problems.push(`check ${meta.quadrature.check_n_quad} != ${ref.quadrature.check_n_quad}`);
      if (meta.quadrature.discrepancy_rel_peak !== ref.quadrature.discrepancy_rel_peak) {
        problems.push(`stored discrepancy ${meta.quadrature.discrepancy_rel_peak} != native ${ref.quadrature.discrepancy_rel_peak}`);
      }
      if (meta.timing_ms.check !== 0) problems.push(`check stage ran (${meta.timing_ms.check} ms)`);
      let maxAbs = 0;
      let bad = 0;
      for (let i = 0; i < refPsi.length; i++) {
        const d = Math.abs(psi[i] - refPsi[i]);
        if (!(d <= ATOL + RTOL * Math.abs(refPsi[i]))) bad++;
        maxAbs = Math.max(maxAbs, d);
      }
      if (psi.length !== refPsi.length || bad) problems.push(`${bad} values out of tolerance (max ${maxAbs})`);
      rows.push({ id: c.id, status: meta.quadrature.status, used: meta.quadrature.used_n_quad, max_abs_diff: maxAbs, wall_ms: Math.round(wallMs), problems });
      continue;
    }
    rows.push({ id: c.id, problems });
  }
  await testInfo.attach("parity-cached.json", { body: JSON.stringify(rows, null, 1), contentType: "application/json" });
  for (const r of rows) expect.soft(r.problems, r.id).toEqual([]);
});

test("parity: every native reference case, full arrays (browser does its own n vs 2n check)", async ({}, testInfo) => {
  const index = loadRefIndex();
  const deployed = await deployedRevision();
  const reports: CaseReport[] = [];
  const header = {
    rtol: RTOL, atol: ATOL, native_runtime: index.runtime, native_revision: index.sourceRevision,
    browser_revision: deployed, browser: testInfo.project.name, cachedValidation: "stripped (fresh 2n check in the browser)",
  };
  if (deployed !== index.sourceRevision) {
    const why = `SKIPPED ALL ${index.cases.length} parity cases: native refs are for revision ${index.sourceRevision} ` +
      `but the page under test runs ${deployed}; config keys cannot match. Regenerate refs from the deployed revision.`;
    console.log(why);
    testInfo.annotations.push({ type: "skipped-cases", description: why });
    await testInfo.attach("parity.json", { body: JSON.stringify({ ...header, skipped: why }, null, 1), contentType: "application/json" });
    test.skip(true, why);
  }
  const sentBefore = (await testLog(app.page)).sent.length;
  await app.page.evaluate(() => { (window as any).__swTestStripCache = true; });
  try {
    for (const c of index.cases) {
      const ref = loadRefMeta(c);
      const refPsi = c.ok ? loadRefPsi(c) : null;
      const report: CaseReport = { id: c.id, compared: true, problems: [] };
      const { meta, psi, wallMs } = await hookRun(app.page, c.params);
      report.browser_wall_ms = Math.round(wallMs);
      if (LIVE && meta.ok && meta.config_key !== ref.config_key) {
        report.compared = false;
        report.skipped = `config_key ${meta.config_key} differs from native ${ref.config_key}`;
        testInfo.annotations.push({ type: "skipped-case", description: `${c.id}: ${report.skipped}` });
      } else {
        compare(c, meta, psi, ref, refPsi, report);
      }
      reports.push(report);
      console.log(`  [${testInfo.project.name}] ${c.id.padEnd(36)} ${report.status?.browser ?? "-"} ` +
        `maxabs=${report.max_abs_diff?.toExponential(2)} rel=${report.max_diff_over_peak?.toExponential(2)} ` +
        `${Math.round(wallMs)} ms ${report.problems.length ? "FAIL " + report.problems.join("; ") : "ok"}`);
    }
  } finally {
    await app.page.evaluate(() => { (window as any).__swTestStripCache = false; });
    const summary = {
      ...header,
      cases: reports.length,
      compared: reports.filter((r) => r.compared).length,
      max_abs_diff: Math.max(...reports.map((r) => r.max_abs_diff ?? 0)),
      max_diff_over_peak: Math.max(...reports.map((r) => r.max_diff_over_peak ?? 0)),
      reports,
    };
    await testInfo.attach("parity.json", { body: JSON.stringify(summary, null, 1), contentType: "application/json" });
  }
  // Every run message really went out without the cache (so the browser verified convergence itself).
  const log = await testLog(app.page);
  const mine = log.sent.slice(sentBefore).filter((s) => s.type === "run");
  expect(mine.length, "run requests sent during this test").toBe(index.cases.length);
  expect(mine.filter((s) => s.hasCache).length, "runs sent with cachedValidation").toBe(0);
  expect(reports.length).toBe(index.cases.length);
  for (const r of reports) expect.soft(r.problems, r.id).toEqual([]);
  const skipped = reports.filter((r) => !r.compared);
  expect(skipped.map((r) => r.id), "cases skipped for a revision/config mismatch").toEqual([]);
});
