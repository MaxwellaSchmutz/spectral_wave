# Ballesteros–Schober manuscripts: errors, questions, conventions

**Scope.** `docs/papers/1_JostSolutions.pdf` (37 pp, 1 July 2025), `docs/papers/2_LimitingAbsorptionPrinciple.pdf` (30 pp), `docs/papers/3_*.pdf` (27 pp), and `docs/MaxwellAlgorithm.pdf` (2 pp, 25 April 2026).

**How this was produced.** Each paper was read in full twice by independent agents, using two independent text extractions plus page renders at 140–500 dpi. A separate pass covered the algorithm spec, and a separate pass built the cross-document convention table. Three adversarial verifiers then tried to refute every claim, re-rendering the disputed pages themselves and re-deriving the numerics from scratch. **Where a verifier refuted or weakened a claim, the verifier's verdict is what appears below**, and the downgrade is stated explicitly. Nothing under the repo was modified.

**Two extraction hazards that shaped the result, and that anyone re-checking must respect.**

1. Both PyMuPDF and pypdf silently drop LaTeX `\overline` rules. This produced **two false accusations against paper 3** (its `𝔇̄` and `ℂ̄_σ` were read as `𝔇` and `ℂ_σ`), and one against paper 2 (its Theorem 3.2.1 hypothesis reads `\ 𝔇`, Fraktur, not `\ D`, roman). Any conjugation- or closure-sensitive claim must be settled on a render, not on text.
2. Paper 2 carries live red edit marks (strikethroughs, insertions, referee notes). Text extraction renders a strikethrough rule as `(((((((((` and shows struck text as if it were live. Two "leaked LaTeX" findings turned out to be already-struck material.

**What actually touches live output.** Of everything below, exactly **one** paper-level item changes what the shipped code computes today: paper 3 Definition 2.2's leading `σ` (§1.3, item 1). Every other paper-level defect sits at or past the channel thresholds `E = ±2a_k`, which `model.py:99` and `quadrature.safe_open_band_interval` forbid. The three spec-level math errors (§1.4) were already corrected in the code under his April rulings; what §1.4 adds is that two of the three are now **derivable from paper 1**, so they no longer rest on a ruling.

---

# 1. What to tell Jonas about his papers

## 1.0 One-line severity map

| | Paper 1 | Paper 2 | Paper 3 | Spec |
|---|---|---|---|---|
| Changes the mathematics | `C_E` sign at negative thresholds (p.18/p.35) | Eqs (14)/(15) σ-swap (p.21) | — | steps 7, 4/5, 8 |
| Changes current code output | — | — | leading `σ`, Def 2.2 (p.5) | leading `σ`; unbound `±` |
| Load-bearing gap | `P^E_1` undefined; Prop 4.6 is `[TODO]` | `𝔇`, `O^σ_α` undefined; §3 ↮ §4 | Def 4.2's two `[TODO]`s; Prop 3.2.6's proof | `A`, `H`, `H₀` never defined |
| Marker count | 14 `??`, 7 `[TODO]`, 1 `Corregir` | 19 `??`, 4 `[TODO]`, 6 live referee notes | 8 `[TODO]` brackets (10 tokens) | — |

---

## 1.1 Paper 1 — *Existence and analytic behaviour of Jost solutions*

### A. Changes the mathematics

**1.1.1 — `C_E` has the wrong sign at every negative threshold. p.18 Definition 3.4, and the display on p.35 that derives it. Confidence: CONFIRMED (analytically and numerically, by two independent implementations).**

p.18 verbatim:
> `C_E := ( (Z_σ − Z_σ^{-1})(1 − P^E_=) − P^E_= )^{-1}`

p.35 verbatim:
> `= (2AZ_σ − E)(1 − P^E_=) + ((2n−1)AZ_σ − En)P^E_=`
> `= A(Z_σ − Z_σ^{-1})(1 − P^E_=) − AP^E_= = A(C_E)^{-1}`

On `ran P^E_=` write `Z_σ e_k = ε e_k`, `E = 2a_k ε`, `ε = ±1`. Then `ϕ_+(n) = ε^n`, `ψ_+(n) = ε^n n`, and the Wronskian block is
`a_k[ε^{n+1}ε^n n + ε^n ε^{n−1}(n−1)] − 2a_kε·ε^{2n}n = a_k(2n−1)ε − 2a_kεn = −a_kε`,
i.e. `−A Z_σ P^E_=`, **not** `−A P^E_=`. The last step of the p.35 display silently uses `A Z_σ P^E_= = A P^E_=`, which holds only for `ε = +1`. Since `a_k > 0`, a fixed `E > 0` forces `ε ≡ +1` (paper correct) and `E < 0` forces `ε ≡ −1` (paper off by a sign on the whole `P^E_=` block).

This is **not a transcription typo**: the printed derivation commits the same step, and Remark 2.9 (`P^E_= ℂ^L = ker(Z_σ−1) ⊕ ker(Z_σ+1)`) shows the author knows `ε = −1` occurs.

Correct constant:
```
C^σ_E = ( (Z_σ − Z_σ^{-1})(1 − P^E_=) − Z_σ P^E_= )^{-1}     [ = … − sgn(E)·P^E_= ]
```

Consequence, checked: **Proposition 3.6(b) is false as stated at every `E = −2a_k`**, and those energies are inside its own stated scope. With `a = (2,1)`, `σ = +`, residual `max_n |(H₀−E)K̃^σ_ψ − δ_j|`:

| E | printed `C_E` | corrected `C^σ_E` |
|---|---|---|
| `+2a_1 = +4` | 4.4e-16 | 4.4e-16 |
| `+2a_2 = +2` | 1.9e-16 | 1.9e-16 |
| `−2a_2 = −2` | **2.000** | 9.2e-16 |
| `−2a_1 = −4` | **2.000** | 9.1e-16 |
| `E = 1.3` (`P^E_= = 0`) | 5.6e-16 | 5.6e-16 |

The `2.000` is `|1 − ε| = 2` on `ran P^E_=`, independent of `a_k`. At negative thresholds the ψ-kernel returns `−δ_j`, so Definition 3.2(a) fails, Lemma 3.1's cancellation fails, and the `u` it produces does not solve `(H−E)u = 0`.

*Minor, fold into the same sentence, do not send separately:* `C_E` genuinely depends on `σ` (by Prop 2.7(f), `Z_σ − Z_σ^{-1} = −(Z_{−σ} − Z_{−σ}^{-1})` on open channels), so writing `C^σ_E` would be clearer — but `σ` is already in scope from Definition 3.4's first line, so this is notation, not a defect. *(Downgraded on verification; the original list filed it as a second finding.)*

**1.1.2 — p.22, Lemma 4.1: the radius is the distance to the branch *points* where it must be the distance to the branch *cuts*. Confidence: CONFIRMED (proof-level error; statement survives).**

p.22 verbatim:
> *We first consider the case that `w ∉ {−2, 2}`. Then, setting `r := √dist(w, {−2, 2})`, the function `z_σ` is holomorphic on `U_{r²}(w)`.*

The singular set of `z_σ` is the two closed **rays** `±2 + σi(−∞,0]`, not the two points, because `√(w∓2)_σ` is cut where `w ∓ 2 ∈ σi(−∞,0)`. A disc of radius `dist(w,{±2})` routinely swallows large arcs of them. `σ = +`, jump probed at `±10⁻⁹` across `2 + i(−∞,0]`:

| `w` | printed `r² = dist(w,{±2})` | `dist(w, cuts)` | jump of `z_σ` | `\|z(p+ε) − 1/z(p−ε)\|` |
|---|---|---|---|---|
| `1 − 10i` | 10.0499 | **1.0000** | 10.378 | 1.9e-11 |
| `0.5 − 6i` | 6.1847 | **1.5000** | 6.578 | 4.7e-11 |
| `1.5 − 3i` | 3.0414 | **0.5000** | 3.873 | 1.4e-10 |

So `z_σ` is not merely non-holomorphic on that disc — at ray points it is undefined, and `f^w_σ(ζ) := z_σ(ζ²+w)` is not well defined on `U_r(0)`. Repair: `r² := dist(w, (2 + σi(−∞,0]) ∪ (−2 + σi(−∞,0]))`. One symbol.

*Two things NOT to change, both checked:* (i) the `w ∈ {−2,2}` branch of the same proof correctly uses `r = 2` — `dist(2, −2+σi(−∞,0]) = 4 = r²` exactly, and `ζ²±4` never meets `σi(−∞,0]` for `|ζ| < 2`; (ii) Theorem 3.7(a)'s holomorphy on `int(O^σ_α)` is correct, because `int(O^σ_α) ⊆ int(C^σ_a)` already excludes the thresholds and their cuts.

*Refuted sub-claim, do not send:* the original list said the bad radius "propagates into `r_E`, Definition 4.3 and Prop 4.6 — every radius in Section 4 is too large." It does not. Lemma 4.2 reads "*there exists* `r_E > 0`…" and Definition 4.3 says "let `r_E` … be **as in Lemma 4.2**". Every downstream radius is existentially quantified, so no downstream statement is affected.

**1.1.3 — p.3 and p.4: "`τ_A = 1` iff `A` is unitary" is false. Confidence: CONFIRMED (counterexample).**

p.3: *"τ_A = 1, if and only if η_A = 1, which holds true if and only if `A` is unitary (notice that `‖A‖ = 1 = ‖A^{-1}‖` implies that `A` is an isometry…)"*. `η_A = 1` says the **product** `‖A‖·‖A^{-1}‖` is 1, not that each factor is. `A = 2·1_L`: `‖A‖ = 2`, `‖A^{-1}‖ = 1/2`, `η_A = τ_A = 1`, `A` not unitary. The parenthetical proves a different implication. Correct statement: `η_A = 1` iff `A` is a **scalar multiple of a unitary** — which is the phrase the author himself uses on p.2. The same slip repeats on p.4: *"τ_A = 1 implies that A is unitary and the above will imply that A = I"* — false for `A = a·1_L`, `a ≠ 1`. Harmless mathematically (that case is a rescaling of `[BFGS22]`), but the printed sentences are false.

### B. Unproven gaps

**1.1.4 — `P^E_1` is never defined anywhere in the 37 pages. Confidence: CONFIRMED.** First use p.18, Definition 3.4, last line: `K^σ_ψ := K^{−σ}_ϕ P^E_1 + K̃^σ_ψ (1_L − P^E_1)`. Then used p.18 (Prop 3.6(b)), p.32 (Lemma B.2), p.33 (Lemma B.3), pp.35–37 (Prop 3.6(b) proof). Definition 2.8 (p.10) defines `I_E` and `P^E_=` and nothing else.

Two independent reconstructions agree: `P^E_1` = orthogonal projection onto `{e_k : |z_σ(E/a_k)| = 1, E/a_k ≠ ±2}` — the **strictly** open channels, thresholds excluded, so `P^E_1 P^E_= = 0`. Forced three ways: p.37 needs `‖Z_σ(1 − P^E_= − P^E_1)‖ < 1`; p.33 needs `ψ^{E,σ}_+(n)^{-1}P^E_1 = ϕ^{E,σ}_+(n) = ϕ^{E,−σ}_−(n)`, whose second equality is Prop 2.7(f) with hypothesis `|Re E| < 2a_k`; p.33 needs "`P^E_1 ≠ 0` and therefore `‖Z_σ‖ ≥ 1`". *Note for the wording:* the characterisation is via `|z_σ(E/a_k)| = 1`, **not** via `|E| < 2a_k` — the latter is correct only for real `E`; for non-real `E ∈ C^σ_{[−2a₁,2a₁]}` one has `P^E_1 = 0`. This is a hard stop for an implementer: Definition 3.4 cannot be evaluated without it.

**1.1.5 — p.24, Proposition 4.6's proof is literally `...[TODO]` twice, and §4 never states its own conclusion. Confidence: CONFIRMED verbatim by three extractions.**

p.24, complete:
> **Proposition 4.6.** Let `σ ∈ {±}` and `E ∈ C^σ_a`. Then, the quadruple `(U_{r_E}(0), Y ↦ Y² + E, K^{E,σ}_Φ, Φ^{E,σ}_{τ,·})` is admissible.
> *Proof.* `...[TODO]`
> `...[TODO]`

This is the only proposition in §4 that does work — 4.1, 4.2, 4.5 and Remark 4.4 are setup. The corollary the section exists to produce (that `E ↦ u^{E,σ}_τ(n)` lifts holomorphically to `Y = √(E − E₀)` across a threshold `E₀ ∈ a`) is never written down. §4 is a stub.

*Two claims from the original list are REFUTED here and must not be sent.* (i) "The statement as written is false because `r_E` is fixed by `A` and `E` alone." `r_E` is existentially quantified in Lemma 4.2 and Definition 4.3 says "as in Lemma 4.2", so the paper is already read as "for a suitable `r_E`" — the proposed repair is the only available reading. (ii) The supporting sentence "the disc covers both sheets, `F^E_σ(−Y) = F^E_σ(Y)^{-1}`" is **factually wrong** on non-threshold channels: for `w ∉ {±2}`, Lemma 4.1 sets `f^w_σ(ζ) = z_σ(ζ²+w)`, which is **even**, so `f(−Y) = f(Y)`. Verified for `w = 1.3, −0.7, 3.0`. The sheet swap holds only for the `w = ±2` branch (checked to `<1e-12`), i.e. only channel-wise at thresholds.

What survives as a *question*: §4 needs a hypothesis relating `sup_{|Y|<r} α_σ` to the potential's decay rate `ε`, and the "`α = τ_A` balance" (p.20, itself a `[TODO]`) is exactly what would supply it. Shrinking `r` alone does not close it, because at a threshold `α_σ(E) = ‖Z_σ^{-1}‖ ≤ τ_A` with equality possible while Definition 1.1 permits `ε = τ_A` exactly.

**1.1.6 — pp.18–19, Theorem 3.7 asserts a stronger uniqueness than Theorem 3.3 proves. Confidence: gap CONFIRMED; truth status UNSURE (see §1.5).** Thm 3.7 claims *"there exists **a unique** function `u^{E,σ}_τ ∈ G_L(H,E)` such that `lim_{n→τ∞} ϕ^{E,σ}_τ(n)^{-1}u^{E,σ}_τ(n) = 1_L`"* — uniqueness in `G_L(H,E)` from the asymptotics alone. Theorem 3.3's uniqueness argument runs entirely inside the class satisfying its (a)+(b)+(c) (it sets `ṽ^z := ϕ^{-1}v`, uses (b) to put it in `ℓ^∞`, uses (a) to get `ṽ = 1 + T^z ṽ`, then inverts). Nothing bridges the two, and Lemma 3.8 (p.20) leans on the stronger version explicitly ("by the uniqueness assertion in Theorem 3.7").

**1.1.7 — pp.3 / 18 / 20: the standing growth condition does not imply the hypothesis actually used, at the value `α = τ_A` the paper says to use. Confidence: CONFIRMED, low severity.** Definition 1.1 (p.3): *"there exists `ε > 1`, with `ε ≥ τ_A`, such that `Σ_n ‖V(n)‖ε^{|n|} < ∞`"* … *"In the case that `τ_A > 1` we can simply take `ε = τ_A`."* But Prop 3.6 and Thm 3.7 (p.18) assume `Σ_j ‖V(j)‖ |j| α^{|j|} < ∞` — extra factor `|j|` — and p.20 says *"both can be balanced by choosing `α = τ_A` (`...[TODO]`)"*. Counterexample: `V(j) = τ_A^{−|j|}|j|^{−2}1_L` (`j ≠ 0`) is Hermitian and admissible under Definition 1.1, with `Σ‖V‖τ_A^{|j|} = 2Σj^{−2} < ∞` but `Σ‖V‖|j|τ_A^{|j|} = 2Σj^{−1} = ∞`. Fix: `ε > τ_A` strictly, or write `|n|` into condition (1).

*Two mitigations, so this is filed correctly:* no theorem in the paper is false — Prop 3.6, Thm 3.7 and Lemma 3.8 each carry the `|j|α^{|j|}` condition as their own explicit hypothesis; the only defective sentence is the p.20 aspiration, which is already marked `[TODO]`. Related, and missed by the first pass: **Lemma 3.8 (p.20) writes `Σ_j ‖V(j)‖ j α^{|j|}` — bars missing on `j`.** Also **Remark 1.2 contradicts Definition 1.1**: Def 1.1 requires `ε > 1`; Remark 1.2 says *"In the case that `τ_A = 1`, condition (1) becomes `Σ_n ‖V(n)‖ < ∞`"*, i.e. `ε = 1`.

**1.1.8 — p.20, the `α = τ_A` claim is a bare `[TODO]` and needs restating precisely. Confidence: observation, DOWNGRADED from the original "provably does not cover".** `α_σ(E) := (max{1,‖Z_σ‖})²·‖Z_σ‖·‖Z_σ^{-1}‖` (Def 3.5) carries a prefactor that Prop 2.7(g) does not bound. Measured (`a = (2,1)`, `τ_A = 3.732051`): `α_σ ≡ 1.000000` on `(−2a_L, 2a_L)`; `sup α_σ` over real `E` off thresholds `= 3.729896 ≤ τ_A`; but over `{σ Im E < 0, |Re E| < 2a_L}` it is **unbounded** (`α_σ ≈ 2|E|²`; 134.5 at `−1.999 − 8i`). *The original list reported the sup there as 13.55 — that was a grid artifact; the verifier's `∞` is what to believe.* The right framing is not an accusation: **`ℝ ∩ C^σ_a ⊆ O^σ_{τ_A}` is provable** (for real `E`, Prop 2.7(b) gives `‖Z_σ‖ ≤ 1`, so the prefactor is 1 and `α_σ = ‖Z_σ‖‖Z_σ^{-1}‖ ≤ τ_A` by Prop 2.7(g)), and that is almost certainly the intended content. Ask him to state it; the paper claims nothing about the half-plane set.

**1.1.9 — pp.13 & 18: the `τ = −` kernel is never written out. Confidence: DOWNGRADED to a suggestion; the original "hidden sign trap" claim is REFUTED.** p.13: *"we will just execute the proof … for the case `τ = +`, the case `τ = −` can be shown exactly analogously."* Mirroring Definition 3.4 *literally* — `K(n,j) = A^{-1}s^{E,σ}(j−n)` for `j < n` — gives `(H₀−E)K = −δ_j` (measured `2.000`), because `s^{E,σ}` is odd; the correct left kernel is `A^{-1}s^{E,σ}(n−j)` (measured `5.0e-16`). **But "exactly analogously" in this subject means conjugating by the reflection `R:(Rϕ)(n) = ϕ(−n)`, under which `H₀` is invariant, and that gives `K^{σ,−}(n,j) = K^{σ,+}(−n,−j) = A^{-1}s^{E,σ}(n−j)` automatically.** The paper asserts nothing false. Send at most as: worth writing the `τ = −` kernel out explicitly, since `s^{E,σ}` is odd and a careless mirror flips the sign — and since this is the paper-1 origin of the code's `+i/−i` split.

### C. Broken references, undefined notation, typos

All confirmed by two extractions unless noted. Counts: **14 `??`, 7 `[TODO]`** (the first pass said 6; Prop 4.6 alone has two), 1 `Corregir`, 1 `(please verify care-fully)`.

| p. | Item |
|---|---|
| 2 | **Every** cross-reference in the Introduction is `??` — "Proposition ??", "Section ??" (×5), "Corollary ??", "Theorem ??", "Definition ??". |
| 2 | The Introduction and abstract describe a *different, longer* paper: "In Section 1 … prove that `H₀` has purely absolutely continuous spectrum with varying spectral multiplicity" — no such result exists in this draft (`"absolutely continuous"` occurs exactly once in 37 pp., on this page); "In Section ?? we construct the scattering matrix" — not here either. Presumably a slice of a merged paper 1+2. |
| 9 | Prop 2.7(c) proof cites "Lemma 2.5(g)" but needs **2.5(h)**; Prop 2.7(d) proof cites "Lemma 2.5(h)" but needs **2.5(g)**. **The two citations are swapped.** |
| 10 | Lemma 2.11(c): `...[TODO] (make this the defintio and make the definition part of the lemma)` — editorial note in the text, plus "defintio". |
| 12 | Lemma 2.12(a) proof: "Since, by `...[TODO]`, `ker(Z_σ − Z_σ^{-1}) = P^E_= ℂ^L`" → Prop 2.7(d) / Remark 2.9. |
| 13 | §3 opening: "[Te00, Lem. 7.8] and [BFGS22, Thm. 33] **Corregir**". |
| 19 | Thm 3.7(a) proof: "follows by (??)". Thm 3.7(b) proof: "recall the definition of **M** in (??)" — `M` is never defined in Thm 3.7; it is Thm 3.3's `N`-after-increasing, and `N` means two different things between the two theorems. |
| 20 | Thm 3.7(c) proof: "The recursive relation (10) and (??)"; **"(please verify care-fully)"**; "By (7), `‖T^{E,σ}‖ ≤ 1/(2(|E|+1))`" — **(7) says only `‖T^z‖ ≤ 1/2`**. The decay in `|E|` is genuine (Lemma B.1's `3‖A^{-1}‖/(|E|‖A‖^{-1}+1)` gives `‖T‖ ≲ C a₁/|E|`), but the citation and the constant are both wrong; and the proof writes `lim_{E∈F, |E|→∞}` where `F` is the **compact** set from part (b). |
| 29 | Prop A.2 step (3): "by Lemma 2.5(h)" → needs **2.5(b)/(g)**. |
| 32 | Lemma B.2 proof: "by `...[TODO]`, `‖Z_σ‖ ≤ 1`" → Prop 2.7(b). |
| 33 | Lemma B.3 proof: "By `...[TODO]`, `ψ^{E,σ}_+(n)^{-1}P^E_1 = …`" → Lemma 2.12(e)/Prop 2.7(f), plus the missing `P^E_1`. |
| 2 | `M_N(ℂ) := M_{N,M}(ℂ)` — `M` is a free variable; should be `M_{N,N}`. |
| 5 | `C^σ_M := ℂ ∖ {z : Re(z) ∈ M and Im(z) ∈ σi(−∞,0)}` — type error, `Im(z)` is real. Should be `σ Im(z) < 0`. Propagates to every use. |
| 8 | `a := σ(2A) ∪ σ(−2A)` — `σ` = spectrum collides with `σ ∈ {±}` in the same display as `Z_σ`, and with `a_k`, and with Appendix A's generic `a, b ∈ ℝ` (p.27). |
| 10 | `I_E := span{k : E/a_k ∈ {−2,2}}` — `span` of an index set is meaningless; `I_E` is used as an index set on p.13. Drop `span`. |
| 21/23 | `C^σ_{{w}}`, `C^σ_{{E}}` — Definition 2.3 requires `M ⊆ ℝ` but `w`, `E` are complex. Intended `ℂ ∖ (w + σi(−∞,0))`. |
| 23 | Lemma 4.2 writes `F^{E,σ}` where everything else writes `F^E_σ`. |
| 24 | `K^{E,σ}_Φ : U_r(0) × ℤ × ℤ,` — codomain `→ M_L(ℂ)` missing; `U_r(0)` and `U_{r_E}(0)` used interchangeably. |
| 15–17 | `ℓ^∞(ℕ ∩ [N,∞), M_L(ℂ))` should be `ℤ ∩ [N,∞)` — `N` may be negative (Def 3.2(c), Thm 3.3). Recurs ~5×; Thm 3.7(c) compounds it. |
| 14–17 | Thm 3.3(c): "`u(z,·) ∈ G(H, E(z))`" — `u` is `M_L(ℂ)`-valued, so `G_L`. Thm 3.7 has it right. |
| 28–29 | Prop A.2 step (4): "(18) holds strictly for `w ∈ C^σ`". Read as `C^σ_ℝ` the strictness claim is false (step (2) has equality at `w = ±2b`); it must mean the *open* half-plane. **Downgraded:** the Notation on p.2 defines `ℂ_±`, so this is a sub/superscript slip with an obvious intended meaning, not undefined notation. |
| 33/35/37 | `K^{−σ}_ψ` written where Definition 3.4 says `K^{−σ}_ϕ` — **three** occurrences (p.33 Lemma B.3, p.35 Prop 3.6(b) proof, p.37), not two. |
| 35 | Prop 3.6(b) proof: tildes dropped inside `(H₀−E)K̃^σ_ψ(E,·,j)(n) = δ_j(n)(AK^σ_ψ(E,n+1,n) + …)`. Also applies Lemma B.1 (stated with `α_σ`) to `K^{−σ}_ϕ`, which yields `α_{−σ}` — harmless (`P^E_1 = 1_L` forces `E` real) but worth noting. |
| 5 | Def 2.1: "generalized eigenfunctions **of E** to the generalized eigenvalue E" → "of **K**". |
| 12 | Lemma 2.12(b) proof: `M_τ` where the decomposition two lines above gives `M_ϕ` (both extractors render `M_ϕ` correctly in the same paragraph, so this is in the source); conclusion mixes function and value; `M_{L,N}(ℂ)²` vs `M_{L×N}(ℂ)`. |
| — | **Prose:** p.3 title "[τ_A and the Strict Growth Condition **and** ]"; p.4 "the strict **grout** condition **seams** to be necessary always"; p.4 "assume that `A` is a **positive semi-definite** Hermitian matrix `A > 0`" (contradictory; `A` is positive *definite*); p.10 "**general** eigenfunctions"; p.12 "**injektive**", "**respecitvely**"; p.17 "**continuouity**" (×2), "**uniformely**"; p.20 "**Idealy**, one **what** like …**mainaining**"; p.26 "**in** monotonously decreasing"; p.27 "(18) holds **stictly**". |
| 37 | `[AW21]`: "**Actosun**, T., and R. Weder, *Direct and Inverse Scattering for the Matrix Schrödinger Equation*, Springer, **1979**" — author is **Aktosun**, book is **2021**; 1979 is `[RS79]`'s year, copy-pasted. `[AW21]` occurs exactly once in the file, i.e. **never cited in the body**. |

### D. Checked and CORRECT — do not let anyone "fix" these

Lemma 2.5(a)–(k) (verified on 4000 random `w`, both `σ`: `max|z + 1/z − w| ≤ 4.5e-13`, `max||z|−1| ≤ 4.4e-16` on `[−2,2]`); the `3/(|w|+1)` bound in (k) and its algebra; Prop 2.7(b),(h) — the `‖A‖^{-1}` in (h) is right; the unitary reduction on pp.3–4; Lemma 2.11, Lemma 2.12, Lemma 3.1, Theorem 3.3 incl. Eq. (9); Eq. (21) p.34; Lemma A.1; Prop A.2 steps (1)(2)(3)(5); the proof of Prop 2.7(g) pp.29–30; Lemma B.1's `α^{max{|j−n|,|j|}}` bookkeeping; Lemma 4.1's `r = 2` for `w = ±2`; Theorem 3.7(a)'s holomorphy on `int(O^σ_α)`. **Conjugation statements carrying `\overline` (Lemma 2.5(h), Prop 2.7(c), several Appendix-A displays) were deliberately not audited** — see §4.

---

## 1.2 Paper 2 — *Limiting absorption principle*

### A. Changes the mathematics

**1.2.1 — p.21, Equations (14) and (15): every `σ` on the right-hand side should be `−σ`. Confidence: CONFIRMED (two independent implementations, four channel configurations).**

Printed:
```
(14)  Φ^E_σ b = m^{E,−σ}_{H₀,−}·((W^{E,σ}_{H₀,+})^{-1})* W(m^{E,σ}_{H,+}, b)
              + m^{E,−σ}_{H₀,+}·((W^{E,σ}_{H₀,−})^{-1})* W(m^{E,σ}_{H,−}, b)
(15)  Ψ^E_σ b = m^{E,−σ}_{H,−} ·((W^{E,σ}_{H,+ })^{-1})* W(m^{E,σ}_{H₀,+}, b)
              + m^{E,−σ}_{H,+ }·((W^{E,σ}_{H,− })^{-1})* W(m^{E,σ}_{H₀,−}, b)
```
As printed, the RHS of (14) equals `Φ^E_{−σ}b` and the RHS of (15) equals `Ψ^E_{−σ}b`.

Origin, p.23, first display. Printed:
`G^{E,−σ}_{H₀}(j,n) = ∓ m^{E,σ}_{H₀,±} i (W^{E,σ}_{H₀,±})^{-1} m^{E,−σ}_{H₀,∓}(n)*`
Definition 3.1.1 with `σ ↦ −σ` gives
`G^{E,−σ}_{H₀}(j,n) = ∓ m^{E,−σ}_{H₀,±} i (W^{E,−σ}_{H₀,±})^{-1} m^{Ē,σ}_{H₀,∓}(n)*`
— the two `σ` labels were interchanged, and the swap propagates verbatim into (14) and (15). The rest of the p.22→p.23 chain is internally consistent (the `−i`/`+i` prefactors cancel the `±i` correctly), so this one display is the sole defect.

Measured against the paper's own Eq. (16)/(17), which are exact finite sums for finite-support `V` (residuals normalised by `‖b‖`, `b` over a basis, `n ∈ {−3,0,2}`; Green's function pre-validated at `(K−E)G(·,j) = δ_j 1_L` to `≤4e-16`):

| case | (14) printed vs (16)_σ | (14) with σ→−σ | (14) printed vs (16)_{−σ} |
|---|---|---|---|
| L=1, a=1, E=.55 | 3.59e-01 | 2.25e-16 | 2.25e-16 |
| L=2, a=(1.5,.8), E=.9 (2 open) | 1.11 | 5.06e-16 | 2.96e-16 |
| L=2, E=2.0 (1 open, 1 closed) | 1.48 | 1.59e-15 | 1.59e-15 |
| L=3, a=(2,1.3,.7), E=1.1 | 1.44 | 5.87e-16 | 5.04e-16 |

Same pattern for (15) vs (17).

**Do NOT tell him Theorem 3.2.1(c) fails.** The original list claimed `(Ψ^E_σ ∘ Φ^E_σ)b = b` measures `7.12e-01` with the printed formulas. **REFUTED.** Since the printed (14) computes `Φ_{−σ}` and the printed (15) computes `Ψ_{−σ}`, their composition is `Ψ_{−σ}∘Φ_{−σ} = id`, and it measures `2.31e-16` (L=1), `5.87e-16` (L=2), `2.32e-15` (L=3) — identical to the corrected version to machine precision. **The σ-swap is self-consistent; (c) and (d) are true as printed; only the two displays are wrong, and nothing downstream is damaged.**

Two smaller defects in the same proof, both CONFIRMED:
- **p.23 typo:** `W(m^{E,σ}_{H₀,±}, m^{E,−σ}_{H₀,∓}) = (W^{E,σ}_{H,±})*` — subscript must be **H₀**. With H₀ the identity is exact (`0.00e+00`); with H it is off by `3.5–10.6`. Also forced structurally: the display only telescopes if that Wronskian is `(W^{E,σ}_{H₀,±})*`.
- **p.23 gap:** the last step of (c) is "`= b`, using `...[TODO]`". The missing identity is `b = Σ_± m^{E,−σ}_{H,∓}((W^{E,σ}_{H,±})^{-1})* W(m^{E,σ}_{H,±}, b)` for `b ∈ B(H,E)`; verified true (`≤3.7e-14` for K=H, `≤8.9e-16` for K=H₀, five configurations). Needs a proof or a citation.

**1.2.2 — pp.2–3: two different `H₀`, and the standing hypothesis on `A` is too weak. Confidence: facts CONFIRMED; retagged from MATH-ERROR to *inconsistent standing hypothesis + undefined notation*.**

- p.2: *"Given `L ∈ ℕ` and **a invertible normal** matrix `A ∈ GL_L(ℂ)` … `(H₀φ)(n) := A*φ(n+1) + Aφ(n−1)`."*
- p.3, Def 2.1.1: *"`(H₀Φ)(n) := AΦ(n+1) + AΦ(n−1)`"* — `A` on both sides.

These agree only if `A = A*`, and everything after Def 2.1.1 uses the second form: Prop 2.1.4(a) `A(Z_σ + Z_σ^{-1}) = E1`; Def 2.3.1's Wronskian and Prop 2.3.3's step `= [Au(n+1) + Au(n−1)]*v(n) − …`; `W(u,v)* = W(v,u)`, used in Lemma 4.1.5(c). **Stronger than the first pass reported:** Prop 2.1.4(a) with `Z_σ = diag(z_{σ,k})` forces `A = E(Z_σ+Z_σ^{-1})^{-1}` to be **diagonal**, and p.12's `ω^{E,σ}e_k = −i a_k(…)e_k` presumes `Ae_k = a_k e_k`. So the standing hypothesis should be `A = diag(a₁ ≥ … ≥ a_L > 0)` outright. Relatedly, **`a_k` is never defined anywhere in paper 2**, yet it appears from Def 2.1.3 onward; Remark 4.1.2(a) (p.25) says only *"we recall that `a_k > 0` because `A` is positive **an** invertible"*. Since Def 2.1.1 is introduced "by abuse of notation" as the same operator, one of the two displays is simply a typo — no theorem is false under the intended reading. Does not change the code (`wronskian.py` builds `A_mat = np.diag(a)` with real positive `a`).

Same page: p.2 says the potential obeys *"an exponential **growth** condition"*; the abstract says *decay*, and (1) `Σ‖V(n)‖τ_A^{|n|} < ∞` is decay. "growth condition" recurs throughout.

**1.2.3 — p.4, Def 2.1.3: `𝒮 := {z ∈ ℂ : |Re z| > 2a_L}` is inconsistent with Prop 2.1.4(b). Confidence: inconsistency CONFIRMED; "consequential" REFUTED; the *fix* is DISPUTED (see §1.5).**

With `a₁ ≥ … ≥ a_L`, `2a_L` is the smallest threshold, so `𝒮` contains real energies where channel 1 is still open, and Prop 2.1.4(b)'s *strict* `‖Z_σ(E)‖ < 1` on `ℂ_σ ∪ 𝒮` fails. Reproduced twice independently (`a = (1.5, 0.8)`, `2a_L = 1.6`, `2a₁ = 3.0`):
```
E=1.7 ∈ S(2a_L)   |z|=[1.000000, 0.703465]   ‖Z_σ‖=1.000000   ← not < 1
E=2.0 ∈ S(2a_L)   |z|=[1.000000, 0.500000]   ‖Z_σ‖=1.000000
E=2.9 ∈ S(2a_L)   |z|=[1.000000, 0.300827]   ‖Z_σ‖=1.000000
E=3.1 ∈ S(2a_1)   |z|=[0.772992, 0.278010]   ‖Z_σ‖=0.772992   ✓
```
**Downgrade the framing.** `𝒮` occurs exactly twice in the whole paper (the Def 2.1.3 line and the Prop 2.1.4(b) line); nothing else uses it. The failure region is real `E ∈ (2a_L, 2a₁]`, which lies inside `[−2a₁,2a₁] ⊆ C_σ` anyway, where every downstream result uses only the non-strict `‖Z_σ‖ ≤ 1`; and off the real axis inside that strip, `max|z| = 0.66–0.82 < 1`, so even the non-strict bound is fine. **The original list's second argument — that Def 4.1.1's set identity "forces" `2a₁` — is REFUTED and contradicts the same list's own reading of that identity elsewhere.** Report it as an internal inconsistency / probable typo with no consequence.

### B. Unproven gaps and undefined notation

**1.2.4 — p.15, Definition 3.1.1: `O^σ_α` and `𝔇` are both undefined, and `𝔇′` (p.24) with them. Confidence: CONFIRMED verbatim at 500 dpi. This absorbs the "Theorem 3.2.1 omits the thresholds" finding, which was a misquote.**

p.15 reads, character for character:
```
Definition 3.1.1.  Let K ∈ {H₀,H}, σ,τ ∈ {±} and E ∈ O^σ_α ∖ 𝔇.  We define
       W^{E,σ}_{K,τ} := W(m^{Ē,−σ}_{K,−τ}, m^{E,σ}_{K,τ})
```
- **`O^σ_α`** is never defined in paper 2 and no `α` appears anywhere else in 30 pages. It recurs identically in Lemma 3.1.2 (p.16) and Theorem 3.1.3 (p.17). (It is paper 1's Definition 3.5 — see §3.)
- **`𝔇` (Fraktur) is undefined and is a different symbol from the roman `D` of Definition 2.2.3** (`D_τ := {E ∈ ℂ_A : ℰ_τ(H,E) ∩ ℬ_{−τ}(H,E) ≠ {0}}`, `D := D₊ ∪ D₋`), which is what Def 4.1.6 and Prop 4.2.1 use. Theorem 3.2.1(d)'s "`If E ∈ 𝔇′`" is undefined too.
- Consequently **the reader cannot tell where the Green's function exists.** The intended definition is visible: Lemma 2.3.9 with `N = L`, `B = C = 1_L` (so `B*C = 1_L ∈ GL_L`, as required) already proves that `{E : W^{E,σ}_{K,τ} ∉ GL_L}` is **discrete**, and Corollary 4.2.3(b) later introduces exactly such an enlarged discrete set `D̃ := {E ∈ ℂ_A : W(q^E_∓, q^E_±) not invertible}`. `𝔇` is almost certainly `D̃`, and it belongs before Def 3.1.1 rather than after Prop 4.2.2.

**Two corrections to how this was originally filed.** (i) The claim "*Theorem 3.2.1 (p.20) reads `E ∈ [−2a₁,2a₁] ∖ D` and therefore claims the LAP at the thresholds*" is a **misquote** — the 500 dpi crop shows `E ∈ [−2a₁, 2a₁] ∖ 𝔇`, Fraktur, and under the only sensible reading of `𝔇` the thresholds *are* excluded, because Lemma 2.3.7 gives `W^{E,σ}_{H₀,τ} = τω^{E,σ}`, singular exactly at `E = ±2a_k`. Confirmed by accident: at `L=3`, `a=(2,1.3,0.7)`, `E = 2.6 = 2a₂`, `cond W_{H₀} = inf` (and `6.07`, `42.2`, `13.3` at `E = 2.55, 2.599, 2.61`). (ii) The claim "*nothing proves `W^{E,σ}_{K,τ}` is invertible*" is **weakened**: Def 3.1.1 restricts to `E ∉ 𝔇`, so invertibility is a hypothesis, not an unproven assertion. The real defect is the missing one-line definition. *The supporting evidence "`cond W` up to 2.8e4 at L=3, E=2.6" should be dropped — `E = 2a₂` is a threshold, that number measures the threshold degeneracy. Away from thresholds `cond W_H` runs 5.3–68 across `E ∈ [0.3, 3.9]`, and even at `E = 2.6`, `cond W_H = 34.7`.*

**1.2.5 — the paper stops short of its stated goal, and §3 is never connected to §4. Confidence: CONFIRMED; this is draft incompleteness, not a defective proof.** p.2: *"we show that the function `σ(H₀) ∋ E ↦ S^E`, constructed in [BS25], coincides with the fibration of the scattering operator `S = Ω*₋Ω₊` … The present paper aims to close this gap."* **`Ω` occurs nowhere after p.2** (0 occurrences in the remaining 28 pages). The paper stops at Corollary 4.2.3. The "outline of our proof is as follows:" list on p.2 has exactly one item. And **`Φ^E_σ`/`Ψ^E_σ` last appear on p.24; §4 never mentions them** — nothing relates `Ψ^E_σ` to `S^E`. See §1.5 for the conjectured bridge and how to settle it.

**1.2.6 — p.30, the author's own margin note "What do you do with the inverse of `M^E_σ`?" is a real gap. Confidence: CONFIRMED.** Corollary 4.2.3(b)'s analytic continuation needs `det M^E_σ ≠ 0` off the real axis, but the invertibility of `M^E_σ` comes from Lemma 4.1.5(d)'s proof, which uses `W(b,b) = −σ1`, valid only for real `E`. So `D̃` must also exclude the zeros of `det M^E_σ`.

### C. The §4 sign audit — good news, send it as reassurance

**Lemma 4.1.3 is titled *"sign problem"* (p.25, red italic between the number and "Let"). It is a false alarm: the statement is correct.** I rebuilt §4 independently (transfer-matrix Jost solutions, asymptotic mode decomposition for an honest basis of `B(H,E)`, no use of the paper's formulas) at L=1, L=2 (both open; one open/one closed) and L=3 (all open; one open/two closed), random Hermitian finite-support `V`:

| Statement | printed | verdict |
|---|---|---|
| Lem 4.1.3 `W(b^{E,−σ}_τ, b^{E,σ}_τ) = 0` | — | correct, ≤2.4e-13 |
| Lem 4.1.3 `W(b^{E,σ}_τ, b^{E,σ}_τ) = −σ1` | `−σ1` | **correct**, ≤3e-13 (`+σ1` is off by exactly 2) |
| Lem 4.1.5(a) `= −σM^E_σ` (red `−σ`) | — | correct, 1e-13 |
| Lem 4.1.5(b): struck `−σ`, red `σ` inserted | edited to `σN^E_σ` | **the edit is RIGHT**: `|W − σN| ≤ 1.7e-13`, `|W + σN| = 1.1–26`. Accept it. |
| Lem 4.1.5(c),(d) | — | correct, ≤3e-13 |
| Prop 4.2.1 (`S^E` unitary) | — | correct, `‖S*S−1‖ ≤ 8.7e-14` |
| Remark 4.1.7 (`S^E` is the change of basis) | — | correct, 2.2e-15 |
| Prop 4.2.2 (`b` from `p`, `q`, incl. the non-obvious `τσ` label) | — | correct |

**Nothing in §4 propagates a wrong sign into `S^E`.** Definition 4.1.6's layout, confirmed by rendering p.28 (both text extractors garble it):
```
S^E := ( (M^E_+)^{-1}          −N^E_- (M^E_-)^{-1} )  ∈ Mat(2|J^E| × 2|J^E|, ℂ)
       ( −N^E_+ (M^E_+)^{-1}    (M^E_-)^{-1}       )
```
Read as a 2×2 block matrix in `σ` with `|J^E|×|J^E|` blocks in `k`, i.e. **σ-major, l-minor** — which, with Rem 4.1.7's row vectors `(b^{E,+}_−, b^{E,−}_+)`, fixes the index ordering that paper 3 leaves unstated.

**Two claims to strike before this reaches him.** (i) The margin note *"I do not understand this argument"* is on **p.26, attached to the basis claim** at the foot of the page (*"…also `(b^{E,+}_+, b^{E,−}_+)` and `(b^{E,+}_−, b^{E,−}_−)` form a basis of `B(H,E)`"*), **not** to any sign. The basis claim is fine: Cor 2.2.5(a) gives, for each `τ`, a linear injection `B(H₀,E) → B(H,E)` (injective by Thm 2.2.4(b)), which maps a basis to a basis; Def 4.1.4's decompositions have residual `≤1.4e-15` in every configuration. One sentence closes it. (ii) The original list called Lemma 4.1.5(d)'s proof "right only by cancellation" and said "Ballesteros patched signs by hand until the arithmetic landed." **REFUTED.** The p.27 line prints the four terms with signs `−, +, +, −`: `−(M)*·σ1·M + (M)*·0·N + (N)*·0·M − (N)*·(−σ1)·N`. Term 1's true value is `−σ1` and `−(σ1) = −σ1`; term 4's true value is `+σ1` and `−(−σ1) = +σ1`. Both are correct with the sign factored to the front. There is no error and nothing to cancel. **Do not send that sentence under any circumstances.**

### D. Broken references and typos

Counts: **19 `??`, 4 `...[TODO]`**, six live red referee notes.

- **"Proposition 2.1.4(f)" is cited 4× (pp. 7 ×2, 15, 25) but Prop 2.1.4 has only (a)–(d).** The target is **Proposition 2.1.9** (p.5). Mechanism, and it is decisive: Prop 2.1.4 is attributed `([BS25, Prop. A.3.2])` and Prop 2.1.9 is attributed `([BS25, Prop. A.3.2(f)])` — the *source* item letter was cited against the *local* proposition number. Prop 2.1.9 contains both things the four uses need (explicit `J^E`; `z_{+,k} = z_{−,k}^{-1}` on `J^E`). **This resolves the AUDIT's open question 2 without needing `[BS25]`.**
- **"Theorem 2.1.6(f)" (p.14)** — Thm 2.1.6 has only (a)–(c). By the same mechanism (Thm 2.1.6 is attributed `[BS25, Cor. 2.2.3, Thm. 2.2.2(e)]`) this is almost certainly `[BS25, Thm. 2.2.2(f)]`. *Downgraded:* the original list also tagged it UNPROVEN-GAP because the step needs `u^{E,σ}_τ → φ^{E,σ}_τ` uniformly as `|E| → ∞`, and it is the only support for "D is discrete" (Prop 2.3.12). Ask for the citation; do not call it a gap in *this* paper.
- Live referee notes that would ship if compiled today: p.15 *"(this saw not clearly stated in the hypothesis)"* against the non sequitur *"If `τ_A > 1`, the strict growth condition is fulfilled"* — **"strict growth condition" is never defined**, yet it gates Lemma 2.3.9, Prop 2.3.12 and Cor 4.2.3(b), and `τ_A` is a property of `A` while the condition is a property of `V`; p.24 *"Improve this text. Unitary in the spectrum. Real analytic? … Define or recall generalized eigenfunctions."*; p.26 *"This notation was never introduced…"* **inserted mid-sentence** in Def 4.1.4; p.29 *"The presentation is confusing…"*; p.30 *"(please specify where there are holomorphic)"*, *"please recall the argument"*, *"What do you do with the inverse of `M^E_σ`?"*.
- Undefined / colliding notation: **`C_A` is never defined** (first used p.7, glossed parenthetically in Def 2.2.3 as `= ℂ₊ ∪ ℂ₋`); `ℂ_σ` (blackboard, half-plane) vs `C_σ` (italic, the big domain) are distinguished **by font only** and every extractor collapses them; `σ` is overloaded (branch vs `σ(2A)`, in the same line in Def 4.1.1 and Lemma 4.1.3); Def 2.1.3's `∖ (σ(2A) ∪ σ(−2A))` is ambiguously parenthesised; Def 4.1.1/4.1.4/4.1.5 write `{±1}` where the rest writes `{±}`.
- Typos: p.3 Remark 2.1.2 "for any **n ∈ ℕ**" → `ℤ`, and "`φ·v ∈ **dim** G(K,E)`" (recurs p.24); **p.9** proof of Thm 2.2.4(b) "Together with **(5)**" → **(4)** *(page corrected from the original list's p.8)*; p.8 "**conincide**"; p.9 "exactly **on** function"; p.15 "**Haltonian**"; p.25 "the **radicat**", "positive **an** invertible"; p.2 "if the matrix `A` **that** is not a scalar **multiply** of a unitary"; p.12 Remark 2.3.6 writes `z_{−,k}` three times where it means `z_{σ,k}`; p.19 Lemma 3.1.4(b) `(W^{E,σ}_{K,±}(j))^{-1}` — `W` has no lattice argument; p.20 Eq (13)'s middle term `Σ‖V(n)‖·|n|·τ_A^{|n|}` does not follow from (1) when `τ_A = 1` (and is superfluous — `Σ‖V(n)‖ ≤ Σ‖V(n)‖τ_A^{|n|}` directly since `τ_A ≥ 1`); p.25 Remark 4.1.2(c) stray `ν^E`; p.28 Prop 4.2.2 **never quantifies `σ`** and writes `p^E_τ` for `p^{E,σ}_τ` (twice); p.30 Cor 4.2.3(a) "**see by** Proposition 4.2.2"; p.15 Prop 2.3.12 "for `σ, τ ∈ ±`" missing braces; Theorem 3.1.3 assumes `E ∈ O^σ_α ∖ 𝔇` but items (b),(e) then say "If `E ∈ C_σ`" — vacuous; Lemma 3.1.4's stated domain `C_σ ∖ D` is wider than where Def 3.1.1 built `G`.
- **Bibliography:** the same `[AW21]` error as paper 1 (**Actosun → Aktosun, 1979 → 2021**); `[AW21]` and `[Te00]` are never cited; **`[BS25]`, on which every quoted proposition in §2 depends, carries no venue, year or arXiv number.**
- *Two "cosmetic" items to drop or re-describe:* the reported leaked LaTeX label `"…consequence of Lemma 2.3.9 (((((((((lem : DZeroSubeq"` — on the page there are no parentheses; the `(((((((((` is the extractor rendering a red strikethrough rule, and the label **is already struck out**. Same for Def 2.3.10's spurious `δ_{i_k k}` — already struck in red.

### E. Checked and CORRECT

Def 3.1.1's `−` on `n > j` / `+` on `n ≤ j` and its explicit leading `i` (rendered p.15); `(K−E)G^{E,σ}_K(·,j) = +δ_j 1_L` to **1.79e-15** for both `K`; Thm 3.1.3(h) `G^{E,σ}_{H₀}(n,j) = (iω^{E,σ})^{-1}Z_σ^{|n−j|}` to **1.61e-15**; Thm 3.1.3(d) `G^{E,σ}(n,j) = (G^{E,−σ}(j,n))*` to 1.19e-15; Prop 2.1.4(c) `0 ≤ −σ Im z_{σ,k}` on the closure of `ℂ_σ`; Eq (8) and Remark 4.1.2(a) (this is what makes the code's `ν_l` positive); Lemma 3.1.2's 2L×2L matching computation; Prop 4.2.2. **Prop 2.3.3, Lemma 2.3.7, Lemma 2.3.9, Prop 2.3.12, Def 3.1.1 and Prop 2.1.4(d) all carry an `Ē` that text extraction drops — they are correct, and they look false without the bar. Do not report them.**

---

## 1.3 Paper 3 — *Generalized Fourier transform / diagonalization*

**Housekeeping first, because the numbering in earlier notes was wrong.** The file is **27 pages**. There is no Theorem 2.2.5, no Theorem 3.1, no Theorem 3.2. The real numbers: completeness/unitarity of `F_±` is **Theorem 3.2.5** (p.19); `Ω_± = F_±^*F_0` is **Theorem 4.1** (p.22); the statement for `S` is **Theorem 4.4(b)** (p.24). Also the paper writes **`B^E` and `S^E`** (superscripts), not `B_E`/`S_E` — worth matching before sending.

### A. Changes what the code computes

**1.3.1 — p.5, Definition 2.2: the leading `σ`. Confidence: CONFIRMED analytically and numerically. This is the only paper-level item that changes shipped output.**

```
v^{E,σ}_l(n) := σ · ( e^{−iσ arccos(E/2a_l)} )^n · √( −(d/dE) arccos(E/2a_l) ) · e_l
```
The algorithm spec's step 8 and `eigfunc.py:76` both omit the leading `σ`. Three separate consequences, and the first two are the opposite of what an earlier audit concluded:

- **It is NOT load-bearing for unitarity.** In Lemma 3.1.2 (p.6) it enters as `σσ̄ = σ² = 1` and cancels between the first and second displayed lines. Delete it from *both* Def 2.2 and Def 3.1.1's `Φ` and the proof goes through verbatim. Measured: `‖F₀f‖²_K` = 70.29856917364579 **with** and 70.29856917364579 **without** — bit-identical, against `‖f‖²_{ℓ²}` = 70.298569173658. **Do not tell him the σ is needed for unitarity; he will check Lemma 3.1.2, watch it cancel, and conclude the reading was wrong.**
- **It IS needed for Theorem 3.1.4(b)**, i.e. for internal consistency between Def 2.2's `v` and Def 3.1.1's `Φ`, which carries the same leading `σ`. Drop it from one and not the other and 3.1.4(b) is false.
- **It changes `S^E` by an order-one amount.** Provable, not just measured: `w^{noσ} = σw` (Thm 2.4(c) is linear in `v`), so as row vectors `R^{noσ}_± = R_± D` with `D = diag(σ)`, `D² = 1`, hence `S^{noσ} = D S^E D` — **the sign of every block joining `σ ≠ σ′` (the reflection blocks) flips; the transmission blocks are untouched.** Two independent runs: `‖S_noσ − D S D‖ = 0.000e+00` at **every** energy tested, while `‖S_noσ − S‖ = 0.96–2.64` against `max|S| = 0.65–0.83`.
- **For step 10 with a fixed `f`, adding the leading `σ` is exactly negating `f_{l,−}`.** Invisible for a one-sided packet (measured `0.0`), order-one for a balanced one (measured `max|Δψ|/max ψ = 1.297`). **Consequence for `Ω_±`, `S`, and any state-derived `f`: none**, since `σ² = 1` cancels between `F₀` and `F_±^*`.

### B. Unproven gaps

**1.3.2 — p.23, Definition 4.2: the paper's headline claim rests on two unfilled citations. Confidence: CONFIRMED verbatim at 4×.** The text reads `Definition 4.2. (cf. [BS26b, TODO,TODO])`, and Theorem 4.3 (p.24) is `([BS26b, TODO])`. The abstract promises "the scattering matrix coincides with a unitary matrix introduced in a previous work" and p.25 concludes "proving that it is, in fact, the scattering matrix" — the *entire* bridge from paper 3's `S^E` to paper 2's is that parenthetical. Paper 3 never touches Jost solutions, transfer matrices, or paper 2's `M^E_σ`/`N^E_σ`; it uses only the abstract change-of-basis property.

**What paper 3 does prove is airtight and was confirmed end-to-end.** Brute-force `Sψ₀ = lim_{t→+∞} e^{itH₀}e^{−itH}Ω₊ψ₀` versus `F₀^*(∫^⊕ S^E dE)F₀ψ₀` (L=1, a=1, V(0)=0.8, 801-site lattice, right-moving Gaussian, T=45, stable vs T=60 at 8.1e-16): **rel max-diff 2.44e-14**. Controls: `S^E → 1` gives 0.752; `S^E → (S^E)^*` gives 1.394. So **Theorem 4.4(b) is confirmed non-tautologically**, and the direction of Def 4.2 (`w₊ = w₋S^E`, not the adjoint) is pinned. What is unverified is only "paper 3's `S^E` = paper 2's `S^E`".

**The risk is lower than "headline claim unproven" suggests, and the framing should say so.** Paper 2's Def 4.1.6 + Rem 4.1.7 + Prop 4.2.1 supply exactly the three ingredients the two TODOs need, and two independent consistency checks point the same way: (i) paper 2's normaliser `⟨e_k|ω^{E,−}e_k⟩^{-1/2} = (2a_k Im z_{−,k})^{-1/2} = (4a_k²−E²)^{-1/4}` is **identical** to paper 3's `√ν_l = (−d/dE arccos(E/2a_l))^{1/2} = (4a_l²−E²)^{-1/4}`; (ii) paper 2's domain `[−2a₁,2a₁]∖(σ(2A)∪σ(−2A)∪D)` matches `ℝ∖𝔇̄` given Thm 2.4(a). The residual gap is narrow and specific: paper 2 pairs `(b^{E,σ}_{−σ})_σ` against `(b^{E,σ}_{+σ})_σ` — grouped by **side** — while paper 3 pairs `(w_{l,+})` against `(w_{l,−})` — grouped by **branch**. The unstated link is `w^{E,σ}_{l,±} ≐ σ√ν_l · b^{E,σ}_{∓σ,l}`, and **two independent reconstructions arrived at that same dictionary**. See §1.5 for the experiment.

**1.3.3 — p.21, Proposition 3.2.6: the proof does not work, in two independent ways. Confidence: CONFIRMED (both, verbatim at 3.2×). This is the load-bearing lemma for Theorem 4.1.**

*(a) Weak convergence does not give an a.e.-convergent subsequence.* The proof extracts, "By the Banach–Alaoglu Theorem", a **weakly** convergent subsequence with limit `G ∈ K`, then writes:
> *"This implies the existence of a subsequence `(f̄ F_± V(H_0−E±iε_{n_{k_m}})^{-1}g)_m` that converges almost everywhere pointwise to the function `f̄G` (see [Ru86, Thm. 3.12])"*

The cited theorem requires `L^p` **norm** convergence. Weak convergence does not give it: `e^{inx} ⇀ 0` in `L²([0,2π])` while `|e^{inx}| ≡ 1`. **The repair is cleaner than deleting less:** the sequence is bounded in `K` and — by the proof's own *final* display, via Theorem 2.4(e) — already converges pointwise a.e. for each fixed `E ∈ [−2a_l,2a_l]∖𝔇`. Bounded in `L²` plus a.e. convergent implies weakly convergent to that limit (Egorov + uniform integrability). So Banach–Alaoglu, the double subsequence, and the Rudin citation can simply be **deleted**.

*(b) The statement is not well-formed, and this is the deeper half.* The hypothesis reads *"Let `f ∈ K`, `g ∈ c₀₀(ℤ,ℂ^L)` **and `E ∈ [−2a₁,2a₁]∖𝔇`**"*, but in the conclusion
`lim_k ∫_K f̄(E)(F_± V(H₀−E±iε_{n_k})^{-1}g)(E) dE`
**`E` is a bound integration variable.** The same symbol does two jobs: the fixed spectral parameter inside the resolvent, and the integration variable. Tracing the use site settles which is meant: Eq. (16) on p.23 arises from `⟨F_±f | e^{isM_Id}F_±Ve^{−isH₀}g⟩e^{±εs}`, where the `E` in the exponent came from `e^{isE}` — so **the application needs the diagonal reading**, `X ↦ (F_±V(H₀−X±iε)^{-1}g)(X)`. Under the fixed-`E` reading the first paragraph is correct but proves the wrong statement; under the diagonal reading the statement is right but the boundedness step is not justified, because Thm 3.1.5(b) gives `sup_{E∈F}‖G^{E,σ}_K(·,j)‖_∞ < ∞` only for **compact** `F ⊆ ℂ̄_σ∖𝔇`, and `[−2a₁,2a₁]∖𝔇` is not compact in `ℂ̄_±∖𝔇` (since `{±2a_l} ⊆ 𝔇`). The actual hole is a uniform-in-`ε` `K`-bound for the diagonal family, presumably via localisation to compact `I ⊆ ℝ∖𝔇̄` — for which Lemmas A.1/A.2 are already in the paper. **UNSURE which repair he intends; this is the sharpest question on the list.**

**1.3.4 — p.5, Definition 2.2 is stated for all `E ∈ ℝ` but is undefined at the thresholds. Confidence: CONFIRMED, minor.** `B^E := {l : E ∈ [−2a_l, 2a_l]}` uses **closed** intervals, so `l ∈ B^E` at `E = ±2a_l`, where `−d/dE arccos(E/2a_l) = (4a_l²−E²)^{-1/2} = +∞`. Prop 2.3 (p.5) restricts to `ℝ∖{±2a₁,…,±2a_L}`; Def 2.2 does not. It is the definition the varying-multiplicity story hangs on and should carry the same exclusion.

**1.3.5 — p.23/24, the index ordering of `S^E` is never fixed. Confidence: CONFIRMED, but DOWNGRADED to "please state it" — it is now self-answerable.** `S^E ∈ ℂ^{2|B^E|×2|B^E|}` and `(Ψf)(E) = (f_{l,σ})_{l∈B^E, σ∈{+,−}}`, with no ordering of the pair index `(l,σ)`. Every statement in paper 3 is invariant under simultaneous permutation, so this is not fatal; and **paper 2's Def. 4.1.6 fixes it** — `S^E` is displayed there as a 2×2 block matrix in `σ` with `|J^E|×|J^E|` blocks in `k`, i.e. **σ-major, l-minor**, corroborated by Rem 4.1.7's row vectors. Using that ordering, Eq. (17) holds by least squares to `≤3.1e-15` and `S^E` is unitary to `1.2e-14`. Since `a₁ ≥ … ≥ a_L`, `B^E` is always an initial segment, so only the `l`-vs-`σ` interleaving was ever open.

### C. Editorial / typos

- **p.9, Lemma 3.1.6(b) proof: "`We consider the compact set F := I + σ i[0,1]`"** — `σ` is the *component* index of `(·)_{l,σ}`; the branch is written `±`, and part (a) needs `F ⊆ ℂ̄_±∖𝔇`, which fails if `σ = −1` while the branch is `+`. Must be `F := I ± i[0,1]`. The correct form appears twice on p.14. Confirmed visually at 3.2×.
- **p.9, Lemma 3.1.6(a) proof:** inside `sup_{X∈J}` the radical still reads `−d/dE arccos(E/(2a_l))` — `E` where it should be `X`, twice in the same display. Confirmed at 3.2×.
- **p.10, Lemma 3.1.6(c) proof:** "`⊆ {((E,X),(E′,X′)) ∈ (I×J)² : …}`" — the set constructed two lines above is `I × I_r`, not `I × J`; `J` plays no role in (c). Confirmed at 4×.
- **p.11, Lemma 3.2.3:** "let `I ⊆ ℝ∖𝔇` **by** a compact subset" → "be". Confirmed at 4.5×.
- **p.16, Prop 3.2.4(b):** "no singular **continuos** spectrum". Confirmed at 4.5×.
- **p.17, Eq. (9)** cites the **Monotone** Convergence Theorem for `χ_{I_n} ↓ χ_I`, a *decreasing* sequence. *Substantially downgraded:* the decreasing form of MCT is a genuine standard theorem given an integrable first term, which Eq. (8) supplies, and the original list's supporting claim ("MCT is used correctly ten lines later for the increasing `O_n`") is **wrong** — that second use (p.18) is applied to a *decreasing* sequence of open sets too. The author is consistent. Reduce to: "if your MCT is the increasing one, add 'dominated' or 'by continuity from above'."
- **p.24, Theorem 4.4(a)'s "and thus"** silently uses `S^E(S^E)^* = 1`, i.e. Theorem 4.3. *Downgraded to editorial:* Thm 4.3 is stated **eleven lines earlier on the same page**, and the sentence after it already says the direct integral is unitary. Cite it inline; not a gap. (Unitarity independently reconfirmed twice: `‖S^*S − 1‖ ≤ 1.2e-14`, `|det S^E| = 1.000000000000`.)
- **p.20, Theorem 3.2.5(c)** uses the bounded functional calculus while citing only (b) (the *unbounded* intertwining `F_±H = M_Id F_±`). *Downgraded to editorial:* `H = H₀ + V` is **bounded**, so (b) iterates to `F_±H^n = M_Id^n F_±`, then polynomials → Stone–Weierstrass → bounded Borel `φ` by a monotone-class argument. One line to say why. (The route "via the resolvents" suggested in the first pass is unnecessary here.)
- **p.2 vs p.3:** the intro calls `H₀` "the discrete Laplace operator composed with the **left multiplication** by an invertible matrix `A`", while §1 defines `(H₀φ)(n) = A*φ(n+1) + Aφ(n−1)`. These agree only when `A = A*`; the `A*/A` form is the right one (verified: `⟨ψ,H₀φ⟩ = ⟨H₀ψ,φ⟩` holds for any `A` in the `A*/A` form, and only for `A = A*` otherwise). One-line intro nit. ("energy shift of the discrete Laplace operator" is itself correct.)
- **p.3, `{a₁,…,a_L} = σ(A)`.** *The original "this is simply false" claim is REFUTED* — the sentence reads "*after conjugation by a suitable unitary operator, we can, without loss of generality, **assume that** `A = diag(a₁,…,a_L)` with `{a₁,…,a_L} = σ(A)` and `a₁ ≥ … ≥ a_L > 0`*", and "assume that" governs the whole clause, so `σ(A)` is the spectrum of the *post*-conjugation `A`. The WLOG itself checks out by hand (conjugate by `U*`, then gauge by `(Wφ)(n) = diag(e^{inθ_l})φ(n)` with `λ_l = |λ_l|e^{iθ_l}`; `V(n) ↦ diag(e^{inθ})V(n)diag(e^{−inθ})` stays self-adjoint with the same norm). At most: add a parenthetical "(the new `A`; the `a_l` are the moduli of the original eigenvalues)". **Do not send `A = diag(i,1)` as a counterexample** — after the gauge that `A` is `diag(1,1)`.
- **`ℂ_σ` is never defined in paper 3** (used 9×). *But do not ask "open or closed?"* — **all 9 occurrences carry a closure bar, `ℂ̄_σ` / `ℂ̄_±`**, which the text layer drops. The question is already answered by the notation; the only defect is the missing one-line definition in §1. Also undefined (standard, but undefined): `c₀₀`, `M_Id`, `P_ac`, `P_pp`, `σ_pp`, `P_I(H)`, `U(H)`. (`λ₁` is introduced inline on p.14.)
- **8 unfilled `[TODO]` citation brackets (10 tokens):** p.3 ×2 (incl. "*This decay condition is optimal*", and the unitary reduction of `A`), p.5 ×2 (Prop 2.3, Thm 2.4), p.8 (Thm 3.1.5), p.23 (Def 4.2), p.24 (Thm 4.3), p.26 (acknowledgment).
- **p.2 forward reference:** the intro states `F₀H₀F₀^* = ∫^⊕ E·1 dE` and `F₀SF₀^* = ∫^⊕ S^E dE`, but the isomorphism `Ψ` that makes those parse is only built on p.24. *Downgraded to trivial* — the displays are correctly attributed on p.3 to Theorems 3.1.4 and 4.4(b).

### D. Two claims to strike, and one convention to reassure him about

**REFUTED — do not send: "Theorem 2.4 never says `D` is closed."** The paper writes **`𝔇̄`** — closure — in precisely and only the places where closedness is needed. Confirmed at 4× and by a programmatic scan for `\overline` rules, which finds **14 bars over `𝔇`** (and 9 over `ℂ`) that no text layer reproduces:
- **p.5, Theorem 2.4(b) reads "`𝔇̄` is at most countable"**, not "`𝔇` is at most countable".
- p.17: "*for every compact subset `I ⊆ ℝ∖𝔇̄`, by Lemma A.1, …*" — Lemma A.1's hypothesis "let `𝔇 ⊆ ℝ` be closed" is instantiated at `𝔇̄`, closed by construction.
- p.18 alone carries **11 bars**: "for every open subset `O ⊆ ℝ∖𝔇̄`", "`P_{𝔇̄}(H) = P_pp(H)`", "For the open set `O = ℝ∖𝔇̄`", "the set `𝔇̄` is at most countable and therefore a Lebesgue zero-set", etc.

Count: 14 `𝔇̄` vs 32 plain `𝔇`, and the split is exactly the mathematically correct one — `𝔇̄` closed + countable ⇒ nowhere dense, Lebesgue-null, `ℝ∖𝔇̄` open dense of full measure, which is everything Prop 3.2.4 needs. The plain-`𝔇` uses (Lemma 3.1.6(c), Lemma 3.2.3(a)) need only `dist(I,{±2a_l}) > 0`, which follows from `{±2a_l} ⊆ 𝔇` and `I` compact. **The author is being careful, not sloppy.**

**REFUTED — do not send: the `I` / `𝓘` symbol collision in Lemma 3.2.3(a)'s proof.** At 3.2× the number is calligraphic `𝓘` and the compact set is italic `I`; they are plainly distinct on the page. The collision exists only in the text layer.

**Proposition 1.2's reversed `∓` is deliberate and correct — reassure him, and ask only for a footnote.** p.4 verbatim: *"The wave operators `Ω_± := s-lim_{t→∓∞} e^{itH}e^{−itH₀}` exist and are complete…"*, with `S = Ω_-^*Ω_+`. Three independent confirmations:
1. **Internal consistency, by hand.** Eq. (15)'s `t → ∓∞` gives `∫_0^{∓∞} … e^{±εs}ds`. For the `+` branch (`t→−∞`, `e^{+εs}`), `s = −u`: `∫_0^{−∞} i e^{−is(H₀−E+iε)}ds = −i∫_0^∞ e^{iu(H₀−E)}e^{−εu}du = (H₀−E+iε)^{-1}` — **exactly the sign in Eq. (16)**, and exactly the sign Prop 3.2.6 is stated for. The other convention produces `∓iε` and Prop 3.2.6 no longer applies.
2. **It pairs `Ω₊` with the retarded eigenfunctions.** Thm 2.4(c) defines `w_{l,+} := lim (H−E−iε)^{-1}(H₀−E−iε)v`, i.e. the resolvent at `z = E + iε` — the upper half-plane / Lippmann–Schwinger `ψ^{(+)}` state. `Ω^{in}` built from `ψ^{(+)}` is the textbook pairing, and the `∓` chain locks Prop 1.2 ↔ Eq. (16) ↔ Thm 2.4(e) ↔ Thm 2.4(c) together.
3. **Measured.** L=1, a=1, V(0)=0.8, 601-site lattice, right-moving Gaussian, T=40 (stable vs T=60 at 4.6e-16; `flow(ψ₀,0) = ψ₀` to 8.6e-16; free centre-of-mass at `t = 0/+5/−5` = `0/+9.93/−9.93`):

| | vs `F₊^*F₀ψ₀` | vs `F₋^*F₀ψ₀` |
|---|---|---|
| `Ω₊` = flow at `t = −40` | **2.52e-14** | 5.92e-01 |
| `Ω₋` = flow at `t = +40` | 5.92e-01 | **2.60e-14** |

So Theorem 4.1 is confirmed and consistent with Prop 1.2's `∓`. **The only defect is presentational**: it is reversed relative to Yafaev / Amrein–Jauch–Sinha / most physics texts, which write `W_± = s-lim_{t→±∞}`. One sentence naming the source convention saves every reader the check. *(The attribution to [RS79] is UNSURE — see §4.)*

### E. Theorems checked against the code and confirmed

| Statement | measured |
|---|---|
| Thm 3.2.5(b) `F_±H = M_Id F_±` (the licence for `e^{−itE}` in step 10) | `7.2e-15` abs against scale 4.53 → 1.6e-15 rel; `F₀` version 2.4e-15 |
| Thm 3.2.5(a) `F_±^*F_± = P_ac(H)` | `≤4.1e-10` (θ-quadrature at band edges) with a bound state present; the gap to `‖f‖²` is 0.27–0.98, so the theorem is being tested, not trivially satisfied |
| Thm 2.4(d) `(H−E)w = 0`, both branches, five energies | `6.0e-15` |
| Thm 4.4(a) pointwise: `(F₊f)(E) = (S^E)^*(F₋f)(E)` | `≤4.9e-15` against scale 1.45–3.50 |
| Thm 4.3 unitarity | `‖S^*S−1‖ = 2.2e-16 … 1.2e-14`, `|det S^E| = 1.000000000000` — **but only with the `σ√ν_l` normalisation**; the change of basis between *unnormalised* `w`'s is not unitary |
| `outer_sign = +1` ↔ `w_{l,+}` (retarded) | clean `O(ε)`: `4.15e-3 / 4.17e-5 / 4.17e-7` at `ε = 1e-3/1e-5/1e-7`, vs `0.548` flat for the crossed pairing; `L=2` version `8.9e-3/9.0e-5/9.0e-7` vs `0.87`. Built from an *exact infinite-lattice* Krein-updated resolvent, validated against an 801-site lattice at 2.6e-16. |

---

## 1.4 The algorithm spec — `docs/MaxwellAlgorithm.pdf`

Three genuine math errors, all already corrected in the code under his April rulings. **What is new is that two of the three are now derivable from paper 1 and paper 2 directly, so they no longer rest on a ruling.**

**1.4.1 — Step 7's branch signs are inverted.** Spec prints `+` on `n > j_k`, `−` on `n ≤ j_k`. Paper 2 Def 3.1.1 (p.15, rendered) has **`−` on `n > j`, `+` on `n ≤ j`**, and Thm 3.1.3(a) proves `(K−E)G = δ_j 1_L`. So the spec's `G` is `(E−H)^{-1}` and step 8's minus double-counts. Measured (L=2, `a=(1.0,0.6)`, V at `j = −1,0,2`): paper-2 signs give `(H−E)G = +1_L` at `n = j_k` and `3.9e-15` off-site, `max|(H−E)w| = 1.8e-15`; the spec's literal signs give `−1_L` and `max|(H−E)w| = 1.400 = 2·max|V|`. *Strictly it is the **pair** (step 7 sign, step 8 sign) that is inconsistent; paper 2 + paper 3 Thm 2.4(c) (`w = v − (H−E∓i0)^{-1}Vv`) say the fix belongs in step 7, which is where he put it.* `green.py:69,73` implements it.

**1.4.2 — Steps 4/5 are off by a factor `i`, and the prefactor is attached to the wrong index.** The correct prefactor is `+i` on the `u_+` sum and `−i` on the `u_−` sum, **independent of `σ`** and tied to the lower `τ` index. Derivation, now complete from paper 1 alone: Lemma 3.1 (p.14) gives the Volterra equation with a **minus** and `(H₀−E)K(·,j) = δ_j 1_L`; Def 3.4 (p.18) gives `K^σ_ϕ(E,n,j) = A^{-1}s^{E,σ}(j−n)` for `j > n`; Lemma 2.11(c) (p.10) gives `s^{E,σ}(m) = (z^m − z^{−m})/(z − z^{-1})`; and `z − z^{-1} = 2i Im z` on the band, so `A^{-1}s^{E,σ}(m) = −i·ν_l(z^m − z^{−m}) = −i·s_spec`. Measured ratio `A^{-1}s / s_spec = 1.4e-17 + 1.000000j` at every `m`, both `σ` (to 6e-16). Hence `−K = +i·s_spec`. Residuals `max|(H−E)u|`: `+i/−i` **4.7e-16**; `−i/+i` 1.000; literal spec `±/∓` **7.07e-01** (`= 0.5·|1+σi|`); real `+1/−1` 7.07e-01. `jost.py:82-83` (`sgn_plus = +1j`, `sgn_minus = -1j`, σ-independent). **This means "Schober A.2" is no longer a ruling — it is a consequence of Definition 3.4 plus Lemma 3.1, and paper 1 should say so.**

**1.4.3 — Step 8's two indices are transposed; step 10 is correct as written.** Paper 3 Thm 2.4(c) makes `σ` the plane-wave/wave-vector sign and `±` the resolvent boundary branch; step 8 prints `w^{E,±}_{l,σ}` (plane wave driven by the upper index, `G` by the lower), while step 10 prints `w^{E,σ}_{l,±}` and matches paper 3 p.20 character-for-character. **The defect is localised in step 8, not shared between 8 and 10.** Repaired: `w^{E,σ}_{l,±}(n) := z_l^{−σn}e_l − Σ_k G^{E,±}(n,k)V(j_k)z_l^{−σ j_k}e_l`, which is `eigfunc.py` as shipped. Read literally, the spec sums over the *branch* and leaves the *wave-vector sign* free — which is not a state, and would drop half of Thm 2.4(d)'s basis.

**1.4.4 — Not fixed anywhere: the leading `σ` (§1.3.1) and the unbound `±` in step 10.** Step 10's `±` is bound by nothing — the only quantifiers are `n`, `t`, and the sums over `l` and `σ`. **And the two branches provably cannot give the same picture.** His own paper 3 Thm 4.4(a) says `F_− = (∫^⊕ S^E dE)F_+` and Thm 4.3 says `S^E` is unitary; nothing says `S^E = 1`. Measured, with both branches separately normalised to 1 to 1e-12: `V = 0` → difference `0.0`; one site → **0.281**; three sites → **0.353** (relative to `max ψ`). Least-squares fit of `w_{·,+} = w_{·,−}S^E`: residual **7.8e-16**, `‖S^*S−1‖ = 1.4e-15`, `‖S−1‖ = 0.270`. So `ψ_+[f] = ψ_−[S^E f]`, and the correct question is not "which branch" (both are exact unitary eigenbases, `(H−E)w = 8e-16` for both) but **what `f` is**: fixed data (branches must differ) or `f := F_β ψ₀` from a state (branches then agree to 1e-15). **`professor_response.txt` line 47 ("the videos should look exactly the same up to computer precision") is contradicted by his own Theorem 4.4(a).**

**1.4.5 — Smaller, but each blocks a literal implementation.**
- **Step 5 quantifies `n ∈ ℕ ∩ [N,M]`; must be `ℤ`.** Confirmed at 7× (blackboard `ℕ`, distinct from the `ℤ` glyph in steps 4/7/8/10). With `N < 0` — every preset — `u` would be undefined at `n = N, N+1`, which step 6 evaluates.
- **Data (e) permits the closed interval `[a,b] ⊆ [−2a_L, 2a_L]`, on which step 1 is ill-posed.** At `E = ±2a_l` the quadratic has the double real root `z = ±1`, so "the solution with `Im(z) > 0`" does not exist and step 3 divides by zero. Must be `⊂ (−2a_L, 2a_L)`. ("There will be two complex-valued solutions" is also false at the endpoints.) `model.py:99` + `quadrature.safe_open_band_interval` enforce this with a `1e-3` buffer — an undocumented fifth deviation from the written contract.
- **`A` is used in step 6 and never defined anywhere in the document.** Neither is `H`, `H₀`, nor the equation `ψ` solves. `K` is never introduced (it first appears as the subscript of `j_K`), `e_l` is never defined, step 10's `|·|²` on a `ℂ^L`-valued quantity is never explained, and step 7 inverts `W^{E,σ}_±` with no invertibility hypothesis. **Since `ψ` is meaningless without `A` and `H`, this is the largest omission in the document.**
- **Missing `1/(2π)`.** Paper 3 §3 p.6, Thm 3.1.4(b) and Def 3.2.1 p.11 put `1/√(2π)` in `F`, `F₀` and `F_±`; `|F_±^*f|²` therefore carries `1/(2π)`. Literal spec total `Σ_n ψ = 6.283185307134` (= `2π` to 11 digits); with `evolve.py:114`'s `/(p·2π)`, `0.999999999993`, constant across `t = −8, 0, 8`, both `V = 0` and `V = 0.8`, both branches.
- **Step 8 sums `l = 1,…,L` unconditionally**, where paper 3 restricts to `l ∈ B^E`. Consistent only because Data (e) forces `B^E = {1,…,L}`. Corollary worth telling him: **the spec as written cannot express the varying-multiplicity regime the three papers exist to describe.**
- Cosmetic: step 2 omits `and E ∈ [a,b]` from its quantifier list though `E` is free in the formula; `:=` vs `=` inconsistent across steps.

**Not defects — verified, so nobody "fixes" them.** Step 2's `∓` in `z_l^{∓n}` is deliberate and load-bearing (it converts the spec's `Im z > 0` root back to the papers' `Z_σ^n`; see §3). Step 6's missing `i` is harmless — `W_spec = −i W_paper`, and paper 2's `G` carries a compensating explicit `i` that the spec also drops, so `i(W_paper)^{-1} = (W_spec)^{-1}` exactly. Step 6's `E` rather than `Ē` is harmless on real `E`. Step 7's `n > j_k` / `n ≤ j_k` split is unambiguous *and* immaterial (paper 2 Lemma 3.1.2: the two expressions agree at `n = j`; measured `2.2e-15 … 5.1e-15`). Step 5's induction is well-founded. Anchoring step 6 at `N, N+1` is legitimate (paper 2 Prop 2.3.3; measured anchor-independence `1.3e-15 … 9.3e-15`).

---

## 1.5 DISPUTED / open, with the experiment that settles each

**D1 — Is paper 1 Theorem 3.7's uniqueness claim true?** The *gap* is confirmed (§1.1.6). The first pass said "the claim is true; the argument of Lemma 2.12(b) applied past the support forces `M_ψ = 0` then `M_ϕ = 0`; one paragraph fixes it." **That repair is refuted:** the standing hypothesis is only exponential decay (Def 1.1), so there is no "past the support", and Lemma 2.12(b) carries the hypothesis `E ∈ C^σ_{[−2a₁,2a₁]}` while Thm 3.7 ranges over all of `O^σ_α`, which for large `α` contains `E` with `σ Im E < 0`. **Status: UNSURE (very likely true by a Levinson/asymptotic-fundamental-system argument, but not one paragraph).** *Settled by:* take `V(n) = c·ρ^{−|n|}1_L` with `1 < ρ` just above `τ_A` (genuinely non-compact support), compute the full 2L-dimensional solution space of `(H−E)u = 0` by transfer matrices at large `|n|`, and check numerically whether the subspace with `ϕ^{E,σ}_τ(n)^{-1}u(n) → 1_L` is a single point. If it is, the paper needs a Levinson-type asymptotic argument, not a support argument.

**D2 — Does `(Ψ^E_-)^{-1}Ψ^E_+ = S^E`, and is the conjugating `diag(1,−1)` a convention or an artifact?** Paper 2 never connects §3 to §4 (§1.2.5). At L=1, `a=1`, `V = 0.7δ₀`, `E = 0.55`: `Ψ^E_+` maps the free basis diagonally onto `(b^{E,+}_+, b^{E,−}_-)` and `Ψ^E_-` onto `(b^{E,+}_-, b^{E,−}_+)`, and `T := (Ψ^E_-)^{-1}Ψ^E_+` is unitary (`|T^*T − 1| = 2.4e-15`) and equals `diag(1,−1)·S^E·diag(1,−1)`. **One L=1 example cannot settle a general convention, and the verifier declined to.** *Settled by:* rerun at L=2 (both open, then one open/one closed) and L=3 with the ordering fixed to σ-major/l-minor per paper 2 Def 4.1.6, and check whether the conjugating diagonal is always the blockwise `diag(+1,…,+1,−1,…,−1)` in `σ` or depends on `L`. If it is blockwise-in-`σ`, it is exactly the same `diag(σ)` that paper 3's leading `σ` supplies (§1.3.1) — which would be a satisfying cross-check.

**D3 — Is paper 3's `S^E` paper 2's `S^E`?** Unproven in the documents (§1.3.2); this is AUDIT §8 item 3 and it stays open. **Two independent reconstructions of the missing dictionary agree**: `w^{E,σ}_{l,±} = σ√ν_l · b^{E,σ}_{∓σ,l}`. *Settled by:* implement paper 2 Lemma 4.1.5(a),(b) (`M^E_σ = −σW(b^{E,σ}_{−σ}, b^{E,σ}_σ)`, `N^E_σ = σW(b^{E,−σ}_{−σ}, b^{E,σ}_σ)` **with the 4.1.5(b) edit accepted**) and Def 4.1.6's block layout, then compare against paper 3 Def 4.2's `S^E` obtained by least squares from the `w`'s, on the same `V`, at several energies. Inside the open band this is nearly free (`b^{E,σ}_τ` reduces to `u^{E,τσ}_τ ν^E`); with a channel closed it needs paper 2 Prop 4.2.2's projection, which is unimplemented.

**D4 — Should paper 2's `𝒮` read `2a₁`, or should Prop 2.1.4(b)'s strict clause be narrowed?** The inconsistency is real (§1.2.3), but the fix is not unique — `𝒮 → {|Re z| > 2a₁}` works, and so does restricting (b) to `ℂ_σ ∪ (𝒮 ∖ [−2a₁,2a₁])`. **And Prop 2.1.4 is quoted from `[BS25, Prop. A.3.2]`, so the discrepancy may originate there, not in paper 2.** *Settled by:* one sentence from him, or by `[BS25]`.

**D5 — Is `∓` in Prop 1.2 the Reed–Simon convention?** Internal consistency is confirmed three ways (§1.3.D). The *attribution* to `[RS79]` is UNSURE — neither pass could open Reed & Simon Vol. III to verify that it defines `Ω^± = s-lim_{t→∓∞}` and `S = (Ω^-)^*Ω^+`. *Settled by:* opening [RS79] §XI.3. Phrase the question to him as "I believe this is the [RS79] convention — could you confirm and add a footnote?", not as an assertion.

---

# 2. Questions to send him

Twelve, deduplicated across all four documents, ranked by how much they block work. Each is answerable in one or two sentences. Page references are to the PDFs as supplied.

---

**1. Paper 3, p.23, Definition 4.2 — which numbered results does `(cf. [BS26b, TODO,TODO])` point to?**
This is the only link between paper 3's `S^E` and paper 2's, and it is the paper's headline claim. My best reconstruction is `[BS26b, Def. 4.1.6 + Rem. 4.1.7]` for the definition and `[BS26b, Prop. 4.2.1]` for unitarity. Is the intended identification `w^{E,σ}_{l,±} = σ√ν_l · b^{E,σ}_{∓σ,l}`? (Paper 2 groups its bases by *side*, `(b^{E,σ}_{−σ})_σ` vs `(b^{E,σ}_{+σ})_σ`; paper 3 groups by *branch*, `w_{l,+}` vs `w_{l,−}` — that regrouping is what the two TODOs have to supply.) Encouragingly, the normalisers already coincide exactly: `⟨e_k|ω^{E,−}e_k⟩^{-1/2} = (4a_k²−E²)^{-1/4} = √ν_k`.

**2. Paper 1, p.18, Definition 3.4 — should `C_E` be `((Z_σ − Z_σ^{-1})(1 − P^E_=) − Z_σ P^E_=)^{-1}`?**
Recomputing the Wronskian on p.35, the `P^E_=` coefficient is `(2n−1)a_kε_k − En = −a_kε_k` with `ε_k = ±1` the eigenvalue of `Z_σ` there, which gives `−AZ_σP^E_=` rather than `−AP^E_=`. The two agree for `E > 0` and differ by a sign for `E < 0`; numerically `(H₀−E)K̃^σ_ψ − δ_j` is `2.000` at `E = −2a_2` with the printed `C_E` and `9e-16` with the corrected one, so Prop 3.6(b) fails at every negative threshold as printed. (Related and minor: `C_E` changes sign with `σ` on the open channels, so `C^σ_E` might read better.)

**3. Paper 1, p.18, Definition 3.4 — `P^E_1` is never defined in the paper.**
Am I right that it is the orthogonal projection onto the *strictly open* channels `{e_k : |z_σ(E/a_k)| = 1, E/a_k ≠ ±2}`, so that `P^E_1 P^E_= = 0`? That is the only reading under which `‖Z_σ(1_L − P^E_= − P^E_1)‖ < 1` (p.37) and `ψ^{E,σ}_+(n)^{-1}P^E_1 = ϕ^{E,σ}_+(n)` (p.33) both come out true. Definition 3.4 cannot be evaluated without it.

**4. Paper 2, p.21, Equations (14) and (15) — should every `σ` on the right-hand sides be `−σ`?**
As printed, the RHS of (14) computes `Φ^E_{−σ}b` and of (15) `Ψ^E_{−σ}b`. The origin looks like the first display on p.23, which expands `G^{E,−σ}_{H₀}(·,n)` using Definition 3.1.1 with label `σ` instead of `−σ`. Corrected, they match Eqs (16)/(17) to `5e-16`; as printed they are off by 0.36–1.5 (L=1, 2 and 3, open and mixed channels). **Note that Theorem 3.2.1(c) and (d) are unaffected** — the swap is consistent across the two displays, so the composition `Ψ∘Φ` is still the identity to `2e-16`. Two smaller things in the same proof: the Wronskian identity on p.23 should have subscript `H₀`, not `H` (exact with `H₀`, off by `‖V‖` with `H`); and the `[TODO]` in step (c) needs `b = Σ_± m^{E,−σ}_{H,∓}((W^{E,σ}_{H,±})^{-1})^* W(m^{E,σ}_{H,±}, b)`, which I verified to `4e-14` but could not find stated anywhere.

**5. Paper 2, p.15, Definition 3.1.1 — what are `O^σ_α` and `𝔇`?**
Neither is defined in paper 2. I read `O^σ_α` as paper 1's Definition 3.5 — is that right, and should the `α` be tied to the growth condition on `V`? And is the Fraktur `𝔇` the set `D̃` of Cor 4.2.3(b) (where `W(q^E_∓, q^E_±)` fails to be invertible), rather than the roman `D` of Def 2.2.3 that Def 4.1.6 and Prop 4.2.1 use? Lemma 2.3.9 with `B = C = 1_L` already shows `{E : W^{E,σ}_{K,τ} ∉ GL_L}` is discrete, which is exactly what a one-line definition of `𝔇` would need — and it would also make explicit that the thresholds are excluded (`W^{E,σ}_{H₀,τ} = τω^{E,σ}` is singular exactly at `E = ±2a_k`; I hit `cond W_{H₀} = inf` at `E = 2a₂` in a test run). Theorem 3.2.1(d)'s `𝔇′` — the complement?

**6. Paper 3, p.5, Definition 2.2 — should the algorithm's step 8 carry the leading `σ`?**
I've now checked what it does and does not do: it is **not** needed for unitarity (in Lemma 3.1.2 it enters as `σσ̄ = 1` and cancels; `‖F₀f‖²_K` is bit-identical with and without it), but it **is** needed for Theorem 3.1.4(b) to match Definition 3.1.1's `Φ`, and it conjugates `S^E` by `diag(σ)` — flipping the sign of every `σ ≠ σ′` block while leaving the transmission blocks alone (`‖S_noσ − D S^E D‖ = 0` exactly, `‖S_noσ − S^E‖ ≈ 1.0–2.6` against `max|S^E| ≈ 0.7`). For step 10 with a fixed `f` it is exactly "negate `f_{l,−}`". Should the code carry it? Separately: Definition 2.2 is stated for `E ∈ ℝ` with `B^E` built from **closed** intervals, but `√(−d/dE arccos(E/2a_l))` is infinite at `E = ±2a_l` — should Def 2.2 exclude the thresholds the way Prop 2.3 does?

**7. Paper 3, p.21, Proposition 3.2.6 — which repair do you intend?**
Two things. (a) The proof gets a *weakly* convergent subsequence from Banach–Alaoglu and then cites [Ru86] for an a.e.-pointwise subsequence, but that theorem needs `L^p` **norm** convergence and weak convergence does not give it (`e^{inx} ⇀ 0` in `L²` while `|e^{inx}| ≡ 1`). The last display of the same proof already gives honest pointwise convergence in `E` via Thm 2.4(e), and "bounded in `L²` + a.e. convergent ⇒ weakly convergent" would let you delete Banach–Alaoglu, the double subsequence and the citation outright — is that the intended route? (b) The hypothesis says "*and `E ∈ [−2a₁,2a₁]∖𝔇`*", but in the conclusion `E` is a bound integration variable; the object Eq. (16) actually needs is the **diagonal** `X ↦ (F_±V(H₀−X±iε)^{-1}g)(X)`. Under that reading the missing piece is a uniform-in-`ε` `K`-bound for the diagonal family — Thm 3.1.5(b) only gives it on **compact** `F ⊆ ℂ̄_σ∖𝔇`, and `[−2a₁,2a₁]∖𝔇` is not compact. Is the fix a localisation to compact `I ⊆ ℝ∖𝔇̄` via Lemmas A.1/A.2?

**8. Paper 2, §4.1 — I believe your outstanding sign edits are correct, and the "sign problem" title can come off.**
I rebuilt §4 independently (transfer-matrix Jost solutions and an asymptotic mode decomposition for the basis of `B(H,E)`, no use of the paper's formulas) at L=1, L=2 and L=3, all-open and mixed. Lemma 4.1.3 is correct exactly as printed (`W(b^{E,σ}_τ, b^{E,σ}_τ) = −σ1`; `+σ1` is off by exactly 2). The struck `−σ → σ` in Lemma 4.1.5(b) is **right** (`|W − σN| ≤ 1.7e-13`; `|W + σN| = 1.1–26`), so please accept that edit. 4.1.5(a),(c),(d), Prop 4.2.1 (`‖S^*S−1‖ ≤ 8.7e-14`), Rem 4.1.7 and Prop 4.2.2 (including the `τσ` label) all check out. Also: the note *"I do not understand this argument"* on p.26 is on the **basis claim**, and I think it is fine — Cor 2.2.5(a) gives a linear injection `B(H₀,E) → B(H,E)` for each `τ` (injective by Thm 2.2.4(b)), which maps a basis to a basis; Def 4.1.4's decompositions have residual `≤1.4e-15` in every case I ran. And your own p.30 question, "*What do you do with the inverse of `M^E_σ`?*", does look like a real gap: Cor 4.2.3(b)'s continuation needs `det M^E_σ ≠ 0` off the real axis, but the invertibility comes from Lemma 4.1.5(d)'s proof, which uses `W(b,b) = −σ1`, valid only for real `E` — so `D̃` should also exclude the zeros of `det M^E_σ`.

**9. Paper 1, p.24, Proposition 4.6 and the shape of §4.**
The proof is `...[TODO]` twice. Beyond that: does §4 need a hypothesis relating `sup_{|Y|<r} α_σ` to the potential's decay rate `ε`? Shrinking `r` alone doesn't seem to do it, because at a threshold `α_σ(E) = ‖Z_σ^{-1}‖ ≤ τ_A` with equality possible, while Definition 1.1 permits `ε = τ_A` exactly — which is presumably the same balance the p.20 `[TODO]` is about. And is the intended conclusion of §4 the corollary that `E ↦ u^{E,σ}_τ(n)` extends holomorphically in `Y = √(E−E₀)` across a threshold? The section currently stops before stating it. Separately, in Lemma 4.1 (p.22): should `r := √dist(w, {−2,2})` be the distance to the two branch **cuts** `±2 + σi(−∞,0]` rather than to the two branch **points**? For `w = 1 − 10i`, `σ = +`, the printed radius gives `r² = 10.05` while the cut point `2 − 10i` is at distance 1, and `z_σ` jumps by 10.38 there (it isn't even defined on the ray). The statement looks fine — only the radius.

**10. Paper 2, pp.2–3 — what is the standing hypothesis on `A`, and where is `a_k` defined?**
Section 1 has `(H₀φ)(n) = A*φ(n+1) + Aφ(n−1)` with `A` merely *invertible normal*, but Def 2.1.1 has `AΦ(n+1) + AΦ(n−1)`, and everything downstream uses the second form. In fact Prop 2.1.4(a), `A(Z_σ + Z_σ^{-1}) = E·1` with `Z_σ` diagonal, forces `A` to be **diagonal**, not just Hermitian, and p.12's `ω^{E,σ}e_k = −ia_k(…)e_k` presumes `Ae_k = a_k e_k`. Should the standing hypothesis just say `A = diag(a₁ ≥ … ≥ a_L > 0)`? And `a_k` is never defined anywhere in paper 2, though it is used from Def 2.1.3 on. Also, in Def 2.1.3, should `𝒮 := {|Re z| > 2a_L}` read `2a₁`? With `2a_L`, Prop 2.1.4(b)'s *strict* inequality fails (`a = (1.5,0.8)`, `E = 2.0 ∈ 𝒮` but `‖Z_σ‖ = 1` exactly) — though the alternative fix is to narrow (b)'s strict clause, and since Prop 2.1.4 is quoted from `[BS25, Prop. A.3.2]` the discrepancy may live there.

**11. The two `±` branches in step 10 of the algorithm cannot give the same picture — what should `f` be?**
Your paper 3 Thm 4.4(a) says `F_− = (∫^⊕ S^E dE)F_+` and Thm 4.3 says `S^E` is unitary; nothing says `S^E = 1`. So `ψ_+[f] = ψ_−[S^E f]`, and with a fixed `f` the two videos must differ whenever `V ≠ 0`. Measured, both branches separately normalised to 1 (to 1e-12): identical for `V = 0`; **28 %** different for one potential site, **35 %** for three; least-squares `w_{·,+} = w_{·,−}S^E` has residual `7.8e-16` with `‖S^*S−1‖ = 1.4e-15` and `‖S^E − 1‖ = 0.27`. Both branches are exact unitary eigenbases (`(H−E)w = 8e-16` for each), so the question isn't which is right — it's whether the user supplies `f` as fixed data (branches differ, and step 10's `±` needs binding) or as `f := F_β ψ₀` derived from an initial state (branches then agree to 1e-15). Relatedly, in your reply lines 51 and 52 cannot both stand: `z_l = e^{−i arccos(E/2a_l)}` has `Im z < 0`, so `ν_l = 1/(2a_l Im z_l)` is *negative* and `√ν_l` imaginary (measured `−0.389, −0.642`). The branch-free rewrite `ν_l(E) := 1/√((2a_l)² − E²)` makes step 3 agree with all three papers, the spec and the code simultaneously.

**12. Bibliography — can I get `[BS25]`, and should the keys be reconciled?**
Paper 2 cites `[BS25, Prop. A.3.2]`, `[BS25, Def. 2.1.4]`, `[BS25, Lem. 2.1.5(a)]`, `[BS25, Lem. 2.1.8]`, `[BS25, Cor. 2.2.3]`, `[BS25, Thm. 2.2.2(e)]` — every quoted proposition in §2 depends on it — but `[BS25]` carries no venue, year or arXiv number, and none of those pointers resolves against paper 1 as supplied (paper 1 has no Appendix A.3 and no §2.2.2; its counterparts are Def 2.3/2.6, Lem 2.5, Prop 2.7, Lem 2.12(d)(e), Thm 3.7, Lem 3.8). Paper 3 renames the same works `[BS26a]`/`[BS26b]`. Two small consequences: "Proposition 2.1.4(f)", cited four times in paper 2 (pp. 7 ×2, 15, 25), is I think **Proposition 2.1.9** — 2.1.4 is `[BS25, Prop. A.3.2]` and 2.1.9 is `[BS25, Prop. A.3.2(f)]`, so the source item letter got attached to the local number; and "Theorem 2.1.6(f)" on p.14 is presumably `[BS25, Thm. 2.2.2(f)]` by the same mechanism. Also, in both papers `[AW21]` reads "Actosun … Springer, 1979" — that should be **Aktosun**, **2021** (1979 looks copy-pasted from `[RS79]`), and `[AW21]` is cited nowhere in either body.

---

# 3. Convention conflicts

Verified numerically: `z₊ = e^{−i arccos(E/2a_l)}` (`Im < 0`), `z₋ = e^{+i arccos(E/2a_l)}` (`Im > 0`), `z₊ = z₋^{-1}` on open channels, `z₊ = z₋` on closed ones (paper 1 Lem 2.5(i)(j); paper 2 Prop 2.1.9).

| Object | Spec | Paper 1 | Paper 2 | Paper 3 | Code | **Wins for the code, and why** |
|---|---|---|---|---|---|---|
| **root branch** | step 1: "`Im(z) > 0`" ⇒ **z₋** | Def 2.3 + Lem 2.5(e)/(f): `0 < −σ Im z_σ` ⇒ **z₊ has Im < 0** | Prop 2.1.4(c): `0 ≤ −σ Im z_{σ,k}` ⇒ same | Def 2.2: `e^{−iσ arccos}` ⇒ **z₊** | `channels.py:31` `0.5*(b + 1j*√(4−b²))` ⇒ **z₋** | **Spec+code, but only as a composite** (next row). Letters conflict, mathematics does not. Papers 1/2/3 and `professor_response.txt` l.51 all use `z₊`. |
| **`φ_τ` exponent** | step 2: `φ^±(n) = diag(z_l^{∓n})` | Def 2.10: `φ^{E,σ}_τ(n) = Z_σ(E)^{τn}` | Def 2.1.5: identical | via `v`: `z₊^{σn}` | `jost.py:56-57` `Z^{∓n}` | **AGREE after composition:** `z₋^{∓n} = z₊^{±n} = φ^{E,±}_+`. The spec's two "errors" cancel exactly, and the spec's `σ` labels then agree with the papers' throughout steps 5–7. Verified `|z_code − e^{+i arccos}| = 1.1e-16`. |
| **`Z_σ` vs one `Z`** | one `z_l`, no `σ` | two branches `Z_σ` | two holomorphic `Z_σ : O_σ → GL_L` | implicit in `v` | one `Z` (= `Z₋`); `σ` carried by the exponent `Z^{−σn}` | **Code's trick is exact on the open band only** (`z₊ = z₋^{-1}` for `k ∈ J^E`). **It is false on closed channels** (`z₊ = z₋` there) — the first thing to rewrite when leaving the band. |
| **resolvent sign** | step 7 as printed gives `−δ` | Lem 3.1: `(H₀−E)K(·,j) = δ_j 1_L` | Thm 3.1.3(a),(g): `(K−E)G = δ_j 1_L` | Thm 3.1.5(d): identical | `green.py:69,73` `−G_right / +G_left` ⇒ `(H−E)G = +δ` | **Papers 1/2/3 unanimous; paper 2 Def 3.1.1 is authoritative** (it is the only document that *defines* `G`, and 3.1.3(a) *proves* the identity). Spec step 7 is the sole outlier. Measured `1.9e-15`. |
| **Wronskian leading `i`** | step 6: none | not defined | Def 2.3.1: `W(u,v)(n) := i[u(n+1)^*Av(n) − u(n)^*Av(n+1)]` | not used | none | **Keep omitting it.** Paper 2's `i` and the `i` in Def 3.1.1's numerator are a matched pair; dropping both is algebraically identical (`i(W_paper)^{-1} = (W_code)^{-1}`). Verified `W_code = −i·τ·ω^{E,σ}` exactly. **But never compare `wronskian.py` to paper 2 numerically without the `−i`.** |
| **`ν_l` / `ω` / normaliser** | step 3: `1/(2a_l Im z_l)` (>0 on `z₋`) | — | Def 2.3.5 `ω^{E,σ} := −iA(Z_σ − Z_σ^{-1})`; Def 4.1.1 normaliser `⟨e_k\|ω^{E,−}e_k⟩^{-1/2}` | Def 2.2: `√(−d/dE arccos(E/2a_l))` | `channels.py:34-40`, `√ν` in `evolve.py` | **All four agree numerically**: `1/(2a_l Im z₋) = 1/√(4a_l²−E²) = −d/dE arccos = 1/ω^{E,−}_{ll} = −1/ω^{E,+}_{ll}`. Note paper 2 **fixes `σ = −`** in the normaliser precisely so it is positive. **Safest form for the spec: `ν_l := 1/√((2a_l)² − E²)` — branch-free.** |
| **what `σ` labels** | steps 6–8: the **±i0 boundary**; step 10: the **wave direction** | `C^σ = {σ Im z > 0}` ⇒ boundary (collapses to direction on the open band) | same; `b^{E,σ}_τ`: `σ` = direction, `τ` = which end | superscript `σ` = direction, subscript `±` = boundary — **never collapse** | `green.py` `σ` = boundary; `eigfunc.py` `σ` = direction, `outer_sign` = boundary | **Paper 3's split wins, and the code already implements it.** The spec uses `σ` for both meanings *on the same page*. Settled numerically: `w_code[σ](outer_sign=β)·σ·√ν_l = w^{E,σ}_{l,β}` of Thm 2.4(c) to `O(ε)` — diagonal residual halves with `ε` (1.33e-1 → 1.29e-2 as `ε: 0.04 → 0.0025`, box to 64001 sites) while the crossed pairing is pinned at 0.346. |
| **`±i0` ↔ `green.py`'s `σ`** | not linked | — | — | Thm 2.4(c) | `sigma_idx = 0` | **Aligned, not inverted.** Direct comparison against `(H−(E±iε))^{-1}` on a 120001-site solve: `G[σ=+]` vs `E+iε` gives 0.186/0.079/0.040/0.016 for `ε = .05/.02/.01/.004` (clean `O(ε)`, ≈ 4ε) while `G[σ=−]` sits at 1.94–1.98. Independently pinned by paper 2 Thm 3.1.3(h) on `V = 0`. So `outer_sign = +1` is paper 3's `w_{l,+}`. |
| **leading `σ` on the free wave** | step 8: absent | absent | absent (`b^{E,σ}_{τ,k}`) | **Def 2.2 and Def 3.1.1: present** | absent | **Paper 3 wins — the code is missing it.** Not a bug in the eigenbasis (unitarity unaffected), but it changes what `f_{l,−}` *means* and it changes `S^E` by `diag(σ)`-conjugation. Needed before any comparison against paper 2's `S^E`. See §1.3.1 and question 6. |
| **Fourier normalisation** | step 10: none | — | — | §3 p.6, Thm 3.1.4(b), Def 3.2.1: `1/√(2π)` in `F`, `F₀`, `F_±` | `evolve.py:114` `/(p·2π)` | **Paper 3 wins**, and it confirms his ruling from his own text rather than from the student's numerics. Literal spec total = `2π` to 11 digits. |
| **`Ω_±`** | absent | absent | only `S = Ω^*_−Ω_+` in the intro | Prop 1.2: `Ω_± := s-lim_{t→∓∞} e^{itH}e^{−itH₀}` | absent | **Paper 3 is the only definition, and it is NOT a typo** — confirmed by the Abelian-limit sign chain, by the retarded pairing with Thm 2.4(c), and numerically (`Ω₊` = flow at `t = −40` matches `F₊^*F₀` to 2.5e-14; crossed pairing off by 59 %). |
| **channel set** | `l = 1..L`, `[a,b] ⊆ [−2a_L,2a_L]` | `I_E` (Def 2.8) — **the threshold set** | `J^E` (Def 2.1.8) — open channels | `B^E` (Def 2.2) — open channels | open band enforced `model.py:99` | Three letters. **Note the collision: paper 1's `I_E` is the *threshold* set, not the open-channel set** — a genuine naming clash, not a rename. |
| **`H₀`** | `Aφ(n+1)+Aφ(n−1)` | §1 `A*φ(n+1)+Aφ(n−1)`; Def 2.1 drops the `*` | p.2 `A*/A`; Def 2.1.1 `A/A` | p.3 `A*φ(n+1)+Aφ(n−1)` | `A` real diagonal | Harmless after the normal-form reduction (`A = A*`). Both papers 1 and 2 carry the internal `A*` vs `A` inconsistency (§1.2.2). |
| **decay condition** | finite support | Def 1.1: `∃ε ≥ τ_A, ε>1 : Σ‖V(n)‖ε^{|n|} < ∞` | Eq (1): `Σ‖V(n)‖τ_A^{|n|} < ∞` | Eq (1): `Σ‖V(n)‖·|n|·τ_A^{|n|} < ∞` | n/a | **Three different hypotheses.** Paper 3's `|n|` is strictly stronger than paper 2's and neither matches paper 1's `ε`-form (see §1.1.7). **Moot for the code — finite support makes all three vacuous.** |
| **`O^σ_α`** | — | **Def 3.5 (p.18) — the only definition** | used in Def 3.1.1, Lem 3.1.2, Thm 3.1.3 but **never defined** | — | n/a | Paper 1 wins by default; paper 2 must import or restate it. |
| **`D` / `𝔇` / `𝔇̄`** | — | — | roman `D` (Def 2.2.3), Fraktur `𝔇` (Def 3.1.1, Thm 3.2.1) — **different symbols, one undefined** | `𝔇` (32×) and `𝔇̄` (14×) — **deliberately distinguished, correctly** | n/a | **Paper 3's usage is the model**: `𝔇̄` exactly where closedness is needed. Paper 2 should define its `𝔇` (probably `= D̃`) and say how it relates to `D`. |

---

# 4. What I could not check

**Sources not available.**
- **`[BS25]` / `[BS26a]` / `[BS26b]` are not in the repo.** Everything paper 2 quotes in §2 (Prop 2.1.4, Def 2.1.5, Thm 2.1.6, Lem 2.1.8, Prop 2.1.9) and everything paper 3 quotes (Prop 2.3, Thm 2.4, Thm 3.1.5, Def 4.2, Thm 4.3) is a black box. In particular I could not check whether paper 2's `𝒮 = 2a_L` discrepancy (D4) originates in `[BS25, Prop. A.3.2]`, nor whether "Theorem 2.1.6(f)" resolves to `[BS25, Thm. 2.2.2(f)]`. **The chain paper 3 → paper 2 → `[BS25]` is not closed by the documents supplied.**
- **Reed & Simon Vol. III could not be opened**, so the attribution of Prop 1.2's `∓` to `[RS79]` is UNSURE (D5). The *internal* consistency of the convention is confirmed three ways.
- **Rudin, *Real and Complex Analysis* could not be opened**, so I cannot confirm the numbering "[Ru86, Thm. 3.12]". The finding in §1.3.3(a) does not depend on it: **no** theorem produces a.e.-convergent subsequences from weak convergence.
- **No LaTeX sources** — only PDFs. Several diagnoses (e.g. whether paper 3's `𝓘`/`I` really are different macros, whether paper 1's `ℓ^∞(ℕ ∩ [N,∞))` is a systematic macro error) would be one grep away with the `.tex`.

**Extraction limits.**
- **`\overline` is invisible to every text extractor tried.** This is not a minor nuisance: it produced two false accusations against paper 3 (`𝔇̄`, `ℂ̄_σ`) and one misquotation of paper 2's Theorem 3.2.1 hypothesis. **Paper 1's conjugation statements — Lemma 2.5(h), Prop 2.7(c), and several Appendix-A displays — were therefore deliberately NOT audited**, since they are exactly the class of statement that looks false without the bar. They are the largest un-reviewed block in paper 1. Settling them requires page renders at ≥300 dpi or the source.
- **Paper 2 carries live red edit marks** (strikethroughs, insertions, six referee notes) that survive only under image rendering. Anything in paper 2 read from text alone is suspect: struck material reads as live, and strikethrough rules read as `(((((((((`.
- Sub/superscript placement in the algorithm spec (steps 8 vs 10) is unreliable below ~6× magnification; those two were read at 8× and 6× respectively.

**Not settled by any pass.**
- **D1** — whether paper 1 Thm 3.7's uniqueness claim is true (only that the proof is missing and the proposed repair fails).
- **D2** — the `Ψ ↔ S^E` bridge: one L=1 example, one conjugated diagonal, no general statement.
- **D3** — whether paper 3's `S^E` is paper 2's `S^E`. Two independent reconstructions of the dictionary agree, which is encouraging but not a proof; the check past a threshold additionally needs paper 2 Prop 4.2.2's projection, which nothing implements.
- **Paper 2 §4's `b^{E,σ}_τ` past a threshold.** Everything in §1.2.C was verified with all channels open or with a closed channel handled by my own asymptotic split — not by paper 2's own Prop 4.2.2 route.
- **Whether the leading `σ` is meant to be folded into `f`** (§1.3.1) — that is an intent question only he can answer.
- **`S^E`'s `(l,σ)` ordering** was inferred as σ-major/l-minor from paper 2 Def 4.1.6's block layout and Rem 4.1.7's row vectors. It is self-consistent (unitarity to 1e-14 under that ordering) but not confirmed by him.
- **A Levinson winding check** over `σ(H₀)` gives exact integers and matches the `ℓ²` bound-state count in 5 of 8 test potentials; the 3 misses are stable under box growth (±300 → ±1200) and are therefore real, not a counting artifact. **UNSURE what the correct formula is** — the closing block of `S^E` tends to `−1₂` at each threshold, which plausibly supplies a half-integer per closing channel that the naive winding omits. Out of scope here; flagged because it bears on whether the threshold analysis in these papers is complete.

**Not attempted.** Nothing in the repo was modified. All numerics ran read-only against the shipped modules or against independent from-scratch implementations; where a number appears twice from two agents on different test systems, the two runs are reported separately rather than merged.
