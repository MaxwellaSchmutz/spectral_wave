"""Composite quadrature over energy windows (memo item B.5).

B.5 is Maxwell's own numerics, not spec territory -- no Schober sign-off
needed, but the behavior is contractual for the GUI presets: window-type
f integrated segment-by-segment converges spectrally; one Gauss-Legendre
rule spanning the window edges does not. These tests pin both facts plus
the deterministic node-allocation rule and the validation surface.
"""

from __future__ import annotations

import numpy as np
import pytest

from wave.maxwell import MaxwellSpec, compute_psi
from wave.maxwell.quadrature import gauss_legendre_segments


def window_f(E):
    """The two-channel window excitation from the memo:
    f_{1,+} = f_{1,-} = indicator[0.4, 0.6]; f_{2,+} = indicator[-0.7, -0.5];
    f_{2,-} = 0. Shape (n_E, L=2, 2), [:, :, 0] = sigma+."""
    E = np.asarray(E, dtype=float).reshape(-1)
    out = np.zeros((E.size, 2, 2), dtype=complex)
    w1 = ((E >= 0.4) & (E <= 0.6)).astype(float)
    w2 = ((E >= -0.7) & (E <= -0.5)).astype(float)
    out[:, 0, 0] = w1
    out[:, 0, 1] = w1
    out[:, 1, 0] = w2
    return out


def _window_spec(n_quad, E_segments=None):
    """Free two-channel spec, a = [2, 1], slab +-120, times {0, 5}."""
    return MaxwellSpec(
        L=2, a=np.array([2.0, 1.0]), N=-120, M=120,
        j_sites=np.array([], dtype=int),
        V_sites=np.zeros((0, 2, 2), dtype=complex),
        interval=(-0.7, 0.6), f=window_f,
        times=np.array([0.0, 5.0]), n_quad=n_quad,
        E_segments=E_segments,
    )


SEGMENTS = [(-0.7, -0.5), (0.4, 0.6)]


def test_segmented_quadrature_is_spectral_where_single_rule_is_not():
    """(i) With segments matching the window supports the integrand is
    smooth on every segment, so 64 total nodes already agree with an
    800-node reference to machine noise (measured 1.9e-15). One rule over
    the whole interval sees the f discontinuities at E = -0.5 and 0.4 and
    stalls at ~3.5e-3 -- three orders past the 1e-5 bound. That gap is why
    E_segments exists."""
    ref = compute_psi(_window_spec(800, E_segments=SEGMENTS))

    seg_coarse = compute_psi(_window_spec(64, E_segments=SEGMENTS))
    assert np.max(np.abs(seg_coarse - ref)) < 1e-10

    single_coarse = compute_psi(_window_spec(64, E_segments=None))
    assert np.max(np.abs(single_coarse - ref)) > 1e-5


@pytest.mark.parametrize(
    "bad_segments",
    [
        [(-0.6, -0.4), (-0.5, 0.2)],      # overlapping
        [(0.6, 0.4)],                     # reversed endpoints (lo >= hi)
        [(0.4, 0.6), (-0.7, -0.5)],       # reversed order == not strictly ordered
        [(1.5, 2.5)],                     # out of the open band |E| < 2
        [],                               # empty list
    ],
    ids=["overlapping", "reversed-endpoints", "reversed-order", "out-of-band", "empty"],
)
def test_segment_validation_rejects_bad_input(bad_segments):
    """(ii) E_segments must be non-empty, each lo < hi, strictly ordered,
    non-overlapping, and inside the buffered open band."""
    with pytest.raises(ValueError):
        _window_spec(64, E_segments=bad_segments).validate()


def test_gauss_legendre_segments_allocation():
    """(iii) Deterministic node budget: proportional to length with
    largest-remainder rounding and a floor of 16 per segment. Lengths
    0.5 and 2.5 out of 120 nodes => exactly [20, 100]. Per-segment
    weights sum to the segment length (Gauss-Legendre exactness on
    constants); nodes come out strictly ascending."""
    nodes, weights = gauss_legendre_segments([(0.0, 0.5), (1.0, 3.5)], 120)

    in_first = (nodes >= 0.0) & (nodes <= 0.5)
    in_second = (nodes >= 1.0) & (nodes <= 3.5)
    assert int(in_first.sum()) == 20
    assert int(in_second.sum()) == 100
    assert int(in_first.sum() + in_second.sum()) == nodes.size == 120

    assert abs(weights[in_first].sum() - 0.5) < 1e-12
    assert abs(weights[in_second].sum() - 2.5) < 1e-12
    assert np.all(np.diff(nodes) > 0.0)
