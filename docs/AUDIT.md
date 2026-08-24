# spectral_wave — Audit Report

**Date:** 2026-08-21 · **Scope:** whole repo — algorithm, papers, spec, GUI, numerics, tests
**Method:** 11 agents (7 parallel audits, 3 adversarial verifiers, 1 synthesis), plus direct
re-verification of every headline claim.

Numbers tagged **[v]** were reproduced independently against the working tree, from scripts
written separately from the agents that first produced them. Untagged numbers come from the
audit and were not independently re-run — treat them as strong but second-hand.

**`MaxwellAlgorithm.pdf` (Schober, April 25 2026) appeared in the repo partway through this
audit.** It is the authoritative spec, it settles three questions the audit had to leave
open, and it is read into every conclusion below.

> **Revised 2026-08-24.** Two documents arrived after this audit was written:
> `papers/4_Levinson.pdf` (12 Aug 2026, a draft in progress) and a **rewritten** paper 3
> (14 Aug 2026, retitled *Wave and scattering operators…*, renumbered end to end).
>
> The **measurements** below — residuals, probability sums, transfer-matrix agreement,
> preset behaviour — were re-checked and still hold. What changed is everything that
> *cites a paper*: §4 is now archived as sent-and-answered, §6 steps 1 and 3 are closed or
> moot, and §8 lost three items. Where this file names a theorem in paper 3, the label is
> from the superseded version; `PAPER_NOTES.md` §1.3 has the mapping.
>
> Nothing here should be read as a statement about the Levinson result. That is an
> unfinished draft the author is actively writing, and this audit predates it.

---

## 1. Bottom line

The algorithm is correct. Steps 1–8 reproduce hand-derived closed forms to ~3e-15;
transmission and reflection amplitudes match a transfer-matrix ground truth across 2040
cases to 3.2e-15. Schober's A.10 and A.11 rulings are both confirmed independently, and
A.11 is confirmed *from his own paper 2*.

**A.12 is not a bug.** Both `outer_sign` branches are exact, norm-preserving eigenbases —
each gives `(H−E)w = 0` to ~6e-16 and `Σ_n ψ = 1.000000000000` **[v]** — and they differ
by exactly the on-shell scattering matrix `S_E` that paper 3 says they must differ by.

The one thing needing Schober's ruling is **not a sign — it is an input convention.** His
tripwire is a theorem when the packet is specified as a state `ψ₀` with `f := F_± ψ₀`
(measured **4.3e-15** for L=1, **7.7e-15** for L=2 with complex-Hermitian V **[v]**), and
provably false when `f` is fixed data independent of `±` (measured **14 % / 42 % / 65 %**
**[v]**). His own spec, Data item (f), specifies `f` as fixed data — so under the spec as
written the two videos *must* differ, and the tripwire cannot pass.

---

## 2. What the spec settles

`MaxwellAlgorithm.pdf` resolves three items the audit could only reason around.

| Question | Spec text | Verdict |
|---|---|---|
| Which root in step 1? | *"We denote the solution with `Im(z) > 0` by `z_l(E)`."* | **The code is right.** `professor_response.txt` line 51 (`z_l = e^{−i·arccos(E/2a_l)}`, which has `Im z < 0`) is a slip. Do not adopt it. |
| Is `ν_l` positive? | Step 3: `ν_l := 1/(2 a_l Im z_l)` | With `Im z > 0` this is `+1/√((2a_l)²−E²)` — matches `professor_response.txt` line 52 exactly **[v]**, and matches the code to `0.0` **[v]**. Line 52 is right, line 51 is wrong; they cannot both stand. |
| Is `f` a state or fixed data? | Data (f): *"Functions `f_{l,σ} : [a,b] → C`"* | **Fixed data.** Given as input, not derived from a state. This is what makes the A.12 tripwire fail — see §4. |

It also confirms the energy restriction is *by design*, not a code limitation: Data item (e)
is `[a,b] ⊆ [−2a_L, 2a_L]`, the common open band. `model.py:94-103` enforces exactly this.

### Two genuine defects in the spec document

**(i) Steps 8 and 10 transpose the indices on `w`.** Step 8 defines `w^{E,±}_{l,σ}` with the
plane wave `z_l^{∓n}` driven by the *upper* `±` and the Green's function `G^{E,σ}` carrying
σ. Step 10 then writes `w^{E,σ}_{l,±}` — superscript and subscript swapped. Matching
superscript-to-superscript recovers Interpretation 2 (summed σ drives `z^{−σn}`, fixed `±`
selects the branch), which is what Schober ruled and what the code implements. But as
written the document contradicts itself, and this is the exact source of the original A.1
ambiguity.

**(ii) Step 10's `±` is never bound.** `ψ(n,t) := (1/p)|Σ_{l,σ} ∫ e^{−itE} f_{l,σ}(E)
w^{E,σ}_{l,±}(n) √ν_l(E) dE|²` sums over `l` and `σ` and integrates over `E`. Nothing
selects `±`. This is A.12, verbatim, in his own notation.

Minor: step 5 reads *"For `n ∈ ℕ ∩ [N,M]`"* — should be `ℤ`.

### Where the code deliberately departs from the spec

Both departures are authorized; both are documented in `README.md`.

| Step | Spec | Code | Authority |
|---|---|---|---|
| 5 | prefactor `±`/`∓` tracking the σ superscript (real signs) | `+i` / `−i`, independent of σ | A.2, blessed 2026-05-19. Reproduces paper 1's Volterra kernel `A⁻¹s^{E,σ}` exactly; the literal version leaves residual `0.5(1+σi)` |
| 7 | `+` on `n > j_k`, `−` on `n ≤ j_k` | `−` / `+` (paper 2 Def 3.1.1) | A.10, ruled 2026-08. Residual `1.600e+00 → 2.4e-16` **[v]** |
| 10 | `ψ = (1/p)\|…\|²` | `ψ = (1/(p·2π))\|…\|²` | A.11, ruled 2026-08. `Σ_n ψ = 0.99999999998` **[v]** |

---

## 3. Findings, ranked

| # | Finding | Confidence | Evidence | Acts |
|---|---|---|---|---|
| 1 | **A.12 is an input-convention question, not a defect.** Both branches are exact eigenbases differing by `S_E`. The tripwire passes iff `f` is transported between branches. | CONFIRMED **[v]** | fixed `f`: 14 % / 42 % / 65 %; state-based `f = F_βψ₀`: 4.3e-15 / 4.3e-15 / 7.7e-15 **[v]** | **Schober** |
| 2 | **Both branches are unitary.** Neither is "the wrong one". | CONFIRMED **[v]** | `Σ_n ψ = 1.000000000000` at t = −30…+30, both branches, for V=0.8, V=3.5, and two-site V=1.0 **[v]** | — |
| 3 | ~~A.10/A.11 fixes are uncommitted~~ | **RESOLVED 2026-08-21** | Committed as `9e319a0`, with both rulings quoted in the message | — |
| 4 | **Steps 1–8 compute correct scattering.** | CONFIRMED | 2040 cases vs transfer matrix: `max\|T_code−T_exact\| = 3.198e-15`; `max\|1−\|T\|²−\|R\|²\| = 6.661e-15`; Fabry–Pérot resonances reproduced to 2.17e-12 | — |
| 5 | **`professor_response.txt` lines 51 and 52 contradict each other by exactly a sign** — and the spec sides with line 52. | CONFIRMED **[v]** | ratio `= −1.000000` at every energy; spec step 1 says `Im(z) > 0` **[v]** | **Schober** |
| 6 | **The GUI cannot perform Schober's ± experiment.** Flipping the outer sign flips the preset to "Custom", dropping the window `f` *and* `E_segments`. | CONFIRMED **[v]** | `gui/main_window.py:923` wires `in_outer.currentTextChanged` → `_field_edited` **[v]** | Maxwell |
| 7 | ~~`dist/maxwell.exe` is committed and stale~~ | **RESOLVED 2026-08-21** | Untracked, deleted from disk, `dist/` gitignored. Note the 64 MB blob remains in git history — purging needs a force-push to `origin` | — |
| 8 | **Spec steps 8/10 transpose the indices on `w`;** step 10's `±` is unbound. | CONFIRMED **[v]** | `MaxwellAlgorithm.pdf` p. 2, steps 8 and 10 **[v]** | **Schober** |
| 9 | **Frame truncation is the dominant quantitative error.** 10 of 13 presets lose most of their mass by `t_max`. | CONFIRMED | Schober 1 retains `Σψ = 0.19–0.25`; Two-Channel Free retains 0.0025; widening to ±800 → 0.9876 | Maxwell |
| 10 | **Leading `σ` on `v^{E,σ}_l` (paper 3 Def. 2.2) is in neither the spec nor the code.** Equivalent to negating `f_{l,−}`. Does not cure A.12. | CONFIRMED | Paper 3 Def. 2.2 p. 5; `eigfunc.py:67-69` has no σ | **Schober** |
| 11 | **`[BS25]` is cited by paper 2 with numbering matching no document in the repo.** | CONFIRMED | Paper 2 p. 30 bibliography; `[BS25, Prop. A.3.2(f)]`, `[Def. 2.1.7]`, … ; paper 1's App. A is "Norm estimates" (Lemma A.1, Prop. A.2 only) | **Schober** |
| 12 | **Paper 2 Lemma 4.1.3 is still titled "sign problem",** with struck-through `−σ → σ` edits in 4.1.5(b),(d). Those signs feed `S_E` — the exact matrix the branches differ by. | CONFIRMED | Paper 2 §4.1 | **Schober** |
| 13 | **The test suite is blind to A.12 by construction.** 0/32 tests run a packet through a non-zero potential; 0 use `t < 0`; 0 set `outer_sign`. | CONFIRMED | Mutation `A_branch_swap` → 32 passed; `I_ignore_outer_sign` → 32 passed | Maxwell |
| 14 | **`eval()` on the V-matrices field is a working RCE.** | CONFIRMED | `gui/main_window.py:1393-1397`; escape demonstrated via `BuiltinImporter` | Maxwell |
| 15 | **`n_t = 0` → uncaught `IndexError`,** silent no-op under `console=False`. | CONFIRMED | `gui/main_window.py:1011`; `validate()` never inspects `times` | Maxwell |
| 16 | **Two-Channel preset descriptions describe physics the code cannot produce** — the Gaussian `f` populates channel 0 only. | CONFIRMED | `gui/main_window.py:1433-1440`; `max\|f[:,1,:]\| = 0.000e+00` | Maxwell |
| 17 | **`min_nquad` advisory is unsafe for narrow packets** (claims ≥20 % headroom; measured 0.29×). All 13 shipped presets are nonetheless converged. | CONFIRMED | `gui/main_window.py:454-471`; at σ_E=0.02 advisory=110 vs required 288 | Maxwell |
| 18 | ~~"Schober's A.12 test is malformed"~~ | **REFUTED** | It is a theorem under `f = F_βψ₀` (4.3e-15 **[v]**). Correct framing: valid under one input convention, false under the other | — |
| 19 | ~~"`ψ₊[f] = ψ₋[Sf]` is the replacement acceptance test"~~ | **REFUTED — near-tautology** | A *random unitary* fake `w₋` passes it at 4.16e-17. It would green-light arbitrary garbage. **Do not show Schober this number.** | — |
| 20 | ~~"Tie the branch to σ" as the A.12 fix~~ | **REFUTED** | Destroys the isometry: `Σψ = 0.30 … 1.56` | — |
| 21 | ~~"`outer_sign=+1` is the advanced/incoming branch"~~ | **REFUTED** | `+1` is retarded/outgoing; the code's labels are right. Its proposed docstring "fix" would have *introduced* an error | — |
| 22 | Paper 2 Def. 4.1.6's `S_E` matrix layout | **DISPUTED — do not cite** | Two PDF extractors disagree and both drop the minus signs. Settle by rendering p. 28 as an image, or ask for the LaTeX | Maxwell |

---

## 4. What was sent to Schober — SENT AND ANSWERED, archived 2026-08-24

> **This is history, not a to-do list.** Items 1–3 were sent on 2026-08-21 and he answered
> them the same day (see `professor_response.txt` and `../new_texts.txt`). He confirmed the
> `S^E` reading verbatim: *"The two videos should differ by S^E, they should not be the
> same!"* and *"you are starting with the same Fourier transform under two different Fourier
> transforms, so if you transform back, you get two different states."*
>
> **Items 6–9 are dead and must not be re-sent.** They were written against the 27-page
> paper 3 of 2026-08-21. That paper was rewritten on 2026-08-14 into a 28-page
> *Wave and scattering operators…*: item 6's leading `σ` was removed by the author himself,
> item 7's Proposition 3.2.6 no longer exists, and item 8's `[BS25]` is gone from paper 3.
> Item 9's sub-items are against July 2025 copies of papers 1 and 2, while `4_Levinson.pdf`
> cites 2026 revisions that are not in this repo.
>
> Kept as a record of what was asked and what came back.

> Hi Jonas — I have the April 25 algorithm PDF now, thanks. Three things need your ruling,
> then some paper questions. All numbers are max over the frame, relative to peak ψ.
>
> **1. I ran the ± test and I think the test needs one word added.** On a single-site
> config (L=1, a=1, V(0)=0.8) the two videos differ by **14 %** of peak; on L=2 with
> complex-Hermitian V at two sites, **65 %**. But I don't think that means anything is
> broken. Both branches individually satisfy `(H−E)w = 0` to 6e-16 **and** `Σ_n ψ(n,t) =
> 1.000000000000` at every time I checked, including t < 0 and a V=3.5 wall — so neither is
> the "wrong" branch, they're both exact orthonormal eigenbases. And the change of basis
> between them, normalised by `σ√ν_l` as in paper 3 Definition 2.2, is unitary to 1e-15 with
> `|det| = 1`. That is `S_E`. So `F_− = (∫^⊕ S_E dE) F_+` forces `ψ_−[f] = ψ_+[S_E^{-1} f]`,
> and the two runs can only coincide when `S_E = 1`, i.e. `V ≡ 0`. Which is exactly what I
> measure: with no potential the two videos agree to **0.000e+00**.
>
> **2. So the real question is what `f` is.** Data item (f) of the algorithm says
> "Functions `f_{l,σ} : [a,b] → C`" — `f` is handed in once, fixed, independent of `±`.
> Under that reading the two branches are *supposed* to differ by `S_E` and your test cannot
> pass. If instead the input is a state `ψ₀ ∈ ℓ²` and `f := F_± ψ₀`, then `F_±^* F_± =
> P_ac(H)` is branch-independent and your test becomes a theorem. **I implemented that second
> reading and your test passes at 4.3e-15** — for L=1, for L=2 with two sites and
> complex-Hermitian V, and for a case with a bound state. **Which input do you intend for
> step 10 — a fixed `f`, or a state `ψ₀`?** If it's a fixed `f`, then the branches are meant
> to differ and I'll fix `outer_sign = +1` and drop the field.
>
> **3. Your step-1 simplification contradicts your step-3 simplification, and your own
> algorithm PDF settles it.** You wrote `z_l(E) = e^{−i arccos(E/(2a_l))}`, which has
> `Im z < 0`. Feeding that into step 3's `ν_l = 1/(2a_l Im z_l)` gives `ν_l =
> −1/√((2a_l)²−E²)` — the ratio to your other formula is **exactly −1 at every energy** — and
> then `√ν_l` in step 10 is imaginary. Step 1 of the algorithm PDF says "the solution with
> `Im(z) > 0`", so I'm keeping that root; it reproduces your `ν_l = +1/√((2a_l)²−E²)` to
> 1.1e-16. **Just confirm that's what you meant** — I think the `−` in the exponent was a
> slip.
>
> **4. Two index problems in the algorithm PDF.** (a) Step 8 defines `w^{E,±}_{l,σ}` — plane
> wave `z_l^{∓n}` driven by the upper `±`, `G^{E,σ}` carrying σ — but step 10 writes
> `w^{E,σ}_{l,±}`, with the two indices swapped. Matching superscript to superscript gives
> Interpretation 2, which is what you ruled and what I implemented, but the document
> contradicts itself and that's where the original ambiguity came from. (b) Step 10's `±` is
> never bound by anything, which is the same question as item 1. Worth fixing in the next
> revision.
>
> **5. The G sign — your own paper 2 already answers it.** Definition 3.1.1 (p. 15) has the
> branch signs `−`(n>j) / `+`(n≤j) with a leading `i`, and Theorem 3.1.3(a) gives
> `(K−E)G = δ·1`, i.e. `G = (H−E)^{-1}`. That's the opposite pattern from algorithm step 7.
> I made the change you authorised and checked it against the exact infinite-lattice
> resolvent: `|G_code − (H−(E+iε))^{-1}| = 3.3e-08 at ε = 1e-8`, scaling cleanly as O(ε). So
> **paper 2 Def 3.1.1 is authoritative and algorithm step 7 is the document that needs
> correcting.** The residual went from `1.600e+00` (= 2|V| exactly) to `2.4e-16`.
>
> **6. The 2π is confirmed, and it's in your paper too.** Definition 3.2.1 (p. 11) puts
> `1/√(2π)` into `F̃_±`, so `|F_±^* f|²` carries `1/(2π)`; step 10 as written omits it. With
> your fix, `Σ_n ψ = 0.99999999998`, constant in t to 1e-14.
>
> **7. Paper 3 Definition 2.2 has a leading `σ` the algorithm doesn't.** You define
> `v^{E,σ}_l(n) := σ · (e^{−iσ arccos(E/2a_l)})^n · √(−d/dE arccos(E/2a_l)) · e_l`, and that
> `σ` reappears in Φ (Def 3.1.1) and is load-bearing in Lemma 3.1.2's unitarity proof.
> Algorithm step 8's free term `z_l^{∓n} e_l` has no `σ`, so I'm currently computing with
> `f_{l,−}` effectively negated. **Should step 8 carry the leading `σ`?** (It doesn't affect
> item 1 — a diagonal ±1 leaves `S_E` unitary.)
>
> **8. I'm missing `[BS25]`.** Paper 2's bibliography cites *"Construction of scattering
> matrices with varying dimension…"* at `[BS25, Prop. A.3.2]`, `[Def. 2.1.4]`,
> `[Lem. 2.1.5(a)]`, `[Def. 2.1.7]`, `[Cor. 2.2.3]`, `[Lem. 2.1.8]` — and none of those
> numbers exist in `1_JostSolutions.pdf`, whose Appendix A is "Norm estimates" with only
> Lemma A.1 and Prop. A.2. **Is `[BS25]` superseded by papers 1+2, and if so what's the
> number map** — especially Prop. A.3.2(f), the explicit computation of `J^E`?
>
> **9. Three smaller paper items, whenever you get to them.** (a) Paper 2 cites
> "Proposition 2.1.4(f)" four times (pp. 7, 7, 15, 25) but Prop. 2.1.4 has only (a)–(d) — is
> the target Prop. 2.1.9? (b) Paper 3 Thm 2.4(a) needs `{±2a_l} ∪ σ_pp(H) ⊆ D`, but paper 2's
> `D` (Def 2.2.3) is a subset of `C_A ⊂ ℂ` and isn't shown to contain `σ_pp(H)` — same `D`?
> (c) **Paper 2 Lemma 4.1.3 is still titled "sign problem"**, and 4.1.5(b),(d) carry visible
> struck-through `−σ → σ` edits. Those signs propagate into `M^E_σ`, `N^E_σ` and hence `S_E`
> — the exact matrix my two runs differ by. **Is 4.1.3 settled, and which sign is final in
> 4.1.5(b)?**
>
> Nothing here blocks me except item 2.

---

## 5. What to show him

**A. The one-slide table — lead with this.** One config, three rows:

| run | `max\|ψ₊ − ψ₋\|` / peak |
|---|---|
| fixed `f` (spec Data item (f)) | **14 % (L=1) … 65 % (L=2 cplx-Herm)** |
| `f := F_± ψ₀` (state-based) | **4.3e-15 … 7.7e-15** |
| `K = 0` control (V ≡ 0) | **0.000e+00** |

*Why it lands:* it isolates the single variable — the input convention — with a
fifteen-order-of-magnitude swing, and the control row shows the discrepancy is `S_E`
vanishing exactly when `S_E = 1`.

**B. The unitarity row, as the "nothing is broken" proof.** `Σ_n ψ(n,t) =
1.000000000000` for both branches, at t = −30, −15, 0, +15, +30, for V=0.8 balanced, V=0.8
one-sided, V=3.5 wall, and a two-site V=1.0. *Why it lands:* it forecloses "so one branch
is the buggy one" in a single line of numbers.

**C. Two videos side by side, `outer_sign = +1` vs `−1`.** L=1, a=1, V(0)=0.8 at j=0,
right-moving Gaussian `f=(1,0)`, E₀=0, σ_E=0.30, N=±160, n_quad=420, **t ∈ [−12, +12]** —
the negative-t half is the point. Then play the `−` video backwards with left/right
mirrored and show it lands on the `+` video (`2.2e-16`). *Why it lands:* he sees it isn't
noise or a broken branch, it's a clean symmetry.

**D. The complex-Hermitian counterexample — the one that kills the easy answer.** L=2,
a=(2,1), K=2, `V(0)=[[0.3, 0.9i], [−0.9i, −0.2]]`, `V(5)=[[1, 0.4i], [−0.4i, 0.5]]`, with a
genuinely two-channel `f`. Here *no* reflection or time-reversal recovers the `−` video from
the `+` one (same-t 29 %, time-reversed 69 %, mirrored 69 %). *Why it lands:* forecloses
"it's just time reversal, pick one" and forces the `S_E` reading. Note this only shows up
with a multi-channel `f` — the GUI's channel-0-only `f` hides it entirely (finding 16).

**E. The `S_E` unitarity table** — four energies, L=2, a=(1.3, 0.8), K=2 non-diagonal
self-adjoint V: `‖S*S−1‖` **with** the `σ√ν_l` normalisation is 3e-16…1.2e-15, **without**
it is 3.7e-2…7.2e-2, and `|det S| = 1.000000000000` throughout. *Why it lands:* two jobs at
once — the branch difference **is** his unitary `S_E`, and the last two columns
independently validate the `√ν` normaliser of his own Definition 2.2. This is the strongest
single piece of evidence that the code implements *his* objects rather than merely
self-consistent ones.

**F. Two code lines on one slide.** `spectral/maxwell/green.py:69,73` (the
`−G_right/+G_left` pattern) beside paper 2 Def 3.1.1's `−/+`; and
`spectral/maxwell/eigfunc.py:67-69` (`Z ** (-sigma_vals * n_arr)`) beside paper 3 Def 2.2's
`σ (e^{−iσ arccos})^n`, showing exactly where the leading `σ` is missing.

**G. The step-1/step-3 sign, as six numbers.** `Im z` under his line-51 formula:
`[−0.9898, −0.9729, −0.9367, −0.8225, −0.9148, −0.7545]`; the resulting `ν` from step 3: all
negative; his line-52 `ν`: same magnitudes, all positive; **ratio −1 in every entry.** Then
the one line from his own spec: *"the solution with `Im(z) > 0`"*.

> **Do NOT show him** the `ψ₊[f] = ψ₋[Sf]` residual (1e-16). It is a change-of-basis
> tautology — a *random unitary* fake `w₋` passes it at 4.16e-17. If he asks "how do you
> know the code is right then", the answer is **E + the transfer-matrix comparison**, not
> that.

---

## 6. Where to look next

> **Steps 1 and 3 are done or dead as of 2026-08-24.** Step 1 was answered: he confirmed
> the branches are *supposed* to differ by `S^E`. Step 3 is moot — the leading `σ` it asks
> about was removed from paper 3's Definition 2.2 in the 2026-08-14 rewrite, so there is
> nothing to restore. Steps 2 and 4–6 are unaffected.

**Step 1 — Get the ruling on the input convention.** ✅ **ANSWERED 2026-08-21.** He
confirmed the two branches should differ by `S^E`, and that they would agree only if you
started from the same *state* rather than handing the same `f` to both transforms.

**Step 2 — Nail down which `S_E` the change-of-basis actually is.** *(~2 h.)*
*Hypothesis:* the matrix extracted from `w₊ = w₋ S` equals the *physical* S-matrix read off
the asymptotics, up to a known row permutation. *Experiment:* extract `S_phys = OUT·IN⁻¹` by
least-squares fitting each `w_β` column to `A z^{−n} + B z^{+n}` on windows outside the
support — a functional of `w` completely disjoint from the `w₊ = w₋ S` fit — and check
`S_cob = J·S_phys`. One verifier got `‖IN₊ − I‖ = 8.95e-16` (L=1) and 9.16e-16 (L=2/K=2
complex-Herm), the two extractions agreeing to 2.00e-15. *Why it matters:* this is the
**non-tautological** version of the test — the one that survives the random-unitary control.
Reproduce it and make it a permanent test.

**Step 3 — ~~Decide whether the leading `σ` changes any delivered video.~~ MOOT.** The `σ`
this step asks about is no longer in paper 3: the 2026-08-14 rewrite states Definition 2.2
(p. 5) as `v^{E,σ}_l(n) := (e^{−iσ arccos(E/2a_l)})^n · ((2a_l)²−E²)^{−1/4} · e_l`, with no
leading factor. The code already matches. Original text below, struck.

> *Hypothesis:* restoring `σ` is equivalent to negating `f_{l,−}`, so it is
invisible for one-sided `f` and visible for balanced `f`. *Experiment:* run all 13 presets
with and without, tabulate `max|Δψ|/peak`. *Prediction:* exactly 0 for every `right`/`left`
preset, non-zero for every `balanced` one — **including both Schober presets**. *Kill
condition:* if a one-sided preset changes, the equivalence argument is wrong and the fix
isn't diagonal.

**Step 4 — Settle paper 2 Def. 4.1.6's `S_E` layout.** *(~30 min.)* Render p. 28 as an image
(needs poppler) or ask for the LaTeX. Two extractors disagree and both drop the minus signs.
Until then, **do not put that formula in writing.**

**Step 5 — Rewrite the lost test-suite §12.** *(~3 h.)* Almost certainly slab-truncation
convergence. Unrecoverable from git — `git log --all -- tests/` shows one commit and §12 is
already absent there. **The test will fail today**: Schober 1 sits at `Σψ = 0.19–0.25`
(finding 9). That failure is the point.

**Step 6 — Threshold and closed-channel behaviour.** *(~1 day. UNVERIFIED by anyone.)* Every
result in this audit is confined to `|E| < 2a_min` with all channels open — which the spec's
Data item (e) mandates, so the shipped presets are inside the tested envelope. But paper 3's
varying-multiplicity content lives outside it, and `S_E` changes dimension there. *Do this
before claiming the multi-channel presets exercise the papers' actual subject.*

---

## 7. Maxwell's action list — no ruling needed

Items 1, 3 and the package rename were done on 2026-08-21; the rest are open.

| # | File:line | Change | Why | Status |
|---|---|---|---|---|
| 1 | working tree | Commit the A.10/A.11 fixes plus all source documents. | Both rulings existed only as uncommitted edits. | **DONE** (`9e319a0`) |
| 2 | `gui/main_window.py:923` | Delete `self.in_outer.currentTextChanged.connect(self._field_edited)`. | Outer sign is a diagnostic switch, not a preset parameter. This one line makes Schober's ± experiment impossible from the GUI. | open |
| 3 | `dist/maxwell.exe` | Untrack, delete, gitignore `dist/`. | 64 MB stale binary computing `Σψ = 6.6198`. | **DONE** |
| 4 | `gui/main_window.py:1393-1397` | `ast.literal_eval` instead of `eval`. | Working RCE from the V-matrices field. `literal_eval` handles `[[[0.4, 0.25j], [-0.25j, -0.2]]]` with nothing lost. | open |
| 5 | `gui/main_window.py:1008-1018` | Move inside the `try`; add `if self.times.size < 2: raise ValueError(...)` to `_build_spec`. | `n_t=0` → uncaught `IndexError`; under `console=False` the button silently does nothing forever. | open |
| 6 | preset table, `gui/main_window.py:344-388` | Widen frames to `M ≥ n_init + 2a₁·t_max + 4σ_n`. Schober 1 needs ±800 for 98.8 %. | 10 of 13 presets lose most of their mass off-screen while a stat block labelled "∑ψ AT T" counts down to 0.003. | open |
| 7 | `tests/` | Add four tests: (a) `t`,`r` vs transfer matrix; (b) flux-weighted unitarity of `S(E)` with `D = diag(1/√ν_l)`; (c) end-to-end vs `e^{−iHt}ψ₀` **with V ≠ 0 and t < 0**; (d) `outer_sign` is honoured end-to-end. | All four pass today; all four are absent. (a)+(b) are the only tests that would catch a wrong transmission coefficient. | open |
| 8 | `tests/test_maxwell.py:146-148` | Guard `1 <= ni <= n_sites-2` in `h_residual_vector_grid`. | Latent bug in the *test* helper: at `j = N` the index `ni-1 = -1` wraps and silently tests the wrong site; at `j = M` it raises. | open |
| 9 | `gui/main_window.py:454-471` | Replace the advisory with `n_quad ≥ ceil(PV/π + 2W/σ_f) + 8`, and make it **block**. | Docstring's "≥20 % headroom" is false; at σ_E=0.02 it's 9× too small. Error jumps 1e-14 → 100 % of peak across one 16-node step. | open |
| 10 | `gui/main_window.py:418-420, 433-437` | Add a channel-weight control to `f`, or rewrite both Two-Channel descriptions. | `max\|f[:,1,:]\| = 0.000e+00` — the Gaussian `f` never excites channel 1. | open |
| 11 | `maxwell.spec:29,32`; `main.py` | `upx=False`; wrap `main.py` in try/except to a logfile; `faulthandler.enable()`. | UPX mangles Qt DLLs — a latent landmine on any build machine that has UPX. | open |
| 12 | `pyproject.toml` | Declare `pillow` explicitly. | The GIF fallback is the only working export path here and depends on Pillow, which arrives only transitively via matplotlib. | open |
| 13 | `gui/main_window.py:1196, 1201-1203` | Use `FFMpegWriter.isAvailable()` not `shutil.which`; add `setDefaultSuffix`; validate the extension **before** rendering. | A `.cmd` shim makes `which` succeed where matplotlib's `Popen` fails. Wrong extension currently fails *after* a 10 s render. | open |
| 14 | `gui/main_window.py:1251-1256, 575-580` | `extent` y-range → `times[0] − dt/2, times[-1] + dt/2`. | Waterfall uses row centres as image edges; the time cursor is `dt/2` out of register. Cosmetic. | open |
| 15 | `spectral/maxwell/model.py:21` | Delete the `from_dict` mention or implement it. | Docstring promises an API that doesn't exist. | **DONE** |

---

## 8. Open questions nobody can currently answer

> Revised 2026-08-24 against `4_Levinson.pdf` and the rewritten paper 3. Items 1, 5 and 8
> were **removed**, not answered: 1 was answered by Schober; 5 asked to settle a layout
> that renders cleanly at 450 dpi and is quotable; 8 challenged the author's own convention
> on no evidence beyond "unusual".

1. **The contents of `[BS25]`.** *Blocked on:* a document not in the repo. Consequence:
   "Proposition 2.1.4(f)", cited four times in paper 2, resolves to nothing. Note `[BS25]`
   has been **removed from paper 3** in the rewrite; it survives only in paper 2
   (pp. 2, 4, 5, 12, 30), which is itself a July 2025 file superseded by a 2026 revision
   that is not here. **Unblocked by:** asking for the current papers 1 and 2.
2. **Current versions of papers 1 and 2.** `4_Levinson.pdf` cites 2026 revisions of both,
   but this repo holds the July 2025 copies. Every erratum in `PAPER_NOTES.md` §1.1–1.2 is
   against a file the author has moved past. **Unblocked by:** the two PDFs.
3. **Whether paper 2's `S^E` is paper 3's.** Both were renumbered; paper 3's is now
   Definition 4.4 (p. 25). Verified numerically for the L=1 single-site case (1.7e-14),
   which is not the same as the identification of the matrices in general.
4. **The final signs in paper 2 §4.1.** *Blocked on:* Schober's own unresolved edits. Lemma
   4.1.3 is titled "sign problem"; 4.1.5(b),(d) carry struck-through `−σ → σ`; a margin note
   reads "I do not understand this argument." Against the July 2025 copy — may be resolved
   in the 2026 revision.
5. **Test-suite §12.** *Blocked on:* nothing — it never existed in version control and must
   be rewritten, not recovered.
6. **Behaviour at and beyond the channel thresholds.** *Blocked on:* nobody tested it. The
   spec's Data item (e) confines `[a,b]` to the common open band, so the shipped presets are
   inside the tested envelope — but the varying-multiplicity content the papers exist for is
   entirely unexercised by this code.
