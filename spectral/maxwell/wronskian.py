"""Step 6 of the Maxwell algorithm: discrete Wronskians W_tau^{E, sigma}.

For tau, sigma in {+, -}:

    W_tau^{E, sigma} = u_{-tau}^{E, -sigma}(N+1)^* A u_tau^{E, sigma}(N)
                     - u_{-tau}^{E, -sigma}(N)^*   A u_tau^{E, sigma}(N+1)

(N here is any anchor lattice site -- conventionally the leftmost.) The
Wronskian is independent of the anchor in regions where V vanishes between
the anchor and the support, and globally for honest H-eigenfunctions.
"""

from __future__ import annotations

import numpy as np

from .jost import JostBundle


def compute_wronskians(
    bundle: JostBundle,
    a: np.ndarray,
    anchor_lattice_idx: int = 0,
) -> np.ndarray:
    """Compute all four W_tau^{E, sigma}.

    Returns shape (2_tau, 2_sigma, n_E, L, L) with both tau and sigma indexed
    [+ -> 0, - -> 1].
    """
    _, n_E, n_sites, L, _ = bundle.u_plus.shape
    if anchor_lattice_idx < 0 or anchor_lattice_idx + 1 >= n_sites:
        raise ValueError(
            f"anchor_lattice_idx {anchor_lattice_idx} out of range for "
            f"n_sites={n_sites}"
        )
    A_mat = np.diag(np.asarray(a, dtype=float)).astype(complex)
    n0 = anchor_lattice_idx
    n1 = anchor_lattice_idx + 1

    W = np.empty((2, 2, n_E, L, L), dtype=complex)
    for tau_idx in range(2):
        for sigma_idx in range(2):
            other_sigma = 1 - sigma_idx
            if tau_idx == 0:           # tau = +
                u_tau = bundle.u_plus[sigma_idx]
                u_minus_tau = bundle.u_minus[other_sigma]
            else:                       # tau = -
                u_tau = bundle.u_minus[sigma_idx]
                u_minus_tau = bundle.u_plus[other_sigma]

            u_mt_n0 = u_minus_tau[:, n0]
            u_mt_n1 = u_minus_tau[:, n1]
            u_t_n0  = u_tau[:, n0]
            u_t_n1  = u_tau[:, n1]

            u_mt_n1_H = np.conj(np.swapaxes(u_mt_n1, -1, -2))
            u_mt_n0_H = np.conj(np.swapaxes(u_mt_n0, -1, -2))

            term1 = np.einsum('Eab,bc,Ecd->Ead', u_mt_n1_H, A_mat, u_t_n0)
            term2 = np.einsum('Eab,bc,Ecd->Ead', u_mt_n0_H, A_mat, u_t_n1)
            W[tau_idx, sigma_idx] = term1 - term2

    return W
