"""The shipped preset library, shared by the desktop viewer and the web bridge.

Single source of truth for the thirteen presets: their parameter values, the
Gaussian amplitude f the form fields describe, and Schober's fixed window f
with its per-window quadrature segments. Pure Python + NumPy (no Qt), so the
browser build can import it.

Each preset is a canonical params dict (the JSON shape spectral/browser.py
validates):

    L, a, N, M, j_sites, V_sites, interval, times{t_min, t_max, n_t}, n_quad,
    outer_sign, threshold_buffer, amplitude

V_sites is a K x L x L nest of [re, im] pairs. amplitude is either
{"mode": "gaussian", "E0", "sigma_E", "direction", "n_init"} or
{"mode": "schober_window"}.

build_spec(params) turns one into a MaxwellSpec exactly as the desktop's
_build_spec does (same dtypes, same f, same E_segments), so both front ends
compute bit-identical psi from the same preset. Nothing here does physics --
compute_psi does that.

Desktop equivalence means bit-identical psi, not bit-identical V. The desktop
parses its V text with Python, where "-0.25j" is -(0.25j) = (-0.0 - 0.25j):
the real part is a NEGATIVE zero. JSON [re, im] pairs do not carry that sign
(spectral/browser.py folds -0.0 into 0.0), so the web's V has +0.0 where the
desktop's has -0.0. psi is still bit-identical for all 13 presets x both
outer signs (checked against the desktop at 47299cf in separate processes).
"""

from __future__ import annotations

import numpy as np

from .model import DEFAULT_THRESHOLD_BUFFER, MaxwellSpec


# Gaussian direction -> (h_plus, h_minus) weights on the two sigma entries of f.
# right (1,0) and left (0,1) select one wave-vector sign; balanced (1,1) takes
# both, which splits the packet into two halves moving apart.
DIRECTION_WEIGHTS: dict[str, tuple[float, float]] = {
    "right":    (1.0, 0.0),
    "left":     (0.0, 1.0),
    "balanced": (1.0, 1.0),
}


# Schober's window f is supported exactly on these two energy windows; passing
# them as MaxwellSpec.E_segments runs one Gauss-Legendre rule per window
# (spectrally convergent for a step-function f).
SCHOBER_E_SEGMENTS: list[tuple[float, float]] = [(-0.7, -0.5), (0.4, 0.6)]


def gaussian_f(L, a0, E0, sigma_E, h_plus, h_minus, n_init):
    """The desktop form's Gaussian amplitude f(E) -> (n_E, L, 2).

    Channel 0 only (every other channel stays zero). h_plus / h_minus scale
    the sigma = + / - entries, and the phase e^{+/- i n_init theta},
    theta = arccos(E / (2 a0)), parks the packet at lattice site n_init at t=0.
    """
    def f(E):
        E = np.asarray(E, dtype=float)
        env = np.exp(-((E - E0) ** 2) / (2.0 * sigma_E ** 2))
        theta = np.arccos(np.clip(E / (2.0 * a0), -1.0, 1.0))
        out = np.zeros((E.size, L, 2), dtype=complex)
        out[:, 0, 0] = h_plus  * env * np.exp(+1j * n_init * theta)
        out[:, 0, 1] = h_minus * env * np.exp(-1j * n_init * theta)
        return out
    return f


def schober_window_f(E):
    """f_{1,+/-}=1 on [0.4,0.6]; f_{2,+}=1 on [-0.7,-0.5]; f_{2,-}=0. (L=2)"""
    E = np.asarray(E, dtype=float)
    out = np.zeros((E.size, 2, 2), dtype=complex)
    ch1 = (E >= 0.4) & (E <= 0.6)
    ch2 = (E >= -0.7) & (E <= -0.5)
    out[ch1, 0, 0] = 1.0   # f_{1,+}
    out[ch1, 0, 1] = 1.0   # f_{1,-}
    out[ch2, 1, 0] = 1.0   # f_{2,+}
    return out


def _v(*sites):
    """Real K x L x L potential -> [re, im] pair nest (im = 0)."""
    return [[[[float(x), 0.0] for x in row] for row in site] for site in sites]


def _gauss(E0, sigma_E, direction="right", n_init=0):
    return {"mode": "gaussian", "E0": float(E0), "sigma_E": float(sigma_E),
            "direction": direction, "n_init": int(n_init)}


def _preset(L, a, N, M, j_sites, V_sites, interval, t_min, t_max, n_t,
            n_quad, amplitude):
    return {
        "L": L, "a": [float(x) for x in a], "N": N, "M": M,
        "j_sites": list(j_sites), "V_sites": V_sites,
        "interval": [float(interval[0]), float(interval[1])],
        "times": {"t_min": float(t_min), "t_max": float(t_max), "n_t": n_t},
        "n_quad": n_quad,
        "outer_sign": 1,
        "threshold_buffer": DEFAULT_THRESHOLD_BUFFER,
        "amplitude": amplitude,
    }


# Desktop order and names (gui/main_window.py @ 47299cf); values identical.
PRESETS: dict[str, dict] = {
    "Free Gaussian Wave Packet": _preset(
        1, [1.0], -120, 120, [], _v(), (-1.5, 1.5), 0, 50, 120, 128,
        _gauss(0.0, 0.30)),
    "Single Barrier — partial reflection": _preset(
        1, [1.0], -100, 100, [0], _v([[0.6]]), (-1.5, 1.5), 0, 55, 140, 128,
        _gauss(0.0, 0.25)),
    "Single Well — attractive site": _preset(
        1, [1.0], -100, 100, [0], _v([[-0.8]]), (-1.5, 1.5), 0, 55, 140, 128,
        _gauss(0.0, 0.25)),
    "Double Barrier — resonant cavity": _preset(
        1, [1.0], -130, 130, [-6, 6], _v([[0.55]], [[0.55]]), (-1.3, 1.3),
        0, 65, 160, 128, _gauss(0.0, 0.20)),
    "Strong Wall — near-total reflection": _preset(
        1, [1.0], -100, 100, [0], _v([[3.5]]), (-1.5, 1.5), 0, 50, 120, 128,
        _gauss(0.0, 0.30)),
    "Weak Barrier — small kick": _preset(
        1, [1.0], -100, 100, [0], _v([[0.12]]), (-1.5, 1.5), 0, 50, 120, 128,
        _gauss(0.0, 0.30)),
    "Wide Barrier — tunneling": _preset(
        1, [1.0], -130, 130, [-3, -1, 1, 3],
        _v([[0.45]], [[0.45]], [[0.45]], [[0.45]]), (-1.5, 1.5),
        0, 55, 140, 144, _gauss(0.0, 0.20)),
    "Random Lattice (L=1)": _preset(
        1, [1.0], -130, 130, [-9, -4, 0, 5, 11],
        _v([[0.30]], [[-0.40]], [[0.55]], [[-0.20]], [[0.35]]), (-1.5, 1.5),
        0, 60, 160, 144, _gauss(0.0, 0.25)),
    "Two-Channel Free (L=2)": _preset(
        2, [1.0, 0.6], -100, 100, [], _v(), (-0.9, 0.9), 0, 60, 140, 128,
        _gauss(0.0, 0.20)),
    "Two-Channel Coupled Scatterer (L=2)": _preset(
        2, [1.0, 0.6], -100, 100, [0],
        [[[[0.40, 0.0], [0.0, 0.25]], [[0.0, -0.25], [-0.20, 0.0]]]],
        (-0.9, 0.9), 0, 60, 140, 128, _gauss(0.0, 0.20)),
    "Slow Packet — near band edge": _preset(
        1, [1.0], -80, 80, [], _v(), (-1.95, -1.40), 0, 80, 120, 80,
        _gauss(-1.65, 0.12)),
    "Schober 1 — two-channel window": _preset(
        2, [2.0, 1.0], -10, 10, [0], _v([[0, 1], [1, 0]]), (-0.7, 0.6),
        -8, 8, 160, 200, {"mode": "schober_window"}),
    "Schober 2 — two-channel + barrier": _preset(
        2, [2.0, 1.0], -100, 100, [0, 40],
        _v([[0, 1], [1, 0]], [[5, 0], [0, -3]]), (-0.7, 0.6),
        -40, 40, 200, 200, {"mode": "schober_window"}),
}


# Stable URL-safe ids, one per preset, in PRESETS order.
PRESET_IDS: dict[str, str] = {
    "Free Gaussian Wave Packet":            "free-gaussian",
    "Single Barrier — partial reflection":  "single-barrier",
    "Single Well — attractive site":        "single-well",
    "Double Barrier — resonant cavity":     "double-barrier",
    "Strong Wall — near-total reflection":  "strong-wall",
    "Weak Barrier — small kick":            "weak-barrier",
    "Wide Barrier — tunneling":             "wide-barrier",
    "Random Lattice (L=1)":                 "random-lattice",
    "Two-Channel Free (L=2)":               "two-channel-free",
    "Two-Channel Coupled Scatterer (L=2)":  "two-channel-coupled",
    "Slow Packet — near band edge":         "slow-packet",
    "Schober 1 — two-channel window":       "schober-1",
    "Schober 2 — two-channel + barrier":    "schober-2",
}


# The six Gaussian form values the desktop shows (disabled) on the window
# presets; they only take effect if the user edits a field and the preset
# flips to Custom. Not part of the window presets' physics.
WINDOW_FORM_GAUSSIAN: dict = _gauss(0.5, 0.1, "balanced", 0)


# Web UI text. Every number below was measured from compute_psi on the shipped
# preset with outer_sign +1 (the default), not taken from the desktop blurbs.
# "In view" is summed psi over the preset's own [N, M] frame. Transmitted /
# reflected fractions come from the same f and V on a +/-450 frame at
# n_quad 1024 (agrees with 2048 to 2e-13), read at the preset's t_max, when
# the potential sites hold < 1e-3 of the mass. "Branch" figures are
# max|psi(+1) - psi(-1)| / max psi(+1) on the shipped preset. With outer_sign
# -1 every Gaussian preset's packet moves right as a whole for t > 0.
WEB_DESCRIPTIONS: dict[str, str] = {
    "Free Gaussian Wave Packet":
        "No potential. The packet starts at site 0 and moves right at speed "
        "about 2 (its peak is at n = 99 by t = 50), keeping almost the same "
        "width. 99.996% of it is still in view at t = 50. Both branches give "
        "the same result.",
    "Single Barrier — partial reflection":
        "One site with V(0) = 0.6. The packet starts on the barrier and "
        "splits: 91.7% moves right and 8.3% is reflected left, both at speed "
        "about 2. Both parts leave the ±100 frame, so only 5% is in view at "
        "t = 55. The − branch differs by up to 27% of the peak.",
    "Single Well — attractive site":
        "One site with V(0) = −0.8. The packet starts on the well and splits: "
        "86.1% moves right and 13.9% is reflected left. Only 5% is still in "
        "view at t = 55. The − branch differs by up to 39% of the peak.",
    "Double Barrier — resonant cavity":
        "Two sites with V = 0.55 at j = −6 and 6. 60% of the packet starts "
        "between them; the cavity empties quickly (1% left inside at t = 13) "
        "rather than ringing. In the end 84.3% is transmitted and 15.7% "
        "reflected. The − branch differs by up to 33% of the peak.",
    "Strong Wall — near-total reflection":
        "One site with V(0) = 3.5. Most of the packet bounces back, but not "
        "all: 75.6% is reflected and 24.4% gets through. The − branch "
        "differs by up to 93% of the peak.",
    "Weak Barrier — small kick":
        "One site with V(0) = 0.12. 99.64% of the packet goes straight "
        "through; the reflected 0.36% is too faint to see on the linear "
        "colour scale. The − branch differs by only 1.4% of the peak.",
    "Wide Barrier — tunneling":
        "Four sites with V = 0.45 at j = −3, −1, 1, 3, spaced one empty site "
        "apart. At these energies the wave is not tunnelling: 57.7% is "
        "transmitted and 42.3% reflected. The ±130 frame keeps 99.6% in view. "
        "The − branch differs by up to 73% of the peak.",
    "Random Lattice (L=1)":
        "Five sites at j = −9, −4, 0, 5, 11 with V between −0.40 and 0.55. "
        "The packet mostly stays together: 90.8% leaves to the right as one "
        "main packet and 9.2% is reflected. The − branch differs by up to 23% "
        "of the peak.",
    "Two-Channel Free (L=2)":
        "Two channels with a = 1.0 and 0.6, no potential. The Gaussian fills "
        "channel 1 only, so a single packet moves right at speed about 2 and "
        "channel 2 stays empty. It leaves the ±100 frame: 0.25% is in view at "
        "t = 60.",
    "Two-Channel Coupled Scatterer (L=2)":
        "Channel-mixing potential V(0) = [[0.40, 0.25i], [−0.25i, −0.20]]. The "
        "packet starts in channel 1 on the scatterer: 93.8% ends up moving "
        "right and 6.2% left. About 5% is moved into channel 2, seen as small, "
        "slower packets (speed about 1.2, near n = ±71 at t = 60). The − branch "
        "differs by up to 21% of the peak.",
    "Slow Packet — near band edge":
        "No potential; energy centred at E₀ = −1.65, near the band edge −2. "
        "The packet moves right at about 1.12, 56% of the top speed, and "
        "spreads from 7.7 to 12.8 sites wide. Its front runs off the ±80 "
        "frame: 22% is in view at t = 80.",
    "Schober 1 — two-channel window":
        "Schober's test case: two channels (a = 2, 1) mixed by "
        "V(0) = [[0, 1], [1, 0]]. The amplitude is a fixed window: channel 1 "
        "on [0.4, 0.6] in both directions, channel 2 on [−0.7, −0.5] moving "
        "right only, integrated window by window. Time runs from −8 to 8. The "
        "±10 frame is small next to the packet's long tails, so only 19–25% "
        "of it is in view at any time. The − branch differs by up to 53% of "
        "the peak.",
    "Schober 2 — two-channel + barrier":
        "Schober 1's window amplitude and mixing site, plus a second site "
        "V(40) = [[5, 0], [0, −3]], on a ±100 frame with t from −40 to 40. The "
        "share in view rises from 34% at t = −40 to a peak of 88% at t ≈ −5 "
        "(86% at t = 0) and falls to 48% at t = 40. The − branch differs by up to 94% of the peak.",
}


def build_spec(params: dict) -> MaxwellSpec:
    """MaxwellSpec from a canonical params dict (not validated here).

    Mirrors the desktop _build_spec: same dtypes, np.linspace time grid, the
    Gaussian f on channel 0 or Schober's window f with its E_segments.
    Callers validate (spectral/browser.py does it strictly, then calls
    spec.validate() as the last word).
    """
    L = int(params["L"])
    a = np.array([float(x) for x in params["a"]], dtype=float)
    N = int(params["N"])
    M = int(params["M"])
    j_sites = np.array([int(j) for j in params["j_sites"]], dtype=int)
    V_raw = params["V_sites"]
    if len(V_raw) == 0:
        V_sites = np.zeros((0, L, L), dtype=complex)
    else:
        V_sites = np.array(
            [[[complex(float(re), float(im)) for re, im in row] for row in site]
             for site in V_raw],
            dtype=complex,
        )
    lo, hi = params["interval"]
    tm = params["times"]
    amp = params["amplitude"]
    if amp["mode"] == "schober_window":
        f = schober_window_f
        E_segments = list(SCHOBER_E_SEGMENTS)
    else:
        h_plus, h_minus = DIRECTION_WEIGHTS[amp["direction"]]
        f = gaussian_f(L, float(a[0]), float(amp["E0"]), float(amp["sigma_E"]),
                       h_plus, h_minus, int(amp["n_init"]))
        E_segments = None
    return MaxwellSpec(
        L=L, a=a, N=N, M=M,
        j_sites=j_sites, V_sites=V_sites,
        interval=(float(lo), float(hi)),
        f=f,
        times=np.linspace(float(tm["t_min"]), float(tm["t_max"]), int(tm["n_t"])),
        n_quad=int(params["n_quad"]),
        E_segments=E_segments,
        threshold_buffer=float(params["threshold_buffer"]),
        outer_sign=int(params["outer_sign"]),
    )
