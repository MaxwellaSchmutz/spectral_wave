"""Steps 1-3 of the Maxwell algorithm.

Channel momenta z_l(E), free plane-wave bases phi_pm(n, E), and per-channel
density-of-states nu_l(E). Everything here is purely algebraic and unambiguous;
all routines are vectorized over the energy axis.
"""

from __future__ import annotations

import numpy as np


def channel_momenta(E: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Step 1: z_l(E), the upper-half-plane root of z^2 - (E/a_l) z + 1 = 0.

    Parameters
    ----------
    E : (n_E,) real
    a : (L,) positive real, descending

    Returns
    -------
    Z : (n_E, L) complex with Im(Z) > 0 strictly on the open band |E| < 2 a_l.
    """
    E = np.asarray(E, dtype=float).reshape(-1)
    a = np.asarray(a, dtype=float).reshape(-1)
    b = E[:, None] / a[None, :]                 # (n_E, L)
    # On the open band b^2 < 4, so 4 - b^2 > 0; the upper-half-plane root is
    # z = (b + i sqrt(4 - b^2)) / 2, giving Im(z) > 0 and |z| = 1.
    pos_part = np.maximum(4.0 - b * b, 0.0)     # clamp tiny negatives near threshold
    return 0.5 * (b + 1j * np.sqrt(pos_part))


def density_of_states(Z: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Step 3: nu_l(E) = 1 / (2 a_l Im z_l(E)).

    Real and strictly positive on the open band.
    """
    a = np.asarray(a, dtype=float).reshape(-1)
    return 1.0 / (2.0 * a[None, :] * np.imag(Z))


def phi_diag(Z: np.ndarray, n: int, sigma: int) -> np.ndarray:
    """Step 2: diagonal of phi_sigma(n) = diag(z_l^{-sigma * n}).

    sigma = +1 -> phi_+(n) has diag entries z_l^{-n}
    sigma = -1 -> phi_-(n) has diag entries z_l^{+n}
    """
    if sigma not in (+1, -1):
        raise ValueError(f"sigma must be +/- 1, got {sigma}")
    return Z ** (-sigma * n)
