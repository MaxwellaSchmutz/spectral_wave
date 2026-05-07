from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np


# Buffer keeping the energy interval away from the channel thresholds E = +/- 2 a_l.
# Below this, nu_l = 1/(2 a_l sin theta_l) blows up and the formulas in steps
# 1-3 lose accuracy. Tunable per-spec via threshold_buffer.
DEFAULT_THRESHOLD_BUFFER = 1e-3


@dataclass
class MaxwellSpec:
    """The 'Data' block from the Maxwell algorithm spec.

    All fields are validated by ``validate()`` against the constraints in
    section 2 of MaxwellAlgorithm.pdf. Construct directly or via
    ``MaxwellSpec.from_dict`` for GUI / JSON-style input.
    """

    L: int
    a: np.ndarray
    N: int
    M: int
    j_sites: np.ndarray
    V_sites: np.ndarray
    interval: tuple[float, float]
    f: Callable[[np.ndarray], np.ndarray]
    times: np.ndarray
    n_quad: int = 128
    threshold_buffer: float = DEFAULT_THRESHOLD_BUFFER
    # Which sign convention to use for the outer w_{l,sigma}^{E,pm} in step 10.
    # +1 selects w^{E,+} (outgoing F_+ branch); -1 selects w^{E,-}. See open
    # questions in MaxwellAlgorithm_SPEC.md. Default + per spec recommendation.
    outer_sign: int = +1

    def __post_init__(self) -> None:
        self.a = np.asarray(self.a, dtype=float).reshape(-1)
        self.j_sites = np.asarray(self.j_sites, dtype=int).reshape(-1)
        self.V_sites = np.asarray(self.V_sites, dtype=complex)
        if self.V_sites.size == 0:
            self.V_sites = np.zeros((0, self.L, self.L), dtype=complex)
        self.times = np.asarray(self.times, dtype=float).reshape(-1)
        self.interval = (float(self.interval[0]), float(self.interval[1]))

    # ------------------------------------------------------------------ #
    # Validation                                                         #
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if self.L < 1:
            raise ValueError("L must be >= 1")
        if self.a.shape != (self.L,):
            raise ValueError(f"a must have shape ({self.L},), got {self.a.shape}")
        if not np.all(np.diff(self.a) <= 0):
            raise ValueError("a must be sorted descending: a[0] >= ... >= a[L-1]")
        if not np.all(self.a > 0):
            raise ValueError("all a_l must be > 0")
        if self.N >= self.M:
            raise ValueError(f"need N < M, got N={self.N}, M={self.M}")

        K = self.j_sites.shape[0]
        if self.V_sites.shape != (K, self.L, self.L):
            raise ValueError(
                f"V_sites shape must be ({K}, {self.L}, {self.L}), "
                f"got {self.V_sites.shape}"
            )
        if K > 0:
            if not np.all(np.diff(self.j_sites) > 0):
                raise ValueError("j_sites must be strictly increasing")
            if self.j_sites[0] < self.N or self.j_sites[-1] > self.M:
                raise ValueError(
                    f"j_sites must lie in [N, M] = [{self.N}, {self.M}]"
                )
            for k in range(K):
                Vk = self.V_sites[k]
                if not np.allclose(Vk, Vk.conj().T, atol=1e-10):
                    raise ValueError(f"V_sites[{k}] is not self-adjoint")

        a, b = self.interval
        if a >= b:
            raise ValueError(f"interval must satisfy a < b, got ({a}, {b})")

        a_min = float(self.a[-1])
        thresh = 2.0 * a_min - self.threshold_buffer
        if a < -thresh or b > thresh:
            raise ValueError(
                f"interval [{a}, {b}] must lie inside the common open band "
                f"[{-thresh}, {thresh}] (a_min={a_min}, "
                f"threshold_buffer={self.threshold_buffer}). "
                f"Outside this range some channels are closed and the "
                f"Maxwell algorithm formulas break down."
            )

        if self.n_quad < 8:
            raise ValueError("n_quad must be >= 8 for stable Gauss-Legendre")

        # The norm-condition guard from paper 1, Definition 1.1 is a strict
        # growth condition sum_n ||V(n)|| rho_A^{|n|} < infty. With finite
        # support that sum is automatically finite, so no extra check needed.

    # ------------------------------------------------------------------ #
    # Convenience                                                        #
    # ------------------------------------------------------------------ #

    @property
    def K(self) -> int:
        return int(self.j_sites.shape[0])

    @property
    def n_sites(self) -> int:
        return self.M - self.N + 1

    def lattice(self) -> np.ndarray:
        return np.arange(self.N, self.M + 1, dtype=int)

    def evaluate_f(self, E: np.ndarray) -> np.ndarray:
        """f(E) -> array of shape (n_E, L, 2)."""
        E = np.asarray(E, dtype=float).reshape(-1)
        out = self.f(E)
        out = np.asarray(out, dtype=complex)
        if out.shape != (E.size, self.L, 2):
            raise ValueError(
                f"f(E) must return shape (n_E={E.size}, L={self.L}, 2); "
                f"got {out.shape}"
            )
        return out
