"""Step 8 of the Maxwell algorithm (Interpretation 2, per Schober A.1).

    w^{E,sigma}_{l,pm}(n) := z_l(E)^{-sigma n} e_l
                           - sum_{k=1}^K G^{E,pm}(n, k) V(j_k) z_l(E)^{-sigma j_k} e_l

Schober ("Interpretation 2 is correct, the formula was right as written"):
  * sigma is the SUMMED index (paired with f_{l,sigma} in step 10) and is the
    WAVE-VECTOR sign -- it drives the plane-wave exponent z_l^{-sigma n}. The two
    sigma values are the two generalized eigenvectors (E approached from above /
    below; A.9).
  * the lower +/- index is the FIXED outer/branch choice (spec.outer_sign); it
    selects ONE Green's-function branch G^{E,pm}, the same for both sigma.

l indexes the channel; the result is a vector in C^L for each (E, sigma, l, n).
"""

from __future__ import annotations

import numpy as np


def full_eigenfunctions(
    Z: np.ndarray,
    j_sites: np.ndarray,
    V_sites: np.ndarray,
    G_grid: np.ndarray,
    lattice: np.ndarray,
    outer_sign: int,
) -> np.ndarray:
    """Compute w^{E,sigma}_{l,outer}(n) for sigma in {+,-} (axis size 2).

    Parameters
    ----------
    Z          : (n_E, L)
    j_sites    : (K,)
    V_sites    : (K, L, L)
    G_grid     : (2, n_E, n_sites, K, L, L) -- both branch Green's functions
                 stacked along axis 0 as [branch=+, branch=-]. Only the branch
                 selected by ``outer_sign`` is used.
    lattice    : (n_sites,)
    outer_sign : +1 or -1 -- the fixed lower (+/-) index; selects the branch.

    Returns
    -------
    w : (2, n_E, L_channel, n_sites, L_component)
        axis 0 = summed sigma index [+, -]  (the wave-vector sign)
    """
    if outer_sign not in (+1, -1):
        raise ValueError("outer_sign must be +/- 1")
    if G_grid.ndim != 6 or G_grid.shape[0] != 2:
        raise ValueError(
            "G_grid must have shape (2, n_E, n_sites, K, L, L) -- "
            "stack the branch=+ and branch=- Green's functions along axis 0."
        )
    _, n_E, n_sites, K, L, _ = G_grid.shape
    n_arr = lattice.astype(float)
    j_arr = j_sites.astype(float)

    # Fixed branch beta = outer_sign selects ONE Green's function (sigma-independent).
    beta_idx = 0 if outer_sign == +1 else 1
    G_beta = G_grid[beta_idx]                                          # (n_E, n_sites, K, L, L)

    sigma_vals = np.array([+1.0, -1.0])                                # axis 0: [+, -]

    # Free part: free_diag[sigma, E, n, chan] = z_chan^{-sigma n}, embedded on the
    # component diagonal (component == channel for the free term).
    free_diag = Z[None, :, None, :] ** (
        -sigma_vals[:, None, None, None] * n_arr[None, None, :, None]
    )                                                                  # (2, n_E, n_sites, L_chan)
    free_part = np.zeros((2, n_E, n_sites, L, L), dtype=complex)        # (.., comp, chan)
    idx = np.arange(L)
    free_part[:, :, :, idx, idx] = free_diag

    # Correction: sum_k G_beta(n, j_k) [V(j_k) z_chan^{-sigma j_k} e_chan].
    #   Z_at_j[sigma, E, k, chan]         = z_chan ** (-sigma * j_k)
    #   phi_part[sigma, E, k, comp, chan] = V[k, comp, chan] * Z_at_j[sigma, E, k, chan]
    Z_at_j = Z[None, :, None, :] ** (
        -sigma_vals[:, None, None, None] * j_arr[None, None, :, None]
    )                                                                  # (2, n_E, K, L_chan)
    phi_part = V_sites[None, None, :, :, :] * Z_at_j[:, :, :, None, :]  # (2, n_E, K, comp, chan)

    # correction[sigma,E,n,comp,chan] = sum_{k,b} G_beta[E,n,k,comp,b] phi_part[sigma,E,k,b,chan]
    correction = np.einsum('Enkab,sEkbc->sEnac', G_beta, phi_part)     # (2, n_E, n_sites, comp, chan)

    out = free_part - correction                                       # (2, n_E, n_sites, comp, chan)

    # Return axes (sigma, n_E, L_chan, n_sites, L_comp).
    return np.transpose(out, (0, 1, 4, 2, 3))
