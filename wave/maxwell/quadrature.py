"""Gauss-Legendre quadrature on a finite interval, with threshold-buffer guard."""

from __future__ import annotations

import numpy as np


def gauss_legendre(a: float, b: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (nodes, weights) for n-point Gauss-Legendre on [a, b]."""
    x, w = np.polynomial.legendre.leggauss(n)
    half = 0.5 * (b - a)
    mid = 0.5 * (b + a)
    nodes = mid + half * x
    weights = half * w
    return nodes, weights


def safe_open_band_interval(
    a_min: float,
    requested: tuple[float, float],
    buffer: float,
) -> tuple[float, float]:
    """Clip a requested interval inside the common open band [-2 a_min, 2 a_min]
    with a buffer to avoid the channel thresholds at +/- 2 a_l.
    """
    lo_safe = -2.0 * a_min + buffer
    hi_safe = +2.0 * a_min - buffer
    lo = max(requested[0], lo_safe)
    hi = min(requested[1], hi_safe)
    if lo >= hi:
        raise ValueError(
            f"Buffer {buffer} on top of band [-{2 * a_min}, {2 * a_min}] "
            f"leaves an empty interval after clipping {requested}."
        )
    return lo, hi
