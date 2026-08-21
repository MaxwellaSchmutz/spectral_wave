"""Schober's matrix-valued lattice scattering algorithm.

See docs/MaxwellAlgorithm.pdf for the ten steps; each is one module here.

    from spectral.maxwell import MaxwellSpec, compute_psi

    psi = compute_psi(spec)      # (n_times, n_sites) real, non-negative
"""

from .model import MaxwellSpec
from .evolve import compute_psi
from .adapter import maxwell_to_frames

__all__ = [
    "MaxwellSpec",
    "compute_psi",
    "maxwell_to_frames",
]
