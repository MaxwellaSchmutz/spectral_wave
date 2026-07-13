# Memo 2 — after the i and Interpretation 2

Status first. Everything from round one landed: step 5 runs your +i / −i (A.2), step 8/10
runs Interpretation 2 (A.1), the Z-domain typo is confirmed fixed in the 2026-05-19 PDF
(A.3), and both program checks you suggested are now permanent regression tests — the
Wronskian is anchor-independent to 2e-14 (A.4) and the two step-7 branch expressions agree
at n = j_k to 2e-15 (A.5). The Jost functions are honest eigenfunctions to 4e-16. Balanced
packets (f_{l,+} = f_{l,−}) stand still and change shape, exactly as you said they should.

Then I composed step 8 and three new things fell out. One of them is a single sign, and it
is currently holding every potential-scattering run hostage. Same format as last time:
numbered questions, hand-checks shown, the literal spec keeps running until you rule.

---

## A.10 — Step 7's G and step 8's minus sign disagree; w misses being an eigenfunction by exactly 2Vφ at the support sites

Good news first: with A.2's i-fix in place, all four Jost functions are honest — (H−E)u = 0
to 4e-16 at every lattice site, every configuration we own. Then step 8 composes them into
w, and the honesty stops at the property line. Off the support of V, (H−E)w = 0 to 1e-15,
as advertised. AT each support site j_k it is neither small nor random:

    (H w)(j_k) − E w(j_k) = 2 V(j_k) z_l^(−σ j_k) e_l        (componentwise, to 1.3e-14)

— exactly twice the potential applied to the incoming FREE wave. Not 2·V·w(j_k), in case
you were wondering; that candidate misses by 0.34 to 8.4 in the same runs. The free φ, on
the nose, at every support site simultaneously. Numbers, literal pipeline, both outer
signs, both σ, every channel:

    config (a): L=1, a=1, V(0)=0.6, lattice −15..15, E ∈ {−0.8, 0, 0.9}:
        max |(H−E)w| off-support ≤ 6.5e-16;  |r(0)| = 1.200000 = 2·0.6 in all twelve
        (E, σ, outer) combinations.
    config (b): L=2, a=(2,1), your V(0)=[[0,1],[1,0]] and V(4)=[[5,0],[0,−3]],
        lattice −12..12, E ∈ {−0.6, 0, 0.5}:
        max off-support ≤ 9.2e-15;  |r(0)| = 2.000000 (both channels),
        |r(4)| = 10.000000 (channel 1) and 6.000000 (channel 2).
        That is 2·‖V(j_k)e_l‖ to six printed digits, in all twenty-four combinations.

Diagnosis: step 7's G, exactly as printed, solves (H−E)G(·,k) = **minus** δ_{·,j_k}·I. We
checked columnwise: max |(H−E)G + δ| = 2.3e-15, while against +δ it misses by exactly
2.000. So the printed G is (E−H)⁻¹, and step 8's w = φ − Σ G V φ subtracts the correction
it should add: (H−E)w = Vφ − (−Vφ) = 2Vφ on the support. Hand-check where everything is
four numbers — L=1, a=1, E=0, V(0)=0.6, z=i:

    u₊(n) = i^(−n) (n ≥ 0),  u₋(n) = i^n (n ≤ 0);  the Wronskians come out
    W₊ = −0.6+2i, W₋ = +0.6−2i (verified to the digit).
    Step 7:  G(0,0) = −1/W₋ = −1/(0.6−2i);   G(1,0) = i^(−1)/W₊ = i/(0.6−2i) = G(−1,0).
    Row sum:  G(1,0) + G(−1,0) + 0.6·G(0,0) = (2i−0.6)/(0.6−2i) = −1.
    Minus one, not plus one.
    Hence w(0) = 1 − 0.6·G(0,0) gives (H−0)w(0) = 0.6 + 0.6 = 1.2 — the table's 1.200000.

Before you point me at the diagnostics we already agreed on: they pass, and that is the
sting. A.4 (Wronskian anchor-independence) holds gloriously — anchors at the left edge, ON
the potential site, and at the right edge agree to 2.2e-14 absolute, 3.5e-15 relative —
because W never sees the sign of G at all. A.5 (the two step-7 branch expressions agree at
the seam n = j_k) holds too — 2.1e-15 — because a global sign flips both branches together
and the seam stays seamless. Every check that compares G with itself is blind to an overall
minus; only the (H−E)-residual of the composed w can see it, and it sees 2Vφ.

The repair is one sign, and there are exactly two places to put it, provably the same
place:

    (fix a) negate step 7's G — equivalently, move the printed minus from the n ≤ j_k
            branch to the n > j_k branch — and keep step 8 as printed;
    (fix b) keep step 7 as printed and flip step 8's minus to a plus:
            w = φ + Σ_k G V φ.

We ran both: the resulting w agree to 0.0e+00 (bitwise — they are the same object), and
either way max |(H−E)w| ≤ 1.1e-14 EVERYWHERE, support sites included, both outer signs,
both configurations.

And it is not cosmetic. On the video configuration (L=2, a=(2,1), your matrices at j=0 and
j=40, window packet on (−0.7, 0.6), t = 0..40): max_n |ψ_literal − ψ_fixed| runs 101% to
316% of the peak of ψ_fixed, the total window mass differs by a factor 1.9–3.2, and the
mass transmitted past the j=40 barrier at t=40 is 6.08 (literal) versus 0.52 (fixed) — a
factor 11.6. The free-space Gaussians are untouched (K=0 never builds G; the difference is
identically 0.000e+00), so the Gaussian videos are fine and every video with a potential in
it is hostage to this sign. A.11's normalization data independently convicts the same sign
from a different direction: with literal G the total probability is f- and V-dependent
(1.04–1.40 × 2π across my tests) and jumps +14.3% between t=0 and any t>0; negate G and all
of it snaps to 2π, flat to 1e-14. Per the house rules, the repo runs the literal spec until
you say otherwise.

**So: is step 7's G secretly (E−H)⁻¹ and the minus belongs on the other branch, or is step
8's minus supposed to be a plus? The w is identical either way — we just need to know which
line changes in the PDF, and we will flip exactly that one and nothing else.**

---

## A.11 — step 9's p normalizes total probability to 2π, not 1

Your A.8 says psi is the probability density, Sigma_n psi "should always be 1", normalized
once at the beginning. I implemented steps 9-10 literally, and the algorithm is in fact
beautifully self-consistent — it just insists on a different constant. For every free
configuration I can build — single Gaussian, balanced sigma pair, phase-shifted packet
parked at n=20, two channels with a=(2,1), your window presets once I mollify their edges —
the once-at-the-beginning total is

    Sigma_n psi(n,0) = 2*pi, to twelve digits.

| config | Sigma psi / 2pi |
|---|---|
| Gaussian sigma+ (L=1, free) | 1.000000000000 |
| balanced f+ = f- | 1.000000000000 |
| phase e^{i 20 theta} (packet at n=20) | 1.000000000000 |
| L=2, a=(2,1), both channels | 0.999999999960 |
| smoothed windows, L=2 | 0.999999999999 |
| V(0)=0.6 (L=1) | 1.166897731448 (*) |
| V(0)=[[0,1],[1,0]], smoothed windows | 1.387852225264 (*) |
| (*) with A.10's one-line sign fix, both become | 1.000000000000 |

The why is two lines. In step 10 the lattice sum meets the plane-wave kernel:
sum_{n in Z} e^{-i n (theta - theta')} = 2*pi delta(theta - theta'), theta = arccos(E/2a)
in (0,pi); cross-sigma terms would need delta(theta + theta'), which is unreachable on
(0,pi), so they vanish (numerically: the n=0 term is 4e-2 of the total, the sum cancels to
9e-15). Substituting E = 2a cos(theta), dE = -2a sin(theta) dtheta, nu = 1/(2a sin(theta))
gives delta(theta-theta') = nu^{-1} delta(E-E'), and the step-10 sqrt(nu) is exactly the
half-density that collapses the measures: sqrt(nu nu')/nu -> 1. What survives is
2*pi * sum_{l,sigma} int |f|^2 dE = 2*pi * p. Your p cancels itself and leaves the bare
completeness constant.

Conservation, which you predicted, is better than predicted: with the packet contained and
the quadrature resolved, max_t |S(t)-S(0)|/S(0) = 3.2e-14 over t in [0,50] (Gaussian,
N=+-150), 5.6e-16 for the smoothed windows. Machine zero. The asterisked rows are A.10
again, wearing a different hat: with the literal step-7/8 sign the w's are not
eigenfunctions, so the family is not orthogonal — the total becomes f- and V-dependent
(1.04 to 1.40 across my tests) and even jumps by +14.3% between t=0 and any t>0. Negate G
and all of it snaps to 2*pi and 1e-14 flatness. Two birds, one sign.

Post-mortem on the ~5% drift in my earlier memo: not the algorithm. It was (i) hard window
presets, whose position tails decay like 1/n^2 and carry 10.4/n_max of the mass past the
lattice edge — exactly 5.0% at N=+-200, extrapolating to 2*pi as the lattice grows
(Richardson: 1.0000052) — plus (ii) undersampled quadrature: at n_quad=64 the E-oscillation
e^{-i(n theta + t E)} aliases into a phantom mirror packet carrying a full 2*pi (S doubles
by t=50; the t=0 frame looks immaculate, which is why I missed it). Rule of thumb,
validated on 12 configs: n_quad >= ceil((n_max * Dtheta + t_max * (b-a)) / pi) + 8, which
flags 64 as unsafe and 128 as safe for the case above. The GUI now computes this.

**The ask: is p missing a 1/(2*pi) (completeness measure), or do you want me to normalize
by the discrete t=0 total? Either is one line; they agree to 1e-12 for contained packets.
Running literal 2*pi until you pick.**

---

## A.12 — the lower ± index on w is never bound; does ψ care? (It does. By roughly a factor of one.)

Step 8 defines w^{E,σ}_{l,±} with four decorations. Step 10 then sums over l and σ and
integrates over E — which binds l, σ, and E, and leaves the lower ± dangling: no sum, no
selection rule, no stated default. A.1 told us it selects which Green's-function branch
G^{E,±} enters step 8 (we implement it as `outer_sign`, currently +1). It did not tell us
which one, or whether the physics notices. It notices.

With the honest w (A.10's one sign applied), on the video configuration (window packet,
f_{2,−} = 0): max_n |ψ₊ − ψ₋| / max ψ₊ = 0.66, 0.92, 1.06, 0.96, 0.96 at t = 0, 10, 20, 30,
40. An L=1 barrier (V(0)=0.6) with a Gaussian on σ=+ only: 0.45, 0.30, 0.096, 0.096, 0.096.
So for the asymmetric σ-modes (1,0) and (0,1) — the exact Gaussians you asked to see — the
unbound index moves ψ by order one. Make f σ-symmetric and the two choices agree at t=0 to
1e-15, then drift apart by 0.7–1.5% for t > 0.

The dependence is not noise; it is one exact identity, machine-precise in every
configuration we ran:

    ψ_{−}[f](n, t) = ψ_{+}[f with f_{l,+} ↔ f_{l,−} swapped](n, −t)     (max rel dev 8.1e-15)

i.e. flipping the lower index is exactly time reversal composed with swapping the
σ-components of f — the retarded/advanced choice, wearing a trench coat. Corollaries, also
verified: for σ-symmetric f it degenerates to pure time reversal, ψ₋(t) = ψ₊(−t) (dev
6.5e-15), which is why t=0 cannot see it; for the parity-symmetric L=1 barrier it is
equally mirror-plus-time-reversal, ψ₋(n,t) = ψ₊(−n,−t) (dev 2.0e-15). The literal, unfixed
code obeys the same identity (dev ≤ 6.2e-15) and its outer-dependence is even larger — 41%
of peak for the symmetric Gaussian, against 1.5% fixed — so this question survives A.10
whichever way that one lands.

Since you also want negative-time footage, note the trap: pick outer=+ and every
negative-time frame is secretly the outer=− movie of the σ-swapped packet, and vice versa.
Someone has to choose on purpose, and the spec currently chooses by omission.

**So: bind the index. For the videos — σ-modes (1,1), (1,0), (0,1), negative times included
— is w^{E,+} (our current default) the intended branch, or w^{E,−}, or is the ± supposed to
be tied to something the PDF doesn't say (σ? the sign of t?)? It is one subscript in step
8, and it moves ψ by 100% of peak for exactly the asymmetric Gaussians you ordered.**

---

## A.13 — three small ones

1. **A.8 notation, once the constant lands.** The PDF's ψ(n,t) is already the squared
   modulus (step 10 has the |·|²), so when you say "Σ|ψ|² should be 1" I read the conserved
   total as Σ_n ψ_PDF(n,t) = 1 — i.e. no second squaring. Confirm?
2. **Negative times: how far back?** The videos will run t from negative to positive as
   requested. Default plan: symmetric [−T, +T] so the packet converges, scatters, and
   departs. Fine, or do you want a specific ratio? (Mind A.12's trap: the meaning of the
   t<0 half currently depends on the unbound ± index.)
3. **Schober 1's frame is too small for its own packet.** N=−10..10 is 21 sites; your
   window f's position tails decay like 1/n² and carry ≈10.4/n_max of the mass, so a
   21-site frame holds well under half the packet. For the video I will run it verbatim
   anyway (your config, your call), but say the word and I widen it to ±100 like Schober 2
   so the physics is visible.

---

## B. What changed on my side since the last memo (yell if anything offends)

- B.1 rebuilt (the hard drive took it): σ-modes balanced/right/left = (h₊,h₋) ∈
  {(1,1),(1,0),(0,1)}, the z₀^{n_init} placement phase, and your two window presets — plus
  video export and time axes that start negative, per your requests.
- B.5 done: the step-9/10 integrals now run one Gauss–Legendre rule per [c,d] window
  (spectral: machine precision at 32 nodes where one rule over the union sat at 1e-3).
  This is also closer to the letter of the spec, which integrates each (l,σ) over its own
  [c_{l,σ}, d_{l,σ}].
- The regression suite is back, and it PINS the literal spec: (H−E)w = 2Vφ at support
  sites and Σψ(·,0) = 2π are asserted EXACTLY, with comments forbidding a "fix" until you
  rule on A.10/A.11. When you pick a line, I flip that line and the pins flip with it.
- The GUI warns when n_quad is below the validated aliasing threshold (A.11 post-mortem).

TL;DR — the three things I actually need from you:
1. **A.10**: which line owns the sign — step 7's G or step 8's minus? (Same w either way.)
2. **A.11**: 1/(2π) into p, or normalize by the discrete t=0 total?
3. **A.12**: bind the lower ± index — which branch is the intended one for the videos?

Thanks Jonas,
Maxwell
