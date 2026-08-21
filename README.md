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

The code follows the 2026-05-19 spec, plus four fixes the author has blessed
(2026-05-19 and 2026-08 chats, the latter in `professor_response.txt`):

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

Two items are OPEN.

**A.12 — the lower `+/-` index of `w`, and it is a live bug, not a
convention.** The author declined to bind the index and instead made it a
correctness test: "You should run the whole programm twice. Once with a + and
once with a -. If everything is correct, the videos should look exactly the
same up to computer precision. If they don't look the same, something in the
algorithm/math is still wrong."

They do not look the same. Measured `max|psi_+ - psi_-| / max|psi_+|` over
`t` in `[-12, 12]`, `L=1`, `a=1`, one site `V(0)=0.8`, `n_quad=400`:

| packet | as-is | after the A.10 fix | branch tied to sigma |
| --- | --- | --- | --- |
| balanced (1,1) | 1.18e-01 | 1.53e-01 | 2.64e-01 |
| right (1,0)    | 3.94e-01 | 3.93e-01 | 3.93e-01 |
| left (0,1)     | 2.99e-01 | 4.03e-01 | 3.93e-01 |

With no potential (`K = 0`) the two branches agree to exactly `0.000e+00`. So
the defect lives in the potential path, steps 5-8; it is independent of A.10;
and `(H-E)w = 0` holds to ~6e-16 for every branch convention, so the residual
check cannot see it. Tying the lower index to sigma does not fix it either.
Likeliest seam: `green.py` produces axis 0 as the sigma label of
`G^{E,sigma}` (from `u_+[sigma]` and `u_-[-sigma]`) while `eigfunc.py`
consumes the same axis as the LAP branch `+/-`. Those coincide only if the
sigma of paper 2's `G^K_{E,sigma}` really is the `+/- i0` boundary label.

**Steps 1 and 3 simplifications — conjugate mismatch, unconfirmed.** The
author offered `z_l(E) = e^{-i arccos(E/(2 a_l))}` and
`nu_l(E) = 1/sqrt((2 a_l)^2 - E^2)`. The nu formula matches the code exactly
(`max|diff| = 0.0`). The `z` formula is the *complex conjugate* of what the
code computes (`max|code - prof| = 2.0`; `max|code - conj(prof)| = 2.2e-16`)
— the code uses `e^{+i arccos}`, i.e. `Im z > 0`, the papers' `z_-`. His two
formulas are mutually inconsistent: substituting his `z` into the code's
`nu = 1/(2 a_l Im z_l)` gives a negative nu, contradicting his own positive
root. Almost certainly an exponent-sign slip, but not adopted until he
confirms — flipping that branch negates the antisymmetric `s`-kernel and
propagates through steps 4-10.

## Tests

    uv run pytest

Thirty-plus regression tests: hand-derivations of steps 1-4, honest-Jost
residuals (A.2), Wronskian anchor-independence (A.4), Green's-branch agreement
at `n = j_k` (A.5), the step-8 eigenfunction residual (A.10, now `< 1e-12`
everywhere), total probability `= 1` (A.11), Interpretation-2 kinematics
(standing wave / left / right, group velocity `2a`), probability conservation,
the per-window quadrature, and the spec-validation errors.

Nothing covers A.12, and no test exercises `t < 0`.

## License

MIT.
