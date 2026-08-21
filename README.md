# Maxwell Algorithm

Reference implementation of Jonas Schober's matrix-valued lattice scattering
algorithm (spec dated 2026-05-19) plus a desktop viewer to actually see the
wave packet move.

The algorithm computes `psi(n, t)`, the time-evolved probability density of a
wave packet on a 1D lattice, given a self-adjoint matrix potential of finite
support. Underlying Hamiltonian:

    (H psi)(n) = A* psi(n+1) + A psi(n-1) + V(n) psi(n)

with `A = diag(a_1, ..., a_L)` and `a_1 >= ... >= a_L > 0`. See
`docs/MaxwellAlgorithm.pdf` for the spec the code follows, and `docs/README.md`
for what every other document in `docs/` is.

## Run from source

The project uses [uv](https://github.com/astral-sh/uv). Python 3.12.

    uv sync
    uv run python main.py

Without uv:

    python -m venv .venv
    .venv\Scripts\activate          # Windows
    source .venv/bin/activate       # macOS / Linux
    pip install numpy matplotlib pyqt6
    python main.py

## Building a standalone binary

PyInstaller is in the dev deps. Build from the pinned spec, from the repo root:

    uv sync
    uv run pyinstaller --noconfirm maxwell.spec

Build from `maxwell.spec`, not from `main.py` — passing `main.py` regenerates
the spec from defaults and silently discards its settings, including
`upx=False` (UPX corrupts Qt DLLs on Windows).

You'll get the binary in `dist/`, which is gitignored -- binaries are not
committed. PyInstaller doesn't cross-compile, so build on the OS you want to
ship to, and distribute the result as a release attachment rather than by
committing it.

The produced binary bundles no ffmpeg, so video export falls back to GIF
unless ffmpeg is on the target machine's PATH.

## Using the viewer

Pick a preset from the dropdown in the sidebar. The thirteen options cover the
free Gaussian wave packet, single barriers and wells, the double-barrier
resonant cavity, the two-channel free and coupled-scatterer cases, a slow
packet near the band edge, and Schober's two window-function test configs
(fixed step-function f, integrated with one quadrature rule per window). Each
preset writes its parameters into the form below the dropdown. Edit any field
by hand and the dropdown switches to "Custom" so you can keep tweaking without
losing where you started.

Gaussian presets expose the full initial-state controls: sigma mode (balanced
(1,1), right (1,0), left (0,1)) picks which of the two sigma families the
packet rides — balanced stands still and spreads, right/left drift at the
group velocity; "start site n_init" parks the packet anywhere on the lattice
via the z_0(E)^n_init phase; "time start t_min" lets the clock begin at
negative times so you can watch the packet converge, interact, and leave.

Hit "Compute & Animate". The algorithm runs off the UI thread, so the window
stays responsive. When it's done, the curve animates on the top panel and the
spacetime view fills in below. The waterfall is the entire `psi(n, t)` rendered
as a heatmap — reflections, tunneling, channel separation all show up as
continuous trails through it.

The transport bar handles playback. Play / pause, restart, scrub anywhere on
the timeline, change speed (0.25x through 4x), and export the animation to a
video file (MP4 when ffmpeg is on the PATH, GIF otherwise; rendering happens
off the UI thread). Vertical markers on both panels show where the potential
sites sit. The four monospace stats below the controls update every frame: max
amplitude, running L1 norm, peak lattice site, current time.

## Layout

    spectral/maxwell/     the algorithm, one file per step
    gui/                  PyQt6 viewer
    tests/                regression suite
    docs/                 the spec, the papers, the correspondence, the audit
    main.py               entry point

Each algorithm step is one file under `spectral/maxwell/`:

- `channels.py` — steps 1-3: `z_l(E)`, `phi^pm(n)`, `nu_l(E)`
- `kernels.py` — step 4: the kernel `s(n, k, E)`
- `jost.py` — step 5: the iterative recursion for `u_+`, `u_-`
- `wronskian.py` — step 6: the four `W_tau^{E,sigma}`
- `green.py` — step 7: the Green's function with the `W_+` vs `W_-` branch
- `eigfunc.py` — step 8: full eigenfunctions `w_{l,sigma}^{E,pm}`
- `evolve.py` — steps 9-10: normaliser `p` and `psi(n, t)`

`MaxwellSpec` (the algorithm's "Data" block) lives in `spectral/maxwell/model.py`.
The Qt bridge that turns spec output into animation frames is
`spectral/maxwell/adapter.py`.

Programmatic use:

    from spectral.maxwell import MaxwellSpec, compute_psi

    psi = compute_psi(spec)      # (n_times, n_sites) real, non-negative

## Algorithm status

The code follows the April 2026 spec, plus four fixes the author has blessed
(2026-05-19 and 2026-08 chats, the latter in `docs/professor_response.txt`):

- Step 5's sum prefactor is `+i` for `u_+` and `-i` for `u_-`, independent of
  sigma (A.2). Jost residuals are ~1e-16. This is not a deviation from the
  theory: it reproduces paper 1's Volterra kernel `A^-1 s^{E,sigma}` exactly.
- Step 8/10 index convention is Interpretation 2 (A.1): the summed sigma is
  the wave-vector sign driving `z^{-sigma n}`; the fixed lower `+/-` index
  (`outer_sign`) picks one Green's-function branch. Balanced packets
  (`f_+ = f_-`) stand still and change shape, per the author.
- A.10: step 7's branch signs now follow paper 2's `-/+` pattern, so `G` is
  `(H-E)^{-1}` and step 8 no longer double-counts the potential.
  `max |(H-E)w|` went from `2|V|` to ~6e-16. The author's ruling put the fix
  in `green.py`, explicitly *not* in step 8's sum: "if you are saying that
  changes the sign of G accomplishes that, please change the sign. I don't
  think we should change the sign in front of the sum."
- A.11: `psi` is divided by `2*pi` at the end of step 10, so total
  probability is 1. Step 9's `p` is left literal, per the ruling: "Don't
  change p, just devide the final function psi by 2pi." He also confirmed the
  reading: `sum_n psi(n,t) = 1`, not `sum |psi|^2 = 1`.

One item is OPEN, and it is a question about the spec, not a defect.

**A.12 — the lower `+/-` index of `w` is never bound.** Step 10 sums over `l`
and `sigma` and integrates over `E`; nothing selects `+/-`. The author declined
to fix a sign and made it a test instead: "run the whole programm twice, once
with a + and once with a -. If everything is correct, the videos should look
exactly the same up to computer precision."

They do not, whenever a potential is present — 14% of peak for `L=1, V=0.8`,
65% for `L=2` with complex-Hermitian `V` at two sites. But nothing is broken.
Both branches satisfy `(H-E)w = 0` to ~6e-16 **and** `sum_n psi(n,t) = 1` to
twelve digits at every time including `t < 0`, so both are exact,
norm-preserving eigenbases. They differ by the on-shell scattering matrix
`S_E`, which is unitary to 1e-15 with `|det| = 1` — so `F_- = (int S_E dE) F_+`
forces `psi_-[f] = psi_+[S_E^-1 f]`, and the two runs can only coincide when
`S_E = 1`, i.e. `V = 0`. Which is exactly what happens: with no potential they
agree to `0.000e+00`.

So the real question is what `f` is. Data item (f) of the spec says
"Functions `f_{l,sigma}: [a,b] -> C`" — fixed data, independent of `+/-`. Under
that reading the branches are *supposed* to differ. If instead the input were a
state `psi_0` with `f := F_+- psi_0`, then `F^* F = P_ac(H)` is
branch-independent and the test becomes a theorem — implemented and measured at
`4.3e-15`. Awaiting the author's ruling on which he intends. See
`docs/AUDIT.md` §1-§4.

**Resolved in passing:** the step-1 simplification in
`docs/professor_response.txt` (`z_l = e^{-i arccos(E/(2 a_l))}`, giving
`Im z < 0`) contradicts both his step-3 simplification and the spec, which says
"the solution with `Im(z) > 0`". The code keeps `Im z > 0`. Do not apply that
line literally.

## Tests

    uv run pytest

Thirty-two regression tests: hand-derivations of steps 1-4, honest-Jost
residuals (A.2), Wronskian anchor-independence (A.4), Green's-branch agreement
at `n = j_k` (A.5), the step-8 eigenfunction residual (A.10, now `< 1e-12`
everywhere), total probability `= 1` (A.11), Interpretation-2 kinematics
(standing wave / left / right, group velocity `2a`), probability conservation,
the per-window quadrature, and the spec-validation errors.

Known gaps: no test runs a packet through a non-zero potential, none uses
`t < 0`, none sets `outer_sign`, and nothing compares against an independent
ground truth such as a transfer-matrix transmission coefficient. `docs/AUDIT.md`
§7 item 7 lists the four tests that would close those gaps — all four pass
today.

## License

MIT.
