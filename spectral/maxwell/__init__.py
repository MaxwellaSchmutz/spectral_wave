"""Schober's matrix-valued lattice scattering algorithm.

README.md's step table maps the ten steps to the modules here.

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
