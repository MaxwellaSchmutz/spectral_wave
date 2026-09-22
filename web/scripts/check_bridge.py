"""Native self-check of spectral/browser.py.

    python web/scripts/check_bridge.py

Prints PASS/FAIL per check and exits non-zero if any check fails. Covers:
  - every invalid-input class the bridge contract lists (plus the budget),
    each rejected with the right kind and field and never raised;
  - the memory model against real process peaks (fresh process per run, OS
    counters minus a do-nothing baseline child; measure_memory.py), the
    measurement harness itself against an emulated fork() floor, and node
    generation at 8192 nodes;
  - label-first validation messages and the strict (rtol 0) Hermitian test;
  - the convergence policy on the two audit failure repros and on a case
    that cannot converge within the refinement cap, with advice that
    depends on why refinement stopped (cap vs memory budget);
  - the cached-validation path, and every way a record can be inconsistent;
  - the source revision (plain HEAD vs HEAD-dirty-<sources digest>);
  - all 13 presets x both outer signs;
  - two results checked against computations that share nothing with
    compute_psi: (a) a free Gaussian on a wide frame against exact FFT time
    evolution of the free lattice on a large periodic ring, and (b)
    single-site barrier transmission |T|^2 = 1 - |R|^2 against the analytic
    lattice formula |T(E)|^2 = 4a^2 sin^2 k / (4a^2 sin^2 k + v^2),
    E = 2a cos k, at three energies.

Desktop equivalence (web preset vs desktop form) is defined as bit-identical
psi, not bit-identical inputs: the desktop's "-0.25j" parses to a V entry
with real part -0.0, which JSON [re, im] pairs do not carry (the bridge
folds -0.0 to 0.0). See spectral/maxwell/presets.py.
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
import time

from _common import source_revision, sources_digest, use_revision

import numpy as np

import spectral.browser as browser
from spectral.maxwell import compute_psi
from spectral.maxwell.presets import PRESET_IDS, PRESETS, build_spec, gaussian_f

use_revision("check-bridge")

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""),
          flush=True)
    return ok


def run(params, cache=None, stages=None):
    text = params if isinstance(params, str) else json.dumps(params)
    on_stage = None if stages is None else (lambda s, d: stages.append(s))
    try:
        meta_json, psi = browser.run(text, cache, on_stage)
    except BaseException as exc:  # the bridge must never raise
        return {"ok": False, "error": {"kind": "RAISED", "field": None,
                                       "message": repr(exc)}}, None
    return json.loads(meta_json), psi


def with_(params, **changes):
    p = copy.deepcopy(params)
    for path, value in changes.items():
        keys = path.split("__")
        d = p
        for k in keys[:-1]:
            d = d[int(k)] if isinstance(d, list) else d[k]
        last = keys[-1]
        if isinstance(d, list):
            d[int(last)] = value
        elif value is _DELETE:
            del d[last]
        else:
            d[last] = value
    return p


_DELETE = object()
FREE = PRESETS["Free Gaussian Wave Packet"]
BARRIER = PRESETS["Single Barrier — partial reflection"]
COUPLED = PRESETS["Two-Channel Coupled Scatterer (L=2)"]
SCHOBER1 = PRESETS["Schober 1 — two-channel window"]
WEAK = PRESETS["Weak Barrier — small kick"]


# ---------------------------------------------------------------------- #
# 1. invalid input                                                       #
# ---------------------------------------------------------------------- #

def invalid_cases():
    nonhermitian = with_(COUPLED, V_sites__0__1__0=[0.25, 0.0])
    one_by_one_in_L2 = with_(COUPLED, V_sites=[[[[0.4, 0.0]]]])
    window_L1 = with_(SCHOBER1, L=1, a=[2.0], V_sites=[[[[0.0, 0.0]]]])
    return [
        # (name, params-or-text, kind, field)
        ("NaN (Python float -> JSON NaN) in E0", with_(FREE, amplitude__E0=float("nan")),
         "invalid_input", "amplitude.E0"),
        ("+inf (Python float -> JSON Infinity) in a[0]", with_(FREE, a=[float("inf")]),
         "invalid_input", "a[0]"),
        ("-inf in times.t_max", with_(FREE, times__t_max=float("-inf")),
         "invalid_input", "times.t_max"),
        ("1e999 literal overflowing to inf in interval[1]",
         json.dumps(FREE).replace('"interval": [-1.5, 1.5]', '"interval": [-1.5, 1e999]'),
         "invalid_input", "interval[1]"),
        ("NaN in V_sites entry", with_(BARRIER, V_sites=[[[[float("nan"), 0.0]]]]),
         "invalid_input", "V_sites[0][0][0][0]"),
        ("fractional site index", with_(BARRIER, j_sites=[0.5]), "invalid_input", "j_sites[0]"),
        ("integral float site index 0.0", with_(BARRIER, j_sites=[0.0]),
         "invalid_input", "j_sites[0]"),
        ("site outside [N, M]", with_(BARRIER, j_sites=[101]), "invalid_input", "j_sites[0]"),
        ("sites not increasing", with_(PRESETS["Double Barrier — resonant cavity"],
                                       j_sites=[6, -6]), "invalid_input", "j_sites[1]"),
        ("non-Hermitian V", nonhermitian, "invalid_input", "V_sites[0]"),
        ("wrong V shape (1x1 in L=2)", one_by_one_in_L2, "invalid_input", "V_sites[0]"),
        ("wrong V count (K mismatch)", with_(BARRIER, V_sites=[]), "invalid_input", "V_sites"),
        ("V entry not a [re, im] pair", with_(BARRIER, V_sites=[[[0.6]]]),
         "invalid_input", "V_sites[0][0][0]"),
        ("V as a string (no eval anywhere)", with_(BARRIER, V_sites="[[[0.6]]]"),
         "invalid_input", "V_sites"),
        ("interval below the band", with_(FREE, interval=[-2.5, 1.5]),
         "invalid_input", "interval"),
        ("interval inside the threshold buffer", with_(FREE, interval=[-1.9995, 1.5]),
         "invalid_input", "interval"),
        ("interval lo >= hi", with_(FREE, interval=[0.5, 0.5]), "invalid_input", "interval"),
        ("zero amplitude on the interval",
         with_(FREE, interval=[-0.5, 0.5], amplitude__E0=1.4, amplitude__sigma_E=0.01),
         "invalid_input", "amplitude.E0"),
        ("outer_sign 0", with_(FREE, outer_sign=0), "invalid_input", "outer_sign"),
        ("outer_sign 2", with_(FREE, outer_sign=2), "invalid_input", "outer_sign"),
        ("outer_sign true", with_(FREE, outer_sign=True), "invalid_input", "outer_sign"),
        ("outer_sign 1.0", with_(FREE, outer_sign=1.0), "invalid_input", "outer_sign"),
        ("outer_sign '1'", with_(FREE, outer_sign="1"), "invalid_input", "outer_sign"),
        ("threshold_buffer 0", with_(FREE, threshold_buffer=0), "invalid_input",
         "threshold_buffer"),
        ("threshold_buffer negative", with_(FREE, threshold_buffer=-1e-3), "invalid_input",
         "threshold_buffer"),
        ("threshold_buffer >= 2 a_min", with_(FREE, threshold_buffer=2.0), "invalid_input",
         "threshold_buffer"),
        ("threshold_buffer NaN", with_(FREE, threshold_buffer=float("nan")), "invalid_input",
         "threshold_buffer"),
        ("window mode with L = 1", window_L1, "invalid_input", "L"),
        ("window mode with extra keys", with_(SCHOBER1, amplitude={"mode": "schober_window",
                                                                   "E0": 0.5}),
         "invalid_input", "amplitude.E0"),
        ("L as bool", with_(FREE, L=True), "invalid_input", "L"),
        ("L = 7", with_(FREE, L=7, a=[1.0] * 7), "invalid_input", "L"),
        ("a entry as text", with_(FREE, a=["1.0"]), "invalid_input", "a[0]"),
        ("a increasing", with_(COUPLED, a=[0.6, 1.0]), "invalid_input", "a[1]"),
        ("a <= 0", with_(FREE, a=[0.0]), "invalid_input", "a[0]"),
        ("len(a) != L", with_(FREE, a=[1.0, 0.5]), "invalid_input", "a"),
        ("N >= M", with_(FREE, N=5, M=5), "invalid_input", "M"),
        ("|N| > 20000", with_(FREE, N=-20001), "invalid_input", "N"),
        ("N fractional", with_(FREE, N=-120.5), "invalid_input", "N"),
        ("n_t = 1", with_(FREE, times__n_t=1), "invalid_input", "times.n_t"),
        ("n_t = 2001", with_(FREE, times__n_t=2001), "invalid_input", "times.n_t"),
        ("t_min >= t_max", with_(FREE, times__t_min=50.0), "invalid_input", "times.t_max"),
        ("n_quad = 7", with_(FREE, n_quad=7), "invalid_input", "n_quad"),
        ("n_quad = 8193", with_(FREE, n_quad=8193), "invalid_input", "n_quad"),
        ("n_quad fractional", with_(FREE, n_quad=128.5), "invalid_input", "n_quad"),
        ("sigma_E = 0", with_(FREE, amplitude__sigma_E=0.0), "invalid_input",
         "amplitude.sigma_E"),
        ("direction unknown", with_(FREE, amplitude__direction="up"), "invalid_input",
         "amplitude.direction"),
        ("n_init outside [N, M]", with_(FREE, amplitude__n_init=500), "invalid_input",
         "amplitude.n_init"),
        ("amplitude mode unknown", with_(FREE, amplitude={"mode": "plane"}), "invalid_input",
         "amplitude.mode"),
        ("unknown top-level key", with_(FREE, f="lambda E: 1"), "invalid_input", "f"),
        ("missing key", with_(FREE, threshold_buffer=_DELETE), "invalid_input",
         "threshold_buffer"),
        ("text is not JSON", "{L: 1", "invalid_input", None),
        ("JSON is not an object", "[1, 2]", "invalid_input", None),
        ("result over 4,000,000 values",
         with_(FREE, N=-1500, M=1500, times__n_t=2000), "over_budget", "times.n_t"),
        ("memory over 700 MB", with_(FREE, N=-3000, M=3000, n_quad=2048),
         "over_budget", "n_quad"),
        ("n_quad whose 2x check exceeds 8192 nodes", with_(FREE, n_quad=5000),
         "over_budget", "n_quad"),
    ]


def check_invalid():
    for name, params, kind, field in invalid_cases():
        stages = []
        meta, psi = run(params, stages=stages)
        err = meta.get("error") or {}
        ok = (not meta["ok"] and psi is None and err.get("kind") == kind
              and err.get("field") == field and isinstance(err.get("message"), str)
              and len(err["message"]) > 10 and "computing" not in stages)
        check(ok, f"rejects {name}",
              f"{err.get('kind')} / {err.get('field')}: {err.get('message', '')[:90]}")
    meta, psi = run(123)
    check(not meta["ok"] and meta["error"]["kind"] == "invalid_input",
          "rejects a non-string params argument")


def check_messages_and_misc():
    # P9: messages lead with the web form's label; error.field is unchanged
    for params, field, text in [
        (with_(FREE, times__n_t=1), "times.n_t", "Frames (n_t) must be between 2 and 2000 (got 1)"),
        (with_(FREE, amplitude__sigma_E=0.0), "amplitude.sigma_E",
         "Energy width σ_E must be > 0 (got 0.0)"),
        (with_(BARRIER, amplitude__n_init=500), "amplitude.n_init",
         "Start site n_init = 500 must lie in [N, M] = [-100, 100]"),
        (with_(COUPLED, V_sites__0__1__0=[0.25, 0.0]), "V_sites[0]",
         "Potential matrices V(j): matrix 1 (V_sites[0], site j = 0) must be Hermitian"),
        (with_(FREE, amplitude__sigma_E=None), "amplitude.sigma_E",
         "Energy width σ_E (amplitude.sigma_E) must be a finite number (got null)"),
        (with_(BARRIER, j_sites=[0.5]), "j_sites[0]",
         "Potential sites, entry 1 (j_sites[0]) must be a whole number (got 0.5)"),
        (with_(FREE, L="1"), "L", "Channels L must be a whole number (got text)"),
    ]:
        meta, _ = run(params)
        err = meta.get("error") or {}
        check(err.get("field") == field and err.get("message", "").startswith(text),
              f"label-first message for {field}", err.get("message", "")[:110])
    # P4: Hermitian test is absolute (rtol 0)
    skew = with_(COUPLED, V_sites=[[[[0.4, 0.0], [1000.0, 0.0]],
                                    [[1000.001, 0.0], [-0.2, 0.0]]]])
    meta, _ = run(skew)
    check(not meta["ok"] and meta["error"]["field"] == "V_sites[0]",
          "Hermitian test uses rtol 0: |V - V^H| = 1e-3 on 1000-sized entries is refused "
          "(np.allclose's default rtol would pass it)", meta.get("error", {}).get("message", "")[:120])
    near = with_(COUPLED, V_sites=[[[[0.4, 0.0], [0.0, 0.25]],
                                    [[0.0, -0.25 + 5e-11], [-0.2, 0.0]]]])
    meta, _ = run(near)
    check(meta["ok"], "a V within HERMITIAN_ATOL = 1e-10 of Hermitian is accepted")
    # P10: window presets carry the desktop's disabled-form Gaussian values
    listed = json.loads(browser.presets_json())
    fg = {x["id"]: x.get("form_gaussian") for x in listed}
    want = {"mode": "gaussian", "E0": 0.5, "sigma_E": 0.1, "direction": "balanced", "n_init": 0}
    check(fg["schober-1"] == want and fg["schober-2"] == want
          and all(v is None for k, v in fg.items() if not k.startswith("schober")),
          "presets_json: form_gaussian on the two Schober presets only", json.dumps(want))
    # P5: the revision names the exact Python sources
    rev = source_revision()
    head = rev.split("-dirty-")[0]
    check(len(head) == 40 and (rev == head or rev == f"{head}-dirty-{sources_digest()[:12]}"),
          "source_revision is HEAD, or HEAD-dirty-<sha256(spectral/**/*.py)[:12]>", rev)


def check_internal_and_callbacks():
    saved = browser.compute_psi
    browser.compute_psi = lambda spec: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        meta, psi = run(FREE)
    finally:
        browser.compute_psi = saved
    check(not meta["ok"] and meta["error"]["kind"] == "internal" and psi is None
          and "boom" in meta["error"]["message"],
          "internal exception -> kind internal, never raised",
          meta["error"]["message"])

    saved = browser.compute_psi
    browser.compute_psi = lambda spec: np.full((spec.times.size, spec.M - spec.N + 1), np.nan)
    try:
        meta, psi = run(FREE)
    finally:
        browser.compute_psi = saved
    check(not meta["ok"] and meta["error"]["kind"] == "nonfinite" and psi is None,
          "non-finite result -> kind nonfinite", meta["error"]["message"][:90])

    def bad_stage(stage, detail):
        raise RuntimeError("callback failure")
    meta_json, psi = browser.run(json.dumps(FREE), None, bad_stage)
    check(json.loads(meta_json)["ok"] and psi is not None,
          "a raising on_stage callback does not break the run")


def check_measurement_harness():
    """The peak the memory checks compare must be the WORK's peak.

    A child process's raw peak also carries whatever the harness put there,
    and on Linux that was once the entire number: subprocess forks, a forked
    child's RSS starts equal to its parent's (copy-on-write pages count), and
    exec latches that high-water mark into the child's accounting, so
    getrusage(RUSAGE_SELF).ru_maxrss can never report less than the RSS this
    process had when it spawned the child. Every configuration then measured
    the same few hundred MB and every bound below failed on CI while passing
    on Windows, which has no fork. measure_memory now reads VmHWM (the
    post-exec mapping's own high-water) on Linux AND subtracts a do-nothing
    baseline child spawned from the same parent state, so anything the two
    children share cancels whatever the counter's exec semantics are.

    Windows cannot produce a fork floor to test that against, so one is
    emulated exactly: SPECTRAL_MEASURE_FAKE_FLOOR_MB raises a child's peak
    counters to at least that value, like an inherited high-water mark. The
    raw peak must then jump to it -- reproducing the CI failure -- while the
    baseline-corrected number must not move. A floor ABOVE the work's own
    peak hides the work rather than inflating it, so the corrected number is
    a lower bound there (clamped at 0), never an over-estimate: it cannot
    fail a sound model, and the reason Linux reads VmHWM is so that no such
    floor exists to begin with.
    """
    from measure_memory import FAKE_FLOOR_ENV, spawn

    p = with_(FREE, N=-300, M=300, n_quad=512)
    job = {"name": "measurement harness self-test", "mode": "run", "params": p}
    plain = spawn(job)
    v = browser._validate(json.loads(json.dumps(p)))
    est = (browser._plan_bytes(v, plain["used"], True) if plain.get("meta_ok")
           else browser.MAX_PEAK_BYTES)
    check(plain["measured"] == max(0, plain["peak_raw"] - plain["baseline"])
          and 0 < plain["measured"] <= est,
          "measured peak = raw child peak - baseline child peak (same imports, no work)",
          f"raw {plain['peak_raw'] / 1e6:.1f} - baseline {plain['baseline'] / 1e6:.1f} "
          f"= {plain['measured'] / 1e6:.1f} MB <= predicted {est / 1e6:.1f} MB")

    floor_mb = 900.0                     # above anything this run can really reach
    os.environ[FAKE_FLOOR_ENV] = str(floor_mb)
    try:
        faked = spawn(job)
    finally:
        os.environ.pop(FAKE_FLOOR_ENV, None)
    check(faked["peak_raw"] > est and faked["baseline"] > est,
          f"an emulated fork() floor ({floor_mb:.0f} MB) does reach the raw child peak "
          "(the Linux failure, reproduced on any platform)",
          f"raw {faked['peak_raw'] / 1e6:.1f} MB, baseline {faked['baseline'] / 1e6:.1f} MB "
          f"vs predicted {est / 1e6:.1f} MB: an uncorrected check fails here")
    check(faked["measured"] <= plain["measured"] + 1e6 and faked["measured"] <= est,
          "the baseline child subtracts that floor back out: the measured peak does not "
          "move, so the bound checks stay platform-independent",
          f"measured {faked['measured'] / 1e6:.1f} MB with the floor vs "
          f"{plain['measured'] / 1e6:.1f} MB without; predicted {est / 1e6:.1f} MB")


def check_estimate():
    est = json.loads(browser.estimate_json(json.dumps(FREE)))
    check(est["ok"] and est["bytes_result"] == 8 * 120 * 241 and est["bytes_peak"] > 0,
          "estimate_json for a preset", f"peak {est['bytes_peak']:,} B")
    est = json.loads(browser.estimate_json(json.dumps(with_(FREE, N=-3000, M=3000,
                                                             n_quad=2048))))
    check(not est["ok"] and est["error"]["kind"] == "over_budget"
          and est["bytes_peak"] > browser.MAX_PEAK_BYTES,
          "estimate_json flags over-budget", f"{est['bytes_peak'] / 1e6:,.0f} MB")
    est = json.loads(browser.estimate_json(json.dumps(with_(FREE, N=0.5))))
    check(not est["ok"] and est["error"]["kind"] == "invalid_input",
          "estimate_json flags invalid input")
    # P1: node generation (leggauss's n x n matrix + LAPACK's copy) is budgeted
    small = with_(FREE, N=-10, M=10, n_quad=4096)
    meta, psi = run(small)
    err = meta.get("error") or {}
    nodes_8192 = browser._node_bytes([8192])
    check(not meta["ok"] and err.get("kind") == "over_budget" and err.get("field") == "n_quad"
          and nodes_8192 > browser.MAX_PEAK_BYTES and psi is None,
          "n_quad 4096 on a 21-site frame: its 8192-node check is rejected over budget",
          f"node generation alone {nodes_8192 / 1e6:,.0f} MB; {err.get('message', '')[:150]}")
    best = browser._max_n_quad(browser._validate(small))
    meta, _ = run(with_(small, n_quad=best))
    check(meta["ok"] and meta["memory_estimate_bytes"] <= browser.MAX_PEAK_BYTES
          and not run(with_(small, n_quad=best + 1))[0]["ok"],
          "the largest n_quad the budget allows on that frame runs; one more is refused",
          f"n_quad {best}: estimate {meta.get('memory_estimate_bytes', 0) / 1e6:,.0f} MB")

    # P2: the estimate bounds the REAL process peak of a whole run() (fresh
    # process each, OS counters, minus a do-nothing baseline child spawned
    # from the same parent -- see measure_memory.spawn), including the check
    # run, refinement, and many-site / many-channel frames
    from measure_memory import make_params, spawn
    configs = [("free wide", with_(FREE, N=-300, M=300, n_quad=512)),
               ("two-channel coupled n256", with_(COUPLED, n_quad=256)),
               ("schober 2", PRESETS["Schober 2 — two-channel + barrier"]),
               ("audit narrow (refines)", with_(WEAK, amplitude__sigma_E=0.02)),
               ("L1 K40 n256 s201", make_params(256, 201, 1, 40, 100)),
               ("L6 K10 n64 s201 (stops at the budget)", make_params(64, 201, 6, 10, 100)),
               ("L1 n2048 s41 (node generation heavy)", make_params(2048, 41, 1, 0, 50))]
    for name, p in configs:
        res = spawn({"name": name, "mode": "run", "params": p})
        v = browser._validate(json.loads(json.dumps(p)))
        if res.get("meta_ok"):
            est = browser._plan_bytes(v, res["used"], True)
            what = f"{res['status']} {res['used']}/{res['check']}"
        else:
            est = browser.MAX_PEAK_BYTES
            what = res["error"]["kind"]
        check(res["measured"] <= est and res["measured"] <= browser.MAX_PEAK_BYTES,
              f"memory model bounds the real run() peak ({name})",
              f"{what}: measured {res['measured'] / 1e6:.1f} MB <= predicted "
              f"{est / 1e6:.1f} MB (ratio {res['measured'] / est:.2f}); "
              f"raw peak {res['peak_raw'] / 1e6:.1f} - baseline "
              f"{res['baseline'] / 1e6:.1f} MB, budget "
              f"{browser.MAX_PEAK_BYTES / 1e6:.0f} MB")


# ---------------------------------------------------------------------- #
# 2. convergence policy                                                  #
# ---------------------------------------------------------------------- #

def _rel(a, b):
    return float(np.max(np.abs(a - b)) / np.max(np.abs(b)))


def check_policy():
    for name, p, truth_n in [
        ("audit wide frame (Free Gaussian, N,M = -400,400, n_quad 128)",
         with_(FREE, N=-400, M=400), 2048),
        ("audit narrow Gaussian (Weak Barrier, sigma_E = 0.02, n_quad 128)",
         with_(WEAK, amplitude__sigma_E=0.02), 2048),
    ]:
        stages = []
        meta, psi = run(p, stages=stages)
        truth = compute_psi(build_spec(with_(p, n_quad=truth_n)))
        raw = compute_psi(build_spec(p))
        q = meta.get("quadrature", {})
        ok = (meta["ok"] and q["status"] == "refined" and q["used_n_quad"] > 128
              and "refining" in stages and _rel(psi, truth) <= 1e-6 and _rel(raw, truth) > 1e-6)
        check(ok, f"policy catches {name}",
              f"{q.get('status')} at {q.get('used_n_quad')} (checks "
              + ", ".join(f"{c['n_quad']}/{c['check_n_quad']}: {c['discrepancy_rel_peak']:.1e}"
                          for c in q.get("checks", []))
              + f"); requested-n error vs n={truth_n}: {_rel(raw, truth):.2e}, "
                f"returned error: {_rel(psi, truth):.2e}; mass(t=0) requested "
                f"{raw[0].sum():.3f} vs returned {psi[0].sum():.3f}")
    meta, psi = run(with_(WEAK, amplitude__sigma_E=0.02, n_quad=32))
    err = meta.get("error") or {}
    msg = err.get("message", "")
    check(not meta["ok"] and err.get("kind") == "unresolved" and err.get("field") == "n_quad"
          and psi is None,
          "policy refuses what 8x refinement cannot resolve (n_quad 32, sigma_E 0.02)",
          msg[:400])
    check("refinement stops at 8 x" in msg and "Start from a larger n_quad: 256 or more" in msg
          and "do not fit in memory" not in msg,
          "unresolved at the refinement cap advises a larger starting n_quad",
          msg[msg.find("Could not"):][:300])
    from measure_memory import make_params
    meta, psi = run(make_params(64, 201, 6, 10, 100))
    err = meta.get("error") or {}
    msg = err.get("message", "")
    check(err.get("kind") == "unresolved" and "memory limit" in msg
          and "do not fit in memory" in msg and "narrow the N..M range" in msg
          and "Start from a larger" not in msg,
          "unresolved at the memory budget advises a smaller frame / time range / n_t, "
          "not more nodes (L6 K10 n64)", msg[msg.find("Could not"):][:300])
    meta, psi = run(with_(WEAK, amplitude__sigma_E=0.02, n_quad=16))
    err = meta.get("error") or {}
    check(not meta["ok"] and err.get("kind") == "invalid_input"
          and err.get("field") == "n_quad" and psi is None,
          "nodes that miss a narrow packet are reported against n_quad (n_quad 16)",
          err.get("message", "")[:120])

    stages = []
    meta, psi = run(FREE, stages=stages)
    check(stages == ["validating", "computing", "checking", "done"],
          "stage sequence of a verified run", " > ".join(stages))
    check(np.allclose(meta["mass_in_frame"], psi.sum(axis=1), rtol=0, atol=0)
          and psi.flags["C_CONTIGUOUS"] and psi.dtype == np.float64
          and meta["shape"] == list(psi.shape),
          "meta shape / mass_in_frame / C-contiguous float64")


def check_cache():
    meta1, psi1 = run(BARRIER)
    rec = browser.validation_record(meta1)
    key = meta1["config_key"]
    stages = []
    meta2, psi2 = run(BARRIER, json.dumps({key: rec}), stages)
    q = meta2["quadrature"]
    check(meta2["ok"] and q["status"] == "cached" and "checking" not in stages
          and psi2.tobytes() == psi1.tobytes()
          and q["discrepancy_rel_peak"] == rec["discrepancy_rel_peak"],
          "cached record: one compute, bit-identical psi, stored numbers reported",
          " > ".join(stages))
    # JS sends 0 for 0.0 and drops nothing else: the key must not care
    def js_numbers(x):     # what JSON.stringify does to integral doubles
        if isinstance(x, float) and x.is_integer():
            return int(x)
        if isinstance(x, list):
            return [js_numbers(v) for v in x]
        if isinstance(x, dict):
            return {k: js_numbers(v) for k, v in x.items()}
        return x
    as_js = js_numbers(BARRIER)
    meta3, _ = run(as_js, json.dumps({key: rec}))
    check(meta3["ok"] and meta3["config_key"] == key and meta3["quadrature"]["status"] == "cached",
          "config_key is the same for 0 and 0.0 (JavaScript number formatting)")
    stale = dict(rec, source_revision="some-other-build")
    meta4, _ = run(BARRIER, json.dumps({key: stale}))
    check(meta4["ok"] and meta4["quadrature"]["status"] == "verified",
          "record from another source revision is ignored")
    meta5, _ = run(with_(BARRIER, outer_sign=-1), json.dumps({key: rec}))
    check(meta5["ok"] and meta5["quadrature"]["status"] == "verified"
          and meta5["config_key"] != key,
          "record for a different config (other outer sign) is not used")
    meta6, _ = run(BARRIER, "not json")
    check(meta6["ok"] and meta6["quadrature"]["status"] == "verified" and meta6["warnings"],
          "unreadable cache -> recompute with a warning")
    bad = dict(rec, used_n_quad="lots")
    meta7, _ = run(BARRIER, json.dumps({key: bad}))
    check(meta7["ok"] and meta7["quadrature"]["status"] == "verified",
          "malformed record is ignored")
    req = rec["requested_n_quad"]
    inconsistent = [
        ("tolerance looser than this build's", dict(rec, tolerance=1e-3,
                                                    discrepancy_rel_peak=5e-4)),
        ("discrepancy above TOLERANCE", dict(rec, discrepancy_rel_peak=2e-6)),
        ("requested n_quad differs from params", dict(rec, requested_n_quad=req * 2,
                                                      used_n_quad=req * 2,
                                                      check_n_quad=req * 4)),
        ("used = 3 x requested (not a power of two)",
         dict(rec, used_n_quad=3 * req, check_n_quad=6 * req, status="refined")),
        ("used = 16 x requested (beyond MAX_REFINE_FACTOR)",
         dict(rec, used_n_quad=16 * req, check_n_quad=32 * req, status="refined")),
        ("check not 2 x used", dict(rec, check_n_quad=3 * req)),
        ("status verified but used > requested",
         dict(rec, used_n_quad=2 * req, check_n_quad=4 * req, status="verified")),
        ("negative tolerance", dict(rec, tolerance=-1.0)),
        ("boolean n_quad", dict(rec, used_n_quad=True)),
    ]
    for name, r in inconsistent:
        stages = []
        m, _ = run(BARRIER, json.dumps({key: r}), stages)
        check(m["ok"] and m["quadrature"]["status"] == "verified" and "checking" in stages
              and any("malformed" in w for w in m["warnings"]),
              f"inconsistent cache record rejected: {name}")
    check(meta2["quadrature"]["tolerance"] == browser.TOLERANCE,
          "cached run reports the stored discrepancy against this build's TOLERANCE")
    ok_refined = dict(rec, used_n_quad=2 * req, check_n_quad=4 * req, status="refined",
                      discrepancy_rel_peak=1e-9)
    m, _ = run(BARRIER, json.dumps({key: ok_refined}))
    check(m["ok"] and m["quadrature"]["status"] == "cached"
          and m["quadrature"]["used_n_quad"] == 2 * req,
          "consistent refined record (used 2 x requested, check 4 x) is accepted")
    # Converged, but only just: the browser's NumPy is not the one that
    # measured this, so the check is run again here instead of trusted.
    borderline = dict(rec, discrepancy_rel_peak=browser.TOLERANCE * 0.5)
    stages = []
    m, _ = run(BARRIER, json.dumps({key: borderline}), stages)
    check(m["ok"] and m["quadrature"]["status"] == "verified"
          and "checking" in stages
          and not any("malformed" in w for w in m["warnings"]),
          "record within TOLERANCE but outside the trust margin is re-checked, not rejected",
          f"stored {borderline['discrepancy_rel_peak']:.1e} vs trust margin "
          f"{browser.TOLERANCE * browser.CACHE_TRUST_FRACTION:.1e}")
    just_inside = dict(rec, discrepancy_rel_peak=browser.TOLERANCE
                       * browser.CACHE_TRUST_FRACTION * 0.5)
    m, _ = run(BARRIER, json.dumps({key: just_inside}))
    check(m["ok"] and m["quadrature"]["status"] == "cached",
          "record comfortably inside the trust margin is still used")

    wide = with_(FREE, N=-400, M=400)
    m_ref, psi_ref = run(wide)
    m_c, psi_c = run(wide, json.dumps({m_ref["config_key"]: browser.validation_record(m_ref)}))
    check(m_c["ok"] and m_c["quadrature"]["status"] == "cached"
          and m_c["quadrature"]["used_n_quad"] == m_ref["quadrature"]["used_n_quad"]
          and psi_c.tobytes() == psi_ref.tobytes(),
          "cached refined record computes once at the refined n_quad",
          f"used {m_c['quadrature']['used_n_quad']}")


def check_presets():
    listed = json.loads(browser.presets_json())
    check([x["name"] for x in listed] == list(PRESETS)
          and [x["id"] for x in listed] == [PRESET_IDS[n] for n in PRESETS]
          and len(listed) == 13 and all(x["description"] for x in listed),
          "presets_json: 13 presets in desktop order with ids and descriptions")
    statuses = {}
    for x in listed:
        for sign in (1, -1):
            meta, psi = run(with_(x["params"], outer_sign=sign))
            statuses[(x["id"], sign)] = (meta["ok"] and meta["quadrature"]["status"],
                                         meta.get("quadrature", {}).get("checks", [{}])[0]
                                         .get("discrepancy_rel_peak"))
    plus_ok = all(statuses[(x["id"], 1)][0] == "verified" for x in listed)
    check(plus_ok, "all 13 presets verify at their shipped n_quad (outer_sign +1)",
          "worst 2x discrepancy "
          f"{max(statuses[(x['id'], 1)][1] for x in listed):.1e}")
    minus = {k[0]: v for k, v in statuses.items() if k[1] == -1}
    not_verified = {k: v for k, v in minus.items() if v[0] != "verified"}
    check(all(v[0] in ("verified", "refined") for v in minus.values()),
          "all 13 presets succeed with outer_sign -1 (verified or refined)",
          "not verified at shipped n_quad: "
          + (", ".join(f"{k} ({v[0]}; 2x discrepancy {v[1]:.1e})"
                       for k, v in not_verified.items()) or "none"))


# ---------------------------------------------------------------------- #
# 3. independent references                                              #
# ---------------------------------------------------------------------- #

def _gl_panels(lo, hi, panels, order=16):
    x, w = np.polynomial.legendre.leggauss(order)
    edges = np.linspace(lo, hi, panels + 1)
    half = 0.5 * np.diff(edges)
    mid = 0.5 * (edges[1:] + edges[:-1])
    return ((mid[:, None] + half[:, None] * x[None, :]).ravel(),
            (half[:, None] * w[None, :]).ravel())


def check_free_closed_form():
    """(a) Free lattice: exact e^{-iHt} by FFT on a periodic ring.

    The initial lattice state is built from f alone in the momentum variable
    theta (E = 2a cos theta, dE = 2a sin theta dtheta):
        phi0(n) = sum_sigma int f_sigma(2a cos theta) e^{-i sigma n theta}
                  sqrt(2a sin theta) dtheta / sqrt(2 pi p),
        p = sum_sigma int |f_sigma|^2 2a sin theta dtheta,
    on a composite Gauss rule in theta (not the energy rule compute_psi uses),
    then evolved with the ring's exact propagator e^{-i 2a cos(k) t} in
    Fourier space. |phi_t(n)|^2 must match compute_psi's psi(n, t).
    """
    a = 1.0
    for direction, n_init, E0 in (("right", -40, 0.3), ("balanced", 25, -0.4)):
        params = with_(FREE, N=-300, M=300, n_quad=512,
                       times={"t_min": -10.0, "t_max": 50.0, "n_t": 13},
                       amplitude={"mode": "gaussian", "E0": E0, "sigma_E": 0.3,
                                  "direction": direction, "n_init": n_init})
        meta, psi = run(params)
        lo, hi = params["interval"]
        th, wth = _gl_panels(math.acos(hi / (2 * a)), math.acos(lo / (2 * a)), 1024)
        E = 2 * a * np.cos(th)
        from spectral.maxwell.presets import DIRECTION_WEIGHTS
        h_p, h_m = DIRECTION_WEIGHTS[direction]
        f = gaussian_f(1, a, E0, 0.3, h_p, h_m, n_init)(E)[:, 0, :]   # (n, 2): input data only
        jac = 2 * a * np.sin(th)
        p = float(np.sum((np.abs(f) ** 2).sum(1) * jac * wth))
        R = 4096
        n_ring = np.arange(-R // 2, R // 2)
        phi0 = np.zeros(R, dtype=complex)
        g = np.sqrt(jac) * wth
        for s in range(0, R, 256):
            nn = n_ring[s:s + 256, None]
            phi0[s:s + 256] = (np.exp(-1j * nn * th) @ (f[:, 0] * g)
                               + np.exp(+1j * nn * th) @ (f[:, 1] * g))
        phi0 /= math.sqrt(2 * math.pi * p)
        k = 2 * np.pi * np.fft.fftfreq(R)
        F0 = np.fft.fft(phi0)
        times = np.linspace(-10.0, 50.0, 13)
        frame = (n_ring >= -300) & (n_ring <= 300)
        ref = np.array([np.abs(np.fft.ifft(np.exp(-1j * 2 * a * np.cos(k) * t) * F0)[frame]) ** 2
                        for t in times])
        err = _rel(psi, ref)
        check(meta["ok"] and err < 1e-9,
              f"(a) free Gaussian ({direction}, n_init {n_init}) vs exact FFT evolution "
              f"on a 4096-site ring", f"max|dpsi|/peak = {err:.2e}; "
              f"sum psi(t=50) = {psi[-1].sum():.12f} vs ring {ref[-1].sum():.12f}")


def check_barrier_transmission():
    """(b) Single-site barrier: transmitted / reflected mass vs analytic |T|^2."""
    a = 1.0
    for v, E0 in ((0.8, 0.0), (1.5, -1.0), (0.6, 0.8)):
        sin_k0 = math.sqrt(1 - (E0 / (2 * a)) ** 2)
        T = 600.0 / (2 * a * sin_k0)            # centre travels -300 -> +300
        params = {"L": 1, "a": [a], "N": -600, "M": 600, "j_sites": [0],
                  "V_sites": [[[[v, 0.0]]]], "interval": [E0 - 0.4, E0 + 0.4],
                  "times": {"t_min": 0.0, "t_max": T, "n_t": 2}, "n_quad": 256,
                  "outer_sign": 1, "threshold_buffer": 0.001,
                  "amplitude": {"mode": "gaussian", "E0": E0, "sigma_E": 0.05,
                                "direction": "right", "n_init": -300}}
        meta, psi = run(params)
        n = np.arange(-600, 601)
        trans = float(psi[-1][n > 0].sum())
        refl = float(psi[-1][n < 0].sum())
        EE = np.linspace(E0 - 0.4, E0 + 0.4, 400001)
        s2 = 1 - (EE / (2 * a)) ** 2
        T2 = 4 * a * a * s2 / (4 * a * a * s2 + v * v)
        wgt = np.exp(-((EE - E0) ** 2) / (0.05 ** 2))      # |f|^2 = env^2
        pred = float(np.trapezoid(T2 * wgt, EE) / np.trapezoid(wgt, EE))
        ok = (meta["ok"] and abs(trans - pred) < 1e-6 and abs(refl - (1 - pred)) < 1e-6
              and psi[0][n > -100].sum() < 1e-9)
        check(ok, f"(b) barrier V={v} at E0={E0}: |T|^2 = 1 - |R|^2 vs analytic",
              f"transmitted {trans:.9f} vs {pred:.9f} (diff {trans - pred:.1e}); "
              f"reflected {refl:.9f} vs {1 - pred:.9f}; status "
              f"{meta.get('quadrature', {}).get('status')}")


def main() -> int:
    t0 = time.perf_counter()
    print(f"spectral.browser self-check (Python {sys.version.split()[0]}, "
          f"NumPy {np.__version__})")
    check_invalid()
    check_messages_and_misc()
    check_internal_and_callbacks()
    check_measurement_harness()
    check_estimate()
    check_policy()
    check_cache()
    check_presets()
    check_free_closed_form()
    check_barrier_transmission()
    failed = [n for ok, n in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed "
          f"in {time.perf_counter() - t0:.1f} s")
    for n in failed:
        print(f"FAILED: {n}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
