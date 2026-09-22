# spectral_wave — Audit

2026-09-21 · Scope: the program as it stands (`main.py`, `gui/`, `spectral/`), `README.md`, and the paper questions the code depends on.
Method: every item re-checked against the current code; numbers re-measured in this pass unless marked "(not re-measured)". The repo has no test suite (removed deliberately); the numbers come from scripts run outside it.

---

## 1. Bottom line

The algorithm is correct. Steps 1-8 reproduce an independent 50-digit transfer-matrix
reference to about 1e-14 mid-band, both branches are exact norm-preserving eigenbases, and the
two branches differ by the physical on-shell scattering matrix as intended. All four approved
departures from the spec (section 2), and the fixed-f ruling, are in the code and behave as
described. The math has not regressed.

The open problems are all in the surrounding program, not the math:

- The library has no quadrature-resolution guard, so a wide frame at the default `n_quad`
  folds a ghost packet back into view; the total-probability readout can read 3.0, or a
  plausible 0.82 when the packet has actually left (medium).
- Frame truncation: 11 of 13 presets hold less than 98% of their mass in frame by `t_max`,
  and 7 hold less than half (medium; the wave itself is fine, the display window is too small).
- Several GUI event paths are unguarded (Enter re-runs, splitter/resize break the plot,
  close-during-export leaves a truncated file).
- A handful of documented numbers come from configs a reader cannot reproduce.

Everything the code supports is confined to `|E| < 2·a_min` with all channels open, which
`MaxwellSpec.validate()` enforces (`spectral/maxwell/model.py:98-107,117-125`). Behaviour at or
above a channel threshold, where the scattering matrix changes dimension, is neither
implemented nor tested. The code does not exercise that regime.

---

## 2. Where the code departs from Schober's written spec

Schober's written spec (the Data block and steps 1-10) is not in this repo. All four departures
below were approved by Schober. Each was re-measured this pass by undoing the departure in a
scratch copy of the package. Bare file names are in `spectral/maxwell/`.

| Departure | Where | Ruling; residual (re-measured) |
|---|---|---|
| Step 5 sum prefactor `+i`/`-i`, independent of sigma (spec has real sigma-dependent signs) | `jost.py:82-83` (set outside the sigma loop at `:85`) | Ruling: the prefactor tracks the lower ± index only (`jost.py:80-81`). The literal prefactor gives a Jost residual of exactly `0.5(1+sigma·i)` at L=1, V(0)=0.5, E=0 (current code: `0.0`), and O(1) for generic L=2 cases (`1.45` and `2.05` in two configs; current code: `1.3e-15` on the first). |
| Step 7 branch signs `-`/`+` so G = (H−E)⁻¹ (spec has them reversed) | `green.py:69-78` (docstring `:3-16`); the step-8 minus stays at `eigfunc.py:94` | Ruling: fix the sign in step 7, keep step 8's minus (`green.py:12-15`). Literal signs leave `(H−E)w = 2·V(j_k)·z^{−σj_k}·e_l` at the support: `1.600` (L=1, V=0.8), `7.000` (V=3.5), against ~1e-15 to 1e-14 now on a ±30 frame (rounding in z^n grows with \|n\|). They also break the norm (Σψ = 1.00/1.30/1.59 at t=−30/0/30). |
| Divide final psi by 2π; leave step-9 `p` literal | `evolve.py:114` (`p` literal at `:88-92`) | Ruling: keep p literal, divide the final ψ by 2π (`evolve.py:108-113`). Literal `1/p` gives Σψ = `6.283185307180` = 2π; current code gives `1.000000000000`. |
| Step 8 index reading "Interpretation 2" (summed sigma drives the plane wave; the fixed lower ± picks one Green's branch) | `eigfunc.py:3-4, 68-70` | Ruling: Interpretation 2 (`eigfunc.py:6-12`). The code reproduces a literal step-8 build to ≤5.6e-16. The other reading gives Σψ = 2.0 at V=0 and a balanced packet drifting to ⟨n⟩=±39.7; the code holds ⟨n⟩=0, Σψ=1. |

`README.md:159`, `:166`, `:170`, `:181` and `:185` quote residual/norm figures (`~1e-16`,
`2.4e-16`, `0.99999999998`, `6e-16`, `1e-15`) from configs that were not recorded and could not
be reproduced exactly; they are the right order of magnitude for small frames.

**Two defects in the spec document itself** (the code works around both). (i) Step 8 defines
`w^{E,±}_{l,σ}` but step 10 uses `w^{E,σ}_{l,±}`: the indices are transposed. (ii) Nothing
binds step 10's `±`; the code exposes it as `MaxwellSpec.outer_sign` (`model.py:39-47`, default
+1). `README.md:160-162` and `:172-177` document both. Minor: step 5 alone writes `ℕ∩[N,M]`
(the other five ranges use `ℤ`; every preset has `N<0`, so step 6's anchor at `N` would be
undefined; the code uses `ℤ`, `model.py:151`), and step 6 uses `A` without defining it (the
code takes `A = diag(a)`, `wronskian.py:36`). The `ℕ→ℤ` reading is not in the departures list
at `README.md:154-170`.

---

## 3. Open findings, ranked

Ranked by severity, then impact.

| # | Finding | Sev. | Where | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | ~~The potential field is parsed with `eval()`~~ | **RESOLVED** | `gui/main_window.py` `_build_spec` | Now `ast.literal_eval`, which parses only literals. Rejects `__import__(...)`, `().__class__.__bases__[0].__subclasses__()`, `[[[0.6]]] + [[[1]]]` and 400-deep nesting with a plain message; all 13 presets, complex entries included, parse identically (psi byte-identical for 13 presets x both signs). | — |
| 2 | The library has no quadrature-resolution guard; at the default `n_quad=128` a wide frame or long time folds a ghost packet into the frame (wraparound), and the Σψ readout is no reliable alarm (3.000 instead of 1 on a ±400 frame; a plausible 0.82 when the true in-frame mass is 5.5e-10) | medium | `spectral/maxwell/model.py:135` (only checks `n_quad≥8`); default `:32`; `evolve.py:46-53` | Free-Gaussian params with N,M widened to ±400 as `README.md:149-150` advises: Σψ = 3.000/2.910/2.000 at t=0/25/50 vs 1.000 at `n_quad=2048`; a ghost sits at n=345 with ψ=0.077 (true peak 0.086). Frame ±150, t=100: Σψ=0.82, packet at n=−146, truth 5.5e-10. E_segments split nodes by length only (`quadrature.py:19-53`), so a near-threshold segment is under-resolved. | Move the phase-resolution check (`min_nquad`'s formula, with margin) into `validate()`/`compute_psi`; allocate segment nodes by phase variation, not length; fix `README.md:149-150` to also say raise `n_quad`. |
| 3 | Frame truncation: 11 of 13 presets hold less than 98% of their mass in frame by `t_max`, and 7 hold less than half | medium | `gui/main_window.py:278-397` (frames); `README.md:146-150` | Σψ at `t_max` < 0.98 for 11 presets (< 0.90 for 10, matching `README.md:148`'s "Ten of the thirteen"; < 0.50 for 7): Two-Channel Free 0.0025, Single Barrier 0.050, Schober 1 0.214; only Free Gaussian (0.99996) and Wide Barrier (0.9959) hold. Schober 1's ±10 frame holds 0.19-0.25 at *every* time because its step-function f has 1/n² tails (~9.8/R beyond ±R). This is not a ψ defect: ψ matches a ±3000 frame at the same sites to ≤8.9e-14. | Widen preset frames to the measured 0.98 minima (e.g. Schober 1 ±490, Schober 2 ±570), and/or relabel the "∑ψ at t" readout as "∑ψ in frame". |
| 4 | GUI `n_quad` advisory is unsafe for narrow packets: `min_nquad` has no `σ_E` term, only warns, and is skipped for `E_segments` | medium | `gui/main_window.py:461-478` (docstring claims ≥20% headroom); check `:1256-1276`; skip `:1263` | Weak-Barrier preset with only `σ_E` edited (advisory 110): the `n_quad` needed for 1e-6 is 288 at σ_E=0.02 and 572 at σ_E=0.01. At n_quad=110 the error is 31% and 141% of peak; a mirror ghost puts 37× the true density at the far edge. At `n_quad = advisory` the GUI shows no warning. Public API checks nothing beyond `n_quad≥8`. All 13 shipped presets are converged (≤3.0e-14). | Add a `σ_E` term (`ceil(PV/π + 2(hi−lo)/σ_E)+8`, measured 1.24-1.64× the threshold); make the check block or auto-raise; correct the docstring. |
| 5 | Pressing Enter in a form field bypasses the disabled Compute button: it stacks uncancellable compute threads, and runs computes during exports | medium | `gui/main_window.py:1101-1105` (returnPressed → `run_compute`); `run_compute:1246` never checks in-flight | 5 Enter presses during a compute → 6 `MaxwellWorker` threads at once. Enter during an export starts a compute; when that compute finishes, `on_finished` re-enables Export (`gui/main_window.py:1421`) while the first export is still running, so two exports run at once sharing one progress bar. | Return early in `run_compute` when a compute/export is in flight; give exports their own token; keep buttons disabled until every worker finishes. |
| 6 | Dragging the splitter (or resizing while paused) breaks the plot: a stale blit background is pasted, or the ψ curve disappears | medium | `gui/main_window.py:1628` (`restore_region`); `_bg` captured `:1411`, cleared only in `_set_empty:1162` and `resizeEvent:1636-1639` (→ `_recapture_bg:1641-1645`), neither of which runs when the splitter resizes the canvas; animated artists `:1407-1409` | Splitter drag: canvas 1075→915 px but `_bg` extents stay (0,0,1075,799); after 5 ticks 16.7% of pixels differ from a clean render, the colorbar is gone and the transmitted peak lines up with the wrong site. Resize while paused: curve pixels go from 1726 to 0 and stay 0. | Recapture `_bg` on `canvas` resize (`resize_event`/`draw_event`), and re-blit the current frame at the end of `_recapture_bg` so a paused frame is redrawn. |
| 7 | Closing the window during an MP4 export, or any export failure, silently leaves a truncated but playable file at the chosen path | medium | `gui/main_window.py:652` (`writer.saving(fig, self.path)`); `closeEvent:1669-1681` waits only 250 ms `:1677`; `_on_export_failed:1521-1526` | matplotlib passes `-y`, so ffmpeg truncates the target at start. Close 15 s into a 53 s export: process exits 0, no prompt, target now 182,591 bytes / 35 frames, decodes cleanly. Fail at frame 20: a good target is replaced by a 13,337-byte file that decodes without error. | Write to a temp file in the same dir and `os.replace()` onto the target only on success; delete it on cancel/failure; in `closeEvent` prompt or cancel a running export. |
| 8 | The "use it without the GUI" snippet only resolves from the repo root; the README never says so | medium | `README.md:214-221`; `pyproject.toml:1-17` (no `[build-system]` table) | The `.venv` holds only `_virtualenv.pth`; `from spectral.maxwell import ...` from any other cwd gives `ModuleNotFoundError`. The snippet also uses an undefined `spec` and never shows the f contract (one callable → shape `(n_E, L, 2)`). | Add a `[build-system]` + package list so `uv sync`/`pip install -e .` installs `spectral`, or state "run from the repo root"; show a minimal `MaxwellSpec(...)` with an f. |
| 9 | Export is only partly fixed: an `ffmpeg.cmd` shim on PATH still passes the availability check and then fails at once, and there is no default suffix or pre-render extension check | low | `gui/main_window.py:538-560` (`_ffmpeg_available`), `1483-1505` (`_export_clicked`) | In matplotlib 3.10.8 `FFMpegWriter.isAvailable()` is itself `shutil.which`, so a `.cmd` shim passes and export fails in 0.07 s with `FileNotFoundError`, no GIF fallback. A missing/`.txt` extension fails after one frame (0.6-1.4 s) in MP4 mode with a 605-char `CalledProcessError`, or after all 120 frames (22-26 s) in GIF mode. | Normalise/validate the path before rendering; confirm the ffmpeg binary actually runs (`-version`) instead of trusting `isAvailable`; surface ffmpeg's stderr on failure. |
| 10 | Schober presets: after an edit flips to Custom, six f-defining fields stay disabled with a tooltip saying they are ignored | low | `gui/main_window.py:1196-1197` (`_preset_changed` returns early for Custom, before the enable loop `:1214-1220`) | Select Schober 1, edit N: preset becomes Custom, but E0/σ_E/sigma-mode/n_init/E_lo/E_hi stay disabled with tooltip "Ignored by this preset". `_build_spec` then drops `E_segments` and builds the Gaussian f from those disabled values (measured f is a balanced Gaussian at the disabled E0=0.5, σ_E=0.1). The Gaussian swap itself is documented (`README.md:121-123`, `gui/main_window.py:439`), but the six fields that now define that Gaussian stay disabled with a false tooltip, contradicting `README.md:120` ("so you can keep tweaking"). Workaround: pick any Gaussian preset first. | Run the enable/tooltip loop (with `uses_window_f=False`) before the early return when `cfg is None`. |
| 11 | `validate()` lets several non-finite inputs through (inf in `a` or `V`, NaN in `interval`, NaN/inf in `times`, NaN `f`), and the GUI reports an all-NaN result as a green success | low | `spectral/maxwell/model.py:94-107` (ordered comparisons, all False for NaN); `evolve.py:91` (`p<=0`); GUI `_build_spec:1717-1724` (`float()` accepts `nan`/`inf`/`1e999`) | `a=inf`, `V=inf`, `interval=(nan,…)` and a NaN `f` pass `validate()` and return an all-NaN psi with no exception (NaN in `a` or `V` and ±inf in `interval` are caught, by accident, by the positivity, self-adjoint and band checks); NaN/inf `times` pass and give non-finite rows. `np.allclose(inf,inf)` is True, which lets `V=inf` through. A NaN `E_segment` is silently dropped and a plausible finite psi is returned. In the GUI, E0/σ_E/`V=[[[1e999]]]` end with status "max ψ = nan", state "ok", play/export enabled. `ast.literal_eval('[[[1e999]]]')→inf`, so fixing #1 does not close this. | In `validate()` require `np.isfinite` on `a`, `interval`, `E_segments`, `times`, `V_sites`, `threshold_buffer`; use `if not np.isfinite(p) or p<=0`; raise if the output psi is non-finite; reject non-finite GUI fields with a per-field message. |
| 12 | Integer-valued Data fields are not validated: non-integer N/M shift the frame outside `[N,M]`, `j_sites` are truncated, and a reassigned float `j` runs with fractional exponents | low | `spectral/maxwell/model.py:151` (`arange(N,M+1)`), `:51` (`__post_init__` int-casts only at construction) | N=−10.5,M=10.5 → lattice −10..11 (site 11 > M). `j_sites=[0.9]`→[0]. `spec.j_sites=np.array([0.5])` after construction passes `validate()` and gives Σψ=[0.833,0.665] (should be 1). `outer_sign=0/7` with K=0 pass; `n_quad=100.5` fails deep in numpy. Nothing bounds \|N\|, \|M\| or `n_init`; the phase error grows ~3e-17·offset (Σψ=178499 at offset 1e17). | In `validate()` check N,M,`j_sites` are integral, `outer_sign∈(+1,−1)`, `n_quad` an int ≥8; bound \|N\|,\|M\|; redo the `__post_init__` coercions inside `validate()` or freeze the dataclass. |
| 13 | `E_segments` are not required to lie inside `interval`: f is evaluated outside its domain, and `interval` is validated then ignored | low | `spectral/maxwell/model.py:117` (segments checked vs band, never vs `[a,b]`); `evolve.py:46-50` | `interval=(−0.1,0.1)` with `E_segments=[(−1.5,1.5)]` passes; f is called on [−1.5,1.5] (122/128 nodes outside `interval`). The reverse (segments covering part of f) drops the rest of the packet; `p` is renormalised over the same segments so the readout hides it. | Require `interval[0] ≤ segments[0][0]` and `segments[-1][1] ≤ interval[1]`, or document that `E_segments` replaces `interval` and skip the interval checks when segments are given. |
| 14 | The status label renders rich text, so an `<img>` tag typed into any numeric field loads a local/UNC file | low | `gui/main_window.py:911` (no `setTextFormat`), `_set_status:1129-1134`, error path `:1253` echoes raw field text | `status_label.textFormat()` = AutoText. Typing `<img src="…/probe.png">` into E0 and running makes the label render it (0→900 red pixels). A UNC `src=//host/…` is fetched over SMB (the usual NTLM-leak pattern). All 14 non-V fields reach this sink; switching V to `literal_eval` does not close it. | `status_label.setTextFormat(PlainText)`; escape the tooltip; report fixed per-field messages without echoing raw text. |
| 15 | The GUI size guard ignores `n_quad`, `L` and `K`, which drive memory and time | low | `gui/main_window.py:1738-1742` (caps only `(M−N+1)·n_t ≤ 40M`) | Following the GUI's own `min_nquad` advice makes memory grow ~quadratically with lattice width: 2001 sites/n_quad 601 +258 MB; 8001/2221 +3.8 GB, all well under the 40M-sample cap. For N=±20000 the advisory recommends `n_quad≥10854`, projecting ~109 GB. Compute runs in an uncancellable thread. | Estimate the working set (~250·n_quad·n_sites·L²·(1+K/4) bytes) up front and refuse above a budget; bound `n_quad` and `L`; stop the advisory recommending values the budget rejects. |
| 16 | A compute error leaves the canvas stuck on "Computing…" and the previous animation is already gone | low | `gui/main_window.py:1369-1376` (`_on_error` only updates status); frames cleared `:1281`, placeholder set `:1326-1331` | After a good run, setting E0 to a value that zeroes f: status shows the error but the canvas still reads "Computing… / 140 frames × 201 sites"; `frames` is None; play/export disabled. Unlike an input error, which returns at `:1252-1254` before anything is torn down (comment `:1247-1249`), a compute error arrives after the old animation has been cleared. | In `_on_error`, restore the placeholder to an error state, or keep the previous frames/artists until a new compute succeeds. |
| 17 | The GUI Gaussian f populates channel 0 only, so the Two-Channel presets cannot show the separation their descriptions promise | low | `gui/main_window.py:1760-1761` (only `out[:,0,:]` written; comment `:1752`) | Two-Channel Free: `max\|f[:,1,:]\|=0`, channel 1 carries exactly 0 in all 140 frames, one peak at speed 2.0. Two-Channel Coupled: V moves 4.7% into channel 1, but its peak is ≤3.3% of plot scale and only clears 10% of a frame's max in the last 13/140 frames. Copying the Gaussian into channel 1 does produce two peaks 33 sites apart. | Add channel weights and fill every channel in `_build_spec` (with per-channel θ_l), or reword the descriptions and `README.md:115-116` to say the Gaussian excites channel 0 only. |
| 18 | `README.md` says a state-based-f version was implemented; no such code exists in the tree | low | `README.md:193-194`; `model.py:30` (only input is a callable f); `evolve.py:59` | No `.py` file in the repo maps a lattice state to f. Re-implemented independently, the claim holds (ψ₊ vs ψ₋ agree to 1.2e-15-3.3e-15), but a reader cannot reproduce it from the repo. The `4.3e-15` and the `14%/65%` at `README.md:179-180,194` come from unrecorded configs. | Reword to "an out-of-repo check … about 2e-15", or commit a small standalone script and cite it; state the config behind the percentages (shipped presets give 1.4-94%). |
| 19 | The waterfall `imshow` extent uses the first/last time-row values as image edges, so the image is squeezed one row and the time cursor is up to `dt/2` out of register | low | `gui/main_window.py:1539-1544` (`_render_waterfall`) and the export copy `:606-611`; cursor `:1611-1613,663-664` | Cursor off-centre by `(t_max−t_min)/(2·n_t)`: 0.208 units (0.496 dt) for Free Gaussian, 0.333 for Slow Packet, exact at the middle frame. At n_t≥120 (all presets) bilinear interp mixes the neighbouring row: mean 25%, 57/120 frames > 25%. Fixing the extent brings the offset to 1e-14. Cosmetic. | Set y extent to `times[0]−dt/2 .. times[-1]+dt/2` in both places (grid is uniform, `n_t≥2` enforced); keep `set_ylim`. |
| 20 | A startup failure overwrites `maxwell-crash.log`, erasing earlier hard-crash dumps | low | `main.py:55` (`log.write_text`) vs `:40` (faulthandler opens append); path is CWD-relative `:38` | A pre-existing 100-byte log with an earlier dump: after a forced startup failure the log is 437 bytes with only the new traceback; the earlier dump is gone. | Append instead of truncating; anchor the log to a fixed location rather than the CWD. |
| 21 | ~~Several preset descriptions overstate what the preset shows~~ | **RESOLVED** | `spectral/maxwell/presets.py` `WEB_DESCRIPTIONS`; `README.md`; `gui/main_window.py` `PRESET_DESCRIPTIONS` | Both viewers and the README now show one measured set of blurbs: Strong Wall 24.4% transmitted, Weak Barrier reflection 0.36% (below the colour scale), Double Barrier drains by t≈13, Wide Barrier spaced sites 57.7% through, Random Lattice five fixed sites, Two-Channel Free fills channel 1 only, Slow Packet speed 1.12. | — |
| 22 | Several `README.md` technical statements are wrong | low | `README.md:64,81-82,185-186,220-221` | (a) `nu_l` is glossed as "how fast a wave travels"; it is `1/(group speed)`, the density of states (`ν·speed=1.0000` measured). (b) S_E is said to have "determinant 1"; measured `det` is a unit-modulus phase (e.g. `0.600−0.800i`), only `\|det\|=1`. (c) Theorem 3.2.5(a) of the current paper 3 is `F±*F± = P_ac(H)` — complete only on the a.c. subspace; every single-site preset has a bound state outside the band. (d) `MaxwellSpec` is not the Data block "field for field": it adds `times`, renames fields, reorders j/V, and enforces a stricter band than Data item (e). | Fix the four statements; add the threshold buffer to the departures list. |

---

## 4. Looks like a bug, isn't — do not "fix" these

- **The two branches give different videos with fixed f.** With V≠0, `max|ψ₊−ψ₋|/peak`
  ranges from 1.4% (Weak Barrier, V=0.12) to 94% (Schober 2) across the shipped presets (39%
  for Single Well, V=−0.8). This is correct: the branches differ by the on-shell scattering
  matrix S_E, and Schober ruled (2026-08-21, recorded at `model.py:44-45`) that the step-10
  input is a fixed f, so they are *meant* to differ. With V=0 they agree exactly (0.0); the
  difference grows as V² (1e-4 at V=1e-2; 1.44% at V=0.12). `outer_sign=+1` is the
  retarded/outgoing branch: its scattered wave has no incoming part (≤2.4e-16), and G_grid[0]
  converges to `(H−(E+iε))⁻¹` at O(ε), matching current paper 3 (14 Aug 2026) Thm 2.4(c).

- **Do not tie the Green's-function branch to sigma.** `eigfunc.py:68-70` uses one branch for
  both sigma. Tying it to sigma keeps every column an eigenfunction but breaks the norm: Σψ
  ranges 0.13-1.87 over potentials and f phases, and is exactly 1 whenever f is one-sided — so
  the right-moving presets would hide it.

- **Do not use the `ψ₊[f] = ψ₋[S f]` residual as an acceptance test.** A smooth random-unitary
  fake ψ₋ passes it (6e-16), and also gives `(H−E)w = 2e-13` and Σψ = 1.000000000000, yet its
  ψ is 48-79% of peak from the real branch. Only a boundary-condition check separates them: the
  fitted S = J·S_phys is the non-tautological version (measured `||S_cob − J S_phys|| ≤ 1.6e-15`
  for L=1, and a random-unitary fake misses it by 1.1-2.2).

- **Do not adopt the step-1 shortcut `z_l = e^{−i·arccos(E/2a_l)}`** (`README.md:198-205`). It
  is the lower-half-plane root, `conj(z)`, giving `nu` = −1 × the closed form. Swapped into
  `compute_psi` in memory it made ψ NaN in 363/363 entries via `np.sqrt(nu)` at `evolve.py:57`.
  The code correctly keeps `Im z > 0` (`channels.py:33-36`), as spec step 1 requires.

---

## 5. Resolved since the last audit

- The potential field is parsed with `ast.literal_eval`, not `eval` (finding 1).
- The preset blurbs in both viewers and the README are generated from one measured set (finding 21).

- The outer-sign dropdown no longer flips the preset to Custom (`gui/main_window.py:1097-1099`); the ± comparison runs from the GUI (53% peak difference on Schober 1).
- `n_t<2` and `t_min≥t_max` give an input error, not an uncaught `IndexError` (`gui/main_window.py:1728-1731`).
- `pillow`, which the GIF fallback needs, is declared as a dependency (`pyproject.toml:15`).
- Startup failures and hard crashes are logged to `maxwell-crash.log` (`main.py:36-59`; see finding 20).
- MP4 export falls back to the bundled imageio-ffmpeg binary (`gui/main_window.py:538-560`); only partly fixed, see finding 9.
- Free eigenfunctions: the current paper 3's Def. 2.2 (p. 5) has no leading σ, and the code's `z^{−σn}·√ν` matches it to 3.9e-15.
- Paper 2's Def. 4.1.6 (July 2025 copy) renders cleanly and matches Remark 4.1.7 to 7.5e-15.

---

## 6. Open questions about the papers

Version caveat on every item: papers 1 and 2 in `docs/` are the July 2025 copies (2026 revisions
exist but are not in the repo); `3_GeneralizedFourier.pdf` (14 Aug 2026) is the current paper 3.
`4_Levinson.pdf` is an unfinished draft; its bibliography cites [BS26a], [BS26b], [BS26c].

1. **Still open.** Paper 2 (July 2025 copy) cites `[BS25]` ("Construction of scattering
   matrices with varying dimension…") at three-level pinpoints (Prop. A.3.2(f), Def. 2.1.7, and
   others) that can't be resolved here: neither paper 1 nor paper 2 (July 2025 copies) nor the
   current paper 3 carries that title, paper 1's July 2025 copy uses two-level numbering (e.g.
   Proposition 2.7), and paper 2's own Def. 2.1.7 is a different statement. Paper 2 also cites a
   nonexistent "Proposition 2.1.4(f)" four times (its 2.1.4 has only (a)-(d)). The current
   paper 3 cites `[BS26a]`/`[BS26b]` instead, with every pinpoint still "TODO". This is
   bookkeeping that is blocked on the 2026 revisions of papers 1 and 2.

2. **Answered numerically.** Built from paper 2's own definitions (July 2025 copy; L=1,2,3; 16
   energies), every printed or red-edited sign in Lemma 4.1.3, Lemma 4.1.5(a)-(d) and
   Remark 4.1.2(c) holds to ≤9.8e-15, and the struck-through `−σ·N_σ` in 4.1.5(b) fails by
   1.0-4.4. The strike-throughs are in (b) only, and these signs enter the unitarity proof, not
   the definition of S_E. Open only in that the 2026 revision of paper 2 is not in this repo.

3. **Now checked for general L.** The current paper 3's S_E (Def. 4.4, eq. 19, p. 25), built
   from the code's own w, is unitary to 4.7e-15 and equals `J·S_E(paper 2, July 2025)·J`
   (J = diag(1_L, −1_L)) to ≤4.9e-15 in all four test configs, while differing from paper 2's
   S_E itself by 0.97-1.76 — i.e. the reflection blocks have opposite sign. A sign flip on the
   σ=− basis vectors produces exactly this; the current paper 3's Def. 2.2 carries no σ
   prefactor. Whether the 2026 revision of paper 2 uses the same sign convention cannot be
   checked from this repo.

---

## 7. Verified properties

- **Scattering (steps 1-8).** 7396 scalar states (43 potentials, 43 energies, both `outer_sign`,
  both σ) matched a 50-digit transfer-matrix reference at every site to 6.3e-14 for `|E|≤1.8a`;
  1376 L=2 complex-Hermitian states to 3.8e-14. Transmission amplitudes agree to 1.2e-14
  mid-band, `|T|²+|R|² = 1` to 2.0e-14, and all 27 Fabry-Perot resonances sit within 8.9e-16 of
  the analytic condition. Worst case is a local 9.4e-13 at the rightmost site at `E = 2a−1e-3`
  (the threshold buffer, `model.py:12`) — a precision limit, not a correctness defect.
- **Eigenbasis and unitarity.** Both branches give `max|(H−E)w|` equal to within rounding
  (5.6e-17 at E=0, ~1e-14 across the band on 121 sites), where a pure free wave computed the
  same way already gives 1.1e-13 on 401 sites. With a smooth f on a wide frame,
  `max|Σ_nψ − 1| ≤ 1.04e-13` on both branches (L=1: barrier, wall, two-site, V=0), and 3.7e-15
  for an L=2 complex-Hermitian V with both channels excited. Every measured shortfall is mass
  outside the frame: it falls as 1/H and does not change with `n_quad`.
- **Scattering vs transfer matrix (branch identity).** The change of basis U (`v_₋ = v_₊ U`)
  satisfies `||S_phys U − 1|| ≤ 8.2e-14` with S_phys read from the `+1` asymptotics alone; for a
  single L=1 site U equals `conj(S)` from the closed form to 4.7e-15. U is unitary to 3.1e-14
  with `|det U| = 1`.
- **Band restriction.** No accepted run has a closed channel: `a=1` accepts `[−1.999,1.999]`
  and rejects `1.999+1e-12`; `a=(2,1)` rejects `[1.5,2.5]`. Inside the band, the default buffer
  gives spectral convergence (128 nodes → 4e-12 for a packet 0.02 from threshold, vs 1.4e-3 at
  buffer=0). The `threshold_buffer` itself is unvalidated (see finding 11).
