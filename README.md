# Maxwell Algorithm

Reference implementation of Jonas Schober's matrix-valued lattice scattering
algorithm (April 2026) plus a desktop viewer to actually see the wave packet
move.

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

Pick a preset from the dropdown in the sidebar. The eleven options cover the
free Gaussian wave packet, single barriers and wells, the double-barrier
resonant cavity, the two-channel free and coupled-scatterer cases, and a
slow packet near the band edge. Each preset writes its parameters into the
form below the dropdown. Edit any field by hand and the dropdown switches to
"Custom" so you can keep tweaking without losing where you started.

Hit "Compute & Animate". The algorithm runs off the UI thread, so the window
stays responsive. When it's done, the curve animates on the top panel and the
spacetime view fills in below. The waterfall is the entire `psi(n, t)` rendered
as a heatmap — reflections, tunneling, channel separation all show up as
continuous trails through it.

The transport bar handles playback. Play / pause, restart, scrub anywhere on
the timeline, change speed (0.25x through 4x). Vertical markers on both panels
show where the potential sites sit. The four monospace stats below the
controls update every frame: max amplitude, running L1 norm, peak lattice
site, current time.

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

## Open question for the author

Step 5 as written in the spec doesn't produce honest `H`-eigenfunctions. Hand
check at L=1, V(0)=0.5, n=0: the residual `(H u)(0) - E u(0)` comes out to
`0.5 (1 + i)` instead of zero. Tracing the construction back through paper 1
(Definition 3.4 + Lemma 2.11(c)) shows the `+/-` prefactor on the sum is
missing a factor of `i`: the correct sign is `+i` for `u_+` and `-i` for
`u_-`, both independent of sigma. With that fix the residual drops to
machine precision.

The current code follows the spec literally, no `i`. One-line patch in
`jost.py` flips it. Waiting on Schober's confirmation before changing the
default.

## License

MIT.
