"""Calibrate spectral/browser.py's memory model against real process peaks.

    python web/scripts/measure_memory.py [--fit] [--out results.json]

Every configuration runs in a FRESH child process (this script re-invoked
with --child), single-threaded BLAS (OPENBLAS_NUM_THREADS=1, like the wasm
build). The child builds its inputs, collects garbage, reads its current
working set and commit, runs the work, and reports

    raw = max(peak working set - working set before,
              peak commit      - commit before)

from the OS counters (Windows: K32GetProcessMemoryInfo PeakWorkingSetSize /
PeakPagefileUsage; Linux: /proc/self/status VmHWM; elsewhere ru_maxrss), so
memory NumPy never reports to tracemalloc -- LAPACK's copy of the n x n
companion matrix inside numpy.polynomial.legendre.leggauss, BLAS buffers --
is counted. The counters are monotonic, so raw can only overstate the work's
own peak (by at most the "floor" column: peak-before minus current-before).

Every measurement is paired with a BASELINE child spawned back to back with
it from the same parent state: the same process, the same imports (NumPy,
spectral.browser), no work. What it reports is everything the number owes to
the harness rather than to the work, and

    measured = max(0, raw - baseline)

is what the model is checked against. See spawn() for why a raw peak is not
trustworthy on its own (fork() + ru_maxrss made every Linux measurement
report the parent's RSS).

Modes per row:
  compute  one compute_psi at the given n_quad (what the model predicts)
  run      a whole spectral.browser.run() (check run, refinement, copies),
           compared with the plan the bridge budgeted
  nodes    Gauss-Legendre node generation alone
  baseline the imports and nothing else (the correction described above)

--fit prints a non-negative least-squares fit (relative error) of the
compute rows to the model's feature terms, with the node term held at its
measured per-node^2 cost; the coefficients in browser.py come from it.
Always prints measured vs predicted with the model currently in browser.py.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import time

from _common import REPO_ROOT

_PYTHON = sys.executable


# ---------------------------------------------------------------------- #
# Process counters                                                       #
# ---------------------------------------------------------------------- #

FAKE_FLOOR_ENV = "SPECTRAL_MEASURE_FAKE_FLOOR_MB"


def _posix_counters() -> dict:
    """Current / peak RSS from /proc/self/status, else ru_maxrss.

    ru_maxrss must NOT be used on its own on Linux. subprocess starts a child
    with fork() + exec(); the forked child's RSS starts out equal to the
    PARENT's (copy-on-write pages count towards RSS), and on exec the kernel
    latches that high-water mark into the new process's accounting
    (exec_mmap -> setmax_mm_hiwater_rss(&signal->maxrss, old_mm)). So
    getrusage(RUSAGE_SELF).ru_maxrss in the child never reports less than the
    parent's RSS at spawn time. A parent that has done a few hundred MB of
    work therefore makes every child report that same floor regardless of
    what the child does -- which is exactly what CI showed (every case
    530.5 MB) while Windows, which has no fork, was fine.

    VmHWM is the high-water mark of the post-exec mm alone: the pages the
    forked child shared with its parent belonged to the mm that exec threw
    away, so they are not in it. macOS has no /proc and keeps ru_maxrss's
    fork behaviour; there the baseline subtraction in spawn() is the only
    correction, and it can only under-report, never over-report.
    """
    rss = peak = None
    try:
        with open("/proc/self/status", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("VmHWM:"):
                    peak = int(line.split()[1]) * 1024
                elif line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
    except OSError:
        pass
    if peak is None:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak *= 1 if sys.platform == "darwin" else 1024
    if rss is None:
        rss = peak                       # no cheap current RSS (macOS)
    return {"ws": rss, "peak_ws": peak, "commit": rss, "peak_commit": peak}


def _counters() -> dict:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                                wintypes.DWORD]
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc),
                                           pmc.cb):
            raise OSError(ctypes.get_last_error(), "K32GetProcessMemoryInfo failed")
        c = {"ws": pmc.WorkingSetSize, "peak_ws": pmc.PeakWorkingSetSize,
             "commit": pmc.PagefileUsage, "peak_commit": pmc.PeakPagefileUsage}
    else:
        c = _posix_counters()
    fake = os.environ.get(FAKE_FLOOR_ENV)
    if fake:
        # Test hook (check_bridge.check_measurement_harness): emulate the
        # inherited high-water mark a fork()ed child reports on Linux -- a
        # floor under the peak counters that owes nothing to this process's
        # work. Windows cannot produce one, so this is how the correction is
        # exercised on a developer machine.
        floor = int(float(fake) * 1e6)
        c["peak_ws"] = max(c["peak_ws"], floor)
        c["peak_commit"] = max(c["peak_commit"], floor)
    return c


def _child(job: dict) -> dict:
    import gc

    import numpy as np

    import spectral.browser as browser
    from spectral.maxwell import compute_psi
    from spectral.maxwell.presets import build_spec
    from spectral.maxwell.quadrature import gauss_legendre

    params = job["params"]
    mode = job["mode"]
    if mode == "compute":
        p = dict(params, n_quad=job["n_quad"])
        spec = build_spec(p)
        spec.validate()
        work = lambda: compute_psi(spec)        # noqa: E731
    elif mode == "run":
        text = json.dumps(params)
        work = lambda: browser.run(text, None, None)  # noqa: E731
    elif mode == "nodes":
        work = lambda: gauss_legendre(-1.0, 1.0, job["n_quad"])  # noqa: E731
    elif mode == "baseline":
        # same process, same imports above (NumPy, spectral.browser), no work
        work = lambda: None                     # noqa: E731
    else:
        raise SystemExit(f"unknown mode {mode}")
    np.zeros(16).sum()
    gc.collect()
    c0 = _counters()
    t0 = time.perf_counter()
    out = work()
    seconds = time.perf_counter() - t0
    c1 = _counters()
    res = {
        "measured": max(c1["peak_ws"] - c0["ws"], c1["peak_commit"] - c0["commit"]),
        "floor": max(c0["peak_ws"] - c0["ws"], c0["peak_commit"] - c0["commit"]),
        "seconds": seconds,
    }
    if mode == "run":
        meta = json.loads(out[0])
        res["meta_ok"] = meta["ok"]
        if meta["ok"]:
            q = meta["quadrature"]
            res.update(status=q["status"], used=q["used_n_quad"], check=q["check_n_quad"],
                       estimate=meta["memory_estimate_bytes"])
        else:
            res.update(error=meta["error"])
    return res


# ---------------------------------------------------------------------- #
# Configurations                                                         #
# ---------------------------------------------------------------------- #

def make_params(n_quad, n_sites, L, K, n_t, seed=0):
    """Gaussian params with K Hermitian L x L sites spread over the frame."""
    import numpy as np

    rng = np.random.default_rng(seed + 1000 * L + K)
    half = (n_sites - 1) // 2
    N, M = -half, n_sites - 1 - half
    if K:
        span = max(1, (M - N) // 2)
        j = np.unique(np.linspace(-span // 2, span // 2, K).round().astype(int))
        while j.size < K:                     # tiny frames: pack densely
            j = np.arange(-(K // 2), K - K // 2)
        j_sites = [int(x) for x in j]
    else:
        j_sites = []
    V = []
    for _ in j_sites:
        A = rng.normal(size=(L, L)) + 1j * rng.normal(size=(L, L))
        H = 0.15 * (A + A.conj().T) / 2
        V.append([[[float(H[r, c].real), float(H[r, c].imag if r != c else 0.0)]
                   for c in range(L)] for r in range(L)])
    return {
        "L": L, "a": [round(1.0 - 0.08 * i, 2) for i in range(L)], "N": N, "M": M,
        "j_sites": j_sites, "V_sites": V, "interval": [-0.9, 0.9],
        "times": {"t_min": 0.0, "t_max": 30.0, "n_t": n_t}, "n_quad": n_quad,
        "outer_sign": 1, "threshold_buffer": 0.001,
        "amplitude": {"mode": "gaussian", "E0": 0.0, "sigma_E": 0.3,
                      "direction": "right", "n_init": 0},
    }


def compute_rows():
    rows = []
    # (n_quad, n_sites, L, K, n_t)
    grid = [
        (128, 241, 1, 0, 120), (1024, 801, 1, 0, 50), (4096, 201, 1, 0, 50),
        (512, 201, 2, 0, 100), (256, 401, 4, 0, 100), (128, 201, 6, 0, 100),
        (128, 201, 1, 1, 100), (512, 801, 1, 1, 100), (2048, 401, 1, 1, 100),
        (256, 201, 1, 10, 100), (256, 201, 1, 20, 100), (256, 201, 1, 40, 100),
        (128, 401, 1, 48, 100), (512, 301, 1, 40, 100),
        (256, 201, 2, 1, 100), (1024, 401, 2, 1, 100), (256, 201, 2, 10, 100),
        (256, 201, 2, 40, 100), (128, 401, 2, 24, 100),
        (256, 301, 3, 2, 100), (128, 201, 3, 20, 100), (128, 201, 3, 40, 100),
        (256, 201, 4, 3, 100), (128, 201, 4, 12, 100), (64, 201, 4, 40, 100),
        (192, 241, 5, 5, 100), (64, 201, 5, 40, 100),
        (128, 201, 6, 2, 100), (64, 201, 6, 10, 100), (64, 201, 6, 40, 100),
        (32, 101, 6, 40, 100),
        (256, 2001, 1, 1, 2000),
        (4096, 21, 1, 0, 50), (8192, 21, 1, 0, 50), (8192, 21, 2, 1, 50),
    ]
    for n, s, L, K, t in grid:
        rows.append({"name": f"L{L} K{K} n{n} s{s} t{t}", "mode": "compute", "n_quad": n,
                     "params": make_params(n, s, L, K, t)})
    from spectral.maxwell.presets import PRESETS
    sch = PRESETS["Schober 2 — two-channel + barrier"]
    for n in (200, 1600, 8192):
        rows.append({"name": f"Schober 2 n{n}", "mode": "compute", "n_quad": n,
                     "params": dict(sch, n_quad=n)})
    sch1 = PRESETS["Schober 1 — two-channel window"]
    rows.append({"name": "Schober 1 n8192", "mode": "compute", "n_quad": 8192,
                 "params": dict(sch1, n_quad=8192)})
    return rows


def node_rows():
    return [{"name": f"nodes n{n}", "mode": "nodes", "n_quad": n, "params": None}
            for n in (1024, 2048, 4096, 8192)]


def run_rows():
    import copy

    from spectral.maxwell.presets import PRESETS
    rows = []
    for name in ("Free Gaussian Wave Packet", "Random Lattice (L=1)",
                 "Two-Channel Coupled Scatterer (L=2)", "Schober 2 — two-channel + barrier"):
        rows.append({"name": f"run {name[:24]}", "mode": "run", "params": PRESETS[name]})
    wide = copy.deepcopy(PRESETS["Free Gaussian Wave Packet"])
    wide.update(N=-400, M=400)
    rows.append({"name": "run audit wide frame (refines)", "mode": "run", "params": wide})
    narrow = copy.deepcopy(PRESETS["Weak Barrier — small kick"])
    narrow["amplitude"]["sigma_E"] = 0.02
    rows.append({"name": "run audit narrow sigma_E (refines)", "mode": "run", "params": narrow})
    rows.append({"name": "run L1 K40 n256 s201", "mode": "run",
                 "params": make_params(256, 201, 1, 40, 100)})
    rows.append({"name": "run L6 K10 n64 s201", "mode": "run",
                 "params": make_params(64, 201, 6, 10, 100)})
    rows.append({"name": "run L2 K1 n1024 s401", "mode": "run",
                 "params": make_params(1024, 401, 2, 1, 100)})
    rows.append({"name": "run L1 n2048 s41", "mode": "run",
                 "params": make_params(2048, 41, 1, 0, 50)})
    return rows


BASELINE_JOB = {"name": "baseline", "mode": "baseline", "params": None}


def _spawn_one(job: dict) -> dict:
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([_PYTHON, __file__, "--child"], input=json.dumps(job),
                         capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))
    if out.returncode != 0:
        raise SystemExit(f"child failed for {job['name']}:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def spawn(job: dict, baseline: bool = True) -> dict:
    """Measure one configuration, corrected by a do-nothing baseline child.

    A child's raw peak is not the work's peak: it also carries whatever the
    harness put there. On Linux that used to be the whole number -- children
    are forked, and a forked child's ru_maxrss can never fall below the RSS
    its parent had at spawn time (see _posix_counters), so every case
    reported the same few hundred MB. Reading VmHWM removes that particular
    floor, but a measurement should not depend on believing any one
    counter's exec semantics, so what is compared against the model is

        measured = max(0, raw - baseline)

    where the baseline is a child spawned the same way, from the same parent,
    immediately before this one: same imports, no work. Anything both
    children have in common -- interpreter and NumPy start-up, BLAS
    scratch, an inherited peak -- cancels.

    The baseline is re-measured for every configuration because the parent
    keeps allocating as it works, so a baseline taken once at the start would
    not describe the children spawned later. Both raw and baseline are kept
    in the result for diagnosis; a floor that exceeds the work's own peak
    cannot be undone by any subtraction, and makes `measured` a lower bound
    (it is clamped at 0), never an over-estimate.
    """
    base = _spawn_one(BASELINE_JOB) if baseline else None
    res = _spawn_one(job)
    res["peak_raw"] = res["measured"]
    res["baseline"] = base["measured"] if base else 0
    res["baseline_floor"] = base["floor"] if base else 0
    res["measured"] = max(0, res["peak_raw"] - res["baseline"])
    return res


# ---------------------------------------------------------------------- #
# Model features and fit                                                 #
# ---------------------------------------------------------------------- #

def features(params, n_quad):
    """The terms of browser._single_peak_raw, unscaled, for one compute_psi."""
    import spectral.browser as browser
    counts = browser._segment_counts(params, n_quad)
    n_E = sum(counts)
    n_s = params["M"] - params["N"] + 1
    L = params["L"]
    K = len(params["j_sites"])
    n_t = params["times"]["n_t"]
    S = 16.0 * n_E * n_s * L * L
    return {"slab": S, "slab_if_sites": S * (K > 0), "green": S * K,
            "kernel": 16.0 * n_E * n_s * L * K, "frames": 8.0 * n_t * n_s,
            "const": 1e6, "nodes": float(sum(c * c for c in counts))}


FIT_TERMS = ("slab", "slab_if_sites", "green", "kernel", "frames", "const")


def nnls_rel(rows, node_coef):
    """Exact NNLS on relative error by enumerating active sets (6 terms)."""
    import numpy as np
    X = np.array([[r["features"][t] for t in FIT_TERMS] for r in rows])
    y = np.array([r["measured"] - node_coef * r["features"]["nodes"] for r in rows])
    w = 1.0 / np.array([r["measured"] for r in rows], dtype=float)
    Xw, yw = X * w[:, None], y * w
    best = None
    for k in range(1, len(FIT_TERMS) + 1):
        for sub in itertools.combinations(range(len(FIT_TERMS)), k):
            coef, *_ = np.linalg.lstsq(Xw[:, sub], yw, rcond=None)
            if np.any(coef < 0):
                continue
            res = float(np.sum((Xw[:, sub] @ coef - yw) ** 2))
            if best is None or res < best[0]:
                full = np.zeros(len(FIT_TERMS))
                full[list(sub)] = coef
                best = (res, full)
    return dict(zip(FIT_TERMS, best[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--only", choices=("compute", "run", "nodes"))
    ap.add_argument("--from", dest="saved",
                    help="re-evaluate the current model on a saved --out file "
                         "instead of measuring again")
    args = ap.parse_args()
    if args.child:
        print(json.dumps(_child(json.loads(sys.stdin.read()))))
        return 0

    import spectral.browser as browser

    if args.saved:
        with open(args.saved, encoding="utf-8") as fh:
            saved = json.load(fh)
        keep = ("measured", "peak_raw", "baseline", "baseline_floor", "floor", "seconds",
                "meta_ok", "status", "used", "check", "estimate", "error")
        jobs = [(dict(name=r["name"].split(" [")[0], mode=r["mode"], params=r["params"],
                      **({"n_quad": r["n_quad"]} if "n_quad" in r else {})),
                 {k: r[k] for k in keep if k in r}) for r in saved]
    else:
        jobs = []
        if args.only in (None, "nodes"):
            jobs += node_rows()
        if args.only in (None, "compute"):
            jobs += compute_rows()
        if args.only in (None, "run"):
            jobs += run_rows()
        jobs = [(j, None) for j in jobs]
    results = []
    worst = 0.0
    print(f"{'config':40s} {'measured MB':>12s} {'raw MB':>8s} {'base MB':>8s} "
          f"{'predicted MB':>13s} {'ratio':>6s} {'floor MB':>9s}")
    for job, res in jobs:
        if res is None:
            res = spawn(job)
        row = dict(job, **res)
        if job["mode"] == "compute":
            row["features"] = features(job["params"], job["n_quad"])
            row["predicted"] = browser._single_peak(job["params"], job["n_quad"])
        elif job["mode"] == "nodes":
            row["predicted"] = browser._node_bytes([job["n_quad"]]) + int(
                browser._MEM_SAFETY * browser._MEM_COEF["const"] * 1e6)
        else:
            p = browser._validate(json.loads(json.dumps(job["params"])))
            if res.get("meta_ok"):
                # the largest plan the bridge budgeted for this run
                row["predicted"] = browser._plan_bytes(p, res["used"], True)
                row["name"] += f" [{res['status']} {res['used']}/{res['check']}]"
            else:
                row["predicted"] = browser._plan_bytes(p, p["n_quad"], True)
                row["name"] += f" [{res['error']['kind']}]"
        ratio = row["measured"] / row["predicted"]
        if not (job["mode"] == "run" and not res.get("meta_ok")):
            worst = max(worst, ratio)
        print(f"{row['name'][:40]:40s} {row['measured'] / 1e6:12.2f} "
              f"{row.get('peak_raw', row['measured']) / 1e6:8.2f} "
              f"{row.get('baseline', 0) / 1e6:8.2f} "
              f"{row['predicted'] / 1e6:13.2f} {ratio:6.3f} {row['floor'] / 1e6:9.2f}",
              flush=True)
        results.append(row)
    print(f"\nworst measured / predicted = {worst:.3f} "
          f"({'every measured peak is within the model' if worst <= 1 else 'MODEL EXCEEDED'})")

    if args.fit:
        # slope between the two largest node rows (the process's fixed BLAS /
        # LAPACK start-up cost cancels), never below the 16 B/node^2 of the
        # companion matrix plus LAPACK's copy of it
        nodes = sorted((r for r in results if r["mode"] == "nodes"),
                       key=lambda r: r["n_quad"])
        a_, b_ = nodes[-2], nodes[-1]
        node_coef = max(16.0, (b_["measured"] - a_["measured"])
                        / (b_["n_quad"] ** 2 - a_["n_quad"] ** 2))
        comp = [r for r in results if r["mode"] == "compute"]
        coef = nnls_rel(comp, node_coef)
        print(f"\nnode term: {node_coef:.2f} bytes per node^2 (max of 16 and measured)")
        print("NNLS (relative error) coefficients:",
              ", ".join(f"{k} {v:.4g}" for k, v in coef.items()))
        errs = []
        for r in comp:
            f = r["features"]
            fit = sum(coef[t] * f[t] for t in FIT_TERMS) + node_coef * f["nodes"]
            errs.append(r["measured"] / fit)
        print(f"measured / unscaled fit: {min(errs):.3f} .. {max(errs):.3f}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1)
    return 0 if worst <= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
