"""Step 5 of MaxwellAlgorithm.pdf, implemented verbatim.

For n in Z intersect [N, M] and E in [a, b], the spec says:

    u_+^{E, +-}(n) = phi^{+-}(n, E) +- sum_{k: j_k > n} s(n, k, E) V(j_k) u_+^{E, +-}(j_k)
    u_-^{E, +-}(n) = phi^{-+}(n, E) -+ sum_{k: j_k < n} s(n, k, E) V(j_k) u_-^{E, +-}(j_k)

with the +- in the prefactor matching the +- superscript on u_+ (and the
prefactor of u_- being the opposite sign of the superscript on u_-). Each
u_tau^{E, sigma}(n) is an L x L matrix.

The recursion is one-sided: u_+ at n only references u_+ at potential
sites strictly to the right of n. We therefore walk leftward, processing
the K potential sites in reverse order so each u_+(j_k) only references
u_+(j_{k+1}), ..., u_+(j_K) which are already cached. u_- is built
symmetrically, walking rightward.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .kernels import s_kernel_diag


@dataclass
class JostBundle:
    """All four Jost solutions evaluated on the entire lattice slab.

    Layout: each array is shape (2_sigma, n_E, n_sites, L_row, L_col), with
    sigma index 0 -> sigma = +1 and sigma index 1 -> sigma = -1.
    """

    u_plus: np.ndarray
    u_minus: np.ndarray


def compute_jost(
    Z: np.ndarray,
    a: np.ndarray,
    j_sites: np.ndarray,
    V_sites: np.ndarray,
    lattice: np.ndarray,
) -> JostBundle:
    """Run the algorithm's iterative recursion to fill u_+, u_- on the lattice."""
    n_E, L = Z.shape
    n_sites = lattice.shape[0]
    K = j_sites.shape[0]

    # phi^sigma(n) diagonal: phi^+(n)_l = z_l^{-n}, phi^-(n)_l = z_l^{+n}.
    n_arr = lattice.astype(float)
    phi_plus  = Z[:, None, :] ** (-n_arr[None, :, None])   # (n_E, n_sites, L)
    phi_minus = Z[:, None, :] ** (+n_arr[None, :, None])   # (n_E, n_sites, L)

    # Initialise u_+, u_- on the lattice. The starting function is what each
    # recursion contributes when its sum is empty (i.e., past the support):
    #   u_+^{E, sigma}(n) starts at phi^sigma(n).
    #   u_-^{E, sigma}(n) starts at phi^{-sigma}(n).
    u_plus  = np.zeros((2, n_E, n_sites, L, L), dtype=complex)
    u_minus = np.zeros((2, n_E, n_sites, L, L), dtype=complex)
    for l in range(L):
        u_plus[0, :, :, l, l] = phi_plus[:, :, l]      # u_+^{E, +} starts at phi^+
        u_plus[1, :, :, l, l] = phi_minus[:, :, l]     # u_+^{E, -} starts at phi^-
        u_minus[0, :, :, l, l] = phi_minus[:, :, l]    # u_-^{E, +} starts at phi^-
        u_minus[1, :, :, l, l] = phi_plus[:, :, l]     # u_-^{E, -} starts at phi^+

    if K == 0:
        return JostBundle(u_plus=u_plus, u_minus=u_minus)

    # s(n, k, E) on the lattice (diagonal in channel l): (n_E, n_sites, K, L).
    s_diag = s_kernel_diag(Z, a, j_sites, lattice)

    j_to_lat = (j_sites - int(lattice[0])).astype(int)
    j_set = set(int(j) for j in j_sites)

    # Spec prefactors:
    #   u_+^{E, sigma}: +sigma on the sum (sigma = +1 -> +1, sigma = -1 -> -1).
    #   u_-^{E, sigma}: -sigma on the sum (sigma = +1 -> -1, sigma = -1 -> +1).
    sigma_signs = np.array([+1.0, -1.0])

    for sigma_idx in range(2):
        sgn_plus  = +sigma_signs[sigma_idx]
        sgn_minus = -sigma_signs[sigma_idx]

        # ---------- u_+^{E, sigma}: walk leftward ----------
        # Step A: fill u_+ at potential sites in reverse k order (so the sum
        # over kp > k uses values we have already cached).
        for k in reversed(range(K)):
            n_idx = int(j_to_lat[k])
            for kp in range(k + 1, K):
                Vu = np.einsum(
                    'ab,Ebc->Eac',
                    V_sites[kp],
                    u_plus[sigma_idx, :, int(j_to_lat[kp]), :, :],
                )                                                    # (n_E, L, L)
                contribution = s_diag[:, n_idx, kp, :, None] * Vu    # (n_E, L, L)
                u_plus[sigma_idx, :, n_idx, :, :] += sgn_plus * contribution

        # Step B: fill u_+ at non-potential sites (any order works since the
        # recursion only references u_+ at potential sites, which are done).
        for n_idx in range(n_sites):
            n = int(lattice[n_idx])
            if n in j_set:
                continue
            for k in range(K):
                if int(j_sites[k]) <= n:
                    continue
                Vu = np.einsum(
                    'ab,Ebc->Eac',
                    V_sites[k],
                    u_plus[sigma_idx, :, int(j_to_lat[k]), :, :],
                )
                contribution = s_diag[:, n_idx, k, :, None] * Vu
                u_plus[sigma_idx, :, n_idx, :, :] += sgn_plus * contribution

        # ---------- u_-^{E, sigma}: walk rightward ----------
        for k in range(K):
            n_idx = int(j_to_lat[k])
            for kp in range(0, k):
                Vu = np.einsum(
                    'ab,Ebc->Eac',
                    V_sites[kp],
                    u_minus[sigma_idx, :, int(j_to_lat[kp]), :, :],
                )
                contribution = s_diag[:, n_idx, kp, :, None] * Vu
                u_minus[sigma_idx, :, n_idx, :, :] += sgn_minus * contribution

        for n_idx in range(n_sites):
            n = int(lattice[n_idx])
            if n in j_set:
                continue
            for k in range(K):
                if int(j_sites[k]) >= n:
                    continue
                Vu = np.einsum(
                    'ab,Ebc->Eac',
                    V_sites[k],
                    u_minus[sigma_idx, :, int(j_to_lat[k]), :, :],
                )
                contribution = s_diag[:, n_idx, k, :, None] * Vu
                u_minus[sigma_idx, :, n_idx, :, :] += sgn_minus * contribution

    return JostBundle(u_plus=u_plus, u_minus=u_minus)
