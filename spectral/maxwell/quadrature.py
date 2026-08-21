"""Gauss-Legendre quadrature on a finite interval or a union of disjoint
segments, with threshold-buffer guards."""

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


def _allocate_nodes(lengths: np.ndarray, n_total: int) -> np.ndarray:
    """Distribute n_total nodes over segments, proportionally to length.

    Deterministic rule: every segment is guaranteed a floor of 16 nodes; the
    budget is apportioned proportionally to segment length with
    largest-remainder rounding (ties broken by lower segment index), and any
    segment falling below the floor is pinned at 16 with the rest of the
    budget re-apportioned among the others, so the counts sum to exactly
    ``n_total`` whenever ``n_total >= 16 * n_segments``. Below that, the
    budget is split as evenly as possible with a hard minimum of 4 nodes per
    segment (the total may then exceed ``n_total``).
    """
    n_seg = lengths.size
    if n_total < 16 * n_seg:
        base, extra = divmod(n_total, n_seg)
        counts = np.full(n_seg, base, dtype=int)
        counts[:extra] += 1
        return np.maximum(counts, 4)
    counts = np.zeros(n_seg, dtype=int)
    free = np.ones(n_seg, dtype=bool)
    budget = n_total
    while True:
        idx = np.flatnonzero(free)
        quota = budget * lengths[idx] / lengths[idx].sum()
        alloc = np.floor(quota).astype(int)
        leftover = budget - int(alloc.sum())
        order = np.lexsort((idx, alloc - quota))  # largest remainder first
        alloc[order[:leftover]] += 1
        deficient = alloc < 16
        if not deficient.any():
            counts[idx] = alloc
            return counts
        counts[idx[deficient]] = 16
        free[idx[deficient]] = False
        budget -= 16 * int(deficient.sum())


def gauss_legendre_segments(
    segments: list[tuple[float, float]],
    n_total: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Composite Gauss-Legendre rule over a union of disjoint segments.

    Distributes n_total nodes across the segments proportionally to segment
    length, with a floor of 16 nodes per segment (largest-remainder rounding,
    ties to the lower index, so the counts are deterministic and sum to
    exactly ``n_total`` when ``n_total >= 16 * len(segments)``; below that the
    budget is split as evenly as possible with a minimum of 4 per segment).
    Each segment gets its own Gauss-Legendre rule, so integrands that are
    smooth on every segment -- e.g. window-type f supported exactly on the
    segments -- converge spectrally instead of algebraically.

    Returns concatenated (nodes, weights) in ascending segment order.
    """
    if len(segments) == 0:
        raise ValueError("gauss_legendre_segments needs at least one segment")
    segs = sorted((float(lo), float(hi)) for lo, hi in segments)
    lengths = np.array([hi - lo for lo, hi in segs])
    if not np.all(lengths > 0):
        raise ValueError(f"all segments must satisfy lo < hi, got {segs}")
    counts = _allocate_nodes(lengths, n_total)
    nodes, weights = zip(
        *(gauss_legendre(lo, hi, int(n)) for (lo, hi), n in zip(segs, counts))
    )
    return np.concatenate(nodes), np.concatenate(weights)


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


def safe_open_band_segments(
    a_min: float,
    segments: list[tuple[float, float]],
    buffer: float,
) -> list[tuple[float, float]]:
    """Clip each segment inside the common open band [-2 a_min, 2 a_min]
    with a buffer to avoid the channel thresholds at +/- 2 a_l. Segments that
    become empty are dropped; if none survive, raise ValueError.
    """
    lo_safe = -2.0 * a_min + buffer
    hi_safe = +2.0 * a_min - buffer
    clipped = []
    for lo, hi in segments:
        lo_c = max(float(lo), lo_safe)
        hi_c = min(float(hi), hi_safe)
        if lo_c < hi_c:
            clipped.append((lo_c, hi_c))
    if not clipped:
        raise ValueError(
            f"Buffer {buffer} on top of band [-{2 * a_min}, {2 * a_min}] "
            f"leaves no non-empty segment after clipping {list(segments)}."
        )
    return clipped
