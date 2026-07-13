"""Regression suite for the Maxwell algorithm reference implementation.

Rebuilt 2026-07 after the disk failure; same policy as the lost original.

Policy. The code implements MaxwellAlgorithm.pdf (authoritative revision
2026-05-19) LITERALLY, plus exactly two author-blessed deviations, and
nothing else. Every step is re-derived by hand in this file and matched
to about 1e-12. Spec oddities are PINNED: the assertions encode what the
code DOES, not what anyone suspects it should do. If a pinned test fails,
someone "fixed" the algorithm without Schober's blessing -- revert the
change, or produce a dated ruling and flip the pin in the same commit.

BLESSED deviations (in the algorithm; asserted here as correct):
  A.2  step-5 sum prefactor is +i on the u_+ recursion and -i on the u_-
       recursion, independent of the sigma superscript ("the sign just
       depends on the lower index"). Jost residual drops to ~1e-16.
  A.1  step-8 Interpretation 2: the summed sigma (the one paired with
       f_{l,sigma} in step 10) is the wave-vector sign driving
       z^{-sigma n}; the fixed lower +/- (spec.outer_sign) picks ONE
       Green's branch. Schober: if f_{l,+} = f_{l,-} the packet "should
       not move, but just change shape".

PINNED-OPEN (literal spec behavior, known wrong-looking, awaiting the
author -- DO NOT fix in wave/ without his blessing):
  A.10 the composed step-8 eigenfunction w satisfies
       (H - E) w = 2 V(j_k) z_l^{-sigma j_k} e_l exactly AT the potential
       sites, while being ~1e-15 everywhere else. Literal step-7 G is
       (E - H)^{-1}, so step 8's minus sign double-counts the potential.
  A.11 the literal step-9 normaliser p leaves sum_n psi(n, 0) = 2*pi
       exactly, not 1 (a 1/(2*pi) is missing from the completeness
       measure; contradicts his A.8 answer "total is 1").

Endorsed program checks (Schober, 2026-05-19 chat): A.4 the Wronskian is
anchor-independent; A.5 the two step-7 branch formulas agree at n = j_k.
Both hold no matter how A.10 resolves -- his own diagnostics cannot see
the A.10 sign, which is why it is pinned here instead.
"""

from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace

import numpy as np
import pytest

from wave.maxwell import MaxwellSpec, compute_psi
from wave.maxwell.channels import channel_momenta, density_of_states
from wave.maxwell.eigfunc import full_eigenfunctions
from wave.maxwell.green import compute_greens
from wave.maxwell.jost import compute_jost
from wave.maxwell.kernels import s_kernel_diag
from wave.maxwell.wronskian import compute_wronskians

TOL = 1e-12

# --------------------------------------------------------------------- #
# Shared configurations                                                  #
# --------------------------------------------------------------------- #
# Slab and energy grid used by the pipeline tests (steps 4-8). E values
# sit inside the common open band |E| < 2 a_L = 2 for both configs.
N_SLAB, M_SLAB = -12, 12
E_COMMON = np.array([-0.6, 0.0, 0.5])

# Config (i): scalar sanity case. Config (ii): the author's own matrices
# from the 2026-05-19 chat. Anchor indices: lattice index of site j is
# j - N = j + 12, so 12 sits ON j_1 = 0 and 16 sits ON j_2 = 4;
# 23 = n_sites - 2 is the last legal anchor.
CONFIGS = {
    "L1_scalar": dict(
        a=np.array([1.0]),
        j_sites=np.array([0]),
        V_sites=np.array([[[0.5]]], dtype=complex),
        anchors=(0, 12, 23),
    ),
    "L2_author": dict(
        a=np.array([2.0, 1.0]),
        j_sites=np.array([0, 4]),
        V_sites=np.array(
            [
                [[0.0, 1.0], [1.0, 0.0]],
                [[5.0, 0.0], [0.0, -3.0]],
            ],
            dtype=complex,
        ),
        anchors=(0, 12, 16, 23),
    ),
}


@lru_cache(maxsize=None)
def pipeline(name: str) -> SimpleNamespace:
    """Steps 1-8 on one config, computed once and shared across tests."""
    cfg = CONFIGS[name]
    a = cfg["a"]
    j_sites = cfg["j_sites"]
    V_sites = cfg["V_sites"]
    lattice = np.arange(N_SLAB, M_SLAB + 1, dtype=int)
    E = E_COMMON
    Z = channel_momenta(E, a)
    bundle = compute_jost(Z, a, j_sites, V_sites, lattice)
    W = compute_wronskians(bundle, a, anchor_lattice_idx=0)
    G = compute_greens(bundle, W, j_sites, lattice)
    return SimpleNamespace(
        a=a, L=a.size, j_sites=j_sites, V_sites=V_sites,
        Vmap={int(j): V_sites[k] for k, j in enumerate(j_sites)},
        lattice=lattice, E=E, Z=Z, bundle=bundle, W=W, G=G,
        anchors=cfg["anchors"],
    )


# --------------------------------------------------------------------- #
# Hand-rolled Hamiltonian residuals                                      #
# --------------------------------------------------------------------- #
# (H psi)(n) = A* psi(n+1) + A psi(n-1) + V(n) psi(n), and A = diag(a)
# is real, so A* = A. Applied only at interior lattice sites (both
# neighbours available). These helpers are the independent re-derivation
# the whole suite leans on -- keep them dumb and literal.

def h_residual_matrix(u, a, Vmap, lattice, E):
    """(H - E) u at interior sites for a matrix family u: (n_E, n_sites, L, L).

    Returns (n_E, n_sites - 2, L, L), site axis = lattice[1:-1].
    """
    A = np.diag(a).astype(complex)
    n_sites = lattice.size
    res = np.empty((E.size, n_sites - 2) + u.shape[2:], dtype=complex)
    for ii, ni in enumerate(range(1, n_sites - 1)):
        r = A @ u[:, ni + 1] + A @ u[:, ni - 1] - E[:, None, None] * u[:, ni]
        Vn = Vmap.get(int(lattice[ni]))
        if Vn is not None:
            r = r + Vn @ u[:, ni]
        res[:, ii] = r
    return res


def h_residual_vector_grid(w, a, Vmap, lattice, E):
    """(H - E) w at interior sites for w: (2_sigma, n_E, L_chan, n_sites, L).

    Returns (2, n_E, L_chan, n_sites - 2, L), site axis = lattice[1:-1].
    """
    res = (
        a[None, None, None, None, :] * (w[..., 2:, :] + w[..., :-2, :])
        - E[None, :, None, None, None] * w[..., 1:-1, :]
    )
    for n, Vn in Vmap.items():
        ni = int(n - lattice[0])          # absolute lattice index of site n
        res[..., ni - 1, :] += np.einsum("ab,...b->...a", Vn, w[..., ni, :])
    return res


# --------------------------------------------------------------------- #
# Wave-packet helpers (steps 9-10 tests)                                 #
# --------------------------------------------------------------------- #

def gaussian_f(L, sE, E0, w_plus, w_minus, channel=0):
    """f(E) -> (n_E, L, 2), Gaussian envelope; [:, :, 0] is the sigma=+ slot."""

    def f(E):
        E = np.asarray(E, dtype=float).reshape(-1)
        out = np.zeros((E.size, L, 2), dtype=complex)
        g = np.exp(-((E - E0) ** 2) / (2.0 * sE * sE))
        out[:, channel, 0] = w_plus * g
        out[:, channel, 1] = w_minus * g
        return out

    return f


def free_spec(N, M, f, times, n_quad, interval=(-1.5, 1.5)):
    """Free (K = 0) scalar spec: L = 1, a = [1], open band |E| < 2."""
    return MaxwellSpec(
        L=1, a=np.array([1.0]), N=N, M=M,
        j_sites=np.array([], dtype=int),
        V_sites=np.zeros((0, 1, 1), dtype=complex),
        interval=interval, f=f,
        times=np.asarray(times, dtype=float), n_quad=n_quad,
    )


def center_of_mass(psi_row, lattice):
    return float((psi_row * lattice).sum() / psi_row.sum())


@lru_cache(maxsize=None)
def sigma_plus_run():
    """The test-9 sigma=+ run, shared with the group-velocity test (10)."""
    lattice = np.arange(-120, 121)
    spec = free_spec(-120, 120, gaussian_f(1, 0.30, 0.0, 1.0, 0.0),
                     times=[0.0, 15.0, 30.0], n_quad=256)
    return lattice, compute_psi(spec)


# ===================================================================== #
# 1. Steps 1 + 3: channel momenta and density of states                  #
# ===================================================================== #

def test_channel_momenta_and_dos():
    """Step 1: z_l is the upper-half-plane, unit-circle root of the
    dispersion z^2 - (E/a_l) z + 1 = 0; step 3: nu_l real positive."""
    a = np.array([2.0, 1.0])
    E = np.linspace(-1.9, 1.9, 39)          # inside the common band |E| < 2
    Z = channel_momenta(E, a)

    assert np.all(np.imag(Z) > 0.0)                                  # upper half-plane
    assert np.max(np.abs(np.abs(Z) - 1.0)) < TOL                     # on the unit circle
    disp = a[None, :] * (Z + 1.0 / Z) - E[:, None]                   # a_l (z + 1/z) = E
    assert np.max(np.abs(disp)) < TOL

    nu = density_of_states(Z, a)
    assert np.isrealobj(nu)
    assert np.all(np.isfinite(nu))
    assert np.all(nu > 0.0)


# ===================================================================== #
# 2. Step 4: the s-kernel, re-derived entry by entry                     #
# ===================================================================== #

def test_s_kernel_matches_direct_formula():
    """s(n, k, E)_{l,l} = nu_l(E) (z_l^{j_k - n} - z_l^{n - j_k}), verbatim.

    Compared against a dumb quadruple loop on a seeded random config.
    """
    rng = np.random.default_rng(20260519)
    a = np.sort(rng.uniform(0.9, 2.5, size=2))[::-1].copy()   # descending positive
    lattice = np.arange(-6, 7, dtype=int)
    j_sites = np.array([-2, 1, 3])
    E = rng.uniform(-1.5, 1.5, size=4)       # inside band |E| < 2 a_L >= 1.8
    Z = channel_momenta(E, a)

    S = s_kernel_diag(Z, a, j_sites, lattice)
    assert S.shape == (E.size, lattice.size, j_sites.size, a.size)

    direct = np.empty_like(S)
    for e in range(E.size):
        for ni, n in enumerate(lattice):
            for k, jk in enumerate(j_sites):
                for l in range(a.size):
                    z = Z[e, l]
                    nu = 1.0 / (2.0 * a[l] * z.imag)
                    direct[e, ni, k, l] = nu * (z ** (jk - n) - z ** (n - jk))
    np.testing.assert_allclose(S, direct, rtol=0.0, atol=TOL)


# ===================================================================== #
# 3. Step 5: Jost solutions are honest eigenfunctions (A.2 BLESSED)      #
# ===================================================================== #

@pytest.mark.parametrize("name", list(CONFIGS))
def test_jost_solutions_solve_eigenvalue_equation(name):
    """A.2 (BLESSED 2026-05-19): the step-5 sum prefactor is +i for u_+ and
    -i for u_-, INDEPENDENT of the sigma superscript -- "the sign just
    depends on the lower index". With that fix all four families
    u_+^{+-}, u_-^{+-} satisfy (H - E) u = 0 at every interior site,
    including the potential sites. The literal real prefactor left a
    residual of 0.5 (1 + sigma i) at L=1, V(0)=0.5, E=0; this test is the
    regression for the fix.
    """
    p = pipeline(name)
    for family in (p.bundle.u_plus, p.bundle.u_minus):
        for sigma_idx in range(2):
            res = h_residual_matrix(family[sigma_idx], p.a, p.Vmap, p.lattice, p.E)
            assert np.max(np.abs(res)) < TOL


# ===================================================================== #
# 4. Step 6: Wronskian anchor independence (A.4, author-endorsed check)  #
# ===================================================================== #

@pytest.mark.parametrize("name", list(CONFIGS))
def test_wronskian_anchor_independence(name):
    """A.4 (Schober-endorsed diagnostic): W_tau^{E, sigma} must not depend
    on the anchor site. Checked at the left edge, ON each potential site,
    and at the last legal anchor n_sites - 2. Passes because the Jost
    functions are honest eigenfunctions (test 3); constancy of the
    discrete Wronskian is equivalent to that.
    """
    p = pipeline(name)
    W_ref = compute_wronskians(p.bundle, p.a, anchor_lattice_idx=p.anchors[0])
    for anchor in p.anchors[1:]:
        W_alt = compute_wronskians(p.bundle, p.a, anchor_lattice_idx=anchor)
        np.testing.assert_allclose(W_alt, W_ref, rtol=0.0, atol=1e-10)


# ===================================================================== #
# 5. Step 7: the two branch formulas agree at n = j_k (A.5, endorsed)    #
# ===================================================================== #

@pytest.mark.parametrize("name", list(CONFIGS))
def test_greens_branch_formulas_agree_at_support(name):
    """A.5 (Schober-endorsed diagnostic): at n = j_k the n > j_k branch
    formula and the n <= j_k branch formula of step 7 must agree:

        u_+^{sigma}(j_k) (W_+^{sigma})^{-1} u_-^{-sigma}(j_k)^H
        == - u_-^{sigma}(j_k) (W_-^{sigma})^{-1} u_+^{-sigma}(j_k)^H

    Spec reading, verbatim: branch n > j_k uses W_+ with u_+(n) and
    u_-^{-sigma}(j_k)^*; branch n <= j_k uses -u_-(n) W_-^{-1}
    u_+^{-sigma}(j_k)^*. Here the n > j_k FORMULA is evaluated at
    n = j_k and compared to the n <= j_k formula there. NOTE this check
    passing says nothing about the overall sign of G -- see the A.10 pin
    in test 6, which his diagnostics cannot see.
    """
    p = pipeline(name)
    L = p.L
    eye_b = np.broadcast_to(np.eye(L, dtype=complex), (p.E.size, L, L))
    for sigma_idx in range(2):
        other = 1 - sigma_idx
        W_plus_inv = np.linalg.solve(p.W[0, sigma_idx], eye_b.copy())   # tau idx 0 = +
        W_minus_inv = np.linalg.solve(p.W[1, sigma_idx], eye_b.copy())  # tau idx 1 = -
        for k, jk in enumerate(p.j_sites):
            ji = int(jk - p.lattice[0])
            u_p = p.bundle.u_plus[sigma_idx][:, ji]
            u_m = p.bundle.u_minus[sigma_idx][:, ji]
            u_m_other_H = np.conj(np.swapaxes(p.bundle.u_minus[other][:, ji], -1, -2))
            u_p_other_H = np.conj(np.swapaxes(p.bundle.u_plus[other][:, ji], -1, -2))

            expr_plus = np.einsum("Eab,Ebc,Ecd->Ead", u_p, W_plus_inv, u_m_other_H)
            expr_minus = -np.einsum("Eab,Ebc,Ecd->Ead", u_m, W_minus_inv, u_p_other_H)
            np.testing.assert_allclose(expr_plus, expr_minus, rtol=0.0, atol=1e-10)

            # Convention pin: at n = j_k the code's mask (lattice > j_k)
            # picks the n <= j_k branch, i.e. expr_minus.
            np.testing.assert_allclose(
                p.G[sigma_idx, :, ji, k], expr_minus, rtol=0.0, atol=1e-12
            )


# ===================================================================== #
# 6. Step 8: the A.10 PIN -- the loud one                                #
# ===================================================================== #

@pytest.mark.parametrize("name", list(CONFIGS))
@pytest.mark.parametrize("outer_sign", [+1, -1])
def test_step8_residual_pin_A10(name, outer_sign):
    """PIN A.10 -- OPEN. DO NOT 'fix' without Schober's blessing.

    WHAT THIS PINS: with honest Jost u's (test 3), the literal step-7 G
    composed into the literal step-8 w gives

        (H - E) w = 2 V(j_k) z_l^{-sigma j_k} e_l   exactly AT each j_k,
        (H - E) w ~ 1e-15                           everywhere else,

    for BOTH outer_sign branches and BOTH summed sigma.

    WHY: literal step-7 G is (E - H)^{-1} (it satisfies (E - H) G = delta),
    so step 8's w = phi - G V phi has (H - E) w = V phi + V phi = 2 V phi
    at the support -- the minus sign double-counts the potential. Steps 7
    and 8 are off by one overall sign, factor exactly 2, no other damage.
    Schober's own endorsed diagnostics (A.4 anchor independence, A.5
    branch agreement -- tests 4 and 5) pass REGARDLESS, so they cannot
    catch this. This pin is the only tripwire.

    THE TWO EQUIVALENT ONE-LINE FIXES, when (and only when) he rules:
      (a) negate G in wave/maxwell/green.py, or
      (b) flip the step-8 minus to plus in wave/maxwell/eigfunc.py.
    Either one turns the support residual into 0; then flip this pin to
    assert max |(H - E) w| < 1e-12 EVERYWHERE and delete the 2 V phi
    block. Until then the literal behavior is the contract. Awaiting
    Schober.
    """
    p = pipeline(name)
    w = full_eigenfunctions(
        Z=p.Z, j_sites=p.j_sites, V_sites=p.V_sites, G_grid=p.G,
        lattice=p.lattice, outer_sign=outer_sign,
    )  # (2_sigma, n_E, L_chan, n_sites, L_comp)

    res = h_residual_vector_grid(w, p.a, p.Vmap, p.lattice, p.E)
    interior = p.lattice[1:-1]
    on_support = np.isin(interior, p.j_sites)

    # Off the support the composed w is an eigenfunction to machine noise.
    assert np.max(np.abs(res[..., ~on_support, :])) < TOL

    # AT the support: residual == 2 V(j_k) z_l^{-sigma j_k} e_l, componentwise.
    sigma_vals = np.array([+1.0, -1.0])
    for k, jk in enumerate(p.j_sites):
        pos = int(np.flatnonzero(interior == jk)[0])
        got = res[..., pos, :]                                  # (2, n_E, L_chan, L_comp)
        phase = p.Z[None, :, :] ** (-sigma_vals[:, None, None] * float(jk))
        # expected[s, E, l, :] = 2 z_l^{-sigma j_k} V(j_k)[:, l]
        expected = 2.0 * phase[..., None] * p.V_sites[k].T[None, None, :, :]
        np.testing.assert_allclose(got, expected, rtol=0.0, atol=1e-9)

    # Loudness guard: the support residual is O(1) -- if someone applies
    # fix (a) or (b) above, this line fails too and points them here.
    assert np.max(np.abs(res[..., on_support, :])) > 0.1


# ===================================================================== #
# 7. Steps 9-10: the A.11 PIN -- total probability is 2*pi               #
# ===================================================================== #

def test_total_probability_pin_A11():
    """PIN A.11 -- OPEN. DO NOT 'fix' without Schober's blessing.

    WHAT THIS PINS: with the literal step-9 normaliser
    p = sum_{l,sigma} int |f|^2 dE, the total probability comes out

        sum_n psi(n, 0) = 2*pi   exactly (Parseval on the circle),

    not 1. A 1/(2*pi) is missing from the completeness measure. This
    contradicts Schober's A.8 answer ("psi is the density, total is 1,
    normalize once at the beginning") -- but A.8 was about WHERE to
    normalize, not the constant, so the literal 2*pi stays in the code
    until he rules on the constant itself.

    THE ONE-LINE FIX, when he rules: divide p (or psi) by 2*pi in
    wave/maxwell/evolve.py step 9; then flip this pin to
    |sum_n psi - 1| < 1e-6. Awaiting Schober.

    Config: free scalar Gaussian, sigma=+ only, E0 = 0, sE = 0.30, slab
    wide enough (+-150) that the lattice truncation error is ~1e-14.
    """
    spec = free_spec(-150, 150, gaussian_f(1, 0.30, 0.0, 1.0, 0.0),
                     times=[0.0], n_quad=256)
    psi = compute_psi(spec)
    total = float(psi[0].sum())

    assert abs(total - 2.0 * np.pi) < 1e-6      # measured: |diff| ~ 9e-13

    # Loudness guard: anyone silently renormalising to 1 trips this line.
    assert abs(total - 1.0) > 5.0


# ===================================================================== #
# 8. Probability conservation under time evolution                       #
# ===================================================================== #

def test_probability_conservation():
    """Free evolution is unitary: S(t) = sum_n psi(n, t) is conserved to
    quadrature accuracy as long as the packet stays inside the slab
    (v_g = 2 a = 2, t <= 30, slab edge at 150)."""
    spec = free_spec(-150, 150, gaussian_f(1, 0.30, 0.0, 1.0, 0.0),
                     times=np.linspace(0.0, 30.0, 7), n_quad=256)
    psi = compute_psi(spec)
    S = psi.sum(axis=1)
    assert np.max(np.abs(S - S[0])) / S[0] < 1e-9   # measured: ~1e-14


# ===================================================================== #
# 9. Interpretation 2 semantics (A.1 BLESSED)                            #
# ===================================================================== #

def test_interpretation2_balanced_f_is_standing_wave():
    """A.1 (BLESSED 2026-05-19): the summed sigma is the wave-vector sign.
    Schober's own acceptance criterion, verbatim: "if f_{l,+} = f_{l,-}
    the packet should not move, but just change shape." Balanced
    excitation => the center of mass stays put (measured drift ~1e-15
    sites; the bound of 1.0 site is generous on purpose -- the failure
    mode under Interpretation 1 was a drift of ~60 sites)."""
    lattice = np.arange(-120, 121)
    spec = free_spec(-120, 120, gaussian_f(1, 0.30, 0.0, 1.0, 1.0),
                     times=[0.0, 15.0, 30.0], n_quad=256)
    psi = compute_psi(spec)
    com = [center_of_mass(psi[t], lattice) for t in range(3)]
    assert abs(com[1] - com[0]) < 1.0
    assert abs(com[2] - com[0]) < 1.0


def test_interpretation2_sigma_plus_moves_right():
    """A.1 (BLESSED): sigma=+ only => the packet runs right. Measured
    COM(30) - COM(0) = +59.7 at v_g = 2; the bound 40 leaves room."""
    lattice, psi = sigma_plus_run()
    com = [center_of_mass(psi[t], lattice) for t in range(3)]
    assert com[2] - com[0] > 40.0


def test_interpretation2_sigma_minus_moves_left():
    """A.1 (BLESSED): sigma=- only => mirror image, packet runs left."""
    lattice = np.arange(-120, 121)
    spec = free_spec(-120, 120, gaussian_f(1, 0.30, 0.0, 0.0, 1.0),
                     times=[0.0, 15.0, 30.0], n_quad=256)
    psi = compute_psi(spec)
    com = [center_of_mass(psi[t], lattice) for t in range(3)]
    assert com[2] - com[0] < -40.0


# ===================================================================== #
# 10. Group velocity                                                     #
# ===================================================================== #

def test_group_velocity_at_band_center():
    """At E0 = 0 (band center, theta = pi/2) the lattice group velocity is
    |dE/d theta| = 2 a sin(theta) = 2 a = 2. Peak-position slope between
    t = 15 and t = 30 from the sigma=+ run of test 9; measured peaks at
    n = 30 and 59, slope 1.933 (argmax quantises to whole sites)."""
    lattice, psi = sigma_plus_run()
    peaks = lattice[np.argmax(psi, axis=1)]
    slope = (peaks[2] - peaks[1]) / 15.0
    assert abs(slope - 2.0) <= 0.15


# ===================================================================== #
# 11. n_quad aliasing: the phantom-mirror failure mode                    #
# ===================================================================== #

def test_nquad_aliasing_phantom_packet():
    """Documents the known failure mode, not a bug: the step-10 integrand
    oscillates like exp(-i (n theta(E) + t E)); once the Gauss-Legendre
    rule under-resolves it, a PHANTOM mirror packet materialises and mass
    is NOT conserved. At t = 50 with n_quad = 64 the phantom carries a
    full copy of the packet: S(50)/S(0) = 2.000 (measured 1.99996).

    At n_quad = 192 the quadrature is converged. The remaining
    |S(50)/S(0) - 1| = 4.27e-5 is NOT aliasing: it is the leading tail of
    the packet (center n ~ 100 at t = 50) leaving the +-120 slab, and it
    is identical for every n_quad >= 128. Hence the 1e-4 bound here, not
    1e-6. Rule of thumb until the GUI grows its heuristic: pick n_quad
    well above (max|n| + max|t|) * dE_interval / pi.
    """
    f = gaussian_f(1, 0.30, 0.0, 1.0, 0.0)

    spec_coarse = free_spec(-120, 120, f, times=[0.0, 50.0], n_quad=64)
    S = compute_psi(spec_coarse).sum(axis=1)
    assert S[1] / S[0] > 1.5                     # phantom doubles the mass

    spec_fine = free_spec(-120, 120, f, times=[0.0, 50.0], n_quad=192)
    S = compute_psi(spec_fine).sum(axis=1)
    assert abs(S[1] / S[0] - 1.0) < 1e-4         # measured: 4.271e-5, slab truncation


# ===================================================================== #
# 13. MaxwellSpec validation                                             #
# ===================================================================== #

def _valid_spec_kwargs():
    """A known-good spec; each validation test breaks exactly one field."""
    return dict(
        L=1, a=np.array([1.0]), N=-10, M=10,
        j_sites=np.array([0]),
        V_sites=np.array([[[0.5]]], dtype=complex),
        interval=(-1.0, 1.0),
        f=gaussian_f(1, 0.30, 0.0, 1.0, 0.0),
        times=np.array([0.0]), n_quad=32,
    )


def test_validation_rejects_ascending_a():
    kw = _valid_spec_kwargs()
    kw.update(L=2, a=np.array([1.0, 2.0]),        # ascending: forbidden
              j_sites=np.array([0]),
              V_sites=np.zeros((1, 2, 2), dtype=complex),
              f=gaussian_f(2, 0.30, 0.0, 1.0, 0.0))
    with pytest.raises(ValueError):
        MaxwellSpec(**kw).validate()


def test_validation_rejects_N_not_below_M():
    kw = _valid_spec_kwargs()
    kw.update(N=10, M=10, j_sites=np.array([], dtype=int),
              V_sites=np.zeros((0, 1, 1), dtype=complex))
    with pytest.raises(ValueError):
        MaxwellSpec(**kw).validate()


def test_validation_rejects_non_self_adjoint_V():
    kw = _valid_spec_kwargs()
    kw.update(L=2,
              a=np.array([2.0, 1.0]),
              V_sites=np.array([[[0.0, 1.0], [0.0, 0.0]]], dtype=complex),
              f=gaussian_f(2, 0.30, 0.0, 1.0, 0.0))
    with pytest.raises(ValueError):
        MaxwellSpec(**kw).validate()


def test_validation_rejects_interval_outside_band():
    kw = _valid_spec_kwargs()
    kw.update(interval=(-3.0, 3.0))               # band is |E| < 2
    with pytest.raises(ValueError):
        MaxwellSpec(**kw).validate()


def test_validation_rejects_small_n_quad():
    kw = _valid_spec_kwargs()
    kw.update(n_quad=4)
    with pytest.raises(ValueError):
        MaxwellSpec(**kw).validate()


# ===================================================================== #
# 14. K = 0 consistency                                                  #
# ===================================================================== #

def test_free_spec_equals_zero_potential_spec():
    """The dedicated K = 0 fast path in evolve.py must agree with the full
    Jost/Wronskian/Greens pipeline fed V(0) = 0. Measured difference is
    exactly 0.0; asserted at 1e-12."""
    f = gaussian_f(1, 0.30, 0.0, 1.0, 0.0)
    common = dict(L=1, a=np.array([1.0]), N=-30, M=30,
                  interval=(-1.2, 1.2), f=f,
                  times=np.array([0.0, 2.0]), n_quad=48)
    psi_free = compute_psi(MaxwellSpec(
        j_sites=np.array([], dtype=int),
        V_sites=np.zeros((0, 1, 1), dtype=complex), **common))
    psi_zero_V = compute_psi(MaxwellSpec(
        j_sites=np.array([0]),
        V_sites=np.zeros((1, 1, 1), dtype=complex), **common))
    np.testing.assert_allclose(psi_free, psi_zero_V, rtol=0.0, atol=TOL)
