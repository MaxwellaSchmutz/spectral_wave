"""Steps 9-10 of the Maxwell algorithm: wave-packet normaliser p and the
time-evolved density psi(n, t).

Pipeline:
    1. channel_momenta + density_of_states (steps 1-3)
    2. compute_jost on the lattice (step 5, via the s-kernel recursion)
    3. compute_wronskians (step 6, all four W_tau^{E, sigma})
    4. compute_greens (step 7, with the W_+ / W_- branch by n vs j_k)
    5. full_eigenfunctions (step 8)
    6. normaliser p (step 9)
    7. amplitude integral over E and time loop (step 10)
"""

from __future__ import annotations

import numpy as np

from .channels import channel_momenta, density_of_states
from .eigfunc import full_eigenfunctions
from .green import compute_greens
from .jost import compute_jost
from .model import MaxwellSpec
from .quadrature import (
    gauss_legendre,
    gauss_legendre_segments,
    safe_open_band_interval,
    safe_open_band_segments,
)
from .wronskian import compute_wronskians


def compute_psi(spec: MaxwellSpec) -> np.ndarray:
    """Compute psi(n, t) for all (n in [N, M], t in spec.times).

    Returns
    -------
    psi : (n_t, n_sites) real, non-negative.
    """
    spec.validate()
    L = spec.L
    K = spec.K
    a = spec.a
    lattice = spec.lattice()

    a_min = float(a[-1])
    if spec.E_segments is not None:
        # Memo item B.5: one GL rule per [c, d] window converges spectrally
        # where a single rule spanning the f discontinuities does not.
        segs = safe_open_band_segments(a_min, spec.E_segments, spec.threshold_buffer)
        E_nodes, E_weights = gauss_legendre_segments(segs, spec.n_quad)
    else:
        lo, hi = safe_open_band_interval(a_min, spec.interval, spec.threshold_buffer)
        E_nodes, E_weights = gauss_legendre(lo, hi, spec.n_quad)

    Z = channel_momenta(E_nodes, a)                       # (n_E, L)
    nu = density_of_states(Z, a)                          # (n_E, L)
    sqrt_nu = np.sqrt(nu)

    f_vals = spec.evaluate_f(E_nodes)                     # (n_E, L, 2)

    if K == 0:
        # Free case (Interpretation 2, Schober A.1): w^{E,sigma}_{l}(n) = z_l^{-sigma n} e_l.
        # The summed sigma is the wave-vector sign, so the two sigma entries are the
        # distinct generalized eigenvectors z^{-n} and z^{+n} (no potential, so the
        # fixed outer/branch index drops out).
        n_E = E_nodes.size
        n_sites = lattice.shape[0]
        sigma_vals = np.array([+1.0, -1.0])
        w = np.zeros((2, n_E, L, n_sites, L), dtype=complex)  # (2_sigma, n_E, L, n_sites, L)
        for sidx, sgn in enumerate(sigma_vals):
            free_diag = Z[:, None, :] ** (-sgn * lattice[None, :, None].astype(float))
            for l in range(L):
                w[sidx, :, l, :, l] = free_diag[:, :, l]
    else:
        bundle = compute_jost(Z, a, spec.j_sites, spec.V_sites, lattice)
        # Anchor at the leftmost lattice site -- u_-(N) = phi^{-sigma}(N) by construction.
        W = compute_wronskians(bundle, a, anchor_lattice_idx=0)
        G = compute_greens(bundle, W, spec.j_sites, lattice)
        w = full_eigenfunctions(
            Z=Z,
            j_sites=spec.j_sites,
            V_sites=spec.V_sites,
            G_grid=G,
            lattice=lattice,
            outer_sign=spec.outer_sign,
        )

    # Step 9: p = sum_{l, sigma} integral |f[l, sigma](E)|^2 dE
    abs2 = np.abs(f_vals) ** 2
    p = float(np.sum(np.einsum('Els,E->ls', abs2, E_weights)))
    if p <= 0:
        raise ValueError("Wave-packet amplitude f is identically zero on [a, b]")

    # Step 10: psi(n, t) = (1/p) | sum_{l, sigma} integral e^{-itE} f w sqrt(nu) dE |^2
    sigma_axis_f = np.transpose(f_vals, (2, 0, 1))        # (2, n_E, L)
    factor = sigma_axis_f * sqrt_nu[None, :, :]
    weighted = factor[:, :, :, None, None] * w            # (2, n_E, L, n_sites, L)
    integrand_E_n = np.einsum('sElnc->Enc', weighted)     # (n_E, n_sites, L)

    times = spec.times
    n_sites = lattice.shape[0]
    psi = np.zeros((times.size, n_sites), dtype=float)
    for ti, t in enumerate(times):
        ph = np.exp(-1j * t * E_nodes)
        amp = np.einsum('E,E,Enc->nc', ph, E_weights, integrand_E_n)
        psi[ti] = (np.abs(amp) ** 2).sum(axis=-1)

    return psi / p


def compute_psi_frames(spec: MaxwellSpec) -> tuple[list[list[np.ndarray]], float]:
    """Render psi in the GUI's compute_frames shape."""
    psi = compute_psi(spec)
    global_max = float(np.max(psi))
    frames = [[psi[t]] for t in range(psi.shape[0])]
    return frames, global_max
