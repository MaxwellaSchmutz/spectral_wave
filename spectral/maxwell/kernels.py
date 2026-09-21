"""Step 4 of the Maxwell algorithm, implemented verbatim.

    s(n, k, E) = diag(nu_l(E) * (z_l^{j_k - n} - z_l^{n - j_k}))_{l=1,...,L}

This is the propagator used by step 5's recursion in jost.py.
"""

from __future__ import annotations

import numpy as np

from .channels import density_of_states


def s_kernel_diag(
    Z: np.ndarray,
    a: np.ndarray,
    j_sites: np.ndarray,
    lattice: np.ndarray,
) -> np.ndarray:
    """Diagonal entries of s(n, k, E) per step 4.

        s(n, k, E)_{l,l} = nu_l(E) * (z_l^{j_k - n} - z_l^{n - j_k})

    Returns shape (n_E, n_sites, K, L) complex.
    """
    a = np.asarray(a, dtype=float).reshape(-1)
    j_sites = np.asarray(j_sites, dtype=int).reshape(-1)
    lattice = np.asarray(lattice, dtype=int).reshape(-1)

    nu = density_of_states(Z, a)                                  # (n_E, L), step 3
    exponent = (j_sites[None, :] - lattice[:, None]).astype(float)  # (n_sites, K)

    Zb = Z[:, None, None, :]                                       # (n_E, 1, 1, L)
    Eb = exponent[None, :, :, None]                                # (1, n_sites, K, 1)
    pos = Zb ** Eb
    neg = Zb ** (-Eb)
    nub = nu[:, None, None, :]                                     # (n_E, 1, 1, L)
    return nub * (pos - neg)
