"""Maxwell algorithm viewer — interactive dashboard.

Sidebar: preset library + form for every MaxwellSpec field.
Right: live psi(n, t) curve, scrub/play/speed controls, and a spacetime
waterfall heatmap of psi over the full time horizon.
"""

from __future__ import annotations

import shutil

import numpy as np
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from matplotlib import animation
from matplotlib import patheffects as pe
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from wave.maxwell import MaxwellSpec, maxwell_to_frames


# =====================================================================
# Palette
# =====================================================================
BG_DEEP   = "#0f0f18"
BG_PANEL  = "#181826"
BG_INPUT  = "#252535"
BG_INPUT2 = "#2d2d42"
BG_PLOT   = "#13131e"
BORDER    = "#36364e"
TEXT_PRIM = "#e8e8f5"
TEXT_DIM  = "#a4a8c4"
TEXT_FAINT = "#7a7e98"
ACCENT    = "#7d6cff"   # electric purple
ACCENT_HV = "#9485ff"
ACCENT2   = "#4cc9f0"   # cyan — wave-packet line
SUCCESS   = "#06d6a0"   # mint — progress
WARN      = "#ffd166"
DANGER    = "#ff6b8a"


STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "SF Pro Display", "Inter", system-ui, sans-serif;
    font-size: 13px;
    color: {TEXT_PRIM};
}}

QMainWindow, QWidget {{
    background-color: {BG_DEEP};
}}

QFrame#sidebar {{
    background-color: {BG_PANEL};
    border-right: 1px solid {BORDER};
}}

QFrame#controlbar {{
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
}}

QLabel {{
    color: {TEXT_DIM};
    background: transparent;
}}

QLabel#header {{
    color: {TEXT_PRIM};
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

QLabel#subheader {{
    color: {TEXT_FAINT};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 2.2px;
}}

QLabel#section {{
    color: {ACCENT};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2.2px;
}}

QLabel#description {{
    color: {TEXT_DIM};
    font-size: 12px;
    font-style: italic;
    padding: 4px 2px;
    line-height: 1.6;
}}

QLabel#timecode {{
    color: {ACCENT2};
    font-size: 13px;
    font-weight: 600;
    font-family: "Cascadia Code", "Consolas", "SF Mono", monospace;
    letter-spacing: 0.5px;
}}

QLabel#statbig {{
    color: {TEXT_PRIM};
    font-size: 14px;
    font-weight: 600;
    font-family: "Cascadia Code", "Consolas", "SF Mono", monospace;
}}

QLabel#statlbl {{
    color: {TEXT_FAINT};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
}}

QLineEdit, QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 11px;
    selection-background-color: {ACCENT};
}}

QLineEdit:hover, QComboBox:hover  {{ border-color: #4d4d6a; }}
QLineEdit:focus, QComboBox:focus  {{ border-color: {ACCENT}; background-color: {BG_INPUT2}; }}

QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 9px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    color: {TEXT_PRIM};
    padding: 6px;
    outline: 0;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}}

QPushButton {{
    background-color: {ACCENT};
    color: {TEXT_PRIM};
    border: none;
    padding: 11px 18px;
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton:hover    {{ background-color: {ACCENT_HV}; }}
QPushButton:pressed  {{ background-color: #6856e6; }}
QPushButton:disabled {{ background-color: #2c2c40; color: #5a5a72; }}

QPushButton#secondary {{
    background-color: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_PRIM};
}}
QPushButton#secondary:hover    {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#secondary:disabled {{ border-color: #2a2a3a; color: #5a5a72; }}

QPushButton#icon {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    padding: 6px 10px;
    min-width: 38px;
    font-size: 14px;
    border-radius: 8px;
    color: {TEXT_PRIM};
}}
QPushButton#icon:hover    {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton#icon:disabled {{ color: #5a5a72; border-color: #2a2a3a; }}

QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {BG_INPUT};
    height: 5px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {SUCCESS};
    border-radius: 4px;
}}

QSlider::groove:horizontal {{
    background: {BG_INPUT};
    height: 5px;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: {BG_INPUT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: 2px solid {BG_PANEL};
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HV};
    width: 16px;
    margin: -8px 0;
    border-radius: 10px;
}}

QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
"""


# =====================================================================
# Preset library
# =====================================================================
PRESETS: dict[str, dict | None] = {
    "Free Gaussian Wave Packet": dict(
        L="1", a="1.0", N="-120", M="120",
        j_sites="", V_sites="[]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.30",
        sigma_mode="right", n_init="0",
        n_t="120", t_min="0", t_max="50", n_quad="128",
        outer="+",
    ),
    "Single Barrier — partial reflection": dict(
        L="1", a="1.0", N="-100", M="100",
        j_sites="0", V_sites="[[[0.6]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.25",
        sigma_mode="right", n_init="0",
        n_t="140", t_min="0", t_max="55", n_quad="128",
        outer="+",
    ),
    "Single Well — attractive site": dict(
        L="1", a="1.0", N="-100", M="100",
        j_sites="0", V_sites="[[[-0.8]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.25",
        sigma_mode="right", n_init="0",
        n_t="140", t_min="0", t_max="55", n_quad="128",
        outer="+",
    ),
    "Double Barrier — resonant cavity": dict(
        L="1", a="1.0", N="-130", M="130",
        j_sites="-6, 6", V_sites="[[[0.55]], [[0.55]]]",
        interval_lo="-1.3", interval_hi="1.3",
        E0="0.0", sigma_E="0.20",
        sigma_mode="right", n_init="0",
        n_t="160", t_min="0", t_max="65", n_quad="128",
        outer="+",
    ),
    "Strong Wall — near-total reflection": dict(
        L="1", a="1.0", N="-100", M="100",
        j_sites="0", V_sites="[[[3.5]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.30",
        sigma_mode="right", n_init="0",
        n_t="120", t_min="0", t_max="50", n_quad="128",
        outer="+",
    ),
    "Weak Barrier — small kick": dict(
        L="1", a="1.0", N="-100", M="100",
        j_sites="0", V_sites="[[[0.12]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.30",
        sigma_mode="right", n_init="0",
        n_t="120", t_min="0", t_max="50", n_quad="128",
        outer="+",
    ),
    "Wide Barrier — tunneling": dict(
        L="1", a="1.0", N="-130", M="130",
        j_sites="-3, -1, 1, 3", V_sites="[[[0.45]], [[0.45]], [[0.45]], [[0.45]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.20",
        sigma_mode="right", n_init="0",
        n_t="140", t_min="0", t_max="55", n_quad="144",
        outer="+",
    ),
    "Random Lattice (L=1)": dict(
        L="1", a="1.0", N="-130", M="130",
        j_sites="-9, -4, 0, 5, 11", V_sites="[[[0.30]], [[-0.40]], [[0.55]], [[-0.20]], [[0.35]]]",
        interval_lo="-1.5", interval_hi="1.5",
        E0="0.0", sigma_E="0.25",
        sigma_mode="right", n_init="0",
        n_t="160", t_min="0", t_max="60", n_quad="144",
        outer="+",
    ),
    "Two-Channel Free (L=2)": dict(
        L="2", a="1.0, 0.6", N="-100", M="100",
        j_sites="", V_sites="[]",
        interval_lo="-0.9", interval_hi="0.9",
        E0="0.0", sigma_E="0.20",
        sigma_mode="right", n_init="0",
        n_t="140", t_min="0", t_max="60", n_quad="128",
        outer="+",
    ),
    "Two-Channel Coupled Scatterer (L=2)": dict(
        L="2", a="1.0, 0.6", N="-100", M="100",
        j_sites="0", V_sites="[[[0.40, 0.25j], [-0.25j, -0.20]]]",
        interval_lo="-0.9", interval_hi="0.9",
        E0="0.0", sigma_E="0.20",
        sigma_mode="right", n_init="0",
        n_t="140", t_min="0", t_max="60", n_quad="128",
        outer="+",
    ),
    "Slow Packet — near band edge": dict(
        L="1", a="1.0", N="-80", M="80",
        j_sites="", V_sites="[]",
        interval_lo="-1.95", interval_hi="-1.40",
        E0="-1.65", sigma_E="0.12",
        sigma_mode="right", n_init="0",
        n_t="120", t_min="0", t_max="80", n_quad="80",
        outer="+",
    ),
    "Schober 1 — two-channel window": dict(
        L="2", a="2, 1", N="-10", M="10",
        j_sites="0", V_sites="[[[0, 1], [1, 0]]]",
        interval_lo="-0.7", interval_hi="0.6",
        E0="0.5", sigma_E="0.1",
        sigma_mode="balanced", n_init="0",
        n_t="160", t_min="-8", t_max="8", n_quad="200",
        outer="+",
    ),
    "Schober 2 — two-channel + barrier": dict(
        L="2", a="2, 1", N="-100", M="100",
        j_sites="0, 40", V_sites="[[[0, 1], [1, 0]], [[5, 0], [0, -3]]]",
        interval_lo="-0.7", interval_hi="0.6",
        E0="0.5", sigma_E="0.1",
        sigma_mode="balanced", n_init="0",
        n_t="200", t_min="-40", t_max="40", n_quad="200",
        outer="+",
    ),
    "Custom — edit fields below": None,
}


PRESET_DESCRIPTIONS: dict[str, str] = {
    "Free Gaussian Wave Packet":
        "A Gaussian wave packet propagates freely on the lattice. "
        "It drifts at group velocity 2a while spreading dispersively.",
    "Single Barrier — partial reflection":
        "Incoming pulse meets a positive site potential V(0)=0.6. "
        "Part reflects, part transmits — watch the splitting in real time.",
    "Single Well — attractive site":
        "Attractive potential V(0)=−0.8. The well briefly enhances the "
        "wave amplitude at the site; most of the packet still transmits.",
    "Double Barrier — resonant cavity":
        "Two barriers at j=±6 form a Fabry–Pérot cavity. The packet rings "
        "between them, building amplitude before slowly leaking out.",
    "Strong Wall — near-total reflection":
        "V(0)=3.5 acts as an almost-perfect mirror. The packet bounces back "
        "with very little transmission.",
    "Weak Barrier — small kick":
        "V(0)=0.12 barely perturbs the packet. Most amplitude transmits "
        "with a tiny reflected component you can spot in the waterfall.",
    "Wide Barrier — tunneling":
        "Four adjacent barriers V=0.45 at j∈{−3,−1,1,3}. The packet "
        "tunnels through with exponential suppression on the far side.",
    "Random Lattice (L=1)":
        "Five potential sites with mixed signs scatter the packet into "
        "a complex multi-peak speckle pattern.",
    "Two-Channel Free (L=2)":
        "Two propagation channels with a₁=1.0, a₂=0.6. The channels "
        "move at different group velocities — they visibly separate.",
    "Two-Channel Coupled Scatterer (L=2)":
        "A Hermitian off-diagonal V at j=0 mixes the two channels. The "
        "two arrival times become entangled at the scatterer.",
    "Slow Packet — near band edge":
        "Packet centered at E₀=−1.65, near the band edge −2a. Low group "
        "velocity gives a slow, narrow drift — the waterfall looks vertical.",
    "Schober 1 — two-channel window":
        "Schober's test config: L=2 (a=2,1), antidiagonal V(0)=[[0,1],[1,0]] "
        "mixes the channels. f is a fixed window — channel 1 on [0.4,0.6] (both "
        "σ), channel 2 on [−0.7,−0.5] (σ=+ only) — integrated per-window "
        "(spectral quadrature). Time runs from negative t: the packet converges, "
        "scatters, departs. Editing any field switches back to a Gaussian.",
    "Schober 2 — two-channel + barrier":
        "Schober's larger config: adds a diagonal barrier V(40)=[[5,0],[0,−3]] at "
        "j=40 on a wide lattice, so the windowed two-channel packet scatters off "
        "both sites. Same fixed window f and per-window quadrature as Schober 1; "
        "time again runs from negative t (converge → scatter → depart).",
    "Custom — edit fields below":
        "Edit any field below to customise. The dropdown auto-switches "
        "to Custom whenever you hand-edit.",
}


# Sigma-mode choices for the Gaussian f: combo label -> (h_plus, h_minus)
# weights on the two σ channels (memo B.1). Balanced (1,1) gives Schober's
# standing packet; right / left select a single propagation direction.
SIGMA_MODES: dict[str, tuple[float, float]] = {
    "balanced (1,1)": (1.0, 1.0),
    "right (1,0)":    (1.0, 0.0),
    "left (0,1)":     (0.0, 1.0),
}


def min_nquad(N, M, t_min, t_max, lo, hi, a_list) -> int:
    """Smallest safe MaxwellSpec.n_quad for a single-interval run.

    Gauss-Legendre must resolve the integrand phase e^{-i(n*theta(E) + t*E)}:
    total phase variation PV = n_max*Dtheta + t_amp*(hi-lo) needs about one
    node per pi (Nyquist), plus margin. Measured aliasing thresholds sit at
    0.80-0.95*PV/pi across twelve configurations, so this bound carries >=20%
    headroom. Below it a phantom mirror packet appears and the total mass
    roughly doubles -- invisible in the t=0 frame, obvious in the waterfall.
    """
    n_max = max(abs(int(N)), abs(int(M)))
    t_amp = max(abs(float(t_min)), abs(float(t_max)))
    dtheta = 0.0
    for a_l in a_list:
        c_lo = float(np.clip(lo / (2.0 * a_l), -1.0, 1.0))
        c_hi = float(np.clip(hi / (2.0 * a_l), -1.0, 1.0))
        dtheta = max(dtheta, abs(float(np.arccos(c_lo) - np.arccos(c_hi))))
    return max(8, int(np.ceil((n_max * dtheta + t_amp * (hi - lo)) / np.pi)) + 8)


# Schober's window presets use a step-function f (indicator on [c, d]) with per-
# channel / per-sigma amplitudes, which the Gaussian form fields cannot express.
# _build_spec uses these directly (keyed by preset name) instead of the form f.
def _schober_window_f(E):
    """f_{1,+/-}=1 on [0.4,0.6]; f_{2,+}=1 on [-0.7,-0.5]; f_{2,-}=0. (L=2)"""
    E = np.asarray(E, dtype=float)
    out = np.zeros((E.size, 2, 2), dtype=complex)
    ch1 = (E >= 0.4) & (E <= 0.6)
    ch2 = (E >= -0.7) & (E <= -0.5)
    out[ch1, 0, 0] = 1.0   # f_{1,+}
    out[ch1, 0, 1] = 1.0   # f_{1,-}
    out[ch2, 1, 0] = 1.0   # f_{2,+}
    return out


PRESET_F = {
    "Schober 1 — two-channel window": _schober_window_f,
    "Schober 2 — two-channel + barrier": _schober_window_f,
}


# Energy windows matching _schober_window_f's support. _build_spec passes these
# as MaxwellSpec.E_segments so quadrature runs per-window (spectrally convergent
# for step-function f) instead of one rule across all of `interval`.
PRESET_SEGMENTS = {
    "Schober 1 — two-channel window": [(-0.7, -0.5), (0.4, 0.6)],
    "Schober 2 — two-channel + barrier": [(-0.7, -0.5), (0.4, 0.6)],
}


# =====================================================================
# Worker
# =====================================================================
class MaxwellWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, float)
    error = pyqtSignal(str)

    def __init__(self, spec: MaxwellSpec):
        super().__init__()
        self.spec = spec

    def run(self):
        try:
            frames, gmax = maxwell_to_frames(
                self.spec, progress_callback=self.progress.emit
            )
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")
            self.finished.emit([], 0.0)
            return
        self.finished.emit(frames, float(gmax))


# =====================================================================
# Export worker
# =====================================================================
class ExportWorker(QThread):
    """Render the computed frames to an .mp4 (ffmpeg) or .gif (Pillow) file.

    Runs entirely off the GUI thread, so it builds its OWN Agg figure and
    never touches the MainWindow canvas / axes — sharing matplotlib artists
    across threads is exactly what crashed the old export. Only plain data
    (lists, arrays, floats, module colour strings) crosses the boundary.
    """

    progress = pyqtSignal(int)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, frames, lattice, times, j_sites, gmax, ylim,
                 path, use_ffmpeg):
        super().__init__()
        self.frames = frames
        self.lattice = np.asarray(lattice)
        self.times = np.asarray(times, dtype=float)
        self.j_sites = np.asarray(j_sites, dtype=int)
        self.gmax = float(gmax)
        self.ylim = float(ylim)
        self.path = path
        self.use_ffmpeg = use_ffmpeg

    def run(self):
        try:
            fig = Figure(figsize=(12.8, 7.2), dpi=100)
            FigureCanvasAgg(fig)  # attach a private Agg canvas, never the GUI's
            fig.patch.set_facecolor(BG_DEEP)
            gs = fig.add_gridspec(
                2, 1, height_ratios=[1.0, 1.55], hspace=0.10,
                left=0.075, right=0.965, top=0.945, bottom=0.085,
            )
            ax_line = fig.add_subplot(gs[0])
            ax_water = fig.add_subplot(gs[1], sharex=ax_line)
            self._style_axes(ax_line, ax_water)

            # Static spacetime waterfall + moving current-time line
            psi = np.array([fr[0] for fr in self.frames])  # (n_t, n_sites)
            ax_water.imshow(
                psi,
                aspect="auto",
                origin="lower",
                extent=[
                    float(self.lattice[0]) - 0.5,
                    float(self.lattice[-1]) + 0.5,
                    float(self.times[0]),
                    float(self.times[-1]),
                ],
                cmap="plasma",
                interpolation="bilinear",
                vmin=0.0,
                vmax=max(self.gmax, 1e-12),
            )
            for jk in self.j_sites:
                ax_water.axvline(jk, color="white", alpha=0.30, lw=0.8, zorder=5)
                ax_line.axvline(jk, color=ACCENT, alpha=0.42, lw=0.9, zorder=2)
            time_line = ax_water.axhline(
                float(self.times[0]), color="white", alpha=0.85, lw=1.4, zorder=10,
            )
            time_line.set_path_effects([
                pe.Stroke(linewidth=4, foreground="white", alpha=0.22),
                pe.Normal(),
            ])
            ax_water.set_xlim(self.lattice[0], self.lattice[-1])
            ax_water.set_ylim(self.times[0], self.times[-1])

            # Animated psi curve on top
            curve0 = self.frames[0][0]
            (line,) = ax_line.plot(
                self.lattice, curve0,
                lw=2.0, color=ACCENT2, solid_capstyle="round",
            )
            line.set_path_effects([
                pe.Stroke(linewidth=6, foreground=ACCENT2, alpha=0.28),
                pe.Normal(),
            ])
            fill = ax_line.fill_between(
                self.lattice, 0, curve0, color=ACCENT2, alpha=0.18,
            )
            ax_line.set_xlim(self.lattice[0], self.lattice[-1])
            ax_line.set_ylim(0, self.ylim)

            if self.use_ffmpeg:
                writer = animation.FFMpegWriter(fps=30, bitrate=4000)
            else:
                writer = animation.PillowWriter(fps=30)

            n_frames = len(self.frames)
            with writer.saving(fig, self.path, dpi=100):
                for i, frame in enumerate(self.frames):
                    curve = frame[0]
                    line.set_ydata(curve)
                    try:
                        fill.remove()
                    except Exception:
                        pass
                    fill = ax_line.fill_between(
                        self.lattice, 0, curve, color=ACCENT2, alpha=0.18,
                    )
                    t_now = float(self.times[i])
                    time_line.set_ydata([t_now, t_now])
                    ax_line.set_title(f"t = {t_now:.3f}", fontsize=11)
                    writer.grab_frame()
                    self.progress.emit(int(round(100 * (i + 1) / n_frames)))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(self.path)

    @staticmethod
    def _style_axes(ax_line, ax_water):
        """Replicate the MainWindow axis styling on the worker's own axes."""
        for ax in (ax_line, ax_water):
            ax.set_facecolor(BG_PLOT)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4)
            ax.xaxis.label.set_color(TEXT_DIM)
            ax.yaxis.label.set_color(TEXT_DIM)
        ax_line.title.set_color(TEXT_PRIM)
        ax_line.set_ylabel("ψ(n, t)", labelpad=6)
        ax_line.grid(True, color=BORDER, alpha=0.32, linewidth=0.6)
        ax_line.tick_params(labelbottom=False)
        ax_water.set_xlabel("lattice site n", labelpad=6)
        ax_water.set_ylabel("time t", labelpad=6)
        ax_water.set_title("spacetime  ψ(n, t)", fontsize=10, loc="left",
                           color=TEXT_FAINT, pad=4)


# =====================================================================
# MainWindow
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maxwell Algorithm")
        self.setStyleSheet(STYLESHEET)
        self._silent = True

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

        # ---------------- Sidebar ----------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(380)
        sidebar.setMaximumWidth(460)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(26, 26, 26, 22)
        side.setSpacing(0)

        title = QLabel("Maxwell Algorithm")
        title.setObjectName("header")
        side.addWidget(title)
        sub = QLabel("LATTICE  SCATTERING  WAVE  PACKET")
        sub.setObjectName("subheader")
        side.addWidget(sub)

        side.addSpacing(22)
        side.addWidget(self._section("Preset"))
        side.addSpacing(6)
        self.preset_combo = QComboBox()
        for name in PRESETS:
            self.preset_combo.addItem(name)
        side.addWidget(self.preset_combo)

        side.addSpacing(8)
        self.preset_desc = QLabel("")
        self.preset_desc.setObjectName("description")
        self.preset_desc.setWordWrap(True)
        self.preset_desc.setMinimumHeight(56)
        side.addWidget(self.preset_desc)

        side.addSpacing(6)
        side.addWidget(self._section("Configuration"))
        side.addSpacing(6)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(7)
        form.setContentsMargins(0, 0, 0, 0)
        side.addLayout(form)

        self.in_L       = QLineEdit()
        self.in_a       = QLineEdit()
        self.in_N       = QLineEdit()
        self.in_M       = QLineEdit()
        self.in_j_sites = QLineEdit()
        self.in_V_sites = QLineEdit()
        self.in_a_lo    = QLineEdit()
        self.in_b_hi    = QLineEdit()
        self.in_E0      = QLineEdit()
        self.in_sigma_E = QLineEdit()
        self.in_sigma_mode = QComboBox()
        self.in_sigma_mode.addItems(list(SIGMA_MODES))
        self.in_n_init  = QLineEdit()
        self.in_n_t     = QLineEdit()
        self.in_t_min   = QLineEdit()
        self.in_t_max   = QLineEdit()
        self.in_n_quad  = QLineEdit()
        self.in_outer   = QComboBox()
        self.in_outer.addItems(["+", "−"])

        form.addRow("Channels  L",         self.in_L)
        form.addRow("Diagonal  a",         self.in_a)
        form.addRow("Lattice min  N",      self.in_N)
        form.addRow("Lattice max  M",      self.in_M)
        form.addRow("Potential sites  jₖ", self.in_j_sites)
        form.addRow("V matrices",          self.in_V_sites)
        form.addRow("Interval  lower",     self.in_a_lo)
        form.addRow("Interval  upper",     self.in_b_hi)
        form.addRow("Wave packet  E₀",     self.in_E0)
        form.addRow("Wave packet  σ_E",    self.in_sigma_E)
        form.addRow("Sigma mode",          self.in_sigma_mode)
        form.addRow("Start site  n_init",  self.in_n_init)
        form.addRow("Outer sign",          self.in_outer)
        form.addRow("Time frames  n_t",    self.in_n_t)
        form.addRow("Time start  t_min",   self.in_t_min)
        form.addRow("Time horizon  t_max", self.in_t_max)
        form.addRow("Quadrature  n_quad",  self.in_n_quad)

        side.addSpacing(18)
        side.addWidget(self._section("Status"))
        side.addSpacing(8)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        side.addWidget(self.progress_bar)
        side.addSpacing(4)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(38)
        side.addWidget(self.status_label)

        side.addSpacing(8)
        self.run_button = QPushButton("▶   Compute & Animate")
        self.run_button.clicked.connect(self.run_compute)
        side.addWidget(self.run_button)

        side.addStretch()
        splitter.addWidget(sidebar)

        # ---------------- Plot area (right) ----------------
        right = QFrame()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        # Figure with two stacked subplots: line + waterfall
        self.figure = Figure(figsize=(10, 7.5))
        self.figure.patch.set_facecolor(BG_DEEP)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {BG_DEEP};")
        gs = self.figure.add_gridspec(
            2, 1, height_ratios=[1.0, 1.55], hspace=0.10,
            left=0.075, right=0.965, top=0.945, bottom=0.085,
        )
        self.ax_line  = self.figure.add_subplot(gs[0])
        self.ax_water = self.figure.add_subplot(gs[1], sharex=self.ax_line)
        self._style_line_axes()
        self._style_water_axes()
        self.ax_line.tick_params(labelbottom=False)
        self.ax_line.set_title("press   ▶  Compute & Animate", fontsize=11)
        right_v.addWidget(self.canvas, stretch=1)

        # Control bar: play/pause | scrubber | timecode | speed
        controlbar = QFrame()
        controlbar.setObjectName("controlbar")
        cb = QHBoxLayout(controlbar)
        cb.setContentsMargins(20, 14, 20, 14)
        cb.setSpacing(14)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("icon")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        cb.addWidget(self.play_btn)

        self.restart_btn = QPushButton("⏮")
        self.restart_btn.setObjectName("icon")
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(self._restart)
        cb.addWidget(self.restart_btn)

        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 0)
        self.scrubber.setEnabled(False)
        self.scrubber.valueChanged.connect(self._scrubbed)
        cb.addWidget(self.scrubber, stretch=1)

        self.timecode = QLabel("t = 0.00   ·   0 / 0")
        self.timecode.setObjectName("timecode")
        cb.addWidget(self.timecode)

        speed_lbl = QLabel("speed")
        speed_lbl.setObjectName("statlbl")
        cb.addWidget(speed_lbl)
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25×", "0.5×", "1×", "2×", "4×"])
        self.speed_combo.setCurrentText("1×")
        self.speed_combo.setMaximumWidth(78)
        self.speed_combo.currentTextChanged.connect(self._speed_changed)
        cb.addWidget(self.speed_combo)

        self.export_btn = QPushButton("⬇  Export")
        self.export_btn.setObjectName("icon")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_clicked)
        cb.addWidget(self.export_btn)

        right_v.addWidget(controlbar)

        # Stats strip below the controls
        stats = QFrame()
        stats.setObjectName("controlbar")
        sl = QHBoxLayout(stats)
        sl.setContentsMargins(20, 12, 20, 12)
        sl.setSpacing(28)

        def stat_block(label):
            wrap = QFrame()
            v = QVBoxLayout(wrap)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setObjectName("statlbl")
            big = QLabel("—")
            big.setObjectName("statbig")
            v.addWidget(lbl)
            v.addWidget(big)
            return wrap, big

        block_max,  self.stat_max  = stat_block("max ψ")
        block_norm, self.stat_norm = stat_block("∑ψ at t")
        block_peak, self.stat_peak = stat_block("peak n")
        block_t,    self.stat_t    = stat_block("time t")

        sl.addWidget(block_max)
        sl.addWidget(block_norm)
        sl.addWidget(block_peak)
        sl.addWidget(block_t)
        sl.addStretch()

        right_v.addWidget(stats)

        splitter.addWidget(right)
        splitter.setSizes([420, 1180])

        # ---------------- Animation state ----------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.frames: list[list[np.ndarray]] | None = None
        self.frame_idx = 0
        self.lattice = np.array([])
        self.times = np.array([])
        self.ylim = 1.0
        self.gmax = 0.0
        self.line = None
        self.fill = None
        self.water_image = None
        self.water_time_line = None
        self.line_potential_lines = []
        self.water_potential_lines = []
        self._j_sites_for_render = np.array([], dtype=int)
        self._nquad_warning = ""

        # ---------------- Worker lifecycle ----------------
        # Only the worker tagged with the current token is allowed to update
        # the UI; older workers are silently dismissed when their `finished`
        # signal eventually fires. _inflight_workers keeps Python references
        # to running QThreads (compute AND export) alive until they exit, so
        # Qt doesn't tear them down mid-run.
        self._compute_token = 0
        self.worker: MaxwellWorker | None = None
        self._inflight_workers: list[QThread] = []

        # ---------------- Wire signals AFTER UI is built ----------------
        self.preset_combo.currentTextChanged.connect(self._preset_changed)
        for inp in (self.in_L, self.in_a, self.in_N, self.in_M,
                    self.in_j_sites, self.in_V_sites, self.in_a_lo, self.in_b_hi,
                    self.in_E0, self.in_sigma_E, self.in_n_init, self.in_n_t,
                    self.in_t_min, self.in_t_max, self.in_n_quad):
            inp.textChanged.connect(self._field_edited)
        self.in_outer.currentTextChanged.connect(self._field_edited)
        self.in_sigma_mode.currentTextChanged.connect(self._field_edited)

        self._preset_changed(self.preset_combo.currentText())
        self._silent = False

    # ----------------------------------------------------------------- helpers
    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setObjectName("section")
        return lbl

    def _style_line_axes(self):
        ax = self.ax_line
        ax.set_facecolor(BG_PLOT)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        ax.title.set_color(TEXT_PRIM)
        ax.set_ylabel("ψ(n, t)", labelpad=6)
        ax.grid(True, color=BORDER, alpha=0.32, linewidth=0.6)

    def _style_water_axes(self):
        ax = self.ax_water
        ax.set_facecolor(BG_PLOT)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        ax.title.set_color(TEXT_DIM)
        ax.set_xlabel("lattice site n", labelpad=6)
        ax.set_ylabel("time t", labelpad=6)
        ax.set_title("spacetime  ψ(n, t)", fontsize=10, loc="left",
                     color=TEXT_FAINT, pad=4)

    # ----------------------------------------------------------------- presets
    def _preset_changed(self, name: str):
        cfg = PRESETS.get(name)
        self.preset_desc.setText(PRESET_DESCRIPTIONS.get(name, ""))
        if cfg is None:
            return
        self._silent = True
        self.in_L.setText(cfg["L"]);            self.in_a.setText(cfg["a"])
        self.in_N.setText(cfg["N"]);            self.in_M.setText(cfg["M"])
        self.in_j_sites.setText(cfg["j_sites"]);self.in_V_sites.setText(cfg["V_sites"])
        self.in_a_lo.setText(cfg["interval_lo"]);self.in_b_hi.setText(cfg["interval_hi"])
        self.in_E0.setText(cfg["E0"]);          self.in_sigma_E.setText(cfg["sigma_E"])
        # presets store the short mode name; match the full combo label
        self.in_sigma_mode.setCurrentText(
            next(k for k in SIGMA_MODES if k.startswith(cfg["sigma_mode"]))
        )
        self.in_n_init.setText(cfg["n_init"])
        self.in_n_t.setText(cfg["n_t"]);        self.in_t_min.setText(cfg["t_min"])
        self.in_t_max.setText(cfg["t_max"]);    self.in_n_quad.setText(cfg["n_quad"])
        self.in_outer.setCurrentText("+" if cfg["outer"] == "+" else "−")
        self._silent = False
        self.status_label.setText("")

    def _field_edited(self, *_):
        if self._silent:
            return
        custom = "Custom — edit fields below"
        if self.preset_combo.currentText() != custom:
            self._silent = True
            self.preset_combo.setCurrentText(custom)
            self._silent = False

    # ----------------------------------------------------------------- compute
    def run_compute(self):
        # Build & validate the spec FIRST. If this fails we want to keep the
        # current animation visible so the user can fix the typo without
        # losing context.
        try:
            spec = self._build_spec()
        except Exception as exc:
            self.status_label.setText(f"Input error:  {exc}")
            return

        # Advisory aliasing check (single-interval runs only; the per-window
        # Schober presets use narrow segments and are far below threshold).
        # Under-resolved quadrature folds a phantom mirror packet into psi --
        # the t=0 frame looks fine, the waterfall doubles its mass.
        self._nquad_warning = ""
        if spec.E_segments is None:
            recommended = min_nquad(
                spec.N, spec.M, float(spec.times[0]), float(spec.times[-1]),
                spec.interval[0], spec.interval[1], spec.a,
            )
            if spec.n_quad < recommended:
                self._nquad_warning = (
                    f"   ⚠ n_quad={spec.n_quad} may alias "
                    f"(phantom mirror packet); recommend ≥ {recommended}"
                )

        # ---- tear down any in-flight playback / compute ----
        self.timer.stop()
        self.play_btn.setText("▶")
        self.frames = None
        self.frame_idx = 0

        # Bump the dispatch token so any older worker that finishes later is
        # ignored. Disconnect the previous worker's signals defensively so
        # they can't drive the UI during this new run.
        self._compute_token += 1
        my_token = self._compute_token
        if self.worker is not None:
            for sig in (self.worker.progress, self.worker.finished, self.worker.error):
                try:
                    sig.disconnect()
                except (TypeError, RuntimeError):
                    pass
        # Drop references to workers that have already completed.
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]

        # ---- prepare new run ----
        self.lattice = spec.lattice()
        self.times = spec.times
        self._j_sites_for_render = np.asarray(spec.j_sites, dtype=int)
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.play_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.scrubber.setEnabled(False)
        self.scrubber.blockSignals(True)
        self.scrubber.setRange(0, 0)
        self.scrubber.setValue(0)
        self.scrubber.blockSignals(False)
        self.status_label.setText("Computing…" + self._nquad_warning)
        self.line = None
        self.fill = None
        self.water_image = None
        self.water_time_line = None
        self.line_potential_lines = []
        self.water_potential_lines = []
        self.ax_line.clear()
        self.ax_water.clear()
        self._style_line_axes()
        self._style_water_axes()
        self.ax_line.tick_params(labelbottom=False)
        self.ax_line.set_title("Computing…", fontsize=11)
        self.canvas.draw()
        self.timecode.setText("t = 0.000   ·   0 / 0")
        for s in (self.stat_max, self.stat_norm, self.stat_peak, self.stat_t):
            s.setText("—")

        # ---- spawn worker ----
        worker = MaxwellWorker(spec)
        self.worker = worker
        self._inflight_workers.append(worker)
        worker.progress.connect(
            lambda pct, t=my_token: self._on_progress(pct, t)
        )
        worker.finished.connect(
            lambda frames, gmax, t=my_token: self._on_finished(frames, gmax, t)
        )
        worker.error.connect(
            lambda msg, t=my_token: self._on_error(msg, t)
        )
        worker.start()

    # ----------------------------------------------------------------- token-guarded slots
    def _on_progress(self, pct: int, token: int):
        if token != self._compute_token:
            return
        self.progress_bar.setValue(int(pct))

    def _on_finished(self, frames, gmax, token: int):
        if token != self._compute_token:
            return  # a stale worker; result discarded
        self.run_button.setEnabled(True)
        # Drop completed workers from our keep-alive list.
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        # Worker emits finished([], 0.0) on the error path right after error.
        # In that case _on_error has already set the status; don't overwrite.
        if frames:
            self.on_finished(frames, gmax)

    def _on_error(self, msg: str, token: int):
        if token != self._compute_token:
            return
        self.run_button.setEnabled(True)
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        self.status_label.setText(f"Error:  {msg}")

    def on_finished(self, frames, gmax):
        if not frames:
            self.status_label.setText("No frames produced.")
            return
        self.frames = frames
        self.gmax = gmax
        self.ylim = (gmax * 1.10) if gmax > 0 else 1.0
        self.frame_idx = 0
        self.line = None
        self.fill = None
        self.progress_bar.setValue(100)
        self.status_label.setText(
            f"{len(frames)} frames · {self.lattice.size} sites · "
            f"max ψ = {gmax:.4g}" + self._nquad_warning
        )
        self.stat_max.setText(f"{gmax:.4f}")

        # Render the spacetime waterfall once
        self._render_waterfall()

        # Enable transport controls
        self.scrubber.blockSignals(True)
        self.scrubber.setRange(0, len(frames) - 1)
        self.scrubber.setValue(0)
        self.scrubber.blockSignals(False)
        self.scrubber.setEnabled(True)
        self.play_btn.setEnabled(True)
        self.restart_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # Auto-play
        self.play_btn.setText("⏸")
        self.timer.start(self._timer_ms())

    # ----------------------------------------------------------------- transport
    def _toggle_play(self):
        if self.frames is None:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶")
        else:
            if self.frame_idx >= len(self.frames):
                self.frame_idx = 0
            self.timer.start(self._timer_ms())
            self.play_btn.setText("⏸")

    def _restart(self):
        if self.frames is None:
            return
        self.frame_idx = 0
        self._render_frame(0)
        self._set_scrubber(0)
        if not self.timer.isActive():
            self.timer.start(self._timer_ms())
            self.play_btn.setText("⏸")

    def _scrubbed(self, value: int):
        if self.frames is None or self._silent:
            return
        self.timer.stop()
        self.play_btn.setText("▶")
        self.frame_idx = value
        self._render_frame(value)

    def _set_scrubber(self, idx: int):
        self.scrubber.blockSignals(True)
        self.scrubber.setValue(idx)
        self.scrubber.blockSignals(False)

    def _speed_changed(self, _text: str):
        if self.timer.isActive():
            self.timer.start(self._timer_ms())

    def _timer_ms(self) -> int:
        try:
            mult = float(self.speed_combo.currentText().replace("×", ""))
        except ValueError:
            mult = 1.0
        return max(4, int(round(33 / mult)))

    # ----------------------------------------------------------------- export
    def _export_clicked(self):
        if self.frames is None:
            return
        have_ffmpeg = shutil.which("ffmpeg") is not None
        if have_ffmpeg:
            default_name, name_filter = "maxwell.mp4", "MP4 video (*.mp4)"
        else:
            default_name, name_filter = "maxwell.gif", "GIF animation (*.gif)"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export animation", default_name, name_filter
        )
        if not path:
            return

        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Exporting…")

        worker = ExportWorker(
            frames=self.frames,
            lattice=self.lattice,
            times=self.times,
            j_sites=self._j_sites_for_render,
            gmax=self.gmax,
            ylim=self.ylim,
            path=path,
            use_ffmpeg=have_ffmpeg,
        )
        self._inflight_workers.append(worker)
        worker.progress.connect(self.progress_bar.setValue)
        worker.done.connect(self._on_export_done)
        worker.failed.connect(self._on_export_failed)
        worker.start()

    def _on_export_done(self, path: str):
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Export saved:  {path}")
        # Only re-enable if there is still an animation to export (a compute
        # may have started, and cleared frames, while we were writing).
        self.export_btn.setEnabled(self.frames is not None)

    def _on_export_failed(self, msg: str):
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        self.status_label.setText(f"Export failed:  {msg}")
        self.export_btn.setEnabled(self.frames is not None)

    # ----------------------------------------------------------------- rendering
    def _render_waterfall(self):
        ax = self.ax_water
        ax.clear()
        self._style_water_axes()
        psi = np.array([fr[0] for fr in self.frames])  # (n_t, n_sites)

        self.water_image = ax.imshow(
            psi,
            aspect="auto",
            origin="lower",
            extent=[
                float(self.lattice[0]) - 0.5,
                float(self.lattice[-1]) + 0.5,
                float(self.times[0]),
                float(self.times[-1]),
            ],
            cmap="plasma",
            interpolation="bilinear",
            vmin=0.0,
            vmax=max(self.gmax, 1e-12),
        )

        # Potential-site markers on both panels
        self.water_potential_lines = []
        for jk in self._j_sites_for_render:
            ln = ax.axvline(jk, color="white", alpha=0.30, lw=0.8, zorder=5)
            self.water_potential_lines.append(ln)

        # Current-time horizontal line (white with subtle glow)
        t0 = float(self.times[0])
        self.water_time_line = ax.axhline(
            t0, color="white", alpha=0.85, lw=1.4, zorder=10,
        )
        self.water_time_line.set_path_effects([
            pe.Stroke(linewidth=4, foreground="white", alpha=0.22),
            pe.Normal(),
        ])

        ax.set_xlim(self.lattice[0], self.lattice[-1])
        ax.set_ylim(self.times[0], self.times[-1])

    def _render_frame(self, idx: int):
        """Render frame `idx` without advancing."""
        if self.frames is None or idx < 0 or idx >= len(self.frames):
            return
        curve = self.frames[idx][0]

        if self.line is None:
            self.ax_line.clear()
            self._style_line_axes()
            self.ax_line.tick_params(labelbottom=False)
            (self.line,) = self.ax_line.plot(
                self.lattice, curve,
                lw=2.0, color=ACCENT2, solid_capstyle="round",
            )
            self.line.set_path_effects([
                pe.Stroke(linewidth=6, foreground=ACCENT2, alpha=0.28),
                pe.Normal(),
            ])
            self.fill = self.ax_line.fill_between(
                self.lattice, 0, curve, color=ACCENT2, alpha=0.18,
            )
            # potential markers
            self.line_potential_lines = []
            for jk in self._j_sites_for_render:
                ln = self.ax_line.axvline(
                    jk, color=ACCENT, alpha=0.42, lw=0.9, zorder=2,
                )
                self.line_potential_lines.append(ln)
            self.ax_line.set_xlim(self.lattice[0], self.lattice[-1])
            self.ax_line.set_ylim(0, self.ylim)
        else:
            self.line.set_ydata(curve)
            try:
                self.fill.remove()
            except Exception:
                pass
            self.fill = self.ax_line.fill_between(
                self.lattice, 0, curve, color=ACCENT2, alpha=0.18,
            )

        t_now = float(self.times[idx])
        if self.water_time_line is not None:
            self.water_time_line.set_ydata([t_now, t_now])

        # Top-right title with timecode
        self.ax_line.set_title("", fontsize=11)

        # Stats strip
        self.timecode.setText(f"t = {t_now:.3f}   ·   {idx + 1} / {len(self.frames)}")
        self.stat_t.setText(f"{t_now:.3f}")
        peak_idx = int(np.argmax(curve))
        self.stat_peak.setText(f"{int(self.lattice[peak_idx])}")
        self.stat_norm.setText(f"{float(np.sum(curve)):.3f}")

        self.canvas.draw_idle()

    def tick(self):
        try:
            if not self.frames:
                self.timer.stop()
                self.play_btn.setText("▶")
                return
            if self.frame_idx >= len(self.frames):
                self.timer.stop()
                self.play_btn.setText("▶")
                return
            self._render_frame(self.frame_idx)
            self._set_scrubber(self.frame_idx)
            self.frame_idx += 1
        except Exception as exc:
            # A render error (e.g. stale matplotlib artists after a torn-down
            # axis) should pause playback gracefully, not silently kill the
            # timer for the rest of the session.
            self.timer.stop()
            self.play_btn.setText("▶")
            self.status_label.setText(f"Render paused:  {exc}")

    # ----------------------------------------------------------------- shutdown
    def closeEvent(self, event):
        # Stop animation and let any running worker finish briefly so Qt
        # doesn't print "QThread destroyed while still running".
        self.timer.stop()
        self._compute_token += 1  # invalidate any pending callbacks
        for w in list(self._inflight_workers):
            try:
                if w.isRunning():
                    w.wait(1500)
            except RuntimeError:
                pass
        self._inflight_workers.clear()
        super().closeEvent(event)

    # ----------------------------------------------------------------- spec
    def _build_spec(self) -> MaxwellSpec:
        L = int(self.in_L.text())
        a = np.array(
            [float(x) for x in self.in_a.text().split(",") if x.strip()],
            dtype=float,
        )
        if a.size != L:
            raise ValueError(f"need {L} entries in 'a', got {a.size}")
        N = int(self.in_N.text())
        M = int(self.in_M.text())

        j_text = self.in_j_sites.text().strip()
        if j_text:
            j_sites = np.array([int(x) for x in j_text.split(",")], dtype=int)
        else:
            j_sites = np.array([], dtype=int)

        v_text = self.in_V_sites.text().strip() or "[]"
        v_raw = eval(
            v_text,
            {"__builtins__": {}},
            {"list": list, "True": True, "False": False, "None": None},
        )
        if len(v_raw) == 0:
            V_sites = np.zeros((0, L, L), dtype=complex)
        else:
            V_sites = np.asarray(v_raw, dtype=complex)
            if V_sites.shape != (j_sites.size, L, L):
                raise ValueError(
                    f"V_sites must have shape ({j_sites.size}, {L}, {L}); "
                    f"got {V_sites.shape}"
                )

        a_lo    = float(self.in_a_lo.text())
        b_hi    = float(self.in_b_hi.text())
        E0      = float(self.in_E0.text())
        sigma_E = float(self.in_sigma_E.text())
        n_init  = int(self.in_n_init.text())
        n_t     = int(self.in_n_t.text())
        t_min   = float(self.in_t_min.text())
        t_max   = float(self.in_t_max.text())
        n_quad  = int(self.in_n_quad.text())
        outer   = +1 if self.in_outer.currentText() == "+" else -1
        h_plus, h_minus = SIGMA_MODES[self.in_sigma_mode.currentText()]
        if t_min >= t_max:
            raise ValueError("need t_min < t_max")

        # Schober window presets carry a fixed step-function f (keyed by preset
        # name); every other preset / Custom builds the Gaussian f from the form.
        window_f = PRESET_F.get(self.preset_combo.currentText())
        if window_f is not None:
            f = window_f
        else:
            # Gaussian f (memo B.1): sigma-mode weights h± scale the two σ
            # channels, and the θ(E) phase parks the packet at lattice site
            # n_init at t=0. Single channel l₀=0; other channels stay zero.
            a0 = float(a[0])

            def f(E):
                E = np.asarray(E, dtype=float)
                env = np.exp(-((E - E0) ** 2) / (2.0 * sigma_E ** 2))
                theta = np.arccos(np.clip(E / (2.0 * a0), -1.0, 1.0))
                out = np.zeros((E.size, L, 2), dtype=complex)
                out[:, 0, 0] = h_plus  * env * np.exp(+1j * n_init * theta)
                out[:, 0, 1] = h_minus * env * np.exp(-1j * n_init * theta)
                return out

        spec = MaxwellSpec(
            L=L, a=a, N=N, M=M,
            j_sites=j_sites, V_sites=V_sites,
            interval=(a_lo, b_hi),
            f=f,
            times=np.linspace(t_min, t_max, n_t),
            n_quad=n_quad,
            E_segments=PRESET_SEGMENTS.get(self.preset_combo.currentText()),
            outer_sign=outer,
        )
        spec.validate()
        return spec
