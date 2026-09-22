"""Browser bridge: the only Python entry point the web worker calls.

Takes the web UI's canonical params as JSON, validates them strictly, builds
the MaxwellSpec through spectral.maxwell.presets.build_spec (the same builder
the desktop presets use) and runs spectral.maxwell.compute_psi -- the one and
only numerical implementation. Nothing here does physics: this module checks
inputs, budgets memory, checks quadrature convergence by re-running
compute_psi at twice the node count, and reports what happened in plain text.

    presets_json() -> str
    estimate_json(params_json) -> str
    run(params_json, cached_validation_json, on_stage) -> (meta_json, psi | None)

run() never raises: every failure comes back as
{"ok": false, "error": {"kind", "field", "message"}} with psi = None.
Pure Python + NumPy; imported natively by web/scripts/*.py and in Pyodide by
the worker.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import time

import numpy as np

from .maxwell import compute_psi
from .maxwell.presets import (
    DIRECTION_WEIGHTS,
    PRESET_IDS,
    PRESETS,
    SCHOBER_E_SEGMENTS,
    WEB_DESCRIPTIONS,
    WINDOW_FORM_GAUSSIAN,
    build_spec,
)
from .maxwell.quadrature import (
    _allocate_nodes,
    gauss_legendre,
    gauss_legendre_segments,
    safe_open_band_interval,
    safe_open_band_segments,
)

try:  # written only into the web archive by web/scripts/build_py_archive.py
    from ._build_info import SOURCE_REVISION
except ImportError:  # running from a source checkout
    SOURCE_REVISION = "dev"


# ---------------------------------------------------------------------- #
# Limits                                                                 #
# ---------------------------------------------------------------------- #

TOLERANCE = 1e-6                 # max|psi_n - psi_2n| / max|psi_2n|
MAX_QUAD_NODES = 8192            # every run, including the checks
MAX_PEAK_BYTES = 700_000_000     # estimated peak working set of a whole run()
MAX_RESULT_VALUES = 4_000_000    # n_t * n_sites
MAX_L = 6
MAX_ABS_SITE = 20000
MAX_N_T = 2000
MIN_N_QUAD = 8
MAX_REFINE_FACTOR = 8            # compare n/2n, then 2n/4n, then 4n/8n at most
ZERO_AMPLITUDE = 1e-8            # max|f| on the quadrature nodes below this -> reject
HERMITIAN_ATOL = 1e-10           # max|V - V^H| allowed, absolute (rtol 0): stricter
                                 # than MaxwellSpec.validate()'s np.allclose(atol=1e-10),
                                 # whose default rtol=1e-5 lets large entries be skewed

# Memory model for ONE compute_psi call, in bytes. n_E = total energy nodes,
# n_i = nodes in quadrature segment i (one segment unless E_segments),
# n_s = M - N + 1 sites, L channels, K potential sites, n_t times, and the
# complex slab S = 16 n_E n_s L^2:
#
#   peak = 1.25 * ( 4.24 S                   Jost bundle, free / eigenfunction slabs
#                 + 2.93 S [K > 0]           Wronskian / Green temporaries
#                 + 1.73 S K                 Green grid G (2, n_E, n_s, K, L, L)
#                 + 1.70 * 16 n_E n_s L K    s-kernel and its z^(+-) temporaries
#                 + 2.09 * 8 n_t n_s         psi and its normalised copy
#                 + 35.9e6                   BLAS / LAPACK start-up
#                 + 16.04 * sum_i n_i^2 )    node generation: leggauss's n x n
#                                            companion matrix + LAPACK's copy
#
# Calibrated by web/scripts/measure_memory.py against REAL process peaks
# (not tracemalloc, which misses LAPACK's copy): every configuration runs in
# a fresh process with single-threaded BLAS, and the peak is the rise in
# Windows PeakWorkingSetSize / PeakPagefileUsage above the working set just
# before the call (NumPy 2.4.2, Python 3.13). Coefficients are a
# non-negative least-squares fit (relative error) over 39 compute_psi runs,
# L = 1..6, K = 0..48, n_E = 32..8192, n_s = 21..2001, n_t = 50..2000,
# single interval and Schober E_segments; the node coefficient is the
# measured slope between 4096 and 8192 nodes (16 bytes = the matrix and one
# copy). The unscaled fit lies within 0.45..1.23 of every measured peak, so
# the safety factor is 1.25. Summing the segments' n_i^2 is conservative:
# segments are generated one after another (Schober 1 at 8192 nodes peaks
# like a single 4096-node rule). Measured / predicted, MB:
#
#   nodes only n8192          1112 / 1390   L1 K0  n128  s241      37 /   48
#   L1 K0  n4096 s201          304 /  451   L1 K0  n8192 s21     1112 / 1405
#   L1 K1  n2048 s401          218 /  304   L1 K40 n256  s201     171 /  195
#   L1 K48 n128  s401          197 /  222   L1 K40 n512  s301     444 /  496
#   L2 K1  n1024 s401          377 /  387   L2 K40 n256  s201     336 /  501
#   L3 K40 n128  s201          373 /  504   L4 K40 n64   s201     335 /  430
#   L5 K5  n192  s241          413 /  451   L5 K40 n64   s201     503 /  624
#   L6 K2  n128  s201          247 /  253   L6 K40 n64   s201     709 /  858
#   L1 K1  n256  s2001 t2000   189 /  238   Schober 2 n1600       345 /  389
#   Schober 2 n8192           1624 / 2343   Schober 1 n8192       304 /  852
# Whole run() calls (check run, refinement, held results) vs the largest
# plan the bridge budgeted (_plan_bytes):
#   Free Gaussian (verified)    41 /   53   Schober 2 (verified)  113 / 128
#   audit wide frame (refined)  76 /   90   audit narrow (refined) 81 / 111
#   L1 K40 n256 (verified)     308 /  348   L1 n2048 s41 (verif.) 305 / 396
#   L6 K10 n64 (unresolved: stopped at the budget)                487 / 552
# Worst measured / predicted over all 52 rows: 0.978.
#
# A run() holds up to two results at once and the worker copies the returned
# one out of the wasm heap and transfers it, so the budget adds 4 result
# arrays (8 * n_t * n_s bytes each) to the largest single-run peak. The
# refinement guard (_refine_stop) applies this same model before every
# further check, so no check run is started beyond the budget.
_MEM_SAFETY = 1.25
_MEM_COEF = {"slab": 4.24, "slab_if_sites": 2.93, "green": 1.73, "kernel": 1.70,
             "frames": 2.09, "const": 35.9}
_NODE_BYTES_PER_NODE2 = 16.04


def _single_peak_raw(counts, n_sites: int, L: int, K: int, n_t: int) -> float:
    """Unscaled model of ONE compute_psi call (see the table above)."""
    n_E = sum(counts)
    S = 16.0 * n_E * n_sites * L * L
    c = _MEM_COEF
    return (c["slab"] * S + c["slab_if_sites"] * S * (K > 0) + c["green"] * S * K
            + c["kernel"] * 16.0 * n_E * n_sites * L * K
            + c["frames"] * 8.0 * n_t * n_sites + c["const"] * 1e6
            + _NODE_BYTES_PER_NODE2 * sum(n * n for n in counts))


# ---------------------------------------------------------------------- #
# Errors                                                                 #
# ---------------------------------------------------------------------- #

class _BridgeError(Exception):
    def __init__(self, kind: str, field, message: str):
        super().__init__(message)
        self.kind = kind
        self.field = field
        self.message = message


def _invalid(field, message):
    return _BridgeError("invalid_input", field, message)


def _error_meta(kind, field, message) -> str:
    return json.dumps({"ok": False,
                       "error": {"kind": kind, "field": field, "message": message}})


# ---------------------------------------------------------------------- #
# Strict JSON                                                            #
# ---------------------------------------------------------------------- #

class _NonFinite:
    """What NaN / Infinity / -Infinity in the JSON text parse to."""

    def __init__(self, token: str):
        self.token = token


def _loads(text):
    if not isinstance(text, str):
        raise _invalid(None, "params must be a JSON text")
    try:
        return json.loads(text, parse_constant=_NonFinite)
    except (ValueError, RecursionError) as exc:
        raise _invalid(None, f"params are not valid JSON ({exc})")


def _describe(v) -> str:
    if isinstance(v, _NonFinite):
        return v.token
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return "text"
    if isinstance(v, list):
        return "a list"
    if isinstance(v, dict):
        return "an object"
    return repr(v)


# What the web form calls each field (web/src/form.ts). Messages lead with
# these; error.field keeps the params path, which the web maps to a slot.
_LABELS = {
    "L": "Channels L", "a": "Hoppings a", "N": "First site N", "M": "Last site M",
    "j_sites": "Potential sites", "V_sites": "Potential matrices V(j)",
    "interval": "Energy interval", "interval[0]": "Energy interval, lower end E_lo",
    "interval[1]": "Energy interval, upper end E_hi",
    "times": "Time settings", "times.t_min": "t start (t_min)", "times.t_max": "t end (t_max)",
    "times.n_t": "Frames (n_t)", "n_quad": "Quadrature nodes n_quad",
    "outer_sign": "Outer branch (outer_sign)", "threshold_buffer": "Threshold buffer",
    "amplitude": "Amplitude", "amplitude.mode": "Amplitude mode",
    "amplitude.E0": "Centre energy E₀", "amplitude.sigma_E": "Energy width σ_E",
    "amplitude.direction": "Direction", "amplitude.n_init": "Start site n_init",
}
_PART = {0: "real part", 1: "imaginary part"}


def _label(field) -> str:
    """User-facing name of a params path, e.g. times.n_t -> Frames (n_t)."""
    if field is None:
        return "Parameters"
    if field in _LABELS:
        return _LABELS[field]
    head, _, rest = field.partition("[")
    idx = [int(x) for x in rest.rstrip("]").split("][")] if rest else []
    if head == "a" and len(idx) == 1:
        return f"Hoppings a, entry {idx[0] + 1}"
    if head == "j_sites" and len(idx) == 1:
        return f"Potential sites, entry {idx[0] + 1}"
    if head == "V_sites" and idx:
        words = [f"matrix {idx[0] + 1}"]
        if len(idx) > 1:
            words.append(f"row {idx[1] + 1}")
        if len(idx) > 2:
            words.append(f"column {idx[2] + 1}")
        if len(idx) > 3:
            words.append(_PART.get(idx[3], f"entry {idx[3] + 1}"))
        return "Potential matrices V(j): " + ", ".join(words)
    return field


def _typed_label(field) -> str:
    """Label plus the params path when the label does not already show it."""
    label = _label(field)
    return label if field is None or field in label else f"{label} ({field})"


def _number(v, field) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _invalid(field, f"{_typed_label(field)} must be a finite number "
                              f"(got {_describe(v)})")
    try:
        x = float(v)
    except OverflowError:
        x = math.inf
    if not math.isfinite(x):
        raise _invalid(field, f"{_typed_label(field)} must be a finite number (got {v!r})")
    return x + 0.0    # folds -0.0 into 0.0


def _integer(v, field) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        got = repr(v) if isinstance(v, float) and math.isfinite(v) else _describe(v)
        raise _invalid(field, f"{_typed_label(field)} must be a whole number (got {got})")
    return int(v)


def _list(v, field, length=None) -> list:
    if not isinstance(v, list):
        raise _invalid(field, f"{_typed_label(field)} must be a list (got {_describe(v)})")
    if length is not None and len(v) != length:
        raise _invalid(field, f"{_typed_label(field)} must have {length} entries "
                              f"(got {len(v)})")
    return v


def _object(v, field, keys) -> dict:
    name = _typed_label(field) if field else "The parameters"
    if not isinstance(v, dict):
        raise _invalid(field, f"{name} must be an object (got {_describe(v)})")
    for k in keys:
        if k not in v:
            sub = f"{field}.{k}" if field else k
            raise _invalid(sub, f"{_typed_label(sub)} is missing")
    for k in v:
        if k not in keys:
            sub = f"{field}.{k}" if field else str(k)
            raise _invalid(sub, f"{sub} is not a known parameter")
    return v


# ---------------------------------------------------------------------- #
# Validation                                                             #
# ---------------------------------------------------------------------- #

_TOP_KEYS = ("L", "a", "N", "M", "j_sites", "V_sites", "interval", "times",
             "n_quad", "outer_sign", "threshold_buffer", "amplitude")


def _validate(raw) -> dict:
    """Strict checks on the parsed JSON; returns canonical params.

    Every check runs on the JSON values before any lossy coercion. Does not
    evaluate f (that needs quadrature nodes; see _check_amplitude).
    """
    p = _object(raw, None, _TOP_KEYS)

    L = _integer(p["L"], "L")
    if not 1 <= L <= MAX_L:
        raise _invalid("L", f"Channels L must be between 1 and {MAX_L} (got {L})")

    a_raw = _list(p["a"], "a")
    if len(a_raw) != L:
        raise _invalid("a", f"Hoppings a must have one entry per channel, L = {L} "
                            f"(got {len(a_raw)})")
    a = [_number(x, f"a[{i}]") for i, x in enumerate(a_raw)]
    for i, x in enumerate(a):
        if x <= 0:
            raise _invalid(f"a[{i}]", f"{_label(f'a[{i}]')} must be > 0 (got {x!r})")
    for i in range(L - 1):
        if a[i + 1] > a[i]:
            raise _invalid(f"a[{i + 1}]",
                           f"Hoppings a must be non-increasing (largest first): entry "
                           f"{i + 2} = {a[i + 1]!r} is larger than entry {i + 1} = {a[i]!r}")
    a_min = a[-1]

    N = _integer(p["N"], "N")
    M = _integer(p["M"], "M")
    for name, v in (("N", N), ("M", M)):
        if abs(v) > MAX_ABS_SITE:
            raise _invalid(name, f"{_label(name)} must lie in [-{MAX_ABS_SITE}, "
                                 f"{MAX_ABS_SITE}] (got {v})")
    if N >= M:
        raise _invalid("M", f"Last site M must be larger than first site N "
                            f"(got N = {N}, M = {M})")

    j_raw = _list(p["j_sites"], "j_sites")
    j_sites = [_integer(x, f"j_sites[{i}]") for i, x in enumerate(j_raw)]
    for i, j in enumerate(j_sites):
        if not N <= j <= M:
            raise _invalid(f"j_sites[{i}]",
                           f"{_label(f'j_sites[{i}]')} = {j} must lie in "
                           f"[N, M] = [{N}, {M}]")
        if i and j <= j_sites[i - 1]:
            raise _invalid(f"j_sites[{i}]",
                           f"Potential sites must be strictly increasing: entry {i + 1} "
                           f"= {j} follows {j_sites[i - 1]}")
    K = len(j_sites)

    V_raw = _list(p["V_sites"], "V_sites")
    if len(V_raw) != K:
        raise _invalid("V_sites",
                       f"Potential matrices V(j): need one {L}x{L} matrix per potential "
                       f"site (K = {K}), got {len(V_raw)}")
    V_sites = []
    for k, site in enumerate(V_raw):
        rows = _list(site, f"V_sites[{k}]", L)
        mat = []
        for r, row in enumerate(rows):
            entries = _list(row, f"V_sites[{k}][{r}]", L)
            out_row = []
            for c, pair in enumerate(entries):
                fld = f"V_sites[{k}][{r}][{c}]"
                pair = _list(pair, fld, 2)
                out_row.append([_number(pair[0], fld + "[0]"),
                                _number(pair[1], fld + "[1]")])
            mat.append(out_row)
        Vk = np.array([[complex(re, im) for re, im in row] for row in mat])
        asym = float(np.max(np.abs(Vk - Vk.conj().T)))
        if not asym <= HERMITIAN_ATOL:
            raise _invalid(f"V_sites[{k}]",
                           f"Potential matrices V(j): matrix {k + 1} (V_sites[{k}], site "
                           f"j = {j_sites[k]}) must be Hermitian, equal to its conjugate "
                           f"transpose (largest |V - V^H| entry is {asym:.3g}; allowed "
                           f"{HERMITIAN_ATOL:g}); the potential has to be self-adjoint")
        V_sites.append(mat)

    buf = _number(p["threshold_buffer"], "threshold_buffer")
    if not 0 < buf < 2 * a_min:
        raise _invalid("threshold_buffer",
                       f"Threshold buffer must lie strictly between 0 and 2 min(a) = "
                       f"{2 * a_min!r} (got {buf!r})")

    iv = _list(p["interval"], "interval", 2)
    lo = _number(iv[0], "interval[0]")
    hi = _number(iv[1], "interval[1]")
    if lo >= hi:
        raise _invalid("interval", f"Energy interval must have E_lo < E_hi "
                                   f"(got [{lo!r}, {hi!r}])")
    edge = 2 * a_min - buf
    if lo < -edge or hi > edge:
        raise _invalid("interval",
                       f"Energy interval [{lo!r}, {hi!r}] must lie inside the common open "
                       f"band [{-edge!r}, {edge!r}] (2 min(a) - threshold buffer, min(a) "
                       f"= {a_min!r}); outside it some channels are closed")

    tm = _object(p["times"], "times", ("t_min", "t_max", "n_t"))
    t_min = _number(tm["t_min"], "times.t_min")
    t_max = _number(tm["t_max"], "times.t_max")
    n_t = _integer(tm["n_t"], "times.n_t")
    if t_min >= t_max:
        raise _invalid("times.t_max",
                       f"t end (t_max) must be later than t start (got t_min = {t_min!r}, "
                       f"t_max = {t_max!r})")
    if not 2 <= n_t <= MAX_N_T:
        raise _invalid("times.n_t", f"Frames (n_t) must be between 2 and {MAX_N_T} "
                                    f"(got {n_t})")

    n_quad = _integer(p["n_quad"], "n_quad")
    if not MIN_N_QUAD <= n_quad <= MAX_QUAD_NODES:
        raise _invalid("n_quad",
                       f"Quadrature nodes n_quad must be between {MIN_N_QUAD} and "
                       f"{MAX_QUAD_NODES} (got {n_quad})")

    outer = p["outer_sign"]
    if isinstance(outer, bool) or not isinstance(outer, int) or outer not in (1, -1):
        raise _invalid("outer_sign", f"Outer branch (outer_sign) must be 1 or -1 "
                                     f"(got {_describe(outer)})")

    amp_raw = p["amplitude"]
    if not isinstance(amp_raw, dict):
        raise _invalid("amplitude", f"Amplitude must be an object (got {_describe(amp_raw)})")
    mode = amp_raw.get("mode")
    if mode == "gaussian":
        amp = _object(amp_raw, "amplitude",
                      ("mode", "E0", "sigma_E", "direction", "n_init"))
        E0 = _number(amp["E0"], "amplitude.E0")
        sigma_E = _number(amp["sigma_E"], "amplitude.sigma_E")
        if sigma_E <= 0:
            raise _invalid("amplitude.sigma_E",
                           f"Energy width σ_E must be > 0 (got {sigma_E!r})")
        direction = amp["direction"]
        if not isinstance(direction, str) or direction not in DIRECTION_WEIGHTS:
            raise _invalid("amplitude.direction",
                           "Direction must be one of " + ", ".join(DIRECTION_WEIGHTS)
                           + f" (got {_describe(direction)})")
        n_init = _integer(amp["n_init"], "amplitude.n_init")
        if not N <= n_init <= M:
            raise _invalid("amplitude.n_init",
                           f"Start site n_init = {n_init} must lie in [N, M] = [{N}, {M}]")
        amplitude = {"mode": "gaussian", "E0": E0, "sigma_E": sigma_E,
                     "direction": direction, "n_init": n_init}
    elif mode == "schober_window":
        _object(amp_raw, "amplitude", ("mode",))
        if L != 2:
            raise _invalid("L", f"Channels L must be 2 for the Schober window amplitude "
                                f"(got L = {L})")
        for i, (s_lo, s_hi) in enumerate(SCHOBER_E_SEGMENTS):
            if s_lo < -edge or s_hi > edge:
                raise _invalid("a",
                               f"Hoppings a are too small for the Schober window: "
                               f"[{s_lo}, {s_hi}] must lie inside the common open band "
                               f"[{-edge!r}, {edge!r}]; increase a")
        amplitude = {"mode": "schober_window"}
    else:
        raise _invalid("amplitude.mode",
                       "Amplitude mode must be gaussian or schober_window "
                       f"(got {_describe(mode)})")

    return {
        "L": L, "a": a, "N": N, "M": M, "j_sites": j_sites, "V_sites": V_sites,
        "interval": [lo, hi],
        "times": {"t_min": t_min, "t_max": t_max, "n_t": n_t},
        "n_quad": n_quad, "outer_sign": int(outer), "threshold_buffer": buf,
        "amplitude": amplitude,
    }


def _config_key(params: dict) -> str:
    canon = json.dumps(params, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False)
    return hashlib.sha256((canon + "\n" + SOURCE_REVISION).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------- #
# Quadrature bookkeeping (node counts only -- no physics)                #
# ---------------------------------------------------------------------- #

def _segments(params):
    if params["amplitude"]["mode"] == "schober_window":
        return safe_open_band_segments(params["a"][-1], SCHOBER_E_SEGMENTS,
                                       params["threshold_buffer"])
    return None


def _segment_counts(params, n_quad: int) -> list[int]:
    """Gauss-Legendre nodes per segment, exactly as compute_psi allocates them."""
    segs = _segments(params)
    if segs is None:
        return [int(n_quad)]
    lengths = np.array([hi - lo for lo, hi in sorted(segs)])
    return [int(n) for n in _allocate_nodes(lengths, n_quad)]


def _node_bytes(counts) -> int:
    """Modelled peak of generating the nodes alone (numpy leggauss + LAPACK copy)."""
    return int(math.ceil(_MEM_SAFETY * _NODE_BYTES_PER_NODE2 * sum(n * n for n in counts)))


def _single_peak(params, n_quad: int) -> int:
    """Modelled peak bytes of one compute_psi call at n_quad, safety included."""
    raw = _single_peak_raw(_segment_counts(params, n_quad), params["M"] - params["N"] + 1,
                           params["L"], len(params["j_sites"]), params["times"]["n_t"])
    return int(math.ceil(_MEM_SAFETY * raw))


def _result_bytes(params) -> int:
    return 8 * params["times"]["n_t"] * (params["M"] - params["N"] + 1)


def _plan_bytes(params, n_quad: int, check: bool) -> int:
    """Peak of a run at n_quad (+ its 2x check), plus held and copied results."""
    peak = _single_peak(params, 2 * n_quad if check else n_quad)
    return peak + 4 * _result_bytes(params)


def _max_n_quad(params, check: bool = True):
    """Largest n_quad whose plan (with its 2x check if check) fits both limits.

    None if even MIN_N_QUAD does not fit. The plan grows with n_quad, so a
    binary search finds the edge.
    """
    hi = MAX_QUAD_NODES // 2 if check else MAX_QUAD_NODES
    if _plan_bytes(params, MIN_N_QUAD, check) > MAX_PEAK_BYTES:
        return None
    lo = MIN_N_QUAD
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _plan_bytes(params, mid, check) <= MAX_PEAK_BYTES:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _check_budget(params, n_quad: int, check: bool) -> int:
    n_t = params["times"]["n_t"]
    n_sites = params["M"] - params["N"] + 1
    if n_t * n_sites > MAX_RESULT_VALUES:
        raise _BridgeError(
            "over_budget", "times.n_t",
            f"Frames (n_t) x sites is too large: the result would hold "
            f"{n_t * n_sites:,} values (n_t = {n_t} times x {n_sites} sites); the limit "
            f"is {MAX_RESULT_VALUES:,}. Reduce n_t or the N..M range.")
    if check and 2 * n_quad > MAX_QUAD_NODES:
        best = _max_n_quad(params)
        raise _BridgeError(
            "over_budget", "n_quad",
            f"Quadrature nodes n_quad = {n_quad} cannot be verified: the convergence "
            f"check runs at 2 x n_quad = {2 * n_quad} nodes, above the "
            f"{MAX_QUAD_NODES}-node limit. "
            + (f"Use n_quad <= {best} (the largest whose check also fits the memory "
               f"limit here)." if best else
               "Narrow the N..M range or use fewer channels L."))
    need = _plan_bytes(params, n_quad, check)
    if need > MAX_PEAK_BYTES:
        best = _max_n_quad(params, check)
        if best is not None and best < n_quad:
            advice = (f"Reduce n_quad to at most {best}, or narrow the N..M range "
                      f"(memory grows with nodes x sites x L^2 x potential sites, plus "
                      f"about {_MEM_SAFETY * _NODE_BYTES_PER_NODE2:.0f} bytes x nodes^2 "
                      f"to generate the nodes).")
            field = "n_quad"
        else:
            advice = "Narrow the N..M range, or use fewer channels L or potential sites."
            field = "M"
        raise _BridgeError(
            "over_budget", field,
            f"This run would need about {need / 1e6:,.0f} MB (estimated, including the "
            f"2x convergence check); the limit is {MAX_PEAK_BYTES / 1e6:,.0f} MB. {advice}")
    return need


# ---------------------------------------------------------------------- #
# Public API                                                             #
# ---------------------------------------------------------------------- #

def _limits() -> dict:
    return {"bytes_peak": MAX_PEAK_BYTES, "result_values": MAX_RESULT_VALUES,
            "max_quad_nodes": MAX_QUAD_NODES, "tolerance": TOLERANCE}


def presets_json() -> str:
    """[{"id", "name", "description", "params"[, "form_gaussian"]}] in desktop order.

    Window presets (amplitude mode schober_window) also carry
    "form_gaussian": the Gaussian amplitude the desktop shows, disabled, in
    its form for them (E0 0.5, sigma_E 0.1, balanced, n_init 0), so the web
    can fill its Gaussian fields deterministically. It is not part of the
    preset's physics.
    """
    out = []
    for name, params in PRESETS.items():
        item = {"id": PRESET_IDS[name], "name": name,
                "description": WEB_DESCRIPTIONS.get(name, ""), "params": params}
        if params["amplitude"]["mode"] == "schober_window":
            item["form_gaussian"] = dict(WINDOW_FORM_GAUSSIAN)
        out.append(item)
    return json.dumps(out, ensure_ascii=False)


def estimate_json(params_json) -> str:
    """Memory estimate for run() without computing anything."""
    try:
        params = _validate(_loads(params_json))
        out = {"ok": True, "bytes_peak": _plan_bytes(params, params["n_quad"], True),
               "bytes_result": _result_bytes(params), "limits": _limits()}
        try:
            _check_budget(params, params["n_quad"], True)
        except _BridgeError as exc:
            out["ok"] = False
            out["error"] = {"kind": exc.kind, "field": exc.field, "message": exc.message}
        return json.dumps(out)
    except _BridgeError as exc:
        return json.dumps({"ok": False, "bytes_peak": 0, "bytes_result": 0,
                           "limits": _limits(),
                           "error": {"kind": exc.kind, "field": exc.field,
                                     "message": exc.message}})
    except Exception as exc:  # noqa: BLE001 -- never raise to the caller
        return json.dumps({"ok": False, "bytes_peak": 0, "bytes_result": 0,
                           "limits": _limits(),
                           "error": {"kind": "internal", "field": None,
                                     "message": f"Internal error while estimating: "
                                                f"{type(exc).__name__}: {exc}"}})


def validation_record(meta: dict) -> dict:
    """The cache record for a successful run's meta (what presetValidation holds)."""
    q = meta["quadrature"]
    return {"source_revision": meta["source_revision"],
            "requested_n_quad": q["requested_n_quad"], "used_n_quad": q["used_n_quad"],
            "check_n_quad": q["check_n_quad"],
            "discrepancy_rel_peak": q["discrepancy_rel_peak"],
            "tolerance": q["tolerance"], "status": q["status"]}


def _stage(on_stage, stage, detail=""):
    if on_stage is None:
        return
    try:
        on_stage(stage, detail)
    except Exception:  # noqa: BLE001 -- a broken progress callback must not kill the run
        pass


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_real(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _record_consistent(rec, params) -> bool:
    """A record is only trusted if it could have come from this policy.

    It must be for the requested n_quad, the used count must be requested x
    2^k within MAX_REFINE_FACTOR, the check must be at twice the used count
    and within the node limit, and its stored discrepancy must meet the
    tolerance this build enforces (not just the tolerance it claims).
    """
    if not all(_is_int(rec.get(k)) for k in ("requested_n_quad", "used_n_quad",
                                             "check_n_quad")):
        return False
    req, used, chk = rec["requested_n_quad"], rec["used_n_quad"], rec["check_n_quad"]
    if req != params["n_quad"] or used < req or used % req:
        return False
    factor = used // req
    if factor & (factor - 1) or factor > MAX_REFINE_FACTOR:
        return False                        # not a power of two within the cap
    if chk != 2 * used or chk > MAX_QUAD_NODES:
        return False
    tol, disc = rec.get("tolerance"), rec.get("discrepancy_rel_peak")
    if not (_is_real(tol) and _is_real(disc)):
        return False
    if not (0 < tol <= TOLERANCE and 0 <= disc <= tol):
        return False
    status = rec.get("status")
    if status == "verified":
        return used == req
    if status == "refined":
        return used > req
    return status == "cached"


def _cached_record(cached_validation_json, key, params, warnings):
    if cached_validation_json is None:
        return None
    try:
        cache = json.loads(cached_validation_json)
    except (TypeError, ValueError):
        warnings.append("The cached validation data could not be read, so the "
                        "convergence check was run again.")
        return None
    if not isinstance(cache, dict):
        warnings.append("The cached validation data was not an object, so the "
                        "convergence check was run again.")
        return None
    rec = cache.get(key)
    if rec is None:
        return None
    try:
        ok = (isinstance(rec, dict)
              and rec.get("source_revision") == SOURCE_REVISION
              and _record_consistent(rec, params))
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        if isinstance(rec, dict) and rec.get("source_revision") != SOURCE_REVISION:
            return None     # stale build: silently recompute
        warnings.append("A cached validation record for this configuration was "
                        "malformed, so the convergence check was run again.")
        return None
    return rec


def _compute(params, n_quad):
    p = dict(params)
    p["n_quad"] = n_quad
    spec = build_spec(p)
    spec.validate()
    psi = compute_psi(spec)
    if not np.all(np.isfinite(psi)):
        raise _BridgeError(
            "nonfinite", None,
            f"The computation produced non-finite values (NaN or infinity) at "
            f"n_quad = {n_quad}. This input is outside what the algorithm can "
            f"evaluate reliably; try a smaller time range or lattice.")
    return psi


def _discrepancy(psi_a, psi_b) -> float:
    scale = float(np.max(np.abs(psi_b)))
    if scale == 0.0:
        return math.inf
    return float(np.max(np.abs(psi_a - psi_b))) / scale


def _check_amplitude(params):
    """Reject f that is essentially zero on the requested run's nodes."""
    spec = build_spec(params)
    segs = _segments(params)
    if segs is None:
        lo, hi = safe_open_band_interval(float(spec.a[-1]), spec.interval,
                                         spec.threshold_buffer)
        nodes, _ = gauss_legendre(lo, hi, spec.n_quad)
    else:
        nodes, _ = gauss_legendre_segments(segs, spec.n_quad)
    f_max = float(np.max(np.abs(spec.evaluate_f(nodes))))
    if not f_max >= ZERO_AMPLITUDE:
        amp = params["amplitude"]
        lo, hi = params["interval"]
        if amp["mode"] == "gaussian" and lo <= amp["E0"] <= hi:
            raise _invalid("n_quad",
                           f"Quadrature nodes n_quad = {params['n_quad']} miss the wave "
                           f"packet: the largest |f| on the nodes is {f_max:.3g} although "
                           f"E₀ lies inside the interval, so the packet is narrower than "
                           f"the node spacing. Raise n_quad or widen σ_E.")
        if amp["mode"] == "gaussian":
            raise _invalid("amplitude.E0",
                           f"Centre energy E₀: the wave-packet amplitude is essentially "
                           f"zero on the energy interval (largest |f| on the quadrature "
                           f"nodes is {f_max:.3g}). Move E0 inside the interval or widen "
                           f"σ_E.")
        raise _invalid("amplitude",
                       f"Amplitude: the wave-packet amplitude is essentially zero on the "
                       f"energy interval (largest |f| on the quadrature nodes is "
                       f"{f_max:.3g}).")
    spec.validate()   # MaxwellSpec's own checks are the last word


def _refine_stop(params, requested: int, check_n: int):
    """Why the next refinement step (check_n vs 2 check_n) may not run, or None.

    Returns (cause, reason) with cause "refine_cap", "node_cap" or "budget".
    The memory test is the same _plan_bytes model _check_budget applies, so
    no refinement step runs beyond the budget.
    """
    nxt = 2 * check_n
    if nxt > requested * MAX_REFINE_FACTOR:
        return ("refine_cap", f"refinement stops at {MAX_REFINE_FACTOR} x the requested "
                              f"n_quad ({requested * MAX_REFINE_FACTOR} nodes)")
    if nxt > MAX_QUAD_NODES:
        return ("node_cap", f"the next check would need {nxt} nodes, above the "
                            f"{MAX_QUAD_NODES}-node limit")
    need = _plan_bytes(params, check_n, True)
    if need > MAX_PEAK_BYTES:
        return ("budget", f"the next check at {nxt} nodes would need about "
                          f"{need / 1e6:,.0f} MB, over the {MAX_PEAK_BYTES / 1e6:,.0f} MB "
                          f"memory limit")
    return None


def _unresolved_message(params, requested, checks, cause, reason) -> str:
    tried = "; ".join(f"{c['n_quad']} vs {c['check_n_quad']} nodes: "
                      f"{c['discrepancy_rel_peak']:.2e}" for c in checks)
    head = (f"Quadrature nodes n_quad = {requested}: the result did not converge to the "
            f"tolerance {TOLERANCE:g} (relative to the peak). Measured differences: "
            f"{tried}. Could not refine further: {reason}. ")
    narrow = ("narrow the N..M range, shorten the time range (t start..t end), or "
              "use fewer frames (n_t)")
    gauss = params["amplitude"]["mode"] == "gaussian"
    packet = (" A larger σ_E or a narrower energy interval also needs fewer nodes."
              if gauss else "")
    if cause == "budget":
        return (head + f"More nodes do not fit in memory for this frame: {narrow}."
                + packet)
    best = _max_n_quad(params)
    last = checks[-1]["check_n_quad"]
    if best is not None and best > requested:
        start = min(best, last)
        return (head + f"Start from a larger n_quad: {start} or more (at most {best}, "
                f"the largest whose 2x check fits the {MAX_QUAD_NODES}-node and "
                f"{MAX_PEAK_BYTES / 1e6:,.0f} MB limits for this frame). If that is "
                f"still not enough, {narrow}." + packet)
    return (head + f"n_quad is already at the largest value this frame allows, so "
            f"{narrow}." + packet)


def run(params_json, cached_validation_json, on_stage):
    """Validate, budget, compute, check convergence. Returns (meta_json, psi|None)."""
    try:
        return _run(params_json, cached_validation_json, on_stage)
    except _BridgeError as exc:
        return _error_meta(exc.kind, exc.field, exc.message), None
    except MemoryError:
        return _error_meta("over_budget", None,
                           "The computation ran out of memory. Reduce n_quad, the N..M "
                           "range or n_t."), None
    except Exception as exc:  # noqa: BLE001 -- never raise to the caller
        return _error_meta("internal", None,
                           f"Internal error: {type(exc).__name__}: {exc}"), None


def _run(params_json, cached_validation_json, on_stage):
    timing = {"validate": 0.0, "compute": 0.0, "check": 0.0}
    warnings: list[str] = []
    t0 = time.perf_counter()
    _stage(on_stage, "validating", "Checking the parameters")
    params = _validate(_loads(params_json))
    key = _config_key(params)
    requested = params["n_quad"]
    rec = _cached_record(cached_validation_json, key, params, warnings)
    if rec is not None:
        mem = _check_budget(params, rec["used_n_quad"], check=False)
    else:
        mem = _check_budget(params, requested, check=True)
    try:
        _check_amplitude(params)
    except ValueError as exc:     # MaxwellSpec.validate()
        raise _invalid(None, str(exc))
    timing["validate"] = (time.perf_counter() - t0) * 1e3

    checks = []
    if rec is not None:
        used = rec["used_n_quad"]
        _stage(on_stage, "computing",
               f"Computing with {used} quadrature nodes (convergence already verified "
               f"for this configuration)")
        t1 = time.perf_counter()
        psi = _compute(params, used)
        timing["compute"] = (time.perf_counter() - t1) * 1e3
        status, check_n, disc = "cached", rec["check_n_quad"], float(rec["discrepancy_rel_peak"])
        tol = TOLERANCE    # the stored discrepancy is reported against this build's tolerance
    else:
        n = requested
        _stage(on_stage, "computing", f"Computing with {n} quadrature nodes")
        t1 = time.perf_counter()
        psi = _compute(params, n)
        timing["compute"] = (time.perf_counter() - t1) * 1e3
        t2 = time.perf_counter()
        _stage(on_stage, "checking", f"Checking convergence with {2 * n} nodes")
        psi_check = _compute(params, 2 * n)
        disc = _discrepancy(psi, psi_check)
        checks.append({"n_quad": n, "check_n_quad": 2 * n, "discrepancy_rel_peak": disc})
        status, used, check_n = "verified", n, 2 * n
        while disc > TOLERANCE:
            nxt = 2 * check_n
            stop = _refine_stop(params, requested, check_n)
            if stop is not None:
                raise _BridgeError("unresolved", "n_quad",
                                   _unresolved_message(params, requested, checks, *stop))
            _stage(on_stage, "refining",
                   f"{used} vs {check_n} nodes differed by {disc:.2e} of the peak; "
                   f"checking {check_n} against {nxt} nodes")
            psi, used = psi_check, check_n
            psi_check = _compute(params, nxt)
            check_n = nxt
            disc = _discrepancy(psi, psi_check)
            checks.append({"n_quad": used, "check_n_quad": nxt, "discrepancy_rel_peak": disc})
            status = "refined"
        del psi_check
        timing["check"] = (time.perf_counter() - t2) * 1e3
        tol = TOLERANCE
        if status == "refined":
            warnings.append(
                f"The requested n_quad = {requested} was not accurate enough (its 2x check "
                f"differed by {checks[0]['discrepancy_rel_peak']:.2e} of the peak). The "
                f"result shown uses n_quad = {used}, which agreed with {check_n} nodes to "
                f"{disc:.2e}.")

    psi = np.ascontiguousarray(psi, dtype=np.float64)
    mass = psi.sum(axis=1)
    i_min = int(np.argmin(mass))
    times = np.linspace(params["times"]["t_min"], params["times"]["t_max"],
                        params["times"]["n_t"])
    if mass[i_min] < 0.98:
        warnings.append(
            f"At t = {times[i_min]:.4g} only {100 * mass[i_min]:.1f}% of the packet is "
            f"inside the frame [{params['N']}, {params['M']}]; the rest has left the "
            f"window (it is not lost). Widen N and M to follow it.")

    segs = _segments(params)
    lo, hi = safe_open_band_interval(params["a"][-1], tuple(params["interval"]),
                                     params["threshold_buffer"])
    meta = {
        "ok": True,
        "shape": [int(psi.shape[0]), int(psi.shape[1])],
        "dtype": "float64",
        "sites": {"N": params["N"], "M": params["M"]},
        "times": dict(params["times"]),
        "mass_in_frame": [float(x) for x in mass],
        "quadrature": {
            "rule": "gauss-legendre",
            "requested_n_quad": requested,
            "used_n_quad": used,
            "check_n_quad": check_n,
            "discrepancy_rel_peak": disc,
            "tolerance": tol,
            "status": status,
            "segments": None if segs is None else [[s_lo, s_hi] for s_lo, s_hi in segs],
            "interval_used": [lo, hi],
            "threshold_buffer": params["threshold_buffer"],
            "checks": checks,
        },
        "timing_ms": {k: round(v, 3) for k, v in timing.items()},
        "memory_estimate_bytes": mem,
        "source_revision": SOURCE_REVISION,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "config_key": key,
        "warnings": warnings,
    }
    meta_json = json.dumps(meta, allow_nan=False)
    _stage(on_stage, "done", status)
    return meta_json, psi
