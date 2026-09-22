"""Native reference results for the browser parity tests.

    python web/scripts/native_reference.py

Runs every case through spectral.browser.run (the same bridge the worker
calls) under native CPython and writes web/tests/.ref/:

    <id>.json      the run's meta (ok or error)
    <id>.bin       psi as raw little-endian float64, row-major (n_t, n_sites);
                   absent when the run returned an error
    index.json     {"sourceRevision", "runtime", "cases": [{"id", "params",
                    "meta", "bin", "ok", "status" | "error_kind"}]}

Cases: all 13 presets x both outer signs; a free scalar packet; a scalar
barrier; a complex-Hermitian two-channel coupling (both signs); a Schober
window on a wider frame (both signs); and the two audit failure repros (wide
frame, narrow Gaussian), recording what the convergence policy returns.
No cache is passed, so every ok case ran its 2x check.
"""

from __future__ import annotations

import copy
import json
import platform
import shutil
import time

from _common import REPO_ROOT, WEB_DIR, source_revision, use_revision


def _gauss(E0, sigma_E, direction="right", n_init=0):
    return {"mode": "gaussian", "E0": E0, "sigma_E": sigma_E,
            "direction": direction, "n_init": n_init}


def cases() -> list[tuple[str, dict]]:
    from spectral.maxwell.presets import PRESET_IDS, PRESETS

    out = []
    for name, params in PRESETS.items():
        for sign in (1, -1):
            p = copy.deepcopy(params)
            p["outer_sign"] = sign
            out.append((f"preset-{PRESET_IDS[name]}-{'plus' if sign == 1 else 'minus'}", p))

    base = {"threshold_buffer": 0.001, "outer_sign": 1}
    out.append(("free-scalar", {
        **base, "L": 1, "a": [1.0], "N": -60, "M": 60, "j_sites": [], "V_sites": [],
        "interval": [-1.6, 1.6], "times": {"t_min": -5.0, "t_max": 20.0, "n_t": 51},
        "n_quad": 160, "amplitude": _gauss(0.5, 0.3, "right", -20)}))
    out.append(("scalar-barrier", {
        **base, "L": 1, "a": [1.0], "N": -80, "M": 80, "j_sites": [0],
        "V_sites": [[[[0.8, 0.0]]]],
        "interval": [-1.5, 1.5], "times": {"t_min": 0.0, "t_max": 30.0, "n_t": 61},
        "n_quad": 192, "amplitude": _gauss(0.0, 0.25, "right", -25)}))
    coupled = {
        **base, "L": 2, "a": [1.0, 0.7], "N": -70, "M": 70, "j_sites": [-1, 2],
        "V_sites": [
            [[[0.5, 0.0], [0.3, 0.2]], [[0.3, -0.2], [-0.4, 0.0]]],
            [[[0.2, 0.0], [0.0, -0.1]], [[0.0, 0.1], [0.3, 0.0]]],
        ],
        "interval": [-1.3, 1.3], "times": {"t_min": 0.0, "t_max": 25.0, "n_t": 51},
        "n_quad": 192, "amplitude": _gauss(0.2, 0.25, "balanced", 0)}
    for sign in (1, -1):
        p = copy.deepcopy(coupled)
        p["outer_sign"] = sign
        out.append((f"complex-two-channel-{'plus' if sign == 1 else 'minus'}", p))
    window = copy.deepcopy(PRESETS["Schober 1 — two-channel window"])
    window.update({"N": -60, "M": 60, "n_quad": 256})
    for sign in (1, -1):
        p = copy.deepcopy(window)
        p["outer_sign"] = sign
        out.append((f"schober-window-wide-{'plus' if sign == 1 else 'minus'}", p))

    # Audit finding 2: README's "widen N and M" advice at the default n_quad.
    wide = copy.deepcopy(PRESETS["Free Gaussian Wave Packet"])
    wide.update({"N": -400, "M": 400, "n_quad": 128})
    out.append(("audit-wide-frame", wide))
    # Audit finding 4: Weak Barrier with only sigma_E narrowed.
    narrow = copy.deepcopy(PRESETS["Weak Barrier — small kick"])
    narrow["amplitude"]["sigma_E"] = 0.02
    out.append(("audit-narrow-gaussian", narrow))
    return out


def main() -> int:
    t0 = time.perf_counter()
    revision = source_revision()
    use_revision(revision)
    import numpy as np
    import spectral.browser as browser

    ref = WEB_DIR / "tests" / ".ref"
    if ref.exists():
        shutil.rmtree(ref)
    ref.mkdir(parents=True)
    index = {"sourceRevision": revision,
             "runtime": {"python": platform.python_version(), "numpy": np.__version__},
             "cases": []}
    for cid, params in cases():
        meta_json, psi = browser.run(json.dumps(params), None, None)
        meta = json.loads(meta_json)
        (ref / f"{cid}.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        row = {"id": cid, "params": params, "meta": f"{cid}.json", "ok": meta["ok"]}
        if meta["ok"]:
            (ref / f"{cid}.bin").write_bytes(
                np.ascontiguousarray(psi, dtype="<f8").tobytes())
            row["bin"] = f"{cid}.bin"
            q = meta["quadrature"]
            row["status"] = q["status"]
            row["used_n_quad"] = q["used_n_quad"]
            desc = (f"{q['status']:8s} used {q['used_n_quad']:4d} vs {q['check_n_quad']:4d}: "
                    f"{q['discrepancy_rel_peak']:.2e}  shape {meta['shape']}")
        else:
            row["bin"] = None
            row["error_kind"] = meta["error"]["kind"]
            desc = f"{meta['error']['kind']}: {meta['error']['message'][:110]}"
        index["cases"].append(row)
        print(f"  {cid:42s} {desc}")
    (ref / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(index['cases'])} cases to "
          f"{ref.relative_to(REPO_ROOT).as_posix()} in {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
