"""Step 8 of MaxwellAlgorithm.pdf, implemented verbatim.

    w^{E, +-}_{l, sigma}(n) := z_l(E)^{-+ n} e_l
                             - sum_{k=1}^K G^{E, sigma}(n, k) V(j_k) z_l(E)^{-+ j_k} e_l

The "+-" superscript is the wave-vector sign (fixed externally as
spec.outer_sign); l indexes the channel; sigma indexes the Green's function
choice. Returns a vector in C^L for each (E, sigma, l, n).
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
    """Compute w_{l,sigma}^{E,outer}(n) for sigma in {+,-} (axis size 2).

    Parameters
    ----------
    Z          : (n_E, L)
    j_sites    : (K,)
    V_sites    : (K, L, L)
    G_grid     : (n_E, n_sites, K, L, L) -- Green's for ONE sigma. We require
                 it pre-stacked along a leading sigma axis: pass shape
                 (2, n_E, n_sites, K, L, L); axis 0 is [sigma=+, sigma=-].
    lattice    : (n_sites,)
    outer_sign : +1 or -1

    Returns
    -------
    w : (2, n_E, L_channel, n_sites, L_component)
        axis 0 = sigma index [+, -]
    """
    if outer_sign not in (+1, -1):
        raise ValueError("outer_sign must be +/- 1")
    if G_grid.ndim != 6 or G_grid.shape[0] != 2:
        raise ValueError(
            "G_grid must have shape (2, n_E, n_sites, K, L, L) -- "
            "stack the sigma=+ and sigma=- Green's functions along axis 0."
        )
    _, n_E, n_sites, K, L, _ = G_grid.shape
    n_arr = lattice.astype(float)

    # Free part: phi_outer(n) e_l = z_l^{-outer * n} * e_l.
    # Shape (n_E, n_sites, L_channel, L_component) where component == channel for free part.
    Zb = Z[:, None, :]                                                # (n_E, 1, L)
    free_diag = Zb ** (-outer_sign * n_arr[None, :, None])              # (n_E, n_sites, L)
    # Embed as identity * free_diag along the channel axis: w_l(n)_l = free_diag, else 0.
    free_part = np.zeros((n_E, n_sites, L, L), dtype=complex)
    idx = np.arange(L)
    free_part[:, :, idx, idx] = free_diag                               # (n_E, n_sites, L_chan, L_comp)

    # Correction: sum_k G(n, j_k) V(j_k) phi_outer(j_k) e_l
    # phi_outer(j_k) e_l  ->  z_l^{-outer * j_k} e_l, vector with single non-zero entry.
    # So V(j_k) phi_outer(j_k) e_l = V(j_k)[:, l] * z_l^{-outer * j_k}.
    # We assemble the correction across the sigma axis.
    j_arr = j_sites.astype(float)
    Z_at_j = Z[:, None, :] ** (-outer_sign * j_arr[None, :, None])      # (n_E, K, L_channel)

    # V[k, :, l_chan] -> (K, L_comp, L_channel); multiply by Z_at_j[E, k, l_chan]
    # to get the L_comp vector for each (E, k, l_chan):
    #   phi_part[E, k, l_comp, l_chan] = V[k, l_comp, l_chan] * Z_at_j[E, k, l_chan]
    phi_part = V_sites[None, :, :, :] * Z_at_j[:, :, None, :]            # (n_E, K, L_comp, L_chan)

    # Sum_k G(n, j_k) phi_part(j_k):
    #   correction[sigma, E, n, l_comp, l_chan]
    #     = sum_k sum_b G_grid[sigma, E, n, k, l_comp, b] * phi_part[E, k, b, l_chan]
    correction = np.einsum('sEnkab,Ekbc->sEnac', G_grid, phi_part)
    # correction shape: (2, n_E, n_sites, L_comp, L_chan)

    # Reorder free_part to align: (n_E, n_sites, L_chan, L_comp). Need (n_E, n_sites, L_comp, L_chan).
    free_part_ordered = np.swapaxes(free_part, -1, -2)                   # (n_E, n_sites, L_comp, L_chan)
    out = free_part_ordered[None, :, :, :, :] - correction               # (2, n_E, n_sites, L_comp, L_chan)

    # Return with axes (sigma, n_E, L_chan, n_sites, L_comp) per spec.
    out = np.transpose(out, (0, 1, 4, 2, 3))                             # (2, n_E, L_chan, n_sites, L_comp)
    return out
