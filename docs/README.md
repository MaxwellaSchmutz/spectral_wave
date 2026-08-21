# Documents

## The spec the code implements

**`MaxwellAlgorithm.pdf`** — Schober, April 25 2026. The ten algorithm steps and the
"Data" block (items a–f) that `spectral/maxwell/model.py:MaxwellSpec` mirrors field for
field. This is the authoritative document: where it and the theory papers disagree, this
is what the code follows, except for the four deviations listed in the root `README.md`
under "Algorithm status".

Two known defects in it, both raised with Schober and unanswered as of 2026-08-21:

- Steps 8 and 10 transpose the indices on `w` (step 8 writes `w^{E,±}_{l,σ}`, step 10
  writes `w^{E,σ}_{l,±}`). Matching superscript to superscript gives Interpretation 2,
  which is what he ruled and what the code does.
- Step 10's `±` is never bound by anything. That is A.12.

## The theory, in `papers/`

Three drafts by Ballesteros Montero & Schober, July 2025. Read in order — each imports the
previous one's main theorem as a black box.

| | Builds | Key result |
|---|---|---|
| **`1_JostSolutions.pdf`** | the Jost solutions `u^{E,σ}_τ` | Thm 3.3 + 3.7: existence, uniqueness, analyticity in `E`, via a Neumann series on a Volterra kernel |
| **`2_LimitingAbsorptionPrinciple.pdf`** | the Green's function, the LAP, the scattering matrix `S_E` | Lemma 3.1.4 + Thm 3.2.1: the resolvent kernel stays continuous down onto the real band |
| **`3_GeneralizedFourier.pdf`** | the generalized Fourier transforms `F_±` | Thm 2.2.5: `F_±^* F_± = P_ac(H)`, `F_± H = M_E F_±`, `F_± F_±^* = 1`. Schober: *"The whole reason why you do what you do."* |

The repo's `psi(n,t)` is the inverse of that last theorem — the eigenfunction expansion
run backwards, with `e^{-iEt}` supplying the only time dependence.

**Not in this repo:** `[BS25]`, *"Construction of scattering matrices with varying
dimension…"*, which paper 2 cites for several primitives (`Prop. A.3.2(f)`, `Def. 2.1.7`,
…). Its numbering matches no document here, so those citations currently resolve to
nothing. Asking Schober for it is item 8 of the draft message in `AUDIT.md`.

## Correspondence

**`memo2_draft.md`** — the memo that raised A.10, A.11 and A.12, plus the smaller
normalisation and frame-width questions.

**`professor_response.txt`** — Schober's 2026-08 reply, ruling on all three. This is the
authority cited by the A.10 and A.11 commit (`9e319a0`) and by the docstrings in
`spectral/maxwell/green.py` and `evolve.py`.

> Careful with lines 51–52 of that file. The step-1 simplification
> (`z_l = e^{-i arccos(E/2a_l)}`, giving `Im z < 0`) contradicts the step-3 simplification
> (`ν_l = 1/sqrt((2a_l)^2 - E^2)`, which is positive) by exactly a sign, and the algorithm
> PDF sides with step 3 — it says explicitly "the solution with `Im(z) > 0`". The code uses
> `Im z > 0`. Do not apply line 51 literally; it would negate the antisymmetric `s`-kernel
> and propagate through steps 4–10.

## `AUDIT.md`

Full audit of the repo, 2026-08-21 — what is verified and to what precision, what is still
open, a drafted message to Schober (§4), what to show him (§5), and the action list that
needs no ruling (§7). Start at §1.
