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

Four drafts by Ballesteros Montero & Schober. Read in order — each imports the previous
one's main theorem as a black box.

| | Date | Builds | Key result |
|---|---|---|---|
| **`1_JostSolutions.pdf`** | 1 Jul 2025 | the Jost solutions `u^{E,σ}_τ` | Thm 3.3 + 3.7: existence, uniqueness, analyticity in `E`, via a Neumann series on a Volterra kernel |
| **`2_LimitingAbsorptionPrinciple.pdf`** | 2 Jul 2025 | the Green's function, the LAP, the scattering matrix `S^E` | Lemma 3.1.4 + Thm 3.2.1: the resolvent kernel stays continuous down onto the real band |
| **`3_GeneralizedFourier.pdf`** | **14 Aug 2026** | the transforms `F_±`, then `Ω_±` and `S` | **Thm 3.2.5(a), p. 20**: `F_±^* F_± = P_ac(H)`. Schober: *"The whole reason why you do what you do."* |
| **`4_Levinson.pdf`** | **12 Aug 2026** | relates `det S^E` to the bound and half-bound states | Thm 4.2.4, p. 27 — **draft in progress** |

The repo's `psi(n,t)` is the inverse of paper 3's expansion theorem — run backwards, with
`e^{-iEt}` supplying the only time dependence.

⚠ **Papers 1 and 2 here are the July 2025 copies, and they are out of date.**
`4_Levinson.pdf` cites 2026 revisions of both, which are not in this repo. Any erratum
written against these two may already be fixed. Ask for the current versions.

⚠ **Paper 3 was rewritten, not patched**, on 2026-08-14 — retitled *Wave and scattering
operators…* and renumbered end to end. Older notes in this repo cite labels that no longer
exist; `PAPER_NOTES.md` §1.3 has the mapping.

**Not in this repo:** `[BS25]`, *"Construction of scattering matrices with varying
dimension…"*, cited by paper 2 for several primitives (`Prop. A.3.2(f)`, `Def. 2.1.7`, …).
Its numbering matches no document here. It has been removed from paper 3 in the rewrite and
now survives only in paper 2.

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

Errata against the papers and the algorithm spec, each verified by a second agent whose job
was to refute it, and most backed by a number. Section 1 includes a **"checked and CORRECT
— do not let anyone fix these"** list, which matters as much as the error list.

**Read the version warning at the top before using any of it.** §1.3 (paper 3) and §2 (the
question list) were removed on 2026-08-24 — paper 3 was rewritten and five of the twelve
questions had gone stale, two of them asking about things the author had already removed.
§1.1 and §1.2 stand, but they are against July 2025 copies of papers 1 and 2 and a 2026
revision of each exists.

## Levinson — phase two, and why there is no document here yet

`papers/4_Levinson.pdf` is the work in progress: *"A Levinson-type theorem for Schrödinger
operators on a one-dimensional lattice with varying spectral multiplicity"*, Ballesteros
Montero & Schober, 12 August 2026. **It is a draft being actively written, not a settled
result.** It still carries `[BS26a, TODO]` citations for results it depends on.

Two documents used to sit here — `LEVINSON_PLAN.md` and `LEVINSON_GUIDE.md`, written
2026-08-21. **They were deleted on 2026-08-24 and should not be recovered.** They were
written before the draft was available, reconstructed a formula from the adjacent
constant-dimension literature plus numerics, and stated the relation with the **opposite
sign** to the draft:

    those docs   W = J_b + (1/2) J_h - L
    draft, p.3   (1/2 pi i) Int_{sigma(H_0)} det(S_E)'/det(S_E) dE = L - (J_b + (1/2) J_h)

They also asserted that no theorem covered this model, which was the wrong way to describe
a result the author was in the middle of writing. They are in git history at commit
`21b17ab` if anyone needs to see what was wrong, but nothing in them should be cited.

Anything written here in future must be grounded in `papers/4_Levinson.pdf` with page
references, must not restate the draft's results as established, and must keep numerical
measurements clearly separated from claims about what is proved.
