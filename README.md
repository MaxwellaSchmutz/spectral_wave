# Maxwell Algorithm

Reference implementation of Jonas Schober's matrix-valued lattice scattering
algorithm (spec dated 2026-05-19) plus a desktop viewer to actually see the
wave packet move.

The algorithm computes `psi(n, t)`, the time-evolved probability density of a
wave packet on a 1D lattice, given a self-adjoint matrix potential of finite
support. Underlying Hamiltonian:

    (H psi)(n) = A* psi(n+1) + A psi(n-1) + V(n) psi(n)

with `A = diag(a_1, ..., a_L)` and `a_1 >= ... >= a_L > 0`. See
`MaxwellAlgorithm.pdf` for the spec the code follows.

## Run the executable

Windows binary lives at `dist/maxwell.exe`. Double-click it, or:

    .\dist\maxwell.exe

It's a single self-contained file (about 60 MB). You don't need Python
installed. First launch unpacks the bundle to a temp directory and takes a
couple of seconds; later launches are quick. Copy the file anywhere
(desktop, USB stick, network share) and it'll run.

For Mac and Linux you have to build the binary on the target OS. PyInstaller
doesn't cross-compile. See "Building it yourself" below.

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

## Building it yourself

PyInstaller is in the dev deps. From the repo root:

    uv sync
    uv run pyinstaller --noconfirm --name maxwell --windowed --onefile main.py

You'll get the binary in `dist/`. Build on the OS you want to ship to.

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

## Module map

Each algorithm step is one file under `wave/maxwell/`:

- `channels.py` — steps 1-3: `z_l(E)`, `phi^pm(n)`, `nu_l(E)`
- `kernels.py` — step 4: the kernel `s(n, k, E)`
- `jost.py` — step 5: the iterative recursion for `u_+`, `u_-`
- `wronskian.py` — step 6: the four `W_tau^{E,sigma}`
- `green.py` — step 7: the Green's function with the `W_+` vs `W_-` branch
- `eigfunc.py` — step 8: full eigenfunctions `w_{l,sigma}^{E,pm}`
- `evolve.py` — steps 9-10: normaliser `p` and `psi(n, t)`

`MaxwellSpec` (the algorithm's "Data" block) lives in `wave/maxwell/model.py`.
The Qt bridge that turns spec output into animation frames is
`wave/maxwell/adapter.py`.

## Algorithm status

The code follows the 2026-05-19 spec literally, plus exactly two fixes the
author has blessed (2026-05-19 chat):

- Step 5's sum prefactor is `+i` for `u_+` and `-i` for `u_-`, independent of
  sigma (A.2 — the old README's open question, since confirmed). Jost
  residuals are now ~1e-16.
- Step 8/10 index convention is Interpretation 2 (A.1): the summed sigma is
  the wave-vector sign driving `z^{-sigma n}`; the fixed lower `+/-` index
  (`outer_sign`) picks one Green's-function branch. Balanced packets
  (`f_+ = f_-`) stand still and change shape, per the author.

Three discrepancies are OPEN, awaiting the author, and deliberately left
literal in the code — the test suite pins them exactly so nothing changes
silently (see `memo2_draft.md` for the full write-ups):

- A.10: literal step-7 `G` is `(E-H)^{-1}`, so step 8's subtraction leaves
  `(H-E)w = 2 V phi` at the potential sites. One sign, two equivalent one-line
  fixes; changes potential-scattering output at 100-316% of peak.
- A.11: the literal step-9 `p` normalizes total probability to exactly `2*pi`,
  not 1.
- A.12: the spec never binds the lower `+/-` index on `w`, and `psi` depends
  on it at order one for sigma-asymmetric packets:
  `psi_-[f](n,t) = psi_+[f-swapped](n,-t)` exactly.

## Tests

    uv run pytest

Thirty-plus regression tests: hand-derivations of steps 1-4, honest-Jost
residuals (A.2), Wronskian anchor-independence (A.4), Green's-branch agreement
at `n = j_k` (A.5), Interpretation-2 kinematics (standing wave / left / right,
group velocity `2a`), probability conservation, the per-window quadrature, the
spec-validation errors -- and the A.10/A.11 pins described above.

## License

MIT.
