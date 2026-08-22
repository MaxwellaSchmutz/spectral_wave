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

## `PAPER_NOTES.md`

Errors found in the three papers and the algorithm spec, each verified by a second agent
whose job was to refute it, and most backed by a number. Section 1 is grouped by paper and
ordered by severity, and includes a **"checked and CORRECT — do not let anyone fix these"**
list, which matters as much as the error list. Section 2 is twelve questions ready to paste
into an email, each answerable in a sentence or two. Section 3 is the convention table
across all four documents; section 4 is what could not be checked.

## `LEVINSON_PLAN.md`

**Start here for phase two.** The operational plan: what the Levinson integral is, exactly
what formula applies to *this* operator, how far the code already is, and nine ordered steps
from here to a working computation. It supersedes `LEVINSON_GUIDE.md` wherever the two
disagree — in particular on the sign, where it has the measurement and the guide does not.

Three results worth knowing before you read anything else:

- **`det S_repo(E) = conj(det S_BFNS(E))`.** The repo's scattering matrix is the complex
  conjugate of the literature's, for a structural reason (with `Im z > 0` and `e^{−itE}`,
  `z^n` is left-moving), so windings come out with the opposite sign. Calibrate once against
  a known case rather than trusting either convention.
- **Eigenvalues can sit *inside* the band once the `a_l` differ.** For `A = 1` the literature
  proves they cannot; that protection is gone here. Worked counterexample at `a = (1.3, 0.4)`.
  A bound-state count that only looks outside the band will be wrong.
- **Levinson appears in papers 1–3 only in the bibliographies, never in a body**, and no
  published theorem covers this model. Schober is pointing at the gap between his own papers
  and the literature they cite.

## `LEVINSON_GUIDE.md`

The learning path for the next phase. After Schober confirmed the `S^E` result he proposed
computing the **Levinson integral**, explicitly because the code can now produce `S^E` and
its determinant. This guide builds from the argument principle — which you already have
from complex analysis — to the actual formula, with a numerical exercise against this repo
at each step, and a two-week and three-month plan.

The target result is Ballesteros–Franco–Naumkin–Schulz-Baldes, *Levinson theorem for
discrete Schrödinger operators on the line with matrix potentials having a first moment*
([arXiv:2211.05021](https://arxiv.org/abs/2211.05021), Thm 4) — almost certainly the
`[BFNS24]` in paper 1's bibliography. Note it assumes `A = 1`, so all channels open and
close together. This project is the case where they close one at a time, which is where the
new mathematics is and why Schober wants it.
