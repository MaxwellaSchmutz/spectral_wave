Hi Jonas,

The i-correction and interpretation 2 are in. The u's now solve (H−E)u = 0 to machine
precision (10⁻¹⁶), balanced packets (f_{l,+} = f_{l,−}) stand still and just change
shape, and both checks you suggested hold: the Wronskian is anchor-independent and the
two branches of G agree at n = j_k, each to 10⁻¹⁴.

Composing step 8, I found three things I need your ruling on.

First, I think one sign is off between steps 7 and 8. If I am not mistaken, the G of
step 7 satisfies (H−E)G = −δ — it is (E−H)⁻¹ — so the minus in step 8 double-counts: at
every potential site (H−E)w = 2 V(j_k) z^{−σj_k} e_l exactly, and 0 everywhere else.
(The two checks above cannot see this; both are insensitive to an overall sign of G.)
Negating G, or writing step 8 with a plus, gives the same w either way, and then
(H−E)w = 0 everywhere. It matters: with a potential present the two versions give
completely different ψ — transmission through a barrier differs by a factor ~10. Which
of the two formulas carries the sign? I compute the literal version until you say.

Second, if I am not mistaken the total probability sums to 2π, not 1. In every
potential-free case with the packet well inside the frame, Σ_n ψ(n,0) = 2π to twelve
digits: the lattice sum produces Σ_n e^{−in(θ−θ′)} = 2π δ(θ−θ′), the √ν absorbs the
change of variables, and what remains is exactly 2π·p. The total is then constant in t
to 10⁻¹⁴. (The ~5% drift I reported earlier was my fault — mass leaving the finite frame
plus too few quadrature points, not the algorithm.) Should p carry a factor 1/(2π), or
should I simply divide by the computed total at t = 0?

Third, the lower ± index of w is never fixed by anything: step 10 sums over l and σ and
integrates over E, but nothing selects the ±. And ψ depends on it, exactly via
ψ₋[f](n,t) = ψ₊[f with f_{l,+} and f_{l,−} interchanged](n,−t) — the two choices differ
by time reversal combined with swapping the σ-components. For the (1,0) and (0,1)
Gaussians you asked to see, the difference is as large as ψ itself, and the t < 0 part
of any video silently depends on the choice. Which ± do you intend — or should it be
tied to σ, or to the sign of t? I use + for now.

Three small ones. Your ψ in step 10 already contains the |·|², so I read "Σ|ψ|² = 1" as
Σ_n ψ(n,t) = 1 — right? For the videos, is time running over a symmetric [−T, +T] fine?
And in your first example, N = −10..10 holds less than half the packet (an indicator f
decays like 1/n² in position) — keep it as given, or widen the frame?

The Gaussian videos for (1,1), (1,0), (0,1) with negative times are ready; without a
potential they are not affected by the sign question.

Maxwell
