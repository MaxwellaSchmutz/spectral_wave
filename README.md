# Maxwell Algorithm

This program draws a quantum wave packet moving along a line and shows you what
happens when it runs into something. You pick a setup, hit a button, and get an
animation plus a heatmap of the whole thing.

It's my implementation of an algorithm my professor, Jonas Schober, wrote out
for me. The math behind it is his and his coauthor's — three papers, all in
`docs/papers/`. The code is mine.

## What you're actually looking at

Normally you'd think of a particle moving through continuous space. Here space
is a **lattice**: a row of discrete sites at the integers, `..., -2, -1, 0, 1,
2, ...`. The wave only lives at those sites. Think of beads on a string rather
than a smooth curve.

The wave packet is a bump spread over some of those sites. The height of the
bump at site `n` is the probability of finding the particle there. Add up the
whole bump and you get 1 — it's somewhere.

What makes it move is this rule:

    (H psi)(n) = A psi(n+1) + A psi(n-1) + V(n) psi(n)

Read it as: what happens at site `n` next depends on its two neighbours, plus
whatever is sitting *at* `n`. `A` sets how fast stuff hops between neighbours.
`V(n)` is the **potential** — the obstacle. It's zero almost everywhere and
nonzero at a handful of sites. That's the barrier, the well, the wall.

Two things make this more than a first-year problem:

**It's matrix-valued.** At each site the wave isn't one number, it's `L` of
them. Picture `L` parallel lanes stacked on top of each other. Each lane `l`
has its own hopping speed `a_l`, so packets in different lanes travel at
different speeds. The potential `V(n)` is an `L x L` matrix, which means it can
knock the wave from one lane into another. Those lanes are called **channels**.

**The speeds are sorted.** `a_1 >= a_2 >= ... >= a_L > 0`. This matters more
than it looks. Each channel `l` can only carry a wave at energies `|E| < 2*a_l`;
outside that range it's stuck. So as you dial the energy up, channels shut off
one at a time. That's the whole subject of the three papers, and it's why they
exist.

## How the algorithm works

The dumb way to animate this is to step forward in tiny time increments. That's
not what this does.

Instead it finds the wave's **natural modes** — the special shapes that don't
change form as time passes, they just rotate in place at their own frequency.
Once you have those, time evolution is easy: every mode picks up a factor
`e^{-iEt}` and you add them all back up. One formula, any `t` you want, no
stepping. Negative `t` is as cheap as positive `t`.

Finding those modes is the hard part, and it's what steps 1 through 8 do:

| Step | File | What it does |
|---|---|---|
| 1 | `channels.py` | `z_l(E)` — the wave's phase per site, one per channel |
| 2 | `channels.py` | `phi(n)` — plain waves, no obstacle yet |
| 3 | `channels.py` | `nu_l(E)` — how fast a wave at this energy travels |
| 4 | `kernels.py` | `s(n,k,E)` — how a kick at site `k` spreads to site `n` |
| 5 | `jost.py` | **Jost solutions** — waves that look plain far from the obstacle but get bent up close |
| 6 | `wronskian.py` | Wronskians — bookkeeping that says whether two solutions are independent |
| 7 | `green.py` | **Green's function** — the response to poking the system at one site |
| 8 | `eigfunc.py` | The actual modes: plain wave, minus the correction the obstacle causes |
| 9-10 | `evolve.py` | Weight the modes, add them up with `e^{-iEt}`, square it |

Step 10 is the payoff, and everything above it is setup:

    psi(n,t) = | sum over channels and directions, integral over energy of
                   e^{-iEt} * f(E) * (mode at site n) |^2

`f(E)` is yours to pick — it's which energies your packet is built from. Wide
`f` means a sharp packet in space that spreads fast. Narrow `f` means a long
smeared packet that holds its shape.

The reason any of this is legitimate is Theorem 2.2.5 of the third paper, which
proves those modes are a complete, non-redundant basis. Schober's words: *"the
algorithm that you programmed diagonalizes the infinite matrix, which allows us
to calculate its exponential and therefore how things behave over time."*

## Running it

Needs Python 3.12. With [uv](https://github.com/astral-sh/uv):

    uv sync
    uv run python main.py

Without uv:

    python -m venv .venv
    .venv\Scripts\activate          # Windows
    source .venv/bin/activate       # macOS / Linux
    pip install numpy matplotlib pyqt6 pillow
    python main.py

## Using the viewer

Pick a preset from the dropdown. There are thirteen:

- **Free Gaussian** — no obstacle. The packet drifts and spreads. Start here.
- **Single barrier / single well** — part bounces off, part goes through.
- **Double barrier** — the two barriers form a cavity and the wave rings
  between them before leaking out.
- **Strong wall** (`V=3.5`) — almost everything bounces.
- **Weak barrier** (`V=0.12`) — the reflection is too faint to see in the top
  panel; look for it in the heatmap.
- **Wide barrier** — four sites thick. Tunneling drops off sharply with width.
- **Random lattice** — noise everywhere, the packet breaks into speckle.
- **Two-channel free / coupled** — two lanes at different speeds. Coupled adds
  an off-diagonal term so the lanes can trade energy.
- **Slow packet** — energy near the band edge, where the wave barely moves.
- **Schober 1 / 2** — his own test configs.

Editing any field flips the dropdown to "Custom" so you can keep tweaking
without losing your starting point. **Careful:** on the Schober presets that
also silently swaps out the special step-function `f` and the per-window
integration, so you get a plain Gaussian instead. Same goes for the outer-sign
dropdown, which makes it awkward to run the plus-vs-minus comparison from the
GUI. Both are on the fix list in `docs/AUDIT.md`.

For the Gaussian presets:

- **sigma mode** picks direction. `(1,1)` balanced sits still and spreads,
  `(1,0)` runs right, `(0,1)` runs left.
- **start site** parks the packet wherever you want on the lattice.
- **time start** can be negative, so you can watch the packet come in, hit the
  obstacle, and leave.

Hit **Compute & Animate**. The math runs on a background thread so the window
doesn't freeze. Top panel is the packet at one instant; bottom is the whole
`psi(n,t)` as a heatmap, with time going up. Reflections show up as trails
going the other way, tunneling as a faint trail continuing through. Vertical
markers show where the obstacle sits.

Transport bar does play/pause, restart, scrubbing, speed (0.25x to 4x), and
export to video — MP4 if you have ffmpeg on your PATH, GIF otherwise. The four
readouts under the controls are max height, total probability, where the peak
is, and the current time.

**One gotcha worth knowing.** The lattice is finite. If the packet runs off the
edge of the frame it's gone, and the total-probability readout starts dropping.
Ten of the thirteen presets do this by the end of their time range — Schober 1
holds only about 20% of the packet by `t_max`. If that number is falling, widen
`N` and `M`.

## Where things stand

Four places the code knowingly departs from the written spec. All four are
changes Schober approved:

- **Step 5's sign** is `+i` / `-i` rather than the real signs the spec has. Not
  actually a departure once you check it against paper 1 — it reproduces that
  paper's formula exactly, and the residual drops to about `1e-16`.
- **Step 8's indices** follow "Interpretation 2": the summed index drives the
  plane wave, the other one picks a branch. His test for this was that a
  balanced packet should sit still instead of drifting, and it does.
- **Step 7's signs** (A.10). The spec's version made the Green's function come
  out backwards, which double-counted the obstacle — `(H-E)w` came out as
  `2V` at the obstacle instead of 0. Flipping the signs in `green.py` fixed it:
  `1.6` down to `2.4e-16`. He was specific that the fix goes there and *not* in
  step 8's sum.
- **Dividing by 2π** (A.11). Total probability was coming out as `2*pi` instead
  of 1. His answer: *"Don't change p, just divide the final psi by 2pi."* Now
  `sum_n psi = 0.99999999998`.

### The one open question

Step 10 has a `+/-` index that nothing in the spec ever pins down. Schober
wouldn't pick a sign — he turned it into a test instead: *"run the whole
program twice, once with a + and once with a -. If everything is correct, the
videos should look exactly the same."*

They don't. With an obstacle present they differ by 14% for the simple case and
65% for a two-channel one. But **nothing is broken**, and this took a while to
be sure of. Both versions satisfy `(H-E)w = 0` to `6e-16`, and both keep total
probability at `1.000000000000` at every time I checked, including negative
times and a strong wall. Neither one is the wrong branch — they're both exact.

What they differ by is the scattering matrix `S_E`, which comes out unitary to
`1e-15` with determinant 1. That forces `psi_-[f] = psi_+[S^-1 f]`, so the two
runs can only match when `S_E = 1`, meaning no obstacle. Which is exactly what
happens — with `V = 0` they agree to `0.000e+00`.

So the real question isn't a sign, it's what `f` is supposed to be. The spec's
Data item (f) says `f` is a function you hand in, fixed. Under that reading the
two runs are *supposed* to differ and his test can't pass. If instead you hand
in a starting state and derive `f` from it, the test becomes a theorem — I
implemented that version and it agrees to `4.3e-15`. Waiting on his answer.
Full writeup in `docs/AUDIT.md`, sections 1 through 4.

### One thing not to copy

`docs/professor_response.txt` line 51 gives a shortcut for step 1 that has the
sign flipped in the exponent. Using it literally makes `nu` come out negative,
which contradicts his own line 52 *and* the spec, which says explicitly "the
solution with `Im(z) > 0`". The code keeps `Im z > 0`. Don't change that
without asking him.

## Tests

    uv run pytest

Thirty-two of them. They re-derive steps 1-4 by hand and check the code matches
to about `1e-12`, confirm the Jost solutions actually solve the equation, check
the Wronskian doesn't depend on where you anchor it, check both branches of the
Green's function agree where they meet, check the packet moves the right
direction at the right speed, and check probability is conserved.

**What they don't cover**, which matters: nothing runs a packet through an
actual obstacle, nothing uses negative time, nothing touches the `+/-` index,
and nothing compares against an independent answer worked out a different way.
`docs/AUDIT.md` §7 item 7 has the four tests that would close those holes — all
four pass right now, they just aren't written down yet.

## Layout

    spectral/maxwell/   the algorithm, one file per step
    gui/                the viewer
    tests/
    docs/               the spec, the papers, the emails, the audit
    main.py             start here

To use it without the GUI:

    from spectral.maxwell import MaxwellSpec, compute_psi

    psi = compute_psi(spec)      # (times, sites), real, all non-negative

`MaxwellSpec` in `spectral/maxwell/model.py` is the "Data" block from the spec
— same fields, same names, same order. `docs/README.md` explains what every
document in `docs/` is and which one wins when they disagree.

## License

MIT — see `LICENSE`.
