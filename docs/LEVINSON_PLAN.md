# The Levinson Integral â€” final plan

**For:** Maxwell Schmutz Â· **Date:** 21 Aug 2026
**Status of everything below:** five researchers and two adversarial verifiers worked this. Where a verifier refuted or weakened a claim, the verifier wins and I say so inline. I re-ran the four most load-bearing scripts myself this session; those numbers are marked **(re-run)**.

---

# 1. What Schober just told you

He confirmed the finding. From `new_texts.txt:9`:

> **"The two videos should differ by S^E, they should not be the same!"**

and `new_texts.txt:12`:

> **"They would look the same if you start with the same state, but you are not, you are starting with the same Fourier transform under two different Fourier transforms, so if you transform back, you get two different states."**

That closes `AUDIT.md` Â§8 open question 1 and finding 1 in your favour: the Â± tripwire was never a bug, it was an input-convention question, and the state-based reading (`f = F_Î² Ïˆâ‚€`, agreement 4.3e-15) is the one that makes his test a theorem.

Then he proposed phase two, `new_texts.txt:14â€“15`:

> **"But it is still still good, that you did all your analysis, because that means that you can actually calculate S^E. So we could do a second part of the project in which we calculate the Levinson integral."**
> **"For this we actually need the determinant and everything you did."**

**What it means that he proposed this.** He is not handing you an exercise. Levinson's theorem is published for `A = 1` (constant channel dimension) and for varying dimension with a *single-site* potential on a half-line. For his model â€” `A = diag(aâ‚ â‰¥ â€¦ â‰¥ a_L)`, finite-support `V`, dimension of `S_E` dropping at every `Â±2a_l` â€” no researcher and neither verifier found a published theorem. "Levinson" appears in papers 1, 2 and 3 **only in the bibliographies, never in a body** (verified independently by two readers via PyMuPDF page sweep). He is pointing you at the gap between his own papers and the literature they cite.

And the "we actually need the determinant" line is literally correct: `det S_E` is the *only* thing Levinson needs, and it is the one part of your object that is immune to every convention still under dispute (Â§2, point 4).

**The practical detail, and it has a deadline.** `new_texts.txt:34`:

> **"On Tuesday I will present this research, so I want to convince them that this is the coolest shit ever."**

and `new_texts.txt:21, 30, 32`: *"Ok, but do you have the actual videos? I am just getting pictures."* â€¦ *"Can I also have this as a video?"* â€¦ *"And this?"*

Tuesday is **25 Aug â€” four days.** He needs MP4 files, not GIFs. Verified this session:

- `ffmpeg` is **not** on your PATH; `animation.FFMpegWriter.isAvailable()` returns `False` **(re-run)**.
- But `gui/main_window.py:539-561` (`_ffmpeg_available`) already falls back to the bundled binary, and it works: after registering `imageio_ffmpeg`, `FFMpegWriter.isAvailable()` = `True`, binary at `.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe` **(re-run)**.
- **The trap:** `pyproject.toml` puts `imageio-ffmpeg` in `[dependency-groups] dev`, not `[project] dependencies`. Any non-dev install falls back to GIF. And `maxwell.spec:13-16` has `binaries=[]`, `datas=[]`, `hiddenimports=[]` â€” a PyInstaller build may not carry the encoder at all. `README.md:138` still says "MP4 if you have ffmpeg on your PATH," which is stale.
- The harness already exists: `scratchpad/export_mp4.py` drives the program's own `ExportWorker` with the bundled ffmpeg, same figure, same styling as the Export button.

Also worth one line to him: **`AUDIT.md` finding 22 ("Paper 2 Def. 4.1.6's `S_E` layout â€” DISPUTED, do not cite") is now resolved.** Three independent readings agree â€” a 600 dpi page render, a 320 dpi render, and character-for-character agreement with the published `[BFNS24]` Definition 3, eq (7). Both minus signs are on the off-diagonal blocks.

---

# 2. What the Levinson integral is

## 2.1 You already know the hard part

The argument principle: take a closed loop `Î“`, walk it once, and watch the point `f(z)` move around in the complex plane. Count how many times it circles the origin. That integer is (zeros of `f` inside `Î“`) minus (poles inside `Î“`).

```
(1/2Ï€i) âˆ®_Î“  f'(z)/f(z) dz  =  Z âˆ’ P
```

The version you will actually compute is even simpler, because our `f` has **`|f| = 1` everywhere**. A point that never leaves the unit circle can only wind. So there is no residue calculus, no `f'/f`, no contour integral in code:

```
winding = ( unwrapped arg f at the end âˆ’ unwrapped arg f at the start ) / 2Ï€
```

That is `numpy.unwrap(numpy.angle(...))` and a subtraction. Everything below is bookkeeping about *which* `f`, *which* path, and *what the integer counts*.

## 2.2 What `S_E` is, in one paragraph

Fix an energy `E`. Some channels are **open** at that energy (a wave in channel `l` can actually propagate if `|E| < 2a_l`) and the rest are **closed** (the wave decays exponentially and carries no flux). Say `p` channels are open. Then there are exactly `2p` ways a wave can come *in* â€” `p` channels Ã— 2 directions (from the left, from the right) â€” and `2p` ways it can go *out*.

`S_E` is the `2p Ã— 2p` matrix that turns "what came in" into "what went out." Probability is conserved, so `S_E` is **unitary** â€” which forces `|det S_E| = 1` exactly. Measured in your repo: `â€–S*S âˆ’ 1â€– â‰¤ 7.3e-11` and `||det S| âˆ’ 1| â‰¤ 7.3e-11` over 20001 energies **(re-run)**; in a clean transfer-matrix implementation, `â€–S*S âˆ’ 1â€– â‰¤ 1.13e-14` and `|det S| = 1.000000000000` at every energy including deep inside the closed-channel gaps **(re-run)**.

## 2.3 Why the *determinant*, and why it is the safe object

Winding needs a single complex number tracing a curve. `det S_E` is that number.

It is also the one quantity in this project that no convention can break. Every convention you might get wrong â€” the `âˆšÎ½_l` flux normaliser, the channel ordering, a per-channel sign, the `Ïƒ`-major vs `l`-major index layout â€” enters as a **similarity** `S â†’ Dâ»Â¹ S D`, and `det(Dâ»Â¹SD) = det S`. Measured at `a = (1.3, 0.8)`: with and without the `âˆšÎ½` normaliser the *matrices* differ by `O(1)` (`â€–S*Sâˆ’1â€–` goes from `0` to `2.235`), while `max|det S_with âˆ’ det S_without| = 2.437e-15`.

**So the whole `âˆšÎ½` / leading-`Ïƒ` debate in `AUDIT.md` items 7 and 10 is irrelevant to Levinson.** `det S_E = det(Wâ‚‹â»Â¹Wâ‚Š)` directly. Only one convention survives to matter: the overall **orientation** (Â§2.5).

## 2.4 The phase shift, made concrete

For one channel and one site of potential, the algebra closes in three lines (derived independently by two people, matched to a transfer matrix and a direct matching solve at 601 energies, agreement `â‰¤ 5.7e-15`):

```
Î½(E) = 1/âˆš(4aÂ² âˆ’ EÂ²)          t = 1/(1 + i v Î½)        r = âˆ’i v Î½ /(1 + i v Î½)
det S = tÂ² âˆ’ rÂ² = (1 âˆ’ i v Î½)/(1 + i v Î½)        arg det S = âˆ’2 arctan(v Î½)
```

One number per energy: how much extra phase the wave picks up because the obstacle is there. That is the **phase shift**. Levinson's theorem says its total motion across the band is quantised.

Watch it happen. `L=1, a=1, V(0) = 0.8`. There is exactly one bound state (at `E = 2.154066`). `arg det S` starts at `âˆ’Ï€` at the left band edge, rises smoothly to `âˆ’0.76101` at `E = 0`, and returns to `âˆ’Ï€` at the right edge. **Zero crossings of Â±Ï€, zero winding** â€” despite there being a bound state. That is not a failure; it is the `âˆ’L` and the `Â½J_h` doing their job, and Â§2.6 explains where they come from.

Now put three strong sites in: `L=1, a=1, V = 3` at `n = 0, 3, 6`. Three bound states. `arg det S` crosses `Â±Ï€` **seven** times and the unwrapped phase runs `âˆ’3.141591 â†’ +9.424777`, a change of `4Ï€`. **Winding = 2.000000000** after extrapolation **(re-run)**. And `J_b + Â½J_h âˆ’ L = 3 + 0 âˆ’ 1 = 2`. âœ“

## 2.5 The formula, stated exactly, for *your* case

Let `aâ‚ â‰¥ â€¦ â‰¥ a_L > 0`. The thresholds are the distinct values in `{Â±2aâ‚, â€¦, Â±2a_L}`. For a threshold `t`, let `m_t` be how many channels have their band edge exactly there (`m_t = 1` when the `a_l` are distinct). Note `Î£_t m_t = 2L`.

> **Sweep `E` from `+2aâ‚` DOWN to `âˆ’2aâ‚`.** Equivalently, `Ï† = arccos(E / 2aâ‚)` from `0` up to `Ï€`, with `E = 2aâ‚ cos Ï†`.
>
> On each open arc `I_k` between consecutive thresholds, take a *continuous* branch of `arg det S_E` and let `W_k` be its total change divided by `2Ï€`. **Never unwrap across a threshold** â€” the jump there is a real feature, not a numerical artifact, and it is exactly what the `âˆ’L` term accounts for. Then
>
> ```
>     W  =  Î£_k W_k  =  J_b  +  Â½ J_h  âˆ’  L
> ```

- `J_b` = number of eigenvalues of `H`, with multiplicity, **including any embedded inside the band** (see caveat 1).
- `J_h` = total number of threshold resonances / half-bound states â€” bounded, not-square-summable solutions at a threshold â€” summed over **all** `2L` thresholds, not just the outer two.
- `L` = number of channels = (number of thresholds counted with multiplicity)/2.

**Sweeping the other way (`âˆ’2aâ‚ â†’ +2aâ‚`) gives the negative.** This is the single most dangerous detail in the project.

**Where the sign comes from, and why you must not take it on faith.** The published statements â€” Ballesterosâ€“Francoâ€“Schulz-Baldes 2021 Theorem 9 ([arXiv:2004.13099](https://arxiv.org/abs/2004.13099)) and Ballesterosâ€“Francoâ€“Naumkinâ€“Schulz-Baldes 2024 Theorem 4 ([arXiv:2211.05021](https://arxiv.org/abs/2211.05021)) â€” write it with `E` running *upward* from `âˆ’2` to `+2` and the same right-hand side. So relative to the literature, **your `S_E` is the complex conjugate**: `det S_repo(E) = conj(det S_BFNS(E))` exactly, measured at 6 energies by one reader and at 14 energies across three configurations (`L=1 A=1`; `L=2 A=1` complex-Hermitian `V`; `L=2 A=diag(1.3,0.8)`) by the verifier â€” ratio `+1.000000000` at every single energy.

The structural reason (derived, not guessed): with `Im z > 0` and the `e^{âˆ’itE}` convention, `z^n = e^{ikn}` has group velocity `dE/dk = âˆ’2a sin k < 0`, so `z^n` is **left**-moving. The literature's `S^z` maps outgoing to incoming; yours maps incoming to outgoing. Determinants are conjugates; windings flip.

**Ship a calibration test and never argue about it again.** `L=1, a=1, V = 1.0` at `n = 0` and `n = 3` gives `J_b = 2, J_h = 0, L = 1`, so `|W| = 1` and the sign of `W` fixes the orientation in one line. Measured through your own shipped modules: **`W = +1.000000000`, error `âˆ’1.08e-10`** **(re-run)**.

> âš  `docs/LEVINSON_GUIDE.md` Â§10 step 4 states the *opposite* orientation (`J_b + Â½J_h = L + Î£` with the sweep running `âˆ’2aâ‚ â†’ +2aâ‚`). That statement is for a different object â€” the guide's own `det S := conj(det W)/det W` from its Â§7 â€” not for the `S_E` your pipeline produces. Applying it to your `S_E` flips the sign. Correct the guide or delete that step.

### The caveats that survived verification

1. **`J_b` must include embedded eigenvalues, and a naive count will miss them.** For `A = 1` the literature proves eigenvalues can only sit outside `[âˆ’2,2]` (BFNS Prop. 19). **That protection is gone when the `a_l` differ**, and paper 3 Theorem 2.4(a) explicitly allows it: `{Â±2aâ‚,â€¦,Â±2a_L} âˆª Ïƒ_pp(H) âŠ† ð”‡`. Two people constructed the same counterexample independently: `a = (1.3, 0.4)`, `V(0) = diag(0.5, âˆ’1.0)` (channels decoupled) puts an eigenvalue at `E = âˆ’1.280625`, **inside** the band `[âˆ’2.6, 2.6]`. Counting only outside the outer band returns `J_b = 1` instead of `2`, and the Levinson residual is exactly `+1.00000`. Any channel-decoupled `V` with a bound state in a narrow channel triggers it. It dies under coupling (measured: turning on an off-diagonal `Îµ = 10â»Â³` removes it), so it is non-generic â€” but it is trivial to hit by accident.

2. **The threshold-resonance detector must use `(âˆ’1)^{m_t}`, not `(âˆ’1)^p`.** At a threshold `t`, the generic jump factor of `det S_E` is `(âˆ’1)^{m_t}`; a resonance shows up as `(âˆ’1)^{m_t âˆ’ J_h(t)}`. **This is a correction â€” the earlier rule "`det S â†’ +1` at a threshold means a resonance" is REFUTED.** At `a = (1.5, 1.0, 1.0)` two channels close at `E = Â±2` simultaneously, the generic jump is `(âˆ’1)Â² = +1` **with no resonance present**, and the old rule silently returns `J_b = 0` instead of `1`. Deduplicate the threshold list first: with repeated `a_l` there are fewer than `2Lâˆ’1` arcs (`a = (1.5,1,1)` gives 3, not 5).

3. **The determinant only sees `J_h(t) mod 2`.** That is precisely why the varying-dimension literature (Nguyenâ€“Parraâ€“Richard, [arXiv:2509.12684](https://arxiv.org/abs/2509.12684)) enumerates the threshold *matrix* rather than its determinant.

4. **Degenerate thresholds are otherwise fine.** The formula itself holds: residuals `1.04e-07` at `a=(1.5,1,1)`, `1.35e-07` at near-degenerate `a=(1,0.9999)`, `3.80e-11` at exactly degenerate `a=(1,1)`.

5. **DISPUTED / genuinely open â€” the theorem itself for your case.** For `aâ‚ = â€¦ = a_L` the formula is a published theorem. For **distinct `a_l` with a finite-support `K`-site `V`, no researcher and neither verifier found any published Levinson theorem.** The two nearest results miss on complementary axes: BFGS21/BFNS24 do finite support but constant dimension; Austenâ€“Parraâ€“Rennieâ€“Richard ([arXiv:2403.17617](https://arxiv.org/abs/2403.17617)) and NPR25 do varying dimension but for `V` supported on a **single site** of a half-line â€” paper 3's own introduction says exactly that: *"only the case of a potential V supported in a single point has been studied."* The verifier notes the search was demonstrably not exhaustive (a same-group April 2026 paper, `arXiv:2604.01391`, was missed â€” checked, and it does **not** close the gap: no matrix `A`, no varying dimension, no Levinson). **State this as "we found no citation," not "none exists," and ask Schober first.**

### What the evidence for the varying-dimension case actually is

| what | how much | how good |
|---|---|---|
| constant dimension, published theorem | BFGS21 Thm 9, BFNS24 Thm 4, transcribed verbatim by three independent readers | it is a theorem |
| constant dimension, numerical | 69 configurations (`L=1..3`, `K=1..3`, negative/large/multi-site/degenerate `V`, `J_h = 1,2,3`) | worst error `9.6e-12` after Richardson |
| through *your* shipped modules | 7 configurations | errors `âˆ’1.08e-10 â€¦ +1.03e-09` **(re-run)** |
| **varying dimension** | 12 configurations at `L=2, L=3` and doubly-degenerate spectra | `â‰¤ 1e-7` |
| varying dimension, arc-by-arc, crude grid | `a=(1.3,0.8)`, `(1,0.99)`, `(2,1,0.5)`: arc sums `âˆ’0.00359`, `+1.99801`, `âˆ’1.00555` vs targets `0`, `+2`, `âˆ’1` | `O(âˆšÎµ)` from the cusps **(re-run)** |
| **the Â½ at an *interior* threshold** | two engineered resonances at `a=(1.3,0.8)`, one outer + one interior | `J_h = 2` residual **`0.0000000`**; `J_h=1` and `J_h=3` both off by exactly `0.5` **(re-run)** |

**That is strong evidence, not a proof, and it must be labelled that way in anything you show Schober.**

## 2.6 Where the `âˆ’L` and the `Â½` come from â€” measured, not asserted

**The `âˆ’L`.** Turn off the potential entirely. `a = (1.3, 0.8)`, `V = 0`. Then `J_b = 0` and the winding is `âˆ’0.000000000`, but `J_b âˆ’ L = âˆ’2`. The resolution: **all four thresholds are exceptional.** Measured edge/jump factors: `+1.0000000000` at `E = Â±2.6` and `+1.0000000000` at `E = Â±1.6` â€” all four exceptional, so `J_h = 4` **(re-run)**. Then `0 + 4/2 âˆ’ 2 = 0` âœ“. The `âˆ’L` is what the *free* system already contributes; Levinson counts what the potential adds on top.

**The `Â½`.** A threshold resonance sits *on* your contour, not inside it. When you indent around a pole that lies on your path you go halfway around, so you collect half of what a full loop gives. Concretely: `L=1, a=1, V = âˆ’3` at `n = 0, 1, 2` has `J_b = 2` and one half-bound state at `E = âˆ’2`. Target `2 + Â½ âˆ’ 1 = 1.5`. Measured through your own pipeline: **`W = 1.500000000`, error `+1.40e-11`** **(re-run)**.

### Explicitly dropped or downgraded (verifier wins)

- **Dropped:** the Aktosunâ€“Weder Theorem 9.3 quotation. It was a silent rearrangement presented as a verbatim quote, with an `N` that collides with a channel count used one paragraph earlier. It was decorative; do not carry it.
- **Downgraded to a note:** the warning that APRR/NPR write the winding with the opposite sign to BFGS. Both published statements rearrange to `#Ïƒ_p + C/2 âˆ’ N = Var` â€” the same shape as BFGS. Keep the practical advice (calibrate; never assume), drop the claimed conflict.
- **Downgraded:** "`np.unwrap` silently loses whole turns; assert `max|Î” arg| < Ï€/2` and refine." Not reproducible â€” uniform and cosine-substituted grids agreed to six decimals at every resolution from 501 to 32001 nodes, and the proposed assertion would have *falsely rejected* a uniform grid returning the right answer. Keep the cosine substitution (it does cut the max step ~4Ã—). Drop the hard gate. The real rule that survives is "never unwrap through a threshold."
- **Corrected:** "`M_Ïƒ` becomes singular at a half-bound threshold â€” that is intrinsic." It is an artifact of `channels.py:40`'s `Î½ = 1/(2a Im z)`. The transfer-matrix route stays at `8.9e-16` where the repo route degrades to `1.1e-2`.
- **Dropped:** the "partial winding = +0.73101139" figure for `a=(1.3,0.8)`. Unreproducible (the `V` was never stated; the verifier's own `V` gave `+0.83350823`) and meaningless â€” the quantity drifts as `O(âˆšinset)` and never lands on any integer, by construction.
- **Downgraded:** the 72-case least-squares fit headline (`slope 0.999999332458, RÂ² = 0.99999999998`). The slope deficit was entirely their own un-extrapolated `O(Îµ_Ï†)` truncation. With two-point Richardson the slope is `1` to `1e-15`. Report the relation as exact, not as a regression.

**What survives untouched:** the `O(âˆšÎµ)` threshold-cutoff law and two-point Richardson (`W â‰ˆ (10Â·W(Îµ/100) âˆ’ W(Îµ))/9`) â€” error ratios per factor-100 in `Îµ` measured at `11.82, 10.24, 10.02, 10.00`, i.e. exactly `âˆšÎµ`, giving `1e-7â€¦1e-15` accuracy for free.

---

# 3. Where the code already is

## 3.1 The single most important operational fact

**The refuted claim:** that `eigfunc.py` / `green.py` are "not on the critical path," and that you need a new `smatrix.py` (~55 lines solving for `M_Ïƒ, N_Ïƒ`) plus a same-Ïƒ generalisation of `wronskian.py`.

**REFUTED.** The shipped chain `channels â†’ jost â†’ wronskian â†’ green â†’ eigfunc`, **unmodified**, already contains `S_E`. You read the asymptotic coefficients off `full_eigenfunctions` at the slab edges â€” about 20 lines, outside the repo, vectorised over the whole energy axis in one call. Re-run this session, `REFUTE/H_repo_levinson.py`, Richardson from `Îµ_Ï† âˆˆ {1e-5, 1e-6}` on a 20001-node `Ï†` grid:

```
case                              pred  Richardson        err   max|detS_repoâˆ’detS_tm|  ||det|âˆ’1|
L=1 V=(1,1)@0,3                    1.0  1.000000000  âˆ’1.08e-10             6.22e-10     2.84e-14
L=1 V=(âˆ’3,âˆ’3,âˆ’3)@0,1,2 (Jh=1)      1.5  1.500000000  +1.40e-11             1.16e-04     1.16e-04
L=1 V=(3,3,3)@0,3,6                2.0  2.000000000  âˆ’1.76e-10             5.33e-10     1.48e-14
L=2 V=diag(2,2)@0     DEGENERATE   0.0 âˆ’0.000000000  âˆ’8.38e-16             1.78e-10     3.33e-14
L=2 V=I@0, I@4        DEGENERATE   2.0  2.000000000  âˆ’2.28e-10             1.24e-09     4.12e-14
L=2 K=3 complex-Hermitian          4.0  4.000000000  âˆ’3.64e-10             1.07e-09     7.32e-11
L=3 K=2 complex-Hermitian          2.0  2.000000001  +1.03e-09             6.93e-09     9.25e-10
```

**Zero new repo lines.** The incidence check (`Î±_L = I`, `Î²_R = 0` for `outer_sign = +1`) holds to `1e-16`, which also independently confirms `+1` is the retarded branch. The `1.16e-04` on the half-bound row is the `channels.py:40` conditioning artifact, and note the winding is *still* correct to `1.4e-11` despite it.

Also: your existing `wâ‚Š = wâ‚‹ S` change-of-basis matrix `S_cob` has `|det S_cob âˆ’ det S_transfer-matrix| â‰¤ 6.5e-15` in every configuration, **including `a = (1.3, 0.8)`** on the sub-band the code can currently reach. But `|S_cob* S_cob âˆ’ 1| = 0.16â€¦0.28` there â€” it is unitary only when the `a_l` are equal. **The determinant is robust; the matrix identification is not.** For Levinson that is all you need.

## 3.2 The gap list, per file

| file:line | what is wrong / missing | blocks | size |
|---|---|---|---|
| `spectral/maxwell/channels.py:30-31` | `np.maximum(4.0 âˆ’ b*b, 0.0)` clamps. Past a threshold it returns `z = E/(2a_l)`, which is **not a root**: at `E=2.5, a=1` the residual of `zÂ² âˆ’ (E/a)z + 1` is **`âˆ’0.5625`** **(re-run)**. Correct closed-channel branch: `z = (b âˆ’ sgn(b)âˆš(bÂ²âˆ’4))/2`, the `\|z\|<1` root | everything past the first threshold | ~6 lines |
| `channels.py:40` | `1/(2 a Im Z)` â†’ `inf` past threshold **(re-run: `nu at E=2.5 -> inf`, divide-by-zero RuntimeWarning)**. Analytic continuation `Î½ = i/(a(z âˆ’ 1/z))` agrees with the shipped one to **`0.0`** on the band and stays finite past it | same; also the near-threshold conditioning collapse | 1 line |
| `channels.py:25` | `np.asarray(E, dtype=float)` **silently discards `Im E`** â€” `channel_momenta([0.5+0.1j],[1.0])` returns `0.25+0.96824584j`, the `z` for `E = 0.5`, with only a `ComplexWarning` **(re-run)** | only an off-band complex-`E` contour, which the recommended plan does not use â€” but make it **raise** regardless | 2 lines |
| `model.py:98-107` | `validate()` hard-rejects any interval outside `[âˆ’2a_min + buffer, +2a_min âˆ’ buffer]`. At `a=(1.3,0.8)` you cannot even construct a spec for `\|E\| > 1.599` | constructing a threshold-crossing run | ~5 lines, or a separate spec path |
| `quadrature.py:86-128` | `safe_open_band_interval` / `safe_open_band_segments` clip in `E` with `threshold_buffer`. Levinson needs a **`Ï†`**-buffer. `gauss_legendre` (`:9`) is reusable unchanged | contour construction | ~15 lines |
| `__init__.py:14-18` | exports only `MaxwellSpec, compute_psi, maxwell_to_frames`. No public way to get `S_E`, `u_Â±`, `W` or `G` | ergonomics only | ~5 lines |
| `wronskian.py:56-61` | uses `np.conj(...)`, so `W` is anti-holomorphic in `E`; and only ever forms the opposite-Ïƒ pairing | **NOT a blocker.** Needed only for an off-band complex-`E` contour. The real-axis route does not touch it | 0 for this plan |
| `tests/` | 0 of 32 tests touch `S_E`, `det S`, bound states, or the band edge. `AUDIT.md` item 7(b) ("flux-weighted unitarity of `S(E)`") is now a prerequisite | correctness | ~120 lines |
| `pyproject.toml:8-14` | `imageio-ffmpeg` is in `[dependency-groups] dev`, not runtime deps | MP4 export on a clean install | 1 line |
| `maxwell.spec:13-16` | `binaries=[] datas=[] hiddenimports=[]` | MP4 from the packaged `.exe` â€” verify before relying on it | verify |
| `gui/main_window.py:923` | `in_outer.currentTextChanged â†’ _field_edited` makes the Â± comparison impossible from the GUI (`AUDIT.md` item 2, still open) | live demos | 1 line |
| `gui/main_window.py:1393-1397` | `eval()` on the V-matrices field is a working RCE (`AUDIT.md` item 14 / action item 4, still open) | hygiene | 1 line |

**Timing is not a constraint anywhere.** `S_E` + `det` costs 53 Âµs/energy at `L=2, K=2`, flat in `n_E`. A converged Levinson integral is ~7 ms with 128 Gaussâ€“Legendre nodes in `Ï†`.

**Parametrise in `Ï†`, not `E`.** `arg det S` has a square-root cusp at the band edge in `E` and is nearly linear in `Ï† = arccos(E/2aâ‚)`. Gaussâ€“Legendre in `Ï†` converges at `n = 64`; in `E` with a `1e-6` buffer it is still 0.3% off at `n = 1024`. And there is a hard float64 floor: `2a cos Ï†` underflows to exactly `2a` below `Ï† = âˆš(2 Îµ_mach) â‰ˆ 2.1073e-08` **(re-run)** â€” so an `E`-parametrised API cannot push the limit past `Îµ_Ï† â‰ˆ 1e-7`. Feed `z = e^{iÏ†}` directly.

## 3.3 Bound states: **parallel, not a prerequisite**

- **To compute the integral** you need only `S_E` on the band. No bound-state machinery at all.
- **To check the integral** you need `J_b` and `J_h` independently. Without them the number is unverifiable.
- **To *use* the theorem** (count bound states from scattering data) you need `J_h` and the threshold detector, but not `J_b`.

So: two tracks that must meet at the check. Start the integral today; build the counter alongside.

### âš  Do not ship the recommended counter â€” it is refuted

The "exact Jost-determinant counter" (`scratchpad/exp7_diag.py:15-63`) is a **sign-change scan on `np.real(det F(z))`**. A sign-change scan provably cannot see an even-order zero. Run verbatim **(re-run)**:

| `V` | its `J_b` | true `J_b` | its Levinson prediction | truth | measured winding |
|---|---|---|---|---|---|
| `L=2 diag(2,2)@0` | **0** | 2 (`E = 2.8284271247` twice) | `âˆ’2.0` | `0.0` | `0.000000000` |
| `L=2 diag(âˆ’2,âˆ’2)@0` | **0** | 2 | `âˆ’2.0` | `0.0` | `âˆ’0.000000000` |
| `L=3 1.5Â·I@0` | **1** | 3 (`E = 2.5` Ã—3) | `âˆ’2.0` | `0.0` | `0.000000000` |
| `L=2 I@0, I@4` | **0** | 4 | `âˆ’2.0` | **`+2.0`** | `2.000000000` |
| `L=2 diag(2,âˆ’2)@0` (control) | 2 | 2 | `0.0` | `0.0` | `0.000000000` |

**Silent errors of 2.0 and 4.0.** It is *worse* than the `eigh` failure it was meant to replace: `eigh` errs low and visibly (fixed by enlarging the box); this errs low and invisibly (no box size fixes it). It was correct on all 36 random Hermitian cases and wrong on 3/3 degenerate ones â€” random `V` never hits degeneracy, which is why the 72-case sweep looked clean.

### What to use instead

1. **Primary:** dense/banded `eigh` on a truncated slab with a **box-size convergence gate** â€” compute at `h` and `2h` and require both the count and the positions to agree. Justified by minâ€“max: the compression's outside-count is a lower bound converging monotonically up (verified monotone in all 39 stress configs, never exceeding `Î£_k rank V(j_k)`). It genuinely misses weakly-bound states: `v = Â±0.002` (binding `1e-6`) gives counts `[0,0,0,1,1]` for `h = 200,400,800,1600,3200`, so the gate is mandatory, not optional.
2. **Cross-check:** zeros of the Jost determinant `det Mâ‚â‚(E)` off the band, counted **with multiplicity** â€” localise by `Ïƒ_min(Mâ‚â‚)`, then get the multiplicity from a small argument-principle circle in `E` (or from `nullity(Mâ‚â‚)` by SVD). Never from a sign change.
3. **Sanity anchor for `K=1`:** bound states are exactly the roots of `det( sgn(E)Â·diag(âˆš(EÂ² âˆ’ 4a_lÂ²)) âˆ’ V(jâ‚) ) = 0`. Verified 9/9 against `eigh` to `<1e-9`.
4. **Ceiling:** the total number is bounded by `Î£_k rank V(j_k)`, and that bound is attained (verified in all nine `(L,K)` cells over 162 random trials). `2KL` is not the right shape.
5. **`J_h`:** at threshold `t` with sign `s = Â±1`, count `nullity(Mâ‚‚â‚)` in the degenerate free basis `{s^n, nÂ·s^n}`. Verified against 14 tuned two-site families, all giving exactly `0.50000000` with errors `â‰¤ 1.6e-10` **(re-run)**.

---

# 4. The plan

Assume ~10 h/week of evenings.

---

### â–¶ STEP 0 â€” **START HERE TODAY.** Ship Schober his MP4s. (~1 hour)

**Do:** adapt `scratchpad/export_mp4.py` (it already drives the program's own `ExportWorker` with the bundled ffmpeg) to render the "Schober 1 â€” two-channel window" and "Schober 2 â€” two-channel + barrier" presets (`gui/main_window.py:379, 388`) plus whichever two stills he pointed at. While you are there, move `imageio-ffmpeg` from `[dependency-groups] dev` to `[project] dependencies` in `pyproject.toml`, and fix the stale `README.md:138` line.

**Done looks like:** four `.mp4` files in his hands before Tuesday.

**Check:** open each one; confirm `FFMpegWriter.isAvailable()` printed `True` before rendering (it does after `imageio_ffmpeg` is registered â€” verified this session); confirm the total-probability readout is not decaying to zero by `t_max` (`README.md:143-147`: ten of thirteen presets lose most of their mass; Schober 1 retains only ~20% â€” widen `N`/`M` if so, or trim `t_max`).

**Could go wrong:** if you export from the packaged `.exe`, `maxwell.spec:13-16` may not carry the encoder and you silently get GIFs again â€” the exact failure he already hit. Render from source.

---

### STEP 1 â€” Calibrate the sign, in your own repo. (1 evening)

**Do:** run `L=1, a=1, V = 1.0 @ n=0` and `n=3` through `channels â†’ jost â†’ wronskian â†’ green â†’ eigfunc`, read `S_E` off the slab-edge asymptotics, sweep `Ï†` from `0` to `Ï€`, and print the winding.

**Done:** you get `+1.000000000` (target `J_b + Â½J_h âˆ’ L = 2 + 0 âˆ’ 1 = +1`). Commit it as `tests/test_levinson.py::test_orientation`.

**Check:** repeat with `V = âˆ’3 @ n=0,1,2` â†’ `+1.500000000` (`J_b=2, J_h=1`); and `L=2, a=(1,1), V = diag(2,2) @ 0` â†’ `âˆ’0.000000000` (`J_b=2` double, target `0`). All three verified **(re-run)**.

**Could go wrong:** nothing, and that is the point â€” this is the cheapest insurance in the project. If it comes out `âˆ’1`, your orientation is reversed and everything downstream would have been wrong by a global sign.

---

### STEP 2 â€” `spectral/maxwell/levinson.py`. (~2 evenings, ~40 lines)

**Do:** (a) a `Ï†`-contour builder with an `Îµ_Ï†` inset; (b) arc-by-arc `np.unwrap(np.angle(det S))`, summed, never unwrapping across a threshold; (c) two-point Richardson in `Îµ_Ï†`: `W = (10Â·W(Îµ/100) âˆ’ W(Îµ))/9`.

**Done:** the seven-case table in Â§3.1 reproduces from inside the package.

**Check:** the residual to the nearest half-integer is your error bar. Errors of `1e-10` mean it works; errors of `0.5` or `1.0` mean the *count*, not the integral, is wrong.

**Could go wrong:** `Îµ_Ï† < 2.1e-8` hits the float64 floor and `channels.py:40` throws `LinAlgError`. Do not go below `1e-7`; use Richardson instead â€” it gets you `1e-15` from `Îµ_Ï† âˆˆ {1e-5, 1e-6}`.

---

### STEP 3 â€” A bound-state counter you can trust. (1 weekend, ~50 lines)

**Do:** `eigh` with a box-size convergence gate as primary; `Ïƒ_min(Mâ‚â‚)` + argument-principle multiplicity as cross-check; the `K=1` closed form as an anchor. **Delete any sign-change scan.**

**Done:** `V = diag(2,2)@0` returns `2`, `V = I@0, I@4` returns `4`, `v = Â±0.002` returns `1` after the gate forces `h â‰¥ 1600`.

**Check:** the two methods must agree in *count and multiplicity* on all five degenerate cases in Â§3.3, and the total must never exceed `Î£_k rank V(j_k)`.

**Could go wrong:** you build a "localised in band" IPR filter to catch embedded eigenvalues and it lies to you â€” measured, an IPR > 1e-2 filter at `a=(2,1,0.5)` reported 4 gap states at `h=400` and 2 at `h=800`, positions moving by `8e-3`. Pure truncation. Trust only exact constructions in the gaps until you have a real criterion (stack the closed-channel columns at two adjacent sites and require `Ïƒ_min = 0` â€” verified to track the coupling linearly).

---

### STEP 4 â€” The half-bound detector. (~2 evenings)

**Do:** `J_h(t)` from `nullity(Mâ‚‚â‚)` in the degenerate basis, cross-checked against the jump-factor parity `(âˆ’1)^{m_t âˆ’ J_h(t)}`. Deduplicate the threshold list first.

**Done:** the tuned families reproduce. For two sites at `0, 3` with `a=1`: `w = v/(3vâˆ’1)` puts a resonance at `E = +2`, `w = âˆ’v/(1+3v)` at `E = âˆ’2`. All 14 tuned cases give `0.50000000` **(re-run)**.

**Check:** the free case must give `J_h = 2L` and `W = 0`.

**Could go wrong:** using `(âˆ’1)^p` instead of `(âˆ’1)^{m_t}` â€” silently off by one whenever two `a_l` coincide.

---

### STEP 5 â€” Fix `channels.py` so the code can leave the open band. (~1 week)

**Do:** two edits. `channels.py:30-31` â†’ branch on `|b| < 2` and return `(b âˆ’ sgn(b)âˆš(bÂ²âˆ’4))/2` off band. `channels.py:40` â†’ `Î½ = i/(a(z âˆ’ 1/z))`. Also make `channels.py:25` **raise** on complex `E` rather than truncating.

**Done:** residual of `zÂ² âˆ’ (E/a)z + 1` is `â‰¤ 3.3e-16` at every energy including past both thresholds of `a = (1.3, 0.8)`; agreement with the shipped code on the common open band is exactly `0.0`; `Î½` is real-positive on open channels and purely imaginary on closed ones; all 32 existing tests still pass.

**Check:** `max |(Hâˆ’E)u| / |u|` over all four Jost families off band â€” measured `9.46e-16 / 8.04e-16 / 2.08e-15 / 1.60e-15` at fully-open, gap, and outside-band energies. Steps 1â€“5 of the algorithm continue to work unmodified once these two lines change.

**Could go wrong:** steps 7â€“8 blow up if you push through with the shipped Wronskian. Measured: with corrected `Z, Î½` but the shipped `compute_wronskians`, `max rel |(Hâˆ’E)w|` is `2.44e+295` in a gap and `5.68e+287` outside the band â€” and `cond(W)` stays *small*, so it will not warn you. That is the next step's problem, and it is why step 6 builds a separate reduced `S_E` rather than routing through `green.py`.

---

### STEP 6 â€” The reduced `S_E` of dimension `2|B^E|`. (2â€“4 weeks)

**Do:** at each `E`, split channels into open `O` and closed `C`; impose boundedness (`Î²_L[C] = 0`, `Î±_R[C] = 0`); the remaining solution space is exactly `2|O|`-dimensional; read off `(Î±_L[O], Î²_R[O]) â†’ (Î±_R[O], Î²_L[O])`. This is **not** structurally blocked â€” the earlier claim that it is "unpublished mathematics, not a coding gap" was **REFUTED**: a from-scratch implementation is ~25 lines.

**Done:** unitary in the gaps. Verified **(re-run)**: `a=(1.3,0.8)` â†’ `â€–S*Sâˆ’1â€– â‰¤ 9.78e-15`; `a=(1,0.99)` â†’ `â‰¤ 1.13e-14`; `a=(2,1,0.5)` â†’ `â‰¤ 9.67e-15`, with `dim S` stepping `2 â†’ 4 â†’ 6 â†’ 4 â†’ 2` and `|det S| = 1.000000000000` at every energy.

**Check:** it must reduce **exactly** to the literature `S` when all channels are open. Two independent implementations got `max|S_red âˆ’ S_BFNS| â‰ˆ 3e-16` and a `det` ratio of `+1.000000000000`.

**Could go wrong:** building it on top of the repo's `green.py` route rather than as a standalone. Build it standalone first, then reconcile â€” the standalone version is the ground truth.

---

### STEP 7 â€” The varying-dimension Levinson run. (2â€“4 weeks)

**Do:** arcs between deduplicated thresholds, cosine substitution inside each arc, Richardson in `Îµ`, `J_b` from step 3 **including embedded eigenvalues**, `J_h` from step 4.

**Done:** residual `< 1e-4` on â‰¥10 configurations across `L = 2` and `L = 3`, including at least one with an engineered interior-threshold resonance and one with a deliberately embedded eigenvalue.

**Check:** the crude version already lands **(re-run)**: `a=(1.3,0.8)` arcs sum to `âˆ’0.00359` vs target `0`; `a=(1,0.99)` to `+1.99801` vs `+2`; `a=(2,1,0.5)` to `âˆ’1.00555` vs `âˆ’1`. Measured jumps of `arg det S` at every interior threshold: `+3.0037Ï€`, `âˆ’2.9965Ï€`, `+1.0040Ï€`, `+1.0031Ï€`, `âˆ’0.9989Ï€`, `+1.0029Ï€` â€” all `â‰¡ Ï€ (mod 2Ï€)`, i.e. `det S` picks up exactly `âˆ’1` per crossing. That is the discontinuity APRR24 is named after, measured in your model.

**Could go wrong:** the residuals here are `O(âˆšÎµ)`, roughly `5e-3` on a crude grid. Getting to `1e-6` needs the cosine substitution *and* Richardson. If a residual sits stubbornly at `0.5` or `1.0`, suspect `J_h` parity at a degenerate threshold or a missed embedded eigenvalue â€” not the integral.

---

### STEP 8 â€” The memo. (1 week)

Two pages: the formula in his notation, the table of configurations with residuals, the threshold jump factors, and an explicit statement that the varying-dimension case is **numerically verified, not proved**, with the two gaps in the literature named. Plus the questions in Â§6.

---

# 5. What to learn, in order

Ruthlessly minimal. Everything here is on the path; anything not here is off it.

```
                    ALREADY YOURS (name them, don't relearn them)
        Jost solutions Â· Wronskian Â· transfer matrix Â· resolvent (you measured it) Â· unitarity
                                          â”‚
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚                                                                  â”‚
[A] ARGUMENT PRINCIPLE â”€â”€â”€â”€ [B] det AND log-det â”€â”€â”   [C] JOUKOWSKI z â†” E, BRANCH CUTS
   winding number              Jacobi's formula   â”‚       which root is which
   â”‚                                              â”‚                  â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â–¼
              [D] SPECTRUM: essential vs discrete, Â±i0
                          â”‚
                          â–¼
              [E] SCATTERING VOCABULARY: Î©Â±, S, phase shift, spectral shift
                          â”‚
                          â–¼
              [F] THRESHOLDS: half-bound states, band edges, varying multiplicity
                                    â† this is the research
```

**[A] and [C] are both on-ramps and independent.** [A]+[B] alone is enough to *state* Levinson. [C] alone is enough to *fix the code*. **CUT entirely:** K-theory / index-theoretic Levinson (Richard's survey is beautiful and it is a trap â€” BFNS's proof is classical complex analysis and papers 1â€“3 contain zero K-theory); Fredholm determinants and trace ideals (every determinant here is at most `6Ã—6`); unbounded operators and self-adjointness (`H` is bounded, `â€–Hâ‚€â€– = 2aâ‚`); measure theory and the machinery in paper 3 pp. 11â€“21; inverse scattering / GLM; general direct-integral theory (`âˆ«^âŠ•` here just means "an `E`-dependent matrix").

---

### [A] Argument principle and winding number â€” the on-ramp

**Why here:** BFNS Theorem 4 *is* the argument principle. `(1/2Ï€i)âˆ® d log det S` = winding of `det S` about the origin. There is no second idea in the theorem, and you already own most of this.

**Minimum:** winding number about 0; `(1/2Ï€i)âˆ® f'/f = Z âˆ’ P`; and that when `|f| = 1` the winding is just `Î”(arg f)/2Ï€`. RouchÃ© is nice-to-have. Skip Hopf degree, Schwarzâ€“Pick, residue calculus beyond the one statement.

**Resource:** 20 minutes â€” 3Blue1Brown, *Winding numbers and domain coloring*, <https://www.youtube.com/watch?v=b7FxPsqfkOY>. Then Needham, *Visual Complex Analysis*, **Ch. 7 Â§I (Winding Number), Â§III (Polynomials and the Argument Principle)**, and Â§V (RouchÃ©) if you want it. Skip Â§II and Â§VIâ€“VIII.

**Exercise with your own code:** run `L=1, a=1, V(0)=0.8` and plot `det S_E` in the complex plane as `E` sweeps the band. `|det S| = 1` to `1e-14`, so the curve lies on the unit circle and the winding is visible by eye. Then add sites one at a time â€” `V=(1,1)@0,3`, then `V=(3,3,3)@0,3,6` â€” and watch the winding count `0 â†’ 1 â†’ 2`. **~5 hours.**

---

### [B] Determinant, trace, log â€” much smaller than it sounds

**Why here:** the integrand is `det(S)â»Â¹ d/dE det(S)`. That is all.

**Minimum:** *one formula.* Jacobi's: `d/dE log det M = tr(Mâ»Â¹ Mâ€²)`. Plus `det(AB) = det A det B` and `det` is a polynomial in the entries, hence holomorphic wherever they are.

**Resource:** none needed beyond a linear-algebra reference. Verify it numerically instead.

**Exercise:** on your own `S_E` for `L=1, K=2`, compare `d/dE log det S` (finite difference) with `tr(Sâ»Â¹ dS/dE)`. Verified agreement `3.3e-10 â€¦ 7.3e-09` across five energies â€” and note the **real part is `â‰¤ 1e-9` everywhere**, so the integrand is purely imaginary. That is unitarity forcing the Levinson number to be real, and you can see it. **~2 hours.**

---

### [C] Joukowski map, branch cuts, which root â€” the other on-ramp

**Why here:** step 1 of your own algorithm *is* the Joukowski map `E = a_l(z + 1/z)`. Verified: `aÂ·(z + 1/z)` recovers `E` with max imaginary part `1.4e-16`; `arg z = arccos(E/2a)` exactly; `|z| = 1` on the band to `0.0e+00`; the two roots multiply to `1.000000000000`. So `z â†¦ 1/z` is the deck transformation and `âˆš(EÂ² âˆ’ 4aÂ²)` is the branch.

The whole varying-multiplicity phenomenon is one table:

| region | paper 1 Lemma 2.5 | measured |
|---|---|---|
| inside band `\|Re w\| < 2` | (j) `zâ‚Š = zâ‚‹â»Â¹` | `zâ‚ŠÂ·zâ‚‹ = 1.000000` |
| outside band | (i) `zâ‚Š = zâ‚‹` | `zâ‚Š/zâ‚‹ = 1.000000` |
| everywhere | (b),(c) `\|z\|=1` iff `w âˆˆ [âˆ’2,2]`, else `<1` | `1.000000` on band, `0.500000` at `w = 2.5` |

Inside the band the two branches are distinct (two travelling waves); outside they merge into one exponentially decaying solution. The number of open channels drops by one at every `Â±2a_l`. **That is "varying spectral multiplicity" in one line of numbers.**

**Minimum:** multivalued `âˆš`, branch point, branch cut, and "trade a two-valued function of `E` for a single-valued function of `z`." Skip Riemann surfaces, sheaves, covering spaces, genus.

**Resource:** Needham Ch. 2 Â§V plus the conformal-mapping chapter; free supplement with pictures of `z + 1/z` mapping the circle to `[âˆ’2,2]`: <https://personalpages.manchester.ac.uk/staff/yanghong.huang/teaching/AE3410/conformal.pdf>. Then **paper 1, Def 2.3 + Lemma 2.5 (pp. 5â€“9)** â€” tell yourself out loud that paper 1 Â§2 is a *complex analysis* paper, the most approachable of the three for you.

**Exercise:** reproduce the table above; then reproduce the failure (`z = 1.25` at `E=2.5`, residual `âˆ’0.5625`, `Î½ = inf` **(re-run)**); then fix it in four lines and confirm `0.0` change on the band and `â‰¤3.3e-16` residual past it. **~8 hours, and it ends with a shippable patch.**

*One-hour aside worth taking here:* `Î½_l(E) = âˆ’d/dE arccos(E/2a_l)` â€” verified to `9.3e-11` for `a = (1.3, 0.8)`. So your step-3 `Î½` is simultaneously (a) the density of states, (b) the change-of-variables Jacobian that makes the Fourier transform unitary, and (c) the derivative of the scattering phase with respect to energy â€” which is exactly what Levinson integrates. Three names, one object.

---

### [D] Spectrum vs eigenvalues, essential vs discrete, `Â±i0`

**Why here:** `J_b` counts *discrete* spectrum and you cannot count it without knowing it is separate from the band. Also, `G^{E,Ïƒ}` in step 7 *is* the resolvent, and your `outer_sign` *is* which side of the cut you stand on. **You already ran this experiment** â€” `AUDIT.md` Â§4 item 5: `|G_code âˆ’ (H âˆ’ (E+iÎµ))â»Â¹| = 3.3e-08 at Îµ = 1e-8`, scaling as `O(Îµ)`. The gap is vocabulary, not understanding.

**Minimum:** `Ïƒ(H)` is bigger than the eigenvalue set on an infinite lattice; `Ïƒ(Hâ‚€) = [âˆ’2aâ‚, 2aâ‚]` is purely absolutely continuous; discrete spectrum = the finitely many honest `â„“Â²` eigenvalues; the `Â±iÎµ` limits exist and **differ**, and that difference is the branch index. Skip: domains, spectral measures, Stone's formula.

**Resource:** Teschl, *Mathematical Methods in Quantum Mechanics*, free PDF (AMS-permitted) at <https://www.mat.univie.ac.at/~gerald/ftp/book-schroe/> â€” **Ch. 5** (resolvent and spectrum) and **Ch. 6 Â§6.2â€“6.3** (spectral types). Statements only; skip the proofs.

**Exercise:** truncate `H` to `(2h+1)L` sites, `eigvalsh`, and watch the band fill with an ever-denser cloud as `h` grows (essential spectrum â€” never a finite point set) while the outliers stay put (discrete). Then build the counter from Step 3 and reproduce the embedded eigenvalue at `a=(1.3,0.4)`, `V(0)=diag(0.5,âˆ’1.0)`, `E = âˆ’1.280625`, and watch a coupling of `Îµ = 10â»Â³` kill it. **~10 hours.**

---

### [E] Scattering vocabulary: `Î©Â±`, `S`, phase shift, spectral shift

**Why here:** so you know what `S_E` *is*, not just that it is the matrix your two branches differ by. Paper 3 does the whole job in three statements you can read directly: `Î©Â± := s-lim_{tâ†’âˆ“âˆž} e^{itH}e^{âˆ’itHâ‚€}` (Prop 1.2, p. 4 â€” note the `âˆ“`, flagged in `AUDIT.md` Â§8 item 8); `Î©Â± = FÂ±* Fâ‚€` (Thm 4.1, p. 22); `S = Î©â‚‹*Î©â‚Š = Fâ‚€*(âˆ«^âŠ• S^E dE)Fâ‚€` (Thm 4.4, p. 24), where `S^E` is defined (Def 4.2, p. 23) as **exactly the change of basis you already extracted numerically**.

**Minimum:** `Î©Â±` compares the true evolution with the free one; `S` maps "what it looked like in the far past" to "what it looks like in the far future"; `S` commutes with `Hâ‚€`, so it is block-diagonal in energy and `S_E` is one block. Skip existence/completeness proofs, Katoâ€“Rosenblum, Cook's method â€” paper 3 p. 4 disposes of existence in six lines by citing `[RS79, Thm XI.8]`, and so can you.

**Resource:** Teschl, *Jacobi Operators and Completely Integrable Nonlinear Lattices*, free PDF at <https://www.mat.univie.ac.at/~gerald/ftp/book-jac/> â€” **Ch. 12 (Scattering theory)**, the scalar version of your entire problem, cited by paper 1 as `[Te00]`. Plus Teschl *MMQM* **Ch. 16** for the `Î©Â±` vocabulary, and `[BFNS24]` <https://arxiv.org/abs/2211.05021> Â§3 (Def 3: the `T`/`R` block structure) and Â§7 (proof of Levinson).

**The best exercise in the whole curriculum:** the **spectral shift function** `Î¾(E) = âˆ’arg det S_E / 2Ï€`. Compute it two ways â€” (i) from `numpy.angle(numpy.linalg.det(S))` on a `2Ã—2` matrix, and (ii) by counting eigenvalues of a truncated `H` below `E`, subtracting the same count for `Hâ‚€`, averaged over 200 box sizes to smooth the finite-box quantisation. Verified agreement: mean `|difference| = 0.0125`, max `0.197`, over three configurations. After this, "phase shift" is not a word â€” it is "how many eigenvalues the potential pushed past this energy," and you computed it twice by unrelated means. Levinson is then just the endpoint values. **~2â€“3 weeks, and this is the block I would not compress further.**

---

### [F] Thresholds, half-bound states, varying multiplicity â€” the research

**Why here:** everything genuinely new lives here, and it is the only thing between you and the multi-channel result.

Three things happen at `E = Â±2a_l`, all visible in your numbers: (1) `z` stops being analytic in `E` â€” the good local coordinate is `âˆš(E âˆ“ 2a_l)` (paper 1 Lemma 4.1, p. 21); (2) `Î½_l` diverges like `1/âˆš(4a_lÂ² âˆ’ EÂ²)` â€” measured `15.81` at `E = 1.999`, `inf` at `E = 2.0`, which is what `model.py:12`'s `threshold_buffer` was guarding; (3) `|B^E|` drops and `S_E` literally changes size.

And here is why the theorem needs `lim_{Îµâ†’0}` rather than just a small buffer: **a third of the total phase motion happens in the last 1% of the band.** Measured convergence `âˆ’0.654 â†’ âˆ’0.890 â†’ âˆ’0.965 â†’ âˆ’0.989` as the buffer goes `1e-2 â†’ 1e-5`. The careful limit is not fussiness; it is where the answer lives.

**Minimum:** local uniformiser at a square-root branch point; what a bounded-but-not-`â„“Â²` threshold solution is; that `S_E` changes dimension and the closed-channel modes must be **dropped**, not computed wrongly.

**Resources, in order:** `[BFGS22]` <https://arxiv.org/abs/2008.02177> (band-edge limit of `S`, explicit formulas â€” an entire published paper about this one point, which tells you how hard it is); `[APRR24]` <https://arxiv.org/abs/2403.17617> (topological Levinson with embedded thresholds, changes of multiplicity, discontinuous `S`); `[NPR25]` <https://arxiv.org/abs/2509.12684> (the follow-up: "the full picture," including doubly degenerate thresholds). Read **paper 1 Â§4 (pp. 21â€“24)** in parallel â€” but know going in that **Prop 4.6's proof is literally `...[TODO]`**. The threshold section of your professor's own paper is unfinished. That is an opportunity, not an obstacle.

**Exercise:** Steps 4, 6 and 7 of Â§4. **4â€“8 weeks of real work; expect longer.**

---

## Two-week plan (~20 h)

Goal: **a real, presentable result plus one shipped code fix.**

| Day | Do | h |
|---|---|---|
| 0 | **Step 0 â€” the MP4s.** Ship them before Tuesday. | 1 |
| 1 | 3Blue1Brown winding video; Needham Ch. 7 Â§I, Â§III | 2 |
| 2 | **Step 1 â€” the calibration.** Get `+1.000000000` and commit it as a test | 2.5 |
| 3 | Plot `det S_E` on the unit circle; add sites; watch `0 â†’ 1 â†’ 2` | 2 |
| 4 | **Step 2 â€” `levinson.py`.** Arcs, unwrap, Richardson | 3 |
| 5 | Reproduce the seven-case table from inside the package | 2 |
| 6 | Jacobi's formula; confirm the integrand is purely imaginary to `1e-9` | 1.5 |
| 7 | Read **BFNS24 Theorem 4**; match it term-by-term to your own table | 2 |
| 8 | Joukowski: reproduce the Lemma 2.5 table; reproduce the `âˆ’0.5625` failure | 2 |
| 9 | **Step 5 (first half)** â€” patch `channels.py`; confirm `0.0` on band, `3.3e-16` off it; run `pytest` | 2.5 |
| 10 | Write the one-page memo: the table, the formula, the caveats | 1.5 |

**Deliverable:** the seven-case table with residuals at `1e-10`, produced from his own code, plus a strict-improvement patch to `channels.py`. That is the second message to Schober and it opens the phase-2 conversation properly.

**Explicitly NOT in two weeks:** wave operators, spectral theorem, direct integrals, anything from paper 2 Â§4.

## Three-month plan (~120 h)

- **Month 1** â€” Weeks 1â€“2 as above. Week 3: **[D]** resolvent and spectrum (Teschl *MMQM* Ch. 5, Ch. 6 Â§6.2â€“6.3) plus **Step 3**, the trustworthy bound-state counter. Week 4: **Step 4**, the half-bound detector, plus the `Î½`-has-three-faces aside. *Checkpoint: you can read paper 3 Â§Â§1â€“3.1 and Thm 4.4 without stopping.*
- **Month 2** â€” Week 5: `Î©Â±`, `S = Î©â‚‹*Î©â‚Š` (Teschl *MMQM* Ch. 16 statements; paper 3 Prop 1.2, Thm 4.1, Def 4.2, Thm 4.4). Week 6: **the spectral-shift exercise** â€” the keystone. Week 7: Teschl *Jacobi Operators* Ch. 12; connect to your transfer-matrix ground truth (`3.198e-15`, `AUDIT.md` Â§3 finding 4). Week 8: BFNS24 Â§5 and Â§7. *Checkpoint: you can derive Levinson for `L=1` and explain every symbol in Theorem 4.*
- **Month 3** â€” Week 9: read `[BFGS22]`, `[APRR24]`, `[NPR25]`; paper 1 Â§4 alongside. Week 10: **Step 5** completed, plus `model.py`/`quadrature.py`. Week 11: **Step 6** â€” the reduced `S_E`. Week 12: **Step 7** â€” the full-band `a = (1.3, 0.8)` and `a = (2,1,0.5)` runs, and **Step 8**, the memo.

**In parallel, all three months** (unrelated to Levinson, keeps the tool trustworthy): `AUDIT.md` action items 2 (GUI outer-sign wiring, one line), 4 (`eval` â†’ `ast.literal_eval`), and 7 (the four missing tests â€” item 7(b), flux-weighted unitarity of `S(E)`, is now directly load-bearing).

---

# 6. Open questions and risks

## What is genuinely unknown

1. **Is there a published Levinson theorem for varying dimension + finite-support `V`?** Neither a researcher nor a verifier found one. The nearest results miss on complementary axes (Â§2.5 caveat 5). The verifier explicitly softened the finality: a same-group April 2026 paper (`arXiv:2604.01391`) was missed by the first search â€” checked, it does not close the gap, but the search was demonstrably not exhaustive. **Ask Schober before you assume it is open.**

2. **The correct *signed* threshold bookkeeping for varying dimension.** The empirical law works, and the jump factor `(âˆ’1)^{m_t}` is measured at every interior threshold **(re-run)**. But the verifier's own caveat stands: *"the threshold jumps sum to a multiple of 2Ï€ in all three cases, so my arc-sum bookkeeping is unambiguous mod 1 but I have not derived the correct signed accounting â€” that is genuinely the [APRR24]/[BS25] content."* This is the actual research content and the thing a proof would have to supply.

3. **DISPUTED â€” is `[BS25]` a fourth manuscript?** One reader: a genuinely absent third/fourth document where `J^E`, `z_{Ïƒ,k}` and the Jost existence theorem live (cited as `[BS25, Prop. A.3.2]`, `[Def. 2.1.4]`, `[Thm 2.2.2]` on paper 2 pp. 4â€“5, and behind several of paper 2's 19 broken `??` refs). The verifier: **UNSURE** â€” paper 2's introduction cites `[BS25]` in the *same sentence slot* where paper 3 later cites `[BS26b]` (= paper 2 itself), which suggests it may have been absorbed. **Settled by one line to Schober.** Note what *is* settled: `[BS26a]` = paper 1, `[BS26b]` = paper 2, confirmed from paper 3's bibliography and paper 2's title page.

4. **Is `J_b` even finite in this model?** Paper 3 Thm 2.4 says only `Ïƒ_pp(H) âŠ† ð”‡` with `ð”‡Ì„` at most countable â€” and asserts it as a citation with `TODO`. Nothing localises eigenvalues, nothing bounds their number, and BFNS Prop. 19's exclusion of embedded eigenvalues **does not carry over**. If `J_b` were infinite the theorem would be false as stated. Empirically the total never exceeded `Î£_k rank V(j_k)` in 200+ trials, and that bound is attained â€” but that is evidence, not proof.

5. **Is paper 2's `S_E` (Def 4.1.6) the same object as paper 3's `S_E` (Def 4.2)?** Paper 3 marks the identification `(cf. [BS26b, TODO,TODO])` and `([BS26b, TODO])` â€” **the two `TODO` placeholders *are* the identification**, and paper 3's own introduction calls closing this gap its headline contribution. Verified numerically here at `max|Sâ‚ƒ âˆ’ Sâ‚‚| â‰¤ 1.9e-15` (and *not* up to adjoint or inverse â€” those differ by `0.56â€“0.92`), but on **one model** (`L=2, K=3`, complex-Hermitian non-diagonal `V`, 7 energies, all channels open). This matters because your `S_E` is extracted paper-3-style (`wâ‚Š = wâ‚‹ S`) while the literature formula is paper-2/BFNS-style.

6. **Paper 1 Â§4's Prop 4.6 proof is `...[TODO]`.** That proposition is the local uniformisation at a threshold â€” the single input a Levinson theorem most needs (it is what produces BFNS's `(zâˆ“1)^{J_hÂ± âˆ’ L}` exponent). It is the least finished thing in the corpus.

## What could sink the project

| risk | evidence | mitigation |
|---|---|---|
| **The sign.** A global orientation error flips every answer | your `S_E` really is the conjugate of the literature's, confirmed at 20 energies across 4 configurations | Step 1, one line, done in an evening |
| **The bound-state count.** Silent integer errors | the refuted counter returned `0` where the truth is `2`, and `1` where it is `3`; Levinson errors of `2.0` and `4.0` **(re-run)** | Step 3: two independent counters + convergence gate; never a sign-change scan |
| **Embedded eigenvalues.** Silent `âˆ’1` per missed state | `a=(1.3,0.4)`, `V(0)=diag(0.5,âˆ’1.0)`, `E=âˆ’1.280625`; residual exactly `+1.00000` | count inside the band too; use the `Ïƒ_min` rank criterion, not an IPR filter |
| **Threshold conditioning through the repo route** | `â€–S*Sâˆ’1â€–` degrades to `1.1e-2` at `Îµ_Ï†=1e-7`, `LinAlgError` at `1e-8`; float64 floor at `Ï† â‰ˆ 2.1073e-08` **(re-run)** | fix `channels.py:40`; use Richardson, never small `Îµ` |
| **Scope creep into index theory** | BFNS's proof is classical complex analysis; papers 1â€“3 contain zero K-theory | keep [H] off the path (Â§5) |
| **His own drafts are unfinished exactly where you need them** | paper 1 Prop 4.6 `[TODO]`; paper 2 Cor 4.2.3's red note *"What do you do with the inverse of `M_Ïƒ^E`?"*; paper 3 has 10 `TODO`s | this is why the numerical route is the right route â€” ask, don't wait |

## What to ask Schober, in order

1. **Does `[BS25]` exist as a separate document?** If so, may I have the PDF; if not, which of papers 1â€“2 absorbed it. Four citations in paper 2 currently resolve to nothing.
2. **Is there already a Levinson theorem for this model â€” varying dimension, finite-support `V` â€” yours or anyone's?** I could not find one. `[BFGS21]`/`[BFNS24]` are constant dimension; `[APRR24]`/`[NPR25]` are varying dimension but single-site on a half-line. If it is genuinely open, is that the target?
3. **Which `S_E` do you want the winding of** â€” paper 2 Def 4.1.6's or paper 3 Def 4.2's? They agree to `1.9e-15` on the one model I tested, all channels open, but paper 3 marks the identification `TODO` twice.
4. **Orientation.** My winding is the complex conjugate of BFGS21 Thm 9's. I believe that is because your `Im z > 0` convention makes `z^n` left-moving, so my `S` is the inverse of theirs. **I want to state the theorem in your convention, not silently flip a sign.**
5. **Does `Ïƒ_pp(H)` meet the band in your model, and is `J_b` known to be finite?** I can construct an embedded eigenvalue with a decoupled `V` (`a=(1.3,0.4)`, `E=âˆ’1.280625`); it dies under coupling. Paper 3 Thm 2.4(a) seems to allow it deliberately.
6. **Paper 1 Prop 4.6's proof is `[TODO]`.** Is the threshold uniformisation available anywhere? It is the one input Levinson most needs at a band edge.

## Three things to hand him as wins, not questions

- **`AUDIT.md` finding 22 is resolved.** Paper 2 Def 4.1.6's layout is confirmed â€” both minus signs on the off-diagonal `N` blocks, character-identical to the published `[BFNS24]` Definition 3 eq (7). Three independent readings.
- **Paper 2 Â§4.1's red edits are correct.** Testing `M_Ïƒ, N_Ïƒ` against the *defining* equation (20) at 5 lattice sites Ã— 2 `Ïƒ` Ã— 7 energies: the struck-through reading `W(b_{âˆ’Ïƒ}^{E,âˆ’Ïƒ}, b_Ïƒ^{E,Ïƒ}) = +Ïƒ N_Ïƒ^E` gives residual **`4.961e-15`**; the pre-edit `âˆ’Ïƒ` gives **`3.751e+00`**. Lemma 4.1.3 as currently written (`âˆ’ÏƒðŸ™`, Ï„-independent) checks out to `1.8e-15` for all four `(Ï„,Ïƒ)`. The "sign problem" title looks already resolved by the red edits. Lemma 4.1.5(c) `Nâ‚‹ = âˆ’(Nâ‚Š)*` verified to `2.5e-16`; 4.1.5(d) `M*M = 1 + N*N` to `4.0e-15`; Prop 4.2.1 unitarity to `3.1e-15`.
- **BFNS24 Proposition 22 holds verbatim in his varying-multiplicity setting:** `det S^E = det((Mâ‚Š^E)*) / det(Mâ‚‹^E)`, verified at seven energies with `|diff| â‰¤ 4.6e-15` and `|det S| = 1.000000000000`. That reduces the winding of `det S` to the winding of a *single scalar holomorphic function* `det Mâ‚‹` â€” and `det M_Ïƒ^E` is, up to normalisation, exactly the object paper 2 p. 14 already proves holomorphic with a nonzero limit at `|E| â†’ âˆž`. **His own Lemma 2.3.9 is already the argument-principle input.** That is the sentence most likely to make Tuesday's audience sit up.
