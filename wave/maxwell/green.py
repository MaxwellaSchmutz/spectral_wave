"""Step 7 of the Maxwell algorithm: full-Hamiltonian Green's function.

    G^{E,sigma}(n, k) = -u_+^{E, sigma}(n) (W_+^{E, sigma})^{-1} u_-^{E, -sigma}(j_k)^*    if n >  j_k
                      = +u_-^{E, sigma}(n) (W_-^{E, sigma})^{-1} u_+^{E, -sigma}(j_k)^*    if n <= j_k

Sign convention (A.10, Schober ruling 2026-08): the branch signs are the
`-/+` pattern of paper 2's resolvent kernel, so G is (H - E)^{-1}. The
literal spec had them the other way round, making G = (E - H)^{-1}; step 8
then subtracts it and double-counts the potential, leaving
(H - E) w = 2 V(j_k) z^{-sigma j_k} e_l at each support site.

Schober's ruling, verbatim: "What I know for sure is that (H-E)w = 0 has to
be true. So if you are saying that changes the sign of G accomplishes that,
please change the sign. I don't think we should change the sign in front of
the sum." So the fix lands HERE and eigfunc.py's step-8 minus stays. With
this, max |(H - E) w| drops from 2|V| to ~6e-16.

Note paper 2 also carries an explicit i in both the Wronskian definition,
W_paper = i[u(n+1)* A v(n) - u(n)* A v(n+1)], and the kernel numerator,
G = -+ m_+- i (W_paper)^{-1} m^*. wronskian.py omits that i, so
W_code = -i W_paper; since i (W_paper)^{-1} = W_code^{-1} the two omissions
cancel exactly and only the branch signs above were left wrong.
"""

from __future__ import annotations

import numpy as np

from .jost import JostBundle


def compute_greens(
    bundle: JostBundle,
    W: np.ndarray,
    j_sites: np.ndarray,
    lattice: np.ndarray,
) -> np.ndarray:
    """Returns G of shape (2_sigma, n_E, n_sites, K, L, L)."""
    _, n_E, n_sites, L, _ = bundle.u_plus.shape
    K = j_sites.shape[0]
    G = np.zeros((2, n_E, n_sites, K, L, L), dtype=complex)
    if K == 0:
        return G

    j_to_lat = (j_sites - int(lattice[0])).astype(int)
    eye = np.eye(L, dtype=complex)
    eye_b = np.broadcast_to(eye, (n_E, L, L))

    for sigma_idx in range(2):
        other_sigma = 1 - sigma_idx
        W_plus  = W[0, sigma_idx]                       # (n_E, L, L)
        W_minus = W[1, sigma_idx]
        W_plus_inv  = np.linalg.solve(W_plus,  eye_b.copy())
        W_minus_inv = np.linalg.solve(W_minus, eye_b.copy())

        u_plus_grid  = bundle.u_plus[sigma_idx]          # (n_E, n_sites, L, L)
        u_minus_grid = bundle.u_minus[sigma_idx]

        u_minus_at_j = bundle.u_minus[other_sigma][:, j_to_lat]  # (n_E, K, L, L)
        u_plus_at_j  = bundle.u_plus[other_sigma][:,  j_to_lat]
        u_minus_at_j_H = np.conj(np.swapaxes(u_minus_at_j, -1, -2))
        u_plus_at_j_H  = np.conj(np.swapaxes(u_plus_at_j,  -1, -2))

        for k_idx in range(K):
            jk = int(j_sites[k_idx])
            u_minus_jk_H = u_minus_at_j_H[:, k_idx]      # (n_E, L, L)
            u_plus_jk_H  = u_plus_at_j_H[:,  k_idx]

            G_right = -np.einsum(
                'Enab,Ebc,Ecd->Enad',
                u_plus_grid, W_plus_inv, u_minus_jk_H,
            )
            G_left = np.einsum(
                'Enab,Ebc,Ecd->Enad',
                u_minus_grid, W_minus_inv, u_plus_jk_H,
            )
            mask_gt = (lattice > jk)[None, :, None, None]
            G[sigma_idx, :, :, k_idx] = np.where(mask_gt, G_right, G_left)

    return G
