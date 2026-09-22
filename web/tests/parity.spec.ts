// 1. Parity: every native reference case (web/tests/.ref, written by
// web/scripts/native_reference.py through spectral.browser.run under native
// CPython) is run in the browser through window.__spectralWave.run and compared
// element-wise: |b - n| <= atol + rtol * |n| with rtol = 1e-9, atol = 1e-11.
//
// What is an identity and what is a measurement
// ---------------------------------------------
// The two sides of every comparison here are produced on two machines: the
// native references come from the VERIFY job's runner, the shipped validation
// cache (web/src/generated/build-info.json) from the BUILD job's runner, and the
// browser numbers from whichever CPU Playwright happens to run on.
//
//   * Identities -- node counts, status, shape, dtype, config_key,
//     source_revision, segment bounds -- are decided by the code and the
//     parameters, so they are compared exactly.
//   * psi is compared element-wise at rtol = 1e-9 / atol = 1e-11: the same
//     deterministic arithmetic on the same node count, so only the last bits of
//     each dot product may move.
//   * quadrature.discrepancy_rel_peak is a *measurement* -- the peak-relative
//     difference between the n-node and the 2n-node solution, computed through
//     CPU-dependent BLAS kernels. Two runners measuring the same quantity agree
//     on its magnitude, not on its low digits, so it is checked as evidence
//     (finite, >= 0, within tolerance on both sides, same order of magnitude)
//     and never for bitwise equality. It used to be compared with toEqual, which
//     failed in CI for whichever presets happened to differ (and passed locally
//     only because both sides came off the same machine).
//   * The node count itself is *derived from* that measurement: a borderline
//     configuration can be refined by one runtime and not by the other. That is
//     handled explicitly (loudly reported, psi then compared at the convergence
//     tolerance the policy actually guarantees), never silently skipped.
import { test, expect } from "@playwright/test";
import {
  LIVE, hookRun, loadRefIndex, loadRefMeta, loadRefPsi, localBuildInfo, openApp, testLog,
  type App, type RefCase,
} from "./support";

/** Same-node-count parity: the same arithmetic, so only the last bits may move. */
const RTOL = 1e-9;
const ATOL = 1e-11;
/**
 * Different node counts: all the policy promises is that n and 2n agree to
 * TOLERANCE (spectral/browser.py) of the peak, so two runtimes that stopped at
 * different counts can only be held to that.
 */
const CONVERGENCE_TOL = 1e-6;
/** Two measured discrepancies this small both mean "far below tolerance". */
const DISC_NEGLIGIBLE = 1e-9;
/** Above that, two machines measuring the same quantity must stay this close. */
const DISC_FACTOR = 100;

/**
 * spectral/browser.py CACHE_TRUST_FRACTION: a stored record is only used when
 * its measured discrepancy sits this far inside the tolerance. The records are
 * measured with native NumPy at build time and applied in the browser's NumPy,
 * so a decision close to the tolerance is re-checked in the runtime that will
 * display it, and comes back "verified"/"refined" rather than "cached".
 */
const CACHE_TRUST_FRACTION = 0.1;

test.describe.configure({ mode: "serial" });

let app: App;
test.beforeAll(async ({ browser }) => {
  app = await openApp(browser);
});
test.afterEach(async ({}, testInfo) => app.afterEach(testInfo));
test.afterAll(async () => app?.close());

// ------------------------------------------------------------- helpers ----

interface PsiDiff {
  values: number;
  peak: number;
  max_abs_diff: number;
  max_diff_over_peak: number;
  /** worst |b - n| / (atol + rtol |n|); > 1 means at least one element is out */
  worst_ratio_to_tolerance: number;
  violations: number;
}

/** Element-wise difference plus both verdicts; NaN propagates into max_abs_diff. */
function psiDiff(psi: Float64Array, ref: Float64Array): PsiDiff {
  let maxAbs = 0;
  let peak = 0;
  let worst = 0;
  let bad = 0;
  for (let i = 0; i < ref.length; i++) {
    const d = Math.abs(psi[i] - ref[i]);
    if (!(d <= ATOL + RTOL * Math.abs(ref[i]))) bad++;
    if (!(d <= maxAbs)) maxAbs = d; // NaN-propagating
    peak = Math.max(peak, Math.abs(ref[i]));
    worst = Math.max(worst, d / (ATOL + RTOL * Math.abs(ref[i])));
  }
  return {
    values: ref.length, peak, max_abs_diff: maxAbs,
    max_diff_over_peak: peak > 0 ? maxAbs / peak : NaN,
    worst_ratio_to_tolerance: worst, violations: bad,
  };
}

/**
 * Record the comparison and add a problem if it fails. `relaxed` is only ever
 * used when the two sides used different node counts; then the strict bound no
 * longer applies and the convergence tolerance is what the policy guarantees.
 */
function checkPsi(psi: Float64Array, ref: Float64Array, relaxed: boolean, problems: string[]): PsiDiff & { mode: string; bound: string } {
  if (psi.length !== ref.length) {
    problems.push(`psi length ${psi.length} != native ${ref.length}`);
    return { ...psiDiff(new Float64Array(0), new Float64Array(0)), mode: "not compared", bound: "-" };
  }
  const d = psiDiff(psi, ref);
  if (relaxed) {
    const ok = d.peak > 0 && d.max_abs_diff <= CONVERGENCE_TOL * d.peak;
    if (!ok) {
      problems.push(`psi differs by ${d.max_abs_diff.toExponential(3)} = ` +
        `${d.max_diff_over_peak.toExponential(3)} of the peak, above the convergence tolerance ${CONVERGENCE_TOL} ` +
        "(the two sides used different node counts, so this is the bound that applies)");
    }
    return { ...d, mode: "convergence tolerance (node counts differ)", bound: `max|b-n| <= ${CONVERGENCE_TOL} x peak` };
  }
  if (d.violations) {
    problems.push(`${d.violations} of ${d.values} values outside rtol=${RTOL}, atol=${ATOL} ` +
      `(max abs diff ${d.max_abs_diff.toExponential(3)}, worst ${d.worst_ratio_to_tolerance.toExponential(3)}x the bound)`);
  }
  return { ...d, mode: "strict", bound: `|b-n| <= ${ATOL} + ${RTOL}|n|` };
}

interface DiscReport {
  browser: number | null;
  native: number | null;
  tolerance: { browser: number | null; native: number | null };
  ratio: number | null;
  verdict: string;
}

/**
 * quadrature.discrepancy_rel_peak as evidence, not as an identity.
 *
 * Both sides measured the same quantity through CPU-dependent BLAS kernels, so
 * their low digits differ between runners. What must hold is that each side is
 * a real number in [0, its own tolerance] and that the two agree on the
 * magnitude: either both are negligible, or they are within DISC_FACTOR.
 */
function checkDiscrepancy(what: string, b: any, n: any, problems: string[]): DiscReport {
  const out: DiscReport = {
    browser: typeof b?.discrepancy_rel_peak === "number" ? b.discrepancy_rel_peak : null,
    native: typeof n?.discrepancy_rel_peak === "number" ? n.discrepancy_rel_peak : null,
    tolerance: {
      browser: typeof b?.tolerance === "number" ? b.tolerance : null,
      native: typeof n?.tolerance === "number" ? n.tolerance : null,
    },
    ratio: null,
    verdict: "",
  };
  const side = (label: string, v: number | null, tol: number | null): boolean => {
    if (v === null || !Number.isFinite(v)) {
      problems.push(`${what}: ${label} discrepancy_rel_peak is ${JSON.stringify(v)}, not a finite number`);
      return false;
    }
    if (v < 0) {
      problems.push(`${what}: ${label} discrepancy_rel_peak ${v} is negative`);
      return false;
    }
    if (tol === null || !Number.isFinite(tol) || tol <= 0 || tol > CONVERGENCE_TOL) {
      problems.push(`${what}: ${label} tolerance is ${JSON.stringify(tol)}, expected a positive number <= ${CONVERGENCE_TOL}`);
      return false;
    }
    if (!(v <= tol)) {
      problems.push(`${what}: ${label} discrepancy_rel_peak ${v.toExponential(3)} exceeds its tolerance ${tol.toExponential(1)}`);
      return false;
    }
    return true;
  };
  const okB = side("browser", out.browser, out.tolerance.browser);
  const okN = side("native", out.native, out.tolerance.native);
  if (!okB || !okN) {
    out.verdict = "invalid";
    return out;
  }
  const bv = out.browser!;
  const nv = out.native!;
  if (bv < DISC_NEGLIGIBLE && nv < DISC_NEGLIGIBLE) {
    out.ratio = bv > 0 && nv > 0 ? Math.max(bv, nv) / Math.min(bv, nv) : null;
    out.verdict = `both negligible (< ${DISC_NEGLIGIBLE}); low digits are CPU-dependent and not compared`;
    return out;
  }
  const lo = Math.min(bv, nv);
  const hi = Math.max(bv, nv);
  if (lo === 0) {
    out.verdict = "one side measured exactly 0, the other did not";
    problems.push(`${what}: discrepancy_rel_peak browser ${bv.toExponential(3)} vs native ${nv.toExponential(3)}: ` +
      `one side is exactly 0 while the other is above ${DISC_NEGLIGIBLE}`);
    return out;
  }
  out.ratio = hi / lo;
  if (out.ratio > DISC_FACTOR) {
    out.verdict = `disagree by ${out.ratio.toExponential(2)}x`;
    problems.push(`${what}: discrepancy_rel_peak browser ${bv.toExponential(3)} vs native ${nv.toExponential(3)} ` +
      `differ by ${out.ratio.toExponential(2)}x, more than the ${DISC_FACTOR}x two machines may disagree by`);
    return out;
  }
  out.verdict = `agree to ${out.ratio.toFixed(2)}x (<= ${DISC_FACTOR}x)`;
  return out;
}

/**
 * The invariants spectral/browser.py's _record_consistent() enforces before it
 * will trust a cached record. Machine-independent, so this holds everywhere --
 * including the CI verify job, which downloads web/dist only and therefore has
 * no web/src/generated/build-info.json to compare the record against.
 */
function checkRecordShape(q: any, requested: number, problems: string[]): void {
  if (q.requested_n_quad !== requested) problems.push(`requested_n_quad ${q.requested_n_quad} != the params' n_quad ${requested}`);
  const used = q.used_n_quad;
  const chk = q.check_n_quad;
  if (!Number.isInteger(used) || !Number.isInteger(chk)) {
    problems.push(`used_n_quad ${used} / check_n_quad ${chk} are not both integers`);
    return;
  }
  if (used < requested || used % requested !== 0) {
    problems.push(`used_n_quad ${used} is not a multiple of the requested ${requested}`);
    return;
  }
  const factor = used / requested;
  if (factor & (factor - 1)) problems.push(`used_n_quad ${used} is ${factor}x the requested ${requested}, not a power of two`);
  if (chk !== 2 * used) problems.push(`check_n_quad ${chk} != 2 x used_n_quad ${used}`);
}

/** null when the two sides chose the same quadrature, else a description of the difference. */
function nodeCountMismatch(b: any, n: any): string | null {
  if (b?.used_n_quad === n?.used_n_quad && b?.check_n_quad === n?.check_n_quad) return null;
  return `used ${b?.used_n_quad} vs native ${n?.used_n_quad}, check ${b?.check_n_quad} vs native ${n?.check_n_quad}` +
    ` (status ${b?.status} vs native ${n?.status}, requested ${b?.requested_n_quad}/${n?.requested_n_quad})`;
}

async function deployedRevision(): Promise<string | undefined> {
  const log = await testLog(app.page);
  return log.received.find((r) => r.type === "ready")?.sourceRevision;
}

// ------------------------------------------- 1. the shipped cached path ----

interface CachedRow {
  id: string;
  config_key?: string;
  /** what the browser reported; every field of it comes out of the shipped record */
  browser?: Record<string, unknown>;
  /** the record web/src/generated/build-info.json ships for this config_key */
  shipped?: Record<string, unknown> | null;
  /** what the native reference (no cache, its own n vs 2n check) reported */
  native?: Record<string, unknown>;
  discrepancy_rel_peak?: DiscReport;
  node_count_mismatch?: string | null;
  psi?: PsiDiff & { mode: string; bound: string };
  timing_ms?: Record<string, number>;
  wall_ms?: number;
  problems: string[];
}

test("parity: presets through the shipped build-time validation cache (status 'cached', one compute)", async ({}, testInfo) => {
  const index = loadRefIndex();
  const deployed = await deployedRevision();
  if (deployed !== index.sourceRevision) {
    const why = `SKIPPED: native refs are for ${index.sourceRevision}, page runs ${deployed}`;
    testInfo.annotations.push({ type: "skipped-cases", description: why });
    test.skip(true, why);
  }
  // The build-time cache as it was shipped. Present after a local `npm run build`;
  // absent in the CI verify job (it downloads web/dist only) and possibly stale
  // against a live URL. When it is absent the record is still checked
  // structurally (checkRecordShape) and against the native reference, and the
  // attachment says which of the two it was.
  const info = localBuildInfo();
  const shippedAvailable = !!info?.presetValidation && info.sourceRevision === index.sourceRevision;
  const rows: CachedRow[] = [];
  const loud: string[] = [];
  const sentBefore = (await testLog(app.page)).sent.length;

  for (const c of index.cases.filter((k) => k.id.startsWith("preset-"))) {
    const ref = loadRefMeta(c);
    const refPsi = loadRefPsi(c);
    const { meta, psi, wallMs } = await hookRun(app.page, c.params);
    const problems: string[] = [];
    const row: CachedRow = { id: c.id, wall_ms: Math.round(wallMs), problems };
    rows.push(row);
    if (!meta.ok) {
      problems.push(`error ${meta.error.kind}: ${meta.error.message}`);
      continue;
    }
    const q = meta.quadrature;
    row.config_key = meta.config_key;
    row.browser = {
      status: q.status, requested_n_quad: q.requested_n_quad, used_n_quad: q.used_n_quad,
      check_n_quad: q.check_n_quad, discrepancy_rel_peak: q.discrepancy_rel_peak,
      tolerance: q.tolerance, source_revision: meta.source_revision, checks: q.checks?.length ?? 0,
    };
    row.native = {
      status: ref.quadrature.status, requested_n_quad: ref.quadrature.requested_n_quad,
      used_n_quad: ref.quadrature.used_n_quad, check_n_quad: ref.quadrature.check_n_quad,
      discrepancy_rel_peak: ref.quadrature.discrepancy_rel_peak, tolerance: ref.quadrature.tolerance,
      source_revision: ref.source_revision,
    };
    row.timing_ms = meta.timing_ms;

    // (a) What the policy does with this record: use it, or re-check it.
    const shippedRec: any = shippedAvailable ? (info.presetValidation[meta.config_key] ?? null) : null;
    const recDisc: unknown = typeof shippedRec?.discrepancy_rel_peak === "number"
      ? shippedRec.discrepancy_rel_peak : ref.quadrature.discrepancy_rel_peak;
    const recTol: unknown = typeof shippedRec?.tolerance === "number"
      ? shippedRec.tolerance : ref.quadrature.tolerance;
    const expectCached = typeof recDisc === "number" && typeof recTol === "number"
      && recDisc <= recTol * CACHE_TRUST_FRACTION;
    row.expect_cached = expectCached;
    if (expectCached) {
      // The cache really was used: one compute, no check stage, status "cached".
      if (q.status !== "cached") problems.push(`status ${q.status}, expected cached`);
      if (meta.timing_ms.check !== 0) problems.push(`check stage ran (${meta.timing_ms.check} ms); the cached path must compute once`);
      if ((q.checks?.length ?? 0) !== 0) problems.push(`${q.checks.length} convergence check(s) recorded; the cached path records none`);
    } else {
      // Outside the trust margin: the browser must re-check it here, and the
      // result must still be converged.
      loud.push(`TRUST MARGIN ${c.id}: stored discrepancy ${Number(recDisc).toExponential(3)} is not within ` +
        `${CACHE_TRUST_FRACTION}x of the tolerance ${Number(recTol).toExponential(3)}, so the browser re-checks it ` +
        `(status ${q.status}, ${q.checks?.length ?? 0} check(s))`);
      if (q.status !== "verified" && q.status !== "refined") {
        problems.push(`status ${q.status}: a record outside the trust margin must be re-checked, not used`);
      }
      if ((q.checks?.length ?? 0) === 0) problems.push("no convergence check recorded, but the record is outside the trust margin");
    }

    // (b) The record the cache supplied has the shape the policy demands.
    checkRecordShape(q, (c.params as any).n_quad, problems);

    // (c) config_key and source_revision are identities: they must match the shipped build.
    if (meta.config_key !== ref.config_key) problems.push(`config_key ${meta.config_key} != native ${ref.config_key}`);
    if (meta.source_revision !== ref.source_revision) problems.push(`source_revision ${meta.source_revision} != native ${ref.source_revision}`);
    let shipped: any = null;
    if (shippedAvailable) {
      shipped = info.presetValidation[meta.config_key] ?? null;
      row.shipped = shipped;
      if (!shipped) {
        problems.push(`config_key ${meta.config_key} is not in the shipped presetValidation map ` +
          `(${Object.keys(info.presetValidation).length} entries); the cache cannot have supplied this run`);
      } else {
        if (shipped.source_revision !== info.sourceRevision) {
          problems.push(`shipped record source_revision ${shipped.source_revision} != build-info ${info.sourceRevision}`);
        }
        if (meta.source_revision !== info.sourceRevision) {
          problems.push(`browser source_revision ${meta.source_revision} != build-info ${info.sourceRevision}`);
        }
        // (d) When the record is used, it decides the node counts exactly. When
        //     it is outside the trust margin the browser re-checks, so only the
        //     requested count is fixed and "used" may refine beyond it.
        const fixed = expectCached
          ? (["requested_n_quad", "used_n_quad", "check_n_quad"] as const)
          : (["requested_n_quad"] as const);
        for (const k of fixed) {
          if (q[k] !== shipped[k]) problems.push(`${k} ${q[k]} != shipped record ${shipped[k]}`);
        }
        if (!expectCached && q.used_n_quad < shipped.requested_n_quad) {
          problems.push(`used_n_quad ${q.used_n_quad} is below the requested ${shipped.requested_n_quad}`);
        }
      }
    } else {
      row.shipped = null;
      if (rows.length === 1) {
        loud.push("NOTE: web/src/generated/build-info.json is absent or built from another revision, " +
          "so the shipped record could not be read locally; node counts are checked against the native reference only.");
      }
      for (const k of ["requested_n_quad"] as const) {
        if (q[k] !== ref.quadrature[k]) problems.push(`${k} ${q[k]} != native ${ref.quadrature[k]}`);
      }
    }

    // (e) The measured float: evidence, not an identity.
    row.discrepancy_rel_peak = checkDiscrepancy(c.id, q, ref.quadrature, problems);
    if (expectCached && shipped && typeof shipped.discrepancy_rel_peak === "number") {
      // The browser must report exactly what the record stores -- same machine,
      // same JSON, this one IS an identity.
      if (q.discrepancy_rel_peak !== shipped.discrepancy_rel_peak) {
        problems.push(`browser reported discrepancy_rel_peak ${q.discrepancy_rel_peak} but the shipped record stores ` +
          `${shipped.discrepancy_rel_peak}; the cached path must echo the record it used`);
      }
    }

    // (f) psi parity. A borderline preset may be decided differently by two
    //     runtimes; that is legitimate, never silent, and the strict bound is
    //     then replaced by the one the policy actually guarantees.
    const mismatch = nodeCountMismatch(q, ref.quadrature);
    row.node_count_mismatch = mismatch;
    if (mismatch) {
      const line = `NODE COUNT MISMATCH ${c.id}: browser (shipped cache) ${mismatch}. ` +
        `psi compared at the convergence tolerance ${CONVERGENCE_TOL} of the peak instead of rtol=${RTOL}.`;
      loud.push(line);
      console.log(`  [${testInfo.project.name}] ${line}`);
      testInfo.annotations.push({ type: "node-count-mismatch", description: line });
    }
    row.psi = checkPsi(psi, refPsi, !!mismatch, problems);
  }

  const log = await testLog(app.page);
  const runs = log.sent.slice(sentBefore).filter((s) => s.type === "run");
  const summary = {
    browser: testInfo.project.name,
    native_runtime: index.runtime,
    revision: index.sourceRevision,
    shipped_record_source: shippedAvailable
      ? "web/src/generated/build-info.json"
      : "not on disk (the CI verify job downloads web/dist only, and a live URL may be another build); " +
        "the record is checked structurally and against the native reference instead",
    discrepancy_policy: {
      what: "quadrature.discrepancy_rel_peak is measured on the machine that ran the check, " +
        "so it is compared as evidence and never for bitwise equality",
      finite_and_non_negative: true,
      within_tolerance_on_both_sides: true,
      negligible_below: DISC_NEGLIGIBLE,
      otherwise_within_factor: DISC_FACTOR,
    },
    psi_bounds: { strict: { rtol: RTOL, atol: ATOL }, node_counts_differ: { rel_to_peak: CONVERGENCE_TOL } },
    cases: rows.length,
    node_count_mismatches: rows.filter((r) => r.node_count_mismatch).map((r) => ({ id: r.id, detail: r.node_count_mismatch })),
    notes: loud,
    rows,
  };
  await testInfo.attach("parity-cached.json", { body: JSON.stringify(summary, null, 1), contentType: "application/json" });

  expect(rows.length, "preset cases run").toBe(index.cases.filter((k) => k.id.startsWith("preset-")).length);
  expect(runs.length, "run requests sent during this test").toBe(rows.length);
  expect(runs.filter((s) => !s.hasCache).length, "runs sent without the validation cache").toBe(0);
  for (const r of rows) expect.soft(r.problems, r.id).toEqual([]);
});

// --------------------------------- 2. every case, cache stripped, arrays ----

interface CaseReport {
  id: string;
  compared: boolean;
  skipped?: string;
  shape?: [number, number];
  status?: { browser: string; native: string };
  used_n_quad?: { browser: number; native: number };
  check_n_quad?: { browser: number | null; native: number | null };
  node_count_mismatch?: string | null;
  discrepancy_rel_peak?: DiscReport;
  psi_mode?: string;
  max_abs_diff?: number;
  max_diff_over_peak?: number;
  worst_ratio_to_tolerance?: number;
  violations?: number;
  browser_wall_ms?: number;
  problems: string[];
}

function compare(c: RefCase, meta: any, psi: Float64Array, ref: any, refPsi: Float64Array | null, report: CaseReport): string[] {
  const p = report.problems;
  const loud: string[] = [];
  if (!c.ok) {
    if (meta.ok) p.push(`native returned error ${ref.error?.kind} but browser succeeded`);
    else if (meta.error.kind !== ref.error.kind) p.push(`error kind ${meta.error.kind} != native ${ref.error.kind}`);
    else if (meta.error.field !== ref.error.field) p.push(`error field ${meta.error.field} != native ${ref.error.field}`);
    return loud;
  }
  if (!meta.ok) {
    p.push(`browser error ${meta.error.kind}: ${meta.error.message}`);
    return loud;
  }
  const eq = (what: string, a: unknown, b: unknown) => {
    if (JSON.stringify(a) !== JSON.stringify(b)) p.push(`${what}: browser ${JSON.stringify(a)} != native ${JSON.stringify(b)}`);
  };
  eq("shape", meta.shape, ref.shape);
  eq("dtype", meta.dtype, ref.dtype);
  eq("sites", meta.sites, ref.sites);
  eq("times", meta.times, ref.times);
  // Segment bounds are max/min of the parameters, not a measurement: exact.
  eq("quadrature.segments", meta.quadrature.segments, ref.quadrature.segments);
  eq("quadrature.requested_n_quad", meta.quadrature.requested_n_quad, ref.quadrature.requested_n_quad);
  eq("config_key", meta.config_key, ref.config_key);
  eq("source_revision", meta.source_revision, ref.source_revision);
  eq("dtype", meta.dtype, "float64");
  report.shape = meta.shape;
  report.status = { browser: meta.quadrature.status, native: ref.quadrature.status };
  report.used_n_quad = { browser: meta.quadrature.used_n_quad, native: ref.quadrature.used_n_quad };
  report.check_n_quad = { browser: meta.quadrature.check_n_quad, native: ref.quadrature.check_n_quad };

  // Both sides ran their own n vs 2n check here, each on its own CPU. Each must
  // have met the tolerance and the two must agree on the magnitude; the exact
  // value is a measurement and is not compared for equality.
  report.discrepancy_rel_peak = checkDiscrepancy(c.id, meta.quadrature, ref.quadrature, p);

  // used/check (and therefore status, which is just used > requested) follow from
  // that measurement, so a borderline case can be decided differently. Say so.
  const mismatch = nodeCountMismatch(meta.quadrature, ref.quadrature);
  report.node_count_mismatch = mismatch;
  if (mismatch) {
    loud.push(`NODE COUNT MISMATCH ${c.id}: the browser's own convergence check chose ${mismatch}`);
  } else {
    eq("quadrature.status", meta.quadrature.status, ref.quadrature.status);
    eq("quadrature.used_n_quad", meta.quadrature.used_n_quad, ref.quadrature.used_n_quad);
    eq("quadrature.check_n_quad", meta.quadrature.check_n_quad, ref.quadrature.check_n_quad);
  }

  const n = refPsi!;
  if (psi.length !== n.length || n.length !== ref.shape[0] * ref.shape[1]) {
    p.push(`psi length ${psi.length} != native ${n.length} (shape ${ref.shape})`);
    return loud;
  }
  const d = checkPsi(psi, n, !!mismatch, p);
  report.psi_mode = d.mode;
  report.max_abs_diff = d.max_abs_diff;
  report.max_diff_over_peak = d.max_diff_over_peak;
  report.worst_ratio_to_tolerance = d.worst_ratio_to_tolerance;
  report.violations = d.violations;

  // mass_in_frame is Python's own psi.sum(axis=1); check it with the same bound as psi.
  const rel = mismatch ? CONVERGENCE_TOL : RTOL;
  const abs = mismatch ? CONVERGENCE_TOL * Math.max(d.peak, 1e-300) : ATOL;
  for (let i = 0; i < ref.mass_in_frame.length; i++) {
    const a = meta.mass_in_frame[i];
    const b = ref.mass_in_frame[i];
    if (!(Math.abs(a - b) <= abs + rel * Math.abs(b))) {
      p.push(`mass_in_frame[${i}] ${a} vs native ${b}`);
      break;
    }
  }
  return loud;
}

test("parity: every native reference case, full arrays (browser does its own n vs 2n check)", async ({}, testInfo) => {
  const index = loadRefIndex();
  const deployed = await deployedRevision();
  const reports: CaseReport[] = [];
  const loud: string[] = [];
  const header = {
    rtol: RTOL, atol: ATOL, node_counts_differ_rel_to_peak: CONVERGENCE_TOL,
    native_runtime: index.runtime, native_revision: index.sourceRevision,
    browser_revision: deployed, browser: testInfo.project.name, cachedValidation: "stripped (fresh 2n check in the browser)",
    discrepancy_policy: `measured on each machine: finite, >= 0, <= tolerance, and either both < ${DISC_NEGLIGIBLE} or within ${DISC_FACTOR}x`,
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
        for (const line of compare(c, meta, psi, ref, refPsi, report)) {
          loud.push(line);
          console.log(`  [${testInfo.project.name}] ${line}`);
          testInfo.annotations.push({ type: "node-count-mismatch", description: line });
        }
      }
      reports.push(report);
      console.log(`  [${testInfo.project.name}] ${c.id.padEnd(36)} ${report.status?.browser ?? "-"} ` +
        `maxabs=${report.max_abs_diff?.toExponential(2)} rel=${report.max_diff_over_peak?.toExponential(2)} ` +
        `disc=${report.discrepancy_rel_peak?.verdict ?? "-"} ` +
        `${Math.round(wallMs)} ms ${report.problems.length ? "FAIL " + report.problems.join("; ") : "ok"}`);
    }
  } finally {
    await app.page.evaluate(() => { (window as any).__swTestStripCache = false; });
    const summary = {
      ...header,
      cases: reports.length,
      compared: reports.filter((r) => r.compared).length,
      node_count_mismatches: reports.filter((r) => r.node_count_mismatch).map((r) => ({
        id: r.id, detail: r.node_count_mismatch, psi_mode: r.psi_mode,
      })),
      notes: loud,
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
