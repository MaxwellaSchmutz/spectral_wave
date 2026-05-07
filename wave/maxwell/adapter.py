"""GUI adapter: render Maxwell-algorithm output in the same shape that
SpectralSystem.compute_frames produces, so MainWindow needs no changes
downstream.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np

from .evolve import compute_psi
from .model import MaxwellSpec


def maxwell_to_frames(
    spec: MaxwellSpec,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> tuple[list[list[np.ndarray]], float]:
    """Compute psi(n, t) and return (frames, global_max) compatible with
    ComputeWorker.finished signal in gui/main_window.py.

    Each frame is a single-curve list -- the absolute value of the wave
    packet density at lattice sites. The MainWindow plots curves with x =
    spec.lattice() in the GUI; pass that lattice as x_values when wiring.
    """
    if progress_callback is not None:
        progress_callback(5)

    psi = compute_psi(spec)                          # (n_t, n_sites)

    if progress_callback is not None:
        progress_callback(95)

    # GUI plots np.abs(...) of curves; psi is already non-negative.
    global_max = float(np.max(psi)) if psi.size else 0.0
    frames = [[psi[t]] for t in range(psi.shape[0])]

    if progress_callback is not None:
        progress_callback(100)
    return frames, global_max
