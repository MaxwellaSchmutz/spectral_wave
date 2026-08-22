# The Levinson Integral — a learning guide for Maxwell Schmutz

**Written for how you actually work.** You found three real errors in Jonas's algorithm by
tabulating numbers and comparing them, and you established that the two eigenfunction branches
differ by `S^E` the same way. That method is not a lesser method. It is how this particular
subject was built, and it is going to work again here. Nothing below asks you to become a
functional analyst. Levinson needs the argument principle, a determinant, and care at exactly
two points.

Everything numerical in this guide I ran myself against your repo at
`C:\Users\maxwell.schmutz\development\spectral_wave` before writing it down. The numbers quoted
are numbers I got. If yours differ, one of us is wrong and that is worth finding out.

---

## 0. The one-sentence version

**Levinson's theorem says: the number of bound states equals a winding number of `det S^E`.**

You already know winding numbers. That is the whole trick.

Here is the target, stated exactly, from Ballesteros–Franco–Naumkin–Schulz-Baldes,
*Levinson theorem for discrete Schrödinger operators on the line with matrix potentials having a
first moment* ([arXiv:2211.05021](https://arxiv.org/abs/2211.05021), Theorem 4). This is almost
certainly the `[BFNS24]` in paper 1's bibliography — same group, same operator, one step behind
your problem:

```
2 pi i ( J_b + (1/2) J_h  -  L )  =  - lim_{eps -> 0}  Int_{Gamma_eps}  det(S_z)^{-1} d/dz det(S_z) dz
```

- `J_b` = number of bound states (eigenvalues of `H` outside the band).
- `J_h` = number of *half-bound* states (threshold resonances). Usually 0. It is the hard part.
- `L` = your number of channels.
- `Gamma_eps` = the upper unit semicircle in `z`, i.e. the band swept once, with tiny arcs cut
  out around `z = ±1` (the band edges).

**I verified this formula numerically before writing it down.** L=1, single site `V(0)=0.5`:
`J_b = 1`, phase change of `det S` across the band `= 0.000000 π`, and `-2(J_b - L) = 0`. ✓
Three-site potential `{+6,−6,+6}`: `J_b = 3`, phase change `= −4.000000 π`, `−2(J_b−L) = −4`. ✓
Five more cases, all exact to 6 decimals.

**BFNS assumes `A = 1` — all channels open and close together.** Your project is the version
where `A = diag(a_1 ≥ … ≥ a_L)` and channels shut off one at a time. That is why Jonas wants it,
and that is where the new mathematics is. Read BFNS as "the answer for the easy case", not as
"the answer".

---

## 1. Argument principle → winding number

**What it is.** You have this already; here it is in the form you need. If `f` is holomorphic
inside and on a closed curve `Γ`, with zeros `Z` and poles `P` inside (counted with
multiplicity), then

```
(1/2 pi i) Contour-Int_Gamma  f'(z)/f(z) dz  =  Z - P
```

Concretely: walk `Γ` once, watch the point `f(z)` move in the plane, and **count how many times it
circles the origin**. That integer is `Z − P`. That is all a winding number is. You do not need
residue theory beyond this one statement.

**Why it's in your project.** This *is* Levinson. `f` will be the determinant of your Wronskian.
The zeros will be the bound states. The contour will be a loop around the band. There is no
second idea in the theorem.

**Where in the papers.** Paper 2 uses it without naming it: Lemma 2.3.9 (p.13) says the set where
the Wronskian fails to be invertible is *discrete*, which is the identity theorem — a holomorphic
function that is not identically zero has isolated zeros. Prop 2.3.12 (p.15) repeats it for `D`.

**Minimum.** Statement above + "isolated zeros" + the fact that `arg f` unwrapped along the
contour, divided by `2π`, is the same number. Skip: Rouché, the residue calculus, meromorphic
function theory.

**Resource.** Ahlfors, *Complex Analysis* 3rd ed., Ch. 4 §5 (The Calculus of Residues) —
5 pages. If you want the picture first: Needham, *Visual Complex Analysis*, Ch. 7 (Winding Numbers
and Topology).

**Exercise (20 min, no repo).**
```python
import numpy as np
p = np.poly1d([1, 0, -0.09, 0, 0.0004])       # pick any polynomial
th = np.linspace(0, 2*np.pi, 20000, endpoint=False)
z  = 1.5*np.exp(1j*th)
v  = p(z)
w  = (np.unwrap(np.angle(v))[-1] - np.angle(v)[0] + np.angle(v[0]/v[-1])) / (2*np.pi)
print(w, len(p.roots[np.abs(p.roots) < 1.5]))
```
Get the same integer twice. Then make the contour pass *through* a root and watch it break —
that failure is the whole reason the band edges need special treatment later.

---

## 2. Determinant, because `W` and `S` are matrices

**What it is.** `det` is the scalar that turns an `L×L` matrix into something you can wind.
`det M = 0` ⟺ `M` is singular ⟺ `M` has a nontrivial kernel.

**Why it's in your project.** Your Wronskian `W` is `L×L` (`wronskian.py` returns shape
`(2,2,n_E,L,L)`). Your `S^E` is `2|J^E| × 2|J^E|`. A winding number needs a *complex number*
tracing a curve, so every statement in Levinson is about `det W` and `det S`, never `W` and `S`.

**Correction worth having:** you will see the Wronskian described as "vanishes exactly when the
solutions are dependent, so `W ≠ 0` certifies a basis". For a matrix-valued Wronskian that is
wrong. It is **`det W = 0`** that signals dependence, and **`W` invertible** that certifies the
basis. `green.py:53-54` inverts `W`; it does not test `W ≠ 0`.

**Minimum.** `det(AB) = det A det B`; `det M ≠ 0` ⟺ invertible; `det` is a polynomial in the
entries, hence holomorphic wherever the entries are. That last one is the entire reason this works.

**Exercise (10 min).** Run your existing pipeline on the author config and print `det W`:
```python
import numpy as np
from spectral.maxwell.channels import channel_momenta
from spectral.maxwell.jost import compute_jost
from spectral.maxwell.wronskian import compute_wronskians
a=np.array([2.,1.]); j=np.array([0,4])
V=np.array([[[0.,1.],[1.,0.]],[[5.,0.],[0.,-3.]]],dtype=complex)
lat=np.arange(-12,13); E=np.linspace(-1.9,1.9,401)
W=compute_wronskians(compute_jost(channel_momenta(E,a),a,j,V,lat),a,0)
d=np.linalg.det(W[0,1])
print(np.abs(d).min(), np.abs(d).max())
```
I get `min |det W| ≈ 21.2` on `[-1.9, 1.9]` — it never comes close to zero. That is the statement
"there are no resonances *on* the band for this potential", i.e. `D ∩ band = ∅`, which is paper 2's
standing assumption `E ∉ 𝔇`. You have just measured it.

---

## 3. Where the contour lives

**What it is.** Two pictures, and you need both.

*Per channel:* `E = a_l (z + 1/z)`. This maps the **open unit disc `|z| < 1` bijectively onto the
complex plane with the segment `[-2a_l, 2a_l]` removed**, sending `z = 0` to `E = ∞`. The unit
circle `|z| = 1` maps onto the segment, twice (upper semicircle = one pass, lower = the way back).
That is the branch cut. Your `channels.py:31` picks the `Im z > 0` root, which is the upper
semicircle — the band, approached from one side.

*For the whole operator:* the `a_l` differ, so there is no single `z`. The right domain is the
**complex `E`-plane with `[-2a_1, 2a_1]` removed**. Off that segment *every* channel is closed
(`|z_l| < 1` for all `l`), everything decays, and the Jost solutions are honest holomorphic
functions of `E`. Your contour is a loop around that segment.

**Why it's in your project.** The bound states live on the real axis *outside* `[-2a_1, 2a_1]`.
Levinson's contour has to enclose them, so it has to leave the band. Your entire codebase currently
lives *on* the band (`model.py:99-107` forbids anything else). Step one of this project is getting
off it.

**Where in the papers.** Paper 1 Def 2.3 + Remark 2.4 (pp.5–6) define `z_σ` and its two branch
cuts. Def 2.6 (p.8) assembles `Z_σ(E) = diag(z_σ(E/a_k))`. Paper 2 Prop 2.1.4/2.1.9 (pp.4–5) are
the same statements quoted from `[BS25]`.

**Minimum.** The one map `E = a(z + 1/z)` and which root is which. **Do not** read paper 1
Section 4 (pp.21–24). It is a stub: its only real proposition, Prop 4.6, has `...[TODO]` twice
where the proof should be, the section never states its own conclusion, and the claim
`F^E_σ(−Y) = F^E_σ(Y)^{-1}` that gets quoted from it is false except exactly at thresholds.
Skip Riemann surfaces entirely — you need one conformal map, not a theory.

**Resource.** Needham, *Visual Complex Analysis*, Ch. 2 §§4–6 for `z + 1/z` with pictures. Ten
pages, and they are the right ten.

**Exercise (30 min).** Write `Z_inside(E)` returning, for complex `E`, the root of
`z + 1/z = E/a_l` with `|z| < 1`:
```python
def Z_inside(E, a):
    b = np.atleast_1d(np.asarray(E, complex))[:, None] / np.asarray(a, float)[None, :]
    r = np.sqrt(b - 2.) * np.sqrt(b + 2.)
    z1, z2 = 0.5*(b - r), 0.5*(b + r)
    return np.where(np.abs(z1) <= np.abs(z2), z1, z2)
```
Check three things: (a) `a*(z + 1/z) == E` to 1e-15; (b) `|z| < 1` for every `E` off
`[-2a_1, 2a_1]`; (c) on the band it agrees with `channel_momenta` up to `z ↔ 1/z`. Then confirm
the thing that matters: **`|z_l| = 1` only for OPEN channels.** At `a = (2,1)`, `E = 2.5`,
channel 1 has `|z| = 1` and channel 2 has `|z| < 1`. Closed channels are not on the circle. That
asymmetry is the whole subject of these three papers.

---

## 4. Holomorphy — and the one line in your code that breaks it

**What it is.** The argument principle needs `f` holomorphic. `conj(z)` is not. Neither is
`Im z`, `|z|`, or `M*` (conjugate transpose).

**Why it's in your project — two concrete bugs waiting for you.**

**(a) `density_of_states` is not holomorphic.** `channels.py:40` computes
`nu = 1/(2 a_l Im z_l)`. `Im z` is fine on the band and meaningless off it. The holomorphic
continuation is

```
nu_l(z) = i / ( a_l ( z - 1/z ) )
```

which I checked agrees with your version to machine precision on the band. Note where it blows up:
`z = ±1`, i.e. `E = ±2a_l` — **the thresholds**. Your `threshold_buffer` in `model.py:12` was added
for numerical hygiene. It is guarding exactly the two points that carry the `1/2` in Levinson's
theorem. That is not a coincidence and it is worth sitting with.

**(b) `wronskian.py` uses `*`, and `*` is not holomorphic.** Lines 56–57 take
`np.conj(np.swapaxes(...))`. Paper 2's Def 2.3.1 (p.11) actually reads
`W(u,v) = i[u(n+1)* A v(n) − u(n)* A v(n+1)]` where the **first argument is a solution at the
conjugate energy `Ē`** (the overline is in the PDF; every text extractor drops it, which is how
this gets missed). On the real band `Ē = E` and conjugating is harmless. Off the band it is fatal.

The fix is two changes, and I ran them:
- **transpose instead of conjugate-transpose** (`.T`, not `.conj().T`), and
- **same `sigma` index on both factors** instead of `sigma` / `other_sigma`.

**I verified all of this.** Author config `a=(2,1)`, `V` = the two matrices from
`tests/test_maxwell.py`:

| check | result |
|---|---|
| shipped `W[0,1]` vs transpose-paired same-σ, on the band | agree to **1.21e-14** (scale 6.4) |
| transpose-paired `W`, at complex `E = 7+3i`, independence of anchor site `n` | **1.16e-15** |
| shipped `W`, off the band | not anchor-independent — it is not a Wronskian there |

So: **your `W[0,1]` on the band already *is* the analytic object.** You do not need a new theory,
you need `.T`.

**Minimum.** "Conjugation is not holomorphic; transpose is." That is the whole content.

**Where in the papers.** Paper 1 Thm 3.7(a) (p.19): `E ↦ u^{E,σ}` is holomorphic on
`int(O^σ_α)` — verified correct. Paper 2 Prop 2.3.3 (p.11): the Wronskian is independent of `n`,
which is what you just measured at `1.16e-15`.

**Exercise (1–2 hrs — this is the real one).** Copy `wronskian.py` to `wronskian_analytic.py`,
make the two changes, monkeypatch `spectral.maxwell.kernels.density_of_states` to the holomorphic
`nu`, feed it complex `Z` from your `Z_inside`, and confirm anchor-independence at
`E = 7 + 3i`. When the spread drops to ~1e-15, you are off the real axis for the first time.

---

## 5. The Jost function: `det W` vanishes exactly at bound states

**What it is.** `u_+` decays to the right, `u_−` decays to the left (off the band, with
`|z_l| < 1`, both really do decay). A **bound state** is a solution that decays in *both*
directions — so it exists exactly when `u_+` and `u_−` are linearly dependent, i.e. exactly when
`det W(E) = 0`. That function `E ↦ det W(E)` is the **Jost function**. It is holomorphic off the
band, and its zeros are the bound-state energies. Nothing more.

**Why it's in your project.** This is the function you wind. Everything else is plumbing.

**I verified this in your code.** With the two fixes from §4, author config `a=(2,1)`:

```
L=2 bound states, found independently by diagonalising H on 801 sites:  E = 6.40315466
|det W| at E = 6.40315466      :  2.50e-13      <- zero
|det W| at E = 6.70315466      :  3.46e+00      <- not zero
```

And for L=1 with a three-site potential `{+6,−6,+6}`: bound states at `E = −6.166667, +6.166667,
+6.324555`, and `|det W|` at those three energies came out `3.6e-13, 4.1e-16, 2.1e-15`. Three
zeros, three bound states. Exactly.

**Where in the papers.** Paper 2 Def 2.3.1 (p.11), Lemma 2.3.9 (p.13, discreteness), Def 2.2.3
(p.8, the set `D`). **The important gap:** paper 2's Def 3.1.1 (p.15) restricts to `E ∉ 𝔇` and
inverts `W`, but `𝔇` is **never defined anywhere in the paper** and nothing proves `W` is
invertible. That undefined set is exactly the zero set of `det W` — that is, exactly the thing
Levinson counts. Your project and that gap are the same object.

**Minimum.** The sentence in bold above. Skip: transformation operators, Gel'fand–Levitan–Marchenko,
inverse scattering.

**Resource.** Teschl, *Jacobi Operators and Completely Integrable Nonlinear Lattices*, free PDF at
<https://www.mat.univie.ac.at/~gerald/ftp/book-jac/> — **Chapter 12, §12.1–12.2**. This is the
scalar (`L=1`) version of your entire problem, written cleanly, and it is the best 15 pages
you can read for this project. Everything you are doing is the matrix generalisation of it.

**Exercise (1 hr).** For the author config, diagonalise `H` on a big finite lattice, collect the
eigenvalues outside `[-2a_1, 2a_1]`, and evaluate your new `det W` at each. Then at each ± 0.3.
Two number tables. Compare. You have done exactly this before.

---

## 6. The pole at infinity — that's the `−L`

**What it is.** As `E → ∞`, all `z_l → 0` and the free Wronskian behaves like
`prod_l a_l(1/z_l − z_l) ~ E^L`. So `det W` grows like `E^L`, which on the Riemann sphere is a
pole of order `L` at `∞`.

**Why it's in your project.** Apply the argument principle on a big circle `|E| = R`:
```
winding of det W on |E| = R  =  L
```
and separately, deforming that circle down onto the band, `L = J_b + (contribution from the cut)`.
Rearranged, the cut contribution is `L − J_b`. **That is the `−L` in BFNS Theorem 4.** It is not a
convention or a fudge; it is the order of a pole at infinity, and you can measure it.

**I verified it.** Author config, `L = 2`:
```
winding of det W on |E| = 40:  +2.0000    (= L)
```
And for L=1 with `J_b = 3`, using the disc picture, the winding of `det W` on `|z| = 0.995` came
out `+2.0000 = J_b − L = 3 − 1`. Both halves of the bookkeeping, measured.

**Minimum.** "Pole of order `L` at `E = ∞`, and that's the `L` in the formula." One sentence.

**Exercise (30 min).** Wind `det W` on `|E| = 40` for `L = 1` and `L = 2`. Get `1.0000` and
`2.0000`. This is the cheapest confidence you will buy all project.

---

## 7. Boundary values, `±i0`, and why `det S = conj(det W) / det W`

**What it is.** On the band there is no bounded inverse `(H − E)^{-1}` — that is what "`E` is in
the spectrum" means. But `(H − E ∓ iε)^{-1}` exists for `ε > 0`, and the limits as `ε ↓ 0` from
**above** and from **below** both exist and **are different**. `G^{E,+}` and `G^{E,-}` are those
two boundary values. Your `outer_sign` is which side you stand on.

Because the coefficients are real, `det W` on the lower edge of the cut is the conjugate of
`det W` on the upper edge (Schwarz reflection). The scattering matrix is exactly the ratio:

```
det S(E)  =  conj(det W(E)) / det W(E)     (up to the free normalisation)
```

so `|det S| = 1` automatically — that *is* unitarity — and
`arg det S = −2 arg det W`. **The winding of `det S` around the band is minus twice the winding
of the Jost function.** That single line is Levinson.

**Why it's in your project.** This is also the answer to the thing you already found. The two
`outer_sign` branches are the two sides of the cut; they differ by `S^E` because `S^E` is
literally the ratio of the two boundary values. Jonas's "the two videos should differ by `S^E`"
and Levinson's theorem are the same fact, read twice.

**Where in the papers.** Paper 2 Def 3.1.1 (p.15) + Theorem 3.1.3 (p.17) build `G^{E,σ}`; your
`green.py` implements it and matches to 2.1e-15. Paper 3 Thm 2.4(c) (p.5) defines `w_{l,±}` as
the `∓iε` limits; `outer_sign = +1` is paper 3's `w_{l,+}`, the retarded branch (checked to
`O(ε)`: 4.2e-3 / 4.2e-5 / 4.2e-7 as `ε` shrinks). Paper 3 Thm 4.4 (p.24) is
`F_- = (∫^⊕ S^E dE) F_+` — your two branches, differing by exactly `S^E`.

**Minimum.** "No bounded inverse on the band; the two one-sided limits differ; their ratio is
`S`." Do **not** read up on the limiting absorption principle proof. Paper 2's Theorem 3.2.1
proves it, its Eqs. (14)/(15) have a `σ → −σ` slip (harmless — the slip is consistent, so parts
(c) and (d) are still true), and none of it is on the path to Levinson.

**Exercise (45 min).** On the band, compute `d = np.linalg.det(W[0,1])` on a fine `E` grid and
form `dS = np.conj(d)/d`. Check `|dS| = 1` to 1e-15. Then `np.unwrap(np.angle(dS))` and look at
the total change. For a potential with no bound states beyond the trivial count you should get
`≈ 0`; add a strong site and watch it jump by `−2π`. That jump is one bound state appearing.

---

## 8. The band edges: the `1/2`, and where this project gets hard

**What it is.** At `E = ±2a_l` the two roots collide (`z_l → ±1`), the group velocity vanishes,
`nu_l → ∞`, and `Z_σ − Z_σ^{-1}` becomes singular. In the disc picture, `det W` has **poles on the
contour** at `z = ±1`. You cannot integrate through a pole — you indent around it, and an
indentation that goes halfway around a simple pole contributes **half** a residue. That is the
`1/2 J_h` in BFNS Theorem 4, and it is why my L=1 measurement gave phase change `0` for a
potential with `1` bound state: `1 − 1/2 − 1/2 = 0`.

A **half-bound state** is a solution that is bounded but not decaying, existing exactly at a
threshold. Generic potentials do not have them. When one appears, the half-residue changes and
the count shifts by `1/2`.

**Why it's in your project.** Your `A = diag(a_1 … a_L)` has `2L` thresholds, not 2, and they are
*interior* to `[-2a_1, 2a_1]`. At each `±2a_l` one channel closes and `S^E` **changes dimension**.
Nobody has done Levinson in that setting. That is the research.

**Where in the papers, and the honest state of it.**
- Paper 1 Prop 2.7(d) (p.9): `Z_σ − Z_σ^{-1}` is singular exactly at `E/a_k = ±2`. Correct, and
  it is the poles-at-`z = ±1` statement.
- Paper 1 Def 3.4 (p.18): **the constant `C_E` has a sign error at every NEGATIVE threshold.** The
  `P^E_=` coefficient should be `−Z_σ P^E_=`, not `−P^E_=`. With the printed version, at
  `E = −2a_k` the kernel returns `−δ` instead of `+δ` and the residual is `2.000` instead of
  `3e-16`. This was confirmed analytically and numerically by two independent readers. **The
  region your code has never entered is also the region the paper has not finished.** If your
  Levinson contour crosses a negative threshold, you are the first person to use that machinery.
- Paper 1 `P^E_1` (used in Def 3.4, Lemma B.2, B.3, and the Prop 3.6(b) proof) is **never defined
  in the paper**. Reconstructed meaning: projection onto the strictly-open channels
  (`|z_σ(E/a_k)| = 1`, thresholds excluded). Ask.
- Paper 2 Thm 3.2.1 (p.20): the limiting absorption principle is claimed on
  `[-2a_1, 2a_1] \ 𝔇`. At `E = ±2a_k` the bound the proof uses is `‖(iω^{E,σ})^{-1}‖ = ∞`.
  Reading `𝔇` as "where `W` is singular" the thresholds *are* excluded — but `𝔇` is never defined,
  so nobody can tell.
- **The single most useful sentence in all three papers for you** is a referee note in red on
  paper 2, p.30: *"What do you do with the inverse of `M^E_σ`?"* Corollary 4.2.3(b)'s analytic
  continuation needs `det M^E_σ ≠ 0` off the real axis, and the only proof of invertibility
  (Lemma 4.1.5(d)) uses `W(b,b) = −σ1`, which holds only for real `E`. **That open question is
  your project.** Bring it up with Jonas.
- Correction to something you may have been told: `C_E` does **not** blow up at thresholds. It is
  finite there by construction — that is what the `n P^E_=` term in `ψ` is for. What degenerates
  is `Z_σ − Z_σ^{-1}`.

**Minimum.** "Poles on the contour; indent; half a residue each; that's the `1/2`." Then read
[arXiv:2008.02177](https://arxiv.org/abs/2008.02177) (Ballesteros–Franco–Garro–Schulz-Baldes,
*Band edge limit of the scattering matrix for quasi-one-dimensional discrete Schrödinger
operators*) — very likely paper 1's `[BFGS22]`. It is an entire paper about just this one point.
That tells you how hard it is.

**Exercise (2 hrs).** For L=1, `V(0) = v`, sweep `v` from `0.01` to `10` and plot both
(i) `J_b` from diagonalisation and (ii) `1 + (1/2π)·Δ arg det S` across the band. They should
agree at every `v`. Then engineer a half-bound state (tune a two-site potential so a bound state
is just about to detach at `E = 2`) and watch the count go to a half-integer. When that happens
you have seen `J_h ≠ 0` with your own eyes, which almost nobody has.

---

## 9. `S^E` from `M` and `N`, and where `det` actually comes from

**What it is.** Paper 2 Def 4.1.6 (p.28), confirmed by rendering the page at 320 dpi:

```
S^E  =  [  (M^E_+)^{-1}              -N^E_- (M^E_-)^{-1}  ]
        [ -N^E_+ (M^E_+)^{-1}         (M^E_-)^{-1}        ]
```

`M^E_σ` and `N^E_σ` are the coefficients in Def 4.1.4 (p.26) expanding one normalised Jost basis
in terms of the other. Prop 4.2.1 (p.28) proves `S^E` unitary; Remark 4.1.7 says `S^E` is exactly
the change of basis between `(b^{E,+}_-, b^{E,-}_+)` and `(b^{E,+}_+, b^{E,-}_-)` — which is your
`outer_sign` result, stated as a theorem.

Take the Schur complement of that block matrix (`det [[A,B],[C,D]] = det A · det(D − C A^{-1} B)`
with `A^{-1} = M^E_+`):

```
det S^E  =  det(M^E_+)^{-1} · det(M^E_-)^{-1} · det( 1 - N^E_+ N^E_- )
```

So the winding of `det S^E` is controlled by **`det M^E_σ`** — which is why that red referee note
on p.30 is the crux, and why `det M^E_σ` is the matrix-valued Jost function.

**Why it's in your project.** Jonas said, verbatim: *"For this we actually need the determinant
and everything you did."* This is that determinant. `S^E` is **not implemented in your repo yet**.
Building it is the first deliverable.

**Important index note.** `[BS26b]`/paper 2's Def 4.1.6 displays `S^E` as a 2×2 block matrix in
`σ` with `|J^E|×|J^E|` blocks in `l`, so the ordering of the pair index `(l, σ)` is
**σ-major, l-minor**. Paper 3's Def 4.2 (p.23) never states an ordering — use paper 2's.

**Also worth knowing (verified by two independent readers, so don't re-litigate it):** Lemma 4.1.3
in paper 2 is still titled *"sign problem"* in red, and Lemma 4.1.5(b) has a struck `−σ` replaced
by `σ`. **The statements are correct and the edit is correct** — checked to ~1e-13 at L=1,2,3.
`S^E` is unitary to `≤1.2e-14` with `|det S^E| = 1.000000000000`. There is no sign bug in §4.

**Minimum.** Def 4.1.4, Def 4.1.6, Prop 4.2.1, Remark 4.1.7 — four items, six pages
(pp. 26–29). That's the whole section you need.

**Exercise (a full weekend — this is deliverable #1).** From your `compute_jost` output, build the
normalised basis `b^{E,σ}_τ` of Def 4.1.1, extract `M^E_σ` and `N^E_σ` per Def 4.1.4 by solving
the linear system, assemble `S^E` per Def 4.1.6. Then check, on the author config:
`‖S* S − 1‖ < 1e-13` and `|det S^E| = 1.000000000000`. Third check: verify the Schur formula above
numerically against `np.linalg.det(S)`. Fourth: confirm `S^E` really is the change of basis
between your two `outer_sign` eigenfunction families — you already know it is; now you will have
the matrix.

---

## 10. Assembling the integral

Once §§4–9 are done, Levinson is bookkeeping:

1. Sweep `E` across `[-2a_1, 2a_1]`, skipping small windows around each threshold `±2a_l`.
2. Compute `det S^E` at each node (dimension `2|J^E|`, which drops as you cross thresholds).
3. `np.unwrap(np.angle(...))` **within each threshold-bounded window separately**, and sum the
   changes.
4. `J_b + (1/2)J_h = L + (1/2π) · Σ (phase changes)`, with the sweep running `−2a_1 → +2a_1`.
5. Independently: diagonalise `H` on a big finite lattice, count eigenvalues outside the band.
6. Compare the two integers.

**I verified steps 1–6 in the decoupled multi-channel case** (`A = diag(2,1)`, `V` diagonal, so it
splits into two scalar problems), which is the sanity check you should hit first:

```
thresholds: [-4, -2, 2, 4]
bound states per channel: [3, 1]   total J_b = 4
  [-4.000,-2.000] open=[1]     dArg/2pi = +0.812692
  [-2.000,+2.000] open=[1,2]   dArg/2pi = +0.633414
  [+2.000,+4.000] open=[1]     dArg/2pi = +0.552930
  sum = +1.999036     L + sum = 3.999036     J_b = 4     <- agrees
```

Note the three window contributions are ugly irrational numbers and the *sum* is an integer. That
is the signature of a topological quantity and it is a very satisfying thing to watch happen.

**The honest open question:** in the *coupled* case, does `det S^E` behave well enough at an
interior threshold for step 3's window-by-window unwrapping to be legitimate? `det S^E` may
genuinely jump when the dimension drops. Nobody has proved it doesn't. **This is the actual
research content**, and it is exactly the question Jonas is asking you to explore. Do the
decoupled case first so you know what "right" looks like, then turn on the off-diagonal coupling
and see what breaks.

---

## Errata worth carrying (short list, this project only)

- **`Σ_n ψ(n,t)` is only conserved because your `psi` array is already a density.** The conserved
  quantity is `Σ_n ‖ψ(n,t)‖²`, not the bare sum of amplitudes. Your `evolve.py` returns
  `(|amp|²).sum(-1)`, so summing it *is* the squared norm and your test is correct — but the
  statement "the sum of ψ is conserved" is not, and it will mislead you if you change what `psi`
  holds.
- **Your `psi` never sees bound states.** Paper 3 Thm 3.2.5(a): `F_±^* F_± = P_ac(H)`. The
  eigenfunction expansion covers only the absolutely continuous part. A single site `V(0)=0.8`
  already binds a state at `E = 2.154`, and 1–4% of a test vector's norm goes missing from
  `‖F_± f‖²`. Levinson is precisely the theorem that recovers the number of missing states from
  the part you *can* see.
- **`|z_l| = 1` only for open channels.** Closed channels have `|z_l| < 1`.
- **Don't tell Jonas `D` isn't closed.** Paper 3 writes `𝔇̄` (with an overline) in exactly the
  places closedness is needed — 14 of them. Text extraction eats the bar. Same for `ℂ̄_σ`: all 9
  occurrences carry the closure bar, so "is it the open or closed half-plane" is already answered
  in the PDF.
- **`τ_A = 1` does not mean `A` is unitary**, only that `A` is a *scalar multiple* of a unitary
  (`A = 2·1` gives `τ_A = 1`). Paper 1 p.3/p.4 says "unitary" — it is a small false sentence.
- Your `channel_momenta` (`Im z > 0`) is paper 1's and paper 2's **`z_−`**, not `z_+`. Worth a
  comment in the code before you start indexing by `σ` against paper 2.

---

## What is genuinely hard vs. easier than it looks

**Easier than it looks.**
- The argument principle part. One theorem you already have, applied once.
- Getting your code off the real axis. **Two line-level changes**, both verified above:
  `.T` instead of `.conj().T`, and the holomorphic `nu`. That was the part I expected to be hard
  and it took twenty minutes.
- `det W = 0` ⟺ bound state. It falls out; it needs no analysis.
- `S^E` unitarity. Linear algebra, already checked by three people, no sign bug.
- The `−L`. It is a pole order. You can measure it in five lines.

**Genuinely hard.**
- **The band edges.** `[BFGS22]` is an entire published paper about the limit of `S` at `E = ±2`.
  Half-bound states, the `1/2`, and the indentation are real analysis and they resist intuition.
- **Varying multiplicity.** What `det S^E` does when its dimension drops at an interior threshold.
  Unsolved. This is the point of the project.
- **Proving `det M^E_σ ≠ 0` off the real axis.** Paper 2's own referee flagged it in red on p.30
  and it is unresolved in the draft.
- Not hard, but relentless: **index conventions.** `σ` means the branch label, and also the
  spectrum (`σ(2A)`), sometimes in the same displayed line. `τ`, `σ`, `l`, `±`, `outer_sign` and
  paper 3's leading `σ` in Def 2.2 all interact. Write a one-page dictionary early and keep it.

**Don't waste time on** (none of it is on the path): Banach–Alaoglu and weak convergence; direct
integrals; the spectral theorem beyond "eigenvalues are real"; Fredholm theory; Plancherel;
polar decomposition; trace class beyond "V is compact so the essential spectrum doesn't move";
the whole of paper 1 §4; paper 2 §3's proofs; paper 3 §3.2's four pages of Poisson-kernel
bookkeeping.

---

## If you read three things, read these

1. **Teschl, *Jacobi Operators*, Ch. 12 §§12.1–12.2** — free PDF at
   <https://www.mat.univie.ac.at/~gerald/ftp/book-jac/>. About 15 pages. The scalar version of your
   entire problem: Jost solutions, the Wronskian, the Jost function, transmission and reflection.
   Everything you are building is the `L×L` version of these pages.
2. **Ballesteros–Franco–Naumkin–Schulz-Baldes, [arXiv:2211.05021](https://arxiv.org/abs/2211.05021),
   Theorem 4** — the Levinson theorem you are being asked to generalise, in your exact operator
   setting minus the hopping matrix. Read the introduction and Theorem 4; skip the proofs on the
   first pass. This is almost certainly paper 1's `[BFNS24]`.
3. **Ahlfors, *Complex Analysis*, Ch. 4 §5** — five pages, to make the argument principle
   reflexive rather than remembered. If you'd rather have pictures, substitute Needham Ch. 7.

Fourth, when you get to the band edges: **[arXiv:2008.02177](https://arxiv.org/abs/2008.02177)**
(Ballesteros–Franco–Garro–Schulz-Baldes, band edge limit of `S`), very likely `[BFGS22]`.

---

## Two-week plan (≈ 10 evening-sized sessions)

Goal: **reproduce Levinson end-to-end at `L = 1`, in your own repo, with two independent number
tables that agree.**

| Day | Do |
|---|---|
| 1 | §1 exercise (polynomial winding). §2 exercise (`det W` on the band, author config). |
| 2 | Ahlfors Ch. 4 §5, or Needham Ch. 7. One hour, no code. |
| 3 | §3 exercise: write `Z_inside`, verify all three checks. |
| 4–5 | §4 exercise: `wronskian_analytic.py` + holomorphic `nu`. Target: anchor-independence `1e-15` at `E = 7+3i`. **This is the gate — everything after depends on it.** |
| 6 | §5 exercise at `L = 1`: `det W` zeros vs. diagonalisation. Two tables. |
| 7 | §6 exercise: winding of `det W` on `|E| = 40`. Get `1.0000`. |
| 8 | Teschl Ch. 12 §§12.1–12.2. |
| 9 | §7 exercise: `det S = conj(det W)/det W` on the band, `|det S| = 1`, unwrap the phase. |
| 10 | §8 exercise, first half: sweep `v`, plot `J_b` from diagonalisation vs. `1 + Δ arg/2π`. **Two curves, one integer staircase.** Send Jonas the plot. |

If day 4–5 stalls, that is the one to ask about — everything downstream needs it and the fix is
small.

## Three-month plan

**Month 1 — build `S^E`.** §9's exercise: `M^E_σ`, `N^E_σ`, `S^E`, unitarity to `1e-13`, the Schur
formula for `det S^E`, and confirmation that `S^E` is the change of basis between your two
`outer_sign` families. Add it to the repo as `scattering.py` with tests in the style of
`test_maxwell.py`. Deliverable: a `compute_S(spec, E)` Jonas can call. Along the way, send him the
short list of paper-2 questions: what is `𝔇`; what is `α` in `O^σ_α`; is `𝒮` supposed to be
`|Re z| > 2a_1` rather than `2a_L`; and the `σ → −σ` in Eqs. (14)/(15).

**Month 2 — the decoupled multi-channel case.** `A = diag(2,1)`, `V` diagonal. Reproduce the table
in §10: per-window phase changes that are irrational, summing to an integer, `L + sum = J_b`. Then
study what happens *near* an interior threshold — how fast does the phase move, how small can the
buffer be, does the sum converge as the buffer shrinks. Write it up as a two-page memo with the
number tables in it. That memo is the thing Jonas can present.

**Month 3 — turn on the coupling and find out what breaks.** Off-diagonal `V`, so channels mix and
`det S^E` genuinely changes dimension at `±2a_2`. Ask the concrete questions: does `det S^E` have a
limit as `E → ±2a_2` from each side? Is it continuous across, or does it jump by a computable
factor? Does `L + Σ` still land on an integer? Bring `det M^E_σ` into it — its zeros are what the
p.30 referee note is worried about, and if you can *plot* where they are for a coupled example you
will have said something nobody in the three drafts has said.

Do not try to prove anything in month 3. Compute, tabulate, compare, and tell Jonas what the
numbers do. That is the method that got you here and it is the right method for this too.
