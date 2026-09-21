"""GUI adapter: turn a MaxwellSpec into the frame list the viewer animates.

The only bridge between the algorithm and gui/. Nothing here does physics --
compute_psi does that; this reshapes the result and reports coarse progress.
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
    """Compute psi(n, t) and return (frames, global_max).

    This is what MaxwellWorker.finished carries (gui/main_window.py).
    frames[t] is a one-element list holding psi at time t -- a row view into
    the single (n_t, n_sites) array, not a copy. The one-element nesting is
    the shape MainWindow's plotting code expects; x values come from
    spec.lattice(), which the GUI stores separately as self.lattice.

    psi is already a non-negative density, so global_max needs no abs().

    progress_callback, if given, receives 5 / 95 / 100 -- coarse enough that
    the GUI's progress bar is effectively a three-state indicator. Threading
    real progress would mean reaching into compute_psi's energy loop.
    """
    if progress_callback is not None:
        progress_callback(5)

    psi = compute_psi(spec)                          # (n_t, n_sites)

    if progress_callback is not None:
        progress_callback(95)

    global_max = float(np.max(psi)) if psi.size else 0.0
    frames = [[psi[t]] for t in range(psi.shape[0])]

    if progress_callback is not None:
        progress_callback(100)
    return frames, global_max
