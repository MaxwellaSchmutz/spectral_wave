"""Maxwell algorithm viewer — interactive dashboard.

Sidebar: preset library + form for every MaxwellSpec field.
Right: live psi(n, t) curve, scrub/play/speed controls, and a spacetime
waterfall heatmap of psi over the full time horizon.
"""

from __future__ import annotations


import numpy as np
from PyQt6.QtCore import (
    QEvent, QObject, QSize, Qt, QThread, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter
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
    QScrollArea,
    QSizePolicy,
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

from matplotlib import rcParams as _rc

from spectral.maxwell import MaxwellSpec, maxwell_to_frames
from spectral.maxwell import presets as _presets

_rc.update({
    "font.family":     "sans-serif",
    "font.sans-serif": ["Segoe UI", "SF Pro Text", "DejaVu Sans"],
    "font.size":       9.0,
    "axes.titlesize":  10.5,
    "axes.labelsize":  9.5,
    "xtick.labelsize": 9.0,
    "ytick.labelsize": 9.0,
})


# =====================================================================
# Palette
# =====================================================================
BG_DEEP     = "#0f0f18"
BG_PANEL    = "#181826"
BG_INPUT    = "#2c2c44"
BG_INPUT2   = "#37375a"
BG_PLOT     = "#13131e"
BORDER      = "#4f4f7a"
BORDER_SOFT = "#2e2e46"
BORDER_HV   = "#6a6aa0"
GRID        = "#3a3a5c"
TEXT_PRIM   = "#ececf7"
TEXT_DIM    = "#b4b8d1"
TEXT_FAINT  = "#9296b0"
ACCENT      = "#7d6cff"
ACCENT_HV   = "#9485ff"
ACCENT_TXT  = "#9c8fff"
ACCENT_FILL = "#6350d6"
ACCENT_FILL_HV = "#6d5be8"
ACCENT_FILL_PR = "#5745c4"
ACCENT2     = "#5fd4f5"
SUCCESS     = "#06d6a0"
WARN        = "#ffd166"
ERROR       = "#ff6b81"
DISABLED_FG = "#9292b0"
DISABLED_BG = "#2a2a3c"
MONO    = '"Cascadia Code", "Consolas", "SF Mono", monospace'
SYMBOLS = '"Segoe UI Symbol", "Segoe UI", sans-serif'
UI      = '"Segoe UI", "SF Pro Text", system-ui, sans-serif'
INPUT_H = 40


STYLESHEET = f"""
* {{
    font-family: {UI};
    font-size: 13px;
    color: {TEXT_PRIM};
}}

QMainWindow, QWidget {{ background-color: {BG_DEEP}; }}

QFrame#sidebar {{ background-color: {BG_PANEL}; border-right: 1px solid {BORDER_SOFT}; }}
QFrame#sidehead, QFrame#sidefoot, QWidget#sidebody {{
    background-color: {BG_PANEL}; border: none;
}}
QFrame#sidefoot {{ border-top: 1px solid {BORDER_SOFT}; }}
QScrollArea#sidescroll {{ background-color: {BG_PANEL}; border: none; }}
QScrollArea#sidescroll > QWidget {{ background-color: {BG_PANEL}; }}

QFrame#controlbar {{
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER_SOFT};
    border-bottom: 1px solid {BORDER_SOFT};
}}
QFrame#statbar {{ background-color: {BG_PANEL}; border-top: 1px solid {BORDER_SOFT}; }}
QFrame#statblock {{ background: transparent; border: none; }}

QLabel {{ color: {TEXT_DIM}; background: transparent; font-size: 13px; }}

QLabel#header {{
    color: {TEXT_PRIM}; font-size: 21px; font-weight: 700; letter-spacing: -0.2px;
}}
QLabel#subheader {{
    color: {TEXT_FAINT}; font-size: 11px; font-weight: 700; letter-spacing: 1.4px;
}}
QLabel#section {{
    color: {ACCENT_TXT}; font-size: 11px; font-weight: 700; letter-spacing: 1.3px;
}}
QLabel#description {{
    color: {TEXT_DIM}; font-size: 13px; font-weight: 400; font-style: normal;
    padding: 2px 1px;
}}
QLabel#formlbl {{
    color: {TEXT_DIM}; font-size: 13px; min-height: {INPUT_H}px; padding-right: 2px;
}}
QLabel#status {{ font-size: 12px; padding: 0px; color: {TEXT_FAINT}; }}
QLabel#status[state="ok"]    {{ color: {SUCCESS}; }}
QLabel#status[state="warn"]  {{ color: {WARN}; }}
QLabel#status[state="error"] {{ color: {ERROR}; }}

QLabel#timecode {{
    color: {ACCENT2}; font-size: 14px; font-weight: 600;
    font-family: {MONO}; letter-spacing: 0.2px;
}}
QLabel#statbig {{
    color: {TEXT_PRIM}; font-size: 18px; font-weight: 600; font-family: {MONO};
}}
QLabel#statlbl {{
    color: {TEXT_FAINT}; font-size: 11px; font-weight: 700; letter-spacing: 1.1px;
}}

QLineEdit, QComboBox {{
    background-color: {BG_INPUT};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 7px 11px;
    min-height: 22px;
    font-size: 14px;
    color: {TEXT_PRIM};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QComboBox {{ padding-right: 30px; }}
QLineEdit:hover, QComboBox:hover {{ border-color: {BORDER_HV}; }}
QLineEdit:focus, QComboBox:focus, QComboBox:on {{
    border-color: {ACCENT}; background-color: {BG_INPUT2};
}}
QLineEdit:disabled, QComboBox:disabled {{
    background-color: {DISABLED_BG}; border-color: {BORDER_SOFT}; color: {DISABLED_FG};
}}

QComboBox::drop-down {{ border: none; width: 30px; background: transparent; }}
QComboBox::down-arrow {{ image: none; width: 0px; height: 0px; border: none; }}

QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    color: {TEXT_PRIM};
    padding: 6px;
    outline: 0;
    font-size: 14px;
}}
QComboBox QAbstractItemView::item {{
    padding: 7px 10px; border-radius: 5px; min-height: 26px;
}}

QPushButton {{
    font-family: {SYMBOLS};
    background-color: {ACCENT_FILL};
    color: #ffffff;
    border: none;
    padding: 12px 18px;
    min-height: 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton:hover    {{ background-color: {ACCENT_FILL_HV}; }}
QPushButton:pressed  {{ background-color: {ACCENT_FILL_PR}; }}
QPushButton:disabled {{ background-color: {DISABLED_BG}; color: {DISABLED_FG}; }}
QPushButton:focus    {{ border: 2px solid #ffffff; padding: 10px 16px; }}

QPushButton#icon, QPushButton#iconwide {{
    font-family: {SYMBOLS};
    background-color: {BG_INPUT};
    border: 2px solid {BORDER};
    padding: 7px 11px;
    min-width: 22px;
    min-height: 22px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
    color: {TEXT_PRIM};
}}
QPushButton#iconwide {{ min-width: 84px; }}
QPushButton#icon:hover, QPushButton#iconwide:hover {{
    background-color: {BG_INPUT2}; border-color: {ACCENT}; color: {TEXT_PRIM};
}}
QPushButton#icon:pressed, QPushButton#iconwide:pressed {{ background-color: {ACCENT_FILL_PR}; }}
QPushButton#icon:focus, QPushButton#iconwide:focus {{ border-color: {ACCENT}; }}
QPushButton#icon:disabled, QPushButton#iconwide:disabled {{
    color: {DISABLED_FG}; border-color: {BORDER_SOFT}; background-color: {DISABLED_BG};
}}

QProgressBar {{
    border: none;
    border-radius: 3px;
    background-color: {BG_INPUT};
    min-height: 6px;
    max-height: 6px;
    text-align: center;
    color: transparent;
    font-size: 1px;
}}
QProgressBar::chunk {{ background-color: {SUCCESS}; border-radius: 3px; }}

QSlider:horizontal {{ min-height: 26px; background: transparent; }}
QSlider::groove:horizontal   {{ background: {BG_INPUT}; height: 6px; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::add-page:horizontal {{ background: {BG_INPUT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {ACCENT}; border: 2px solid {BG_PANEL};
    width: 14px; height: 14px; margin: -6px 0; border-radius: 9px;
}}
QSlider::handle:horizontal:hover    {{ background: {ACCENT_HV}; border-color: {ACCENT_HV}; }}
QSlider::handle:horizontal:disabled {{ background: #3a3a54; border-color: {BG_PANEL}; }}

QSplitter::handle:horizontal {{
    background-color: {BG_DEEP};
    border-left: 1px solid {BORDER_SOFT};
    width: 5px;
    margin: 0;
}}
QSplitter::handle:horizontal:hover, QSplitter::handle:horizontal:pressed {{
    border-left: 2px solid {ACCENT};
}}

QScrollBar:vertical {{ background: transparent; width: 10px; border: none; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none; background: none; height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QToolTip {{
    background-color: {BG_PANEL}; color: {TEXT_PRIM};
    border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px;
}}
"""


# =====================================================================
# Preset library
# =====================================================================
# Preset values live in spectral/maxwell/presets.py (shared with the web
# build); this turns each canonical params dict into the form-field strings
# _preset_changed fills in. Numbers are written so the form parses back to the
# exact same values (float(text) == value): integral values without ".0"
# ("2, 1", "[[[0, 1], [1, 0]]]", t "0" .. "50"), everything else as repr.
def _num_text(x: float) -> str:
    x = float(x)
    if x.is_integer() and abs(x) < 2.0 ** 53 and not (x == 0 and np.signbit(x)):
        return str(int(x))
    return repr(x)


def _v_entry_text(re: float, im: float) -> str:
    if im == 0:
        return _num_text(re)
    if re == 0:
        return f"{_num_text(im)}j"
    return f"({_num_text(re)}{'+' if im >= 0 else '-'}{_num_text(abs(im))}j)"


def _preset_fields(params: dict) -> dict:
    tm = params["times"]
    amp = params["amplitude"]
    if amp["mode"] == "schober_window":
        amp = _presets.WINDOW_FORM_GAUSSIAN
    V = params["V_sites"]
    return dict(
        L=str(params["L"]), a=", ".join(_num_text(x) for x in params["a"]),
        N=str(params["N"]), M=str(params["M"]),
        j_sites=", ".join(str(j) for j in params["j_sites"]),
        V_sites="[" + ", ".join(
            "[" + ", ".join(
                "[" + ", ".join(_v_entry_text(re, im) for re, im in row) + "]"
                for row in site) + "]"
            for site in V) + "]",
        interval_lo=_num_text(params["interval"][0]),
        interval_hi=_num_text(params["interval"][1]),
        E0=_num_text(amp["E0"]), sigma_E=_num_text(amp["sigma_E"]),
        sigma_mode=amp["direction"], n_init=str(amp["n_init"]),
        n_t=str(tm["n_t"]), t_min=_num_text(tm["t_min"]), t_max=_num_text(tm["t_max"]),
        n_quad=str(params["n_quad"]),
        outer="+" if params["outer_sign"] == 1 else "-",
    )


PRESETS: dict[str, dict | None] = {
    name: _preset_fields(params) for name, params in _presets.PRESETS.items()
}
PRESETS["Custom — edit fields below"] = None


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
# weights on the two σ channels. Balanced (1,1) gives Schober's
# standing packet; right / left select a single propagation direction.
SIGMA_MODES: dict[str, tuple[float, float]] = {
    "balanced (1,1)": _presets.DIRECTION_WEIGHTS["balanced"],
    "right (1,0)":    _presets.DIRECTION_WEIGHTS["right"],
    "left (0,1)":     _presets.DIRECTION_WEIGHTS["left"],
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
_schober_window_f = _presets.schober_window_f

_WINDOW_PRESETS = [
    name for name, params in _presets.PRESETS.items()
    if params["amplitude"]["mode"] == "schober_window"
]

PRESET_F = {name: _schober_window_f for name in _WINDOW_PRESETS}


# Energy windows matching _schober_window_f's support. _build_spec passes these
# as MaxwellSpec.E_segments so quadrature runs per-window (spectrally convergent
# for step-function f) instead of one rule across all of `interval`.
PRESET_SEGMENTS = {
    name: list(_presets.SCHOBER_E_SEGMENTS) for name in _WINDOW_PRESETS
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
def _ffmpeg_available() -> bool:
    """True if matplotlib can actually write an MP4.

    NOT `shutil.which("ffmpeg")`: the dependency `imageio-ffmpeg` ships a
    bundled binary that never lands on PATH, so `which` reported False and the
    export silently fell back to GIF even with a perfectly good encoder
    installed. Ask matplotlib instead, since matplotlib is what does the work.
    Registering the bundled binary first means a system ffmpeg is preferred
    when one exists, and the bundled one is used otherwise.
    """
    try:
        if animation.FFMpegWriter.isAvailable():
            return True                      # a system ffmpeg is on PATH
    except Exception:
        pass
    try:                                      # fall back to the bundled binary
        import imageio_ffmpeg
        import matplotlib
        matplotlib.rcParams["animation.ffmpeg_path"] = \
            imageio_ffmpeg.get_ffmpeg_exe()
        return animation.FFMpegWriter.isAvailable()
    except Exception:
        return False


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
            fig = Figure(figsize=(12.8, 7.2), dpi=100, layout="constrained")
            fig.get_layout_engine().set(h_pad=0.02, w_pad=0.02,
                                        hspace=0.03, wspace=0.0)
            FigureCanvasAgg(fig)  # attach a private Agg canvas, never the GUI's
            fig.patch.set_facecolor(BG_DEEP)
            gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.55])
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
                cmap="inferno",
                interpolation=("bilinear" if len(self.frames) >= 60 else "nearest"),
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
                    ax_line.set_title(f"t = {t_now:.3f}")
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
                spine.set_color(GRID)
            ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4)
            ax.xaxis.label.set_color(TEXT_DIM)
            ax.yaxis.label.set_color(TEXT_DIM)
        ax_line.title.set_color(TEXT_PRIM)
        ax_line.set_ylabel("ψ(n, t)", labelpad=6)
        ax_line.grid(True, color=GRID, alpha=0.55, linewidth=0.6)
        ax_line.tick_params(labelbottom=False)
        ax_water.set_xlabel("lattice site n", labelpad=6)
        ax_water.set_ylabel("time t", labelpad=6)
        ax_water.set_title("spacetime  ψ(n, t)", fontsize=10, loc="left",
                           color=TEXT_FAINT, pad=4)


class Combo(QComboBox):
    """QComboBox that paints its own chevron.

    Qt stylesheets cannot draw a CSS border-triangle: ``QComboBox::down-arrow``
    with border tricks paints a solid square (verified, Qt 6.10 / windows11).
    The native arrow is collapsed to 0x0 in the stylesheet; we draw text here.
    U+25BC is present in Segoe UI, so this needs no fallback font.
    """

    CHEV, CHEV_PX, CHEV_PAD = "\u25BC", 11, 13

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        f = QFont(self.font())
        f.setPixelSize(self.CHEV_PX)
        p.setFont(f)
        if not self.isEnabled():
            col = DISABLED_FG
        elif self.hasFocus():
            col = ACCENT_HV
        else:
            col = TEXT_DIM
        p.setPen(QColor(col))
        p.drawText(self.rect().adjusted(0, 0, -self.CHEV_PAD, 0),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   self.CHEV)
        p.end()


class _WheelGuard(QObject):
    """Wheel over an unfocused combo must not silently change its value.

    Inside the sidebar scroll area the event is forwarded to the scrollbar so
    the sidebar still scrolls; elsewhere it is swallowed.
    """

    def __init__(self, parent, scroll_area=None):
        super().__init__(parent)
        self._sa = scroll_area

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Wheel and not obj.hasFocus():
            if self._sa is not None and self._sa.isAncestorOf(obj):
                bar = self._sa.verticalScrollBar()
                bar.setValue(bar.value() - ev.angleDelta().y())
            return True
        return False


def _field_label(name: str, sym: str) -> QLabel:
    """Two-track form label: prose name + monospace code identifier."""
    lbl = QLabel(
        f'<span style="color:{TEXT_DIM};">{name}</span>&nbsp;&nbsp;'
        f'<span style="font-family:\'Cascadia Code\',Consolas,monospace;'
        f'color:{ACCENT_TXT};">{sym}</span>'
    )
    lbl.setObjectName("formlbl")
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


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
        splitter.setHandleWidth(5)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        # ---------------- Sidebar ----------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(380)
        sidebar.setMaximumWidth(560)
        sidebar.setSizePolicy(QSizePolicy.Policy.Preferred,
                              QSizePolicy.Policy.Expanding)
        side_root = QVBoxLayout(sidebar)
        side_root.setContentsMargins(0, 0, 0, 0)
        side_root.setSpacing(0)

        head = QFrame()
        head.setObjectName("sidehead")
        head.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        hv = QVBoxLayout(head)
        hv.setContentsMargins(24, 20, 24, 14)
        hv.setSpacing(3)
        title = QLabel("Maxwell Algorithm")
        title.setObjectName("header")
        hv.addWidget(title)
        sub = QLabel("LATTICE  SCATTERING  WAVE  PACKET")
        sub.setObjectName("subheader")
        hv.addWidget(sub)
        side_root.addWidget(head, 0)

        self.side_scroll = QScrollArea()
        self.side_scroll.setObjectName("sidescroll")
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.side_scroll.setSizePolicy(QSizePolicy.Policy.Preferred,
                                       QSizePolicy.Policy.Expanding)
        body = QWidget()
        body.setObjectName("sidebody")
        side = QVBoxLayout(body)
        side.setContentsMargins(24, 4, 18, 16)
        side.setSpacing(0)
        self.side_scroll.setWidget(body)
        side_root.addWidget(self.side_scroll, 1)

        side.addWidget(self._section("Preset"))
        side.addSpacing(8)
        self.preset_combo = Combo()
        for name in PRESETS:
            self.preset_combo.addItem(name)
        side.addWidget(self.preset_combo)

        side.addSpacing(12)
        self.preset_desc = QLabel("")
        self.preset_desc.setObjectName("description")
        self.preset_desc.setWordWrap(True)
        self.preset_desc.setMinimumHeight(60)
        side.addWidget(self.preset_desc)

        side.addSpacing(12)
        side.addWidget(self._section("Configuration"))
        side.addSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight |
                               Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
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
        self.in_sigma_mode = Combo()
        self.in_sigma_mode.addItems(list(SIGMA_MODES))
        self.in_n_init  = QLineEdit()
        self.in_n_t     = QLineEdit()
        self.in_t_min   = QLineEdit()
        self.in_t_max   = QLineEdit()
        self.in_n_quad  = QLineEdit()
        self.in_outer   = Combo()
        self.in_outer.addItems(["+  outgoing  w(E,+)", "−  incoming  w(E,−)"])

        form.addRow(_field_label("Channels",        "L"),      self.in_L)
        form.addRow(_field_label("Hopping",         "a"),      self.in_a)
        form.addRow(_field_label("Lattice min",     "N"),      self.in_N)
        form.addRow(_field_label("Lattice max",     "M"),      self.in_M)
        form.addRow(_field_label("Potential sites", "j_k"),    self.in_j_sites)
        form.addRow(_field_label("Potential",       "V"),      self.in_V_sites)
        form.addRow(_field_label("Energy from",     "E_lo"),   self.in_a_lo)
        form.addRow(_field_label("Energy to",       "E_hi"),   self.in_b_hi)
        form.addRow(_field_label("Packet centre",   "E_0"),    self.in_E0)
        form.addRow(_field_label("Packet width",    "s_E"),    self.in_sigma_E)
        form.addRow(_field_label("Sigma mode",      "h+-"),    self.in_sigma_mode)
        form.addRow(_field_label("Start site",      "n_init"), self.in_n_init)
        form.addRow(_field_label("Compare branch",  "+/-"),    self.in_outer)
        form.addRow(_field_label("Time frames",     "n_t"),    self.in_n_t)
        form.addRow(_field_label("Time from",       "t_min"),  self.in_t_min)
        form.addRow(_field_label("Time to",         "t_max"),  self.in_t_max)
        form.addRow(_field_label("Quadrature",      "n_quad"), self.in_n_quad)

        side.addStretch(1)

        foot = QFrame()
        foot.setObjectName("sidefoot")
        foot.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        fv = QVBoxLayout(foot)
        fv.setContentsMargins(24, 14, 24, 16)
        fv.setSpacing(0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        fv.addWidget(self.progress_bar)
        fv.addSpacing(10)

        self.run_button = QPushButton("▶   Compute && Animate")
        self.run_button.setSizePolicy(QSizePolicy.Policy.Preferred,
                                      QSizePolicy.Policy.Fixed)
        self.run_button.setShortcut("Ctrl+Return")
        self.run_button.setToolTip(
            "Compute psi(n,t) and start playback   (Ctrl+Enter)")
        self.run_button.clicked.connect(self.run_compute)
        fv.addWidget(self.run_button)
        fv.addSpacing(10)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(32)
        self.status_label.setMaximumHeight(54)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop |
                                       Qt.AlignmentFlag.AlignLeft)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                        QSizePolicy.Policy.Fixed)
        fv.addWidget(self.status_label)

        side_root.addWidget(foot, 0)
        splitter.addWidget(sidebar)

        # ---------------- Plot area (right) ----------------
        right = QFrame()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(0)

        # Figure with two stacked subplots: line + waterfall
        self.figure = Figure(figsize=(7.2, 5.2), layout="constrained")
        self.figure.get_layout_engine().set(h_pad=0.02, w_pad=0.02,
                                            hspace=0.03, wspace=0.0)
        self.figure.patch.set_facecolor(BG_DEEP)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {BG_DEEP};")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumSize(360, 240)
        gs = self.figure.add_gridspec(2, 1, height_ratios=[1.0, 1.55])
        self.ax_line  = self.figure.add_subplot(gs[0])
        self.ax_water = self.figure.add_subplot(gs[1], sharex=self.ax_line)
        self._empty_hi = self.figure.text(
            0.5, 0.55, "Compute & Animate", ha="center", va="center",
            color=TEXT_PRIM, fontsize=17)
        self._empty_lo = self.figure.text(
            0.5, 0.485,
            "pick a preset on the left, then press the button   \u00b7   Ctrl+Enter",
            ha="center", va="center", color=TEXT_FAINT, fontsize=10)
        self._colorbar = None
        self._bg = None
        self._set_empty(True)
        right_v.addWidget(self.canvas, stretch=1)

        # Control bar: play/pause | scrubber | timecode | speed
        controlbar = QFrame()
        controlbar.setObjectName("controlbar")
        cb = QHBoxLayout(controlbar)
        controlbar.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.Fixed)
        cb.setContentsMargins(16, 12, 16, 12)
        cb.setSpacing(10)

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("icon")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        cb.addWidget(self.play_btn)

        self.restart_btn = QPushButton("⏮")
        self.restart_btn.setToolTip("Restart from frame 0   (Home)")
        self.restart_btn.setObjectName("icon")
        self.restart_btn.setEnabled(False)
        self.restart_btn.clicked.connect(self._restart)
        cb.addWidget(self.restart_btn)

        self.scrubber = QSlider(Qt.Orientation.Horizontal)
        self.scrubber.setRange(0, 0)
        self.scrubber.setEnabled(False)
        self.scrubber.setMinimumWidth(120)
        self.scrubber.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Fixed)
        self.scrubber.valueChanged.connect(self._scrubbed)
        cb.addWidget(self.scrubber, stretch=1)

        self.timecode = QLabel("t = 0.000   ·   0 / 0")
        self.timecode.setObjectName("timecode")
        self.timecode.setMinimumWidth(212)
        self.timecode.setAlignment(Qt.AlignmentFlag.AlignRight |
                                   Qt.AlignmentFlag.AlignVCenter)
        self.timecode.setSizePolicy(QSizePolicy.Policy.Fixed,
                                    QSizePolicy.Policy.Preferred)
        cb.addWidget(self.timecode)

        self.speed_combo = Combo()
        self.speed_combo.addItems(["0.25×", "0.5×", "1×", "2×", "4×"])
        self.speed_combo.setCurrentText("1×")
        self.speed_combo.setToolTip("Playback speed")
        self.speed_combo.setMinimumWidth(96)
        self.speed_combo.setMaximumWidth(104)
        self.speed_combo.currentTextChanged.connect(self._speed_changed)
        cb.addWidget(self.speed_combo)

        self.export_btn = QPushButton("⬇  Export")
        self.export_btn.setObjectName("iconwide")
        self.export_btn.setToolTip("Export animation to MP4/GIF   (Ctrl+E)")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_clicked)
        cb.addWidget(self.export_btn)

        right_v.addWidget(controlbar)

        # Stats strip below the controls
        stats = QFrame()
        stats.setObjectName("statbar")
        stats.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sl = QHBoxLayout(stats)
        sl.setContentsMargins(20, 10, 20, 12)
        sl.setSpacing(22)

        def stat_block(label, min_w=116):
            wrap = QFrame()
            wrap.setObjectName("statblock")
            wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            v = QVBoxLayout(wrap)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(3)
            lbl = QLabel(label.upper())
            lbl.setObjectName("statlbl")
            big = QLabel("—")
            big.setObjectName("statbig")
            for q in (lbl, big):
                q.setMinimumWidth(min_w)
                q.setAlignment(Qt.AlignmentFlag.AlignLeft |
                               Qt.AlignmentFlag.AlignVCenter)
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
        right_v.setStretch(0, 1)
        right_v.setStretch(1, 0)
        right_v.setStretch(2, 0)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([400, 10_000])

        self.setMinimumSize(QSize(1120, 600))

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
        # in_outer is a solver-branch selector, NOT a spec field: connecting it
        # to _field_edited flipped the preset to Custom and silently swapped the
        # window f / E_segments out from under the user.
        self.in_sigma_mode.currentTextChanged.connect(self._field_edited)
        for _le in (self.in_L, self.in_a, self.in_N, self.in_M,
                    self.in_j_sites, self.in_V_sites, self.in_a_lo, self.in_b_hi,
                    self.in_E0, self.in_sigma_E, self.in_n_init, self.in_n_t,
                    self.in_t_min, self.in_t_max, self.in_n_quad):
            _le.returnPressed.connect(self.run_compute)

        self._wheel_guard = _WheelGuard(self, self.side_scroll)
        for _c in (self.preset_combo, self.in_sigma_mode, self.in_outer,
                   self.speed_combo):
            _c.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            _c.installEventFilter(self._wheel_guard)

        self.setTabOrder(self.preset_combo, self.in_L)
        self.setTabOrder(self.run_button, self.play_btn)
        self.setTabOrder(self.play_btn, self.restart_btn)
        self.setTabOrder(self.restart_btn, self.scrubber)
        self.setTabOrder(self.scrubber, self.speed_combo)
        self.setTabOrder(self.speed_combo, self.export_btn)

        self._preset_changed(self.preset_combo.currentText())
        self._silent = False

    # ----------------------------------------------------------------- helpers
    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setObjectName("section")
        return lbl

    def _set_status(self, text: str, kind: str = "info"):
        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self.status_label.setProperty("state", kind)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_empty(self, on: bool, msg: str | None = None,
                   sub: str | None = None):
        """Blank both axes and show a centred call-to-action, or restore them."""
        if on:
            for ax in (self.ax_line, self.ax_water):
                ax.set_xticks([]); ax.set_yticks([])
                ax.grid(False)
                ax.set_xlabel(""); ax.set_ylabel(""); ax.set_title("")
                ax.set_facecolor(BG_DEEP)
                for s in ax.spines.values():
                    s.set_visible(False)
            if msg is not None:
                self._empty_hi.set_text(msg)
            if sub is not None:
                self._empty_lo.set_text(sub)
            self._empty_hi.set_visible(True)
            self._empty_lo.set_visible(True)
        else:
            self._empty_hi.set_visible(False)
            self._empty_lo.set_visible(False)
            for ax in (self.ax_line, self.ax_water):
                for s in ax.spines.values():
                    s.set_visible(True)
            self._style_line_axes()
            self._style_water_axes()
            self.ax_line.tick_params(labelbottom=False)
        self._bg = None
        self.canvas.draw_idle()

    def _style_line_axes(self):
        ax = self.ax_line
        ax.set_facecolor(BG_PLOT)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4,
                       labelsize=9)
        ax.xaxis.label.set_color(TEXT_DIM); ax.xaxis.label.set_fontsize(9.5)
        ax.yaxis.label.set_color(TEXT_DIM); ax.yaxis.label.set_fontsize(9.5)
        ax.title.set_color(TEXT_PRIM); ax.title.set_fontsize(10.5)
        ax.set_ylabel("ψ(n, t)", labelpad=6)
        ax.grid(True, color=GRID, alpha=0.55, linewidth=0.6)

    def _style_water_axes(self):
        ax = self.ax_water
        ax.set_facecolor(BG_PLOT)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.tick_params(colors=TEXT_DIM, which="both", direction="out", length=4,
                       labelsize=9)
        ax.xaxis.label.set_color(TEXT_DIM); ax.xaxis.label.set_fontsize(9.5)
        ax.yaxis.label.set_color(TEXT_DIM); ax.yaxis.label.set_fontsize(9.5)
        ax.set_xlabel("lattice site n", labelpad=6)
        ax.set_ylabel("time t", labelpad=6)
        ax.set_title("SPACETIME  ψ(n, t)", fontsize=9, loc="left",
                     color=TEXT_FAINT, pad=5, fontweight="bold")

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
            next((k for k in SIGMA_MODES if k.startswith(cfg["sigma_mode"])),
                 next(iter(SIGMA_MODES)))
        )
        self.in_n_init.setText(cfg["n_init"])
        self.in_n_t.setText(cfg["n_t"]);        self.in_t_min.setText(cfg["t_min"])
        self.in_t_max.setText(cfg["t_max"]);    self.in_n_quad.setText(cfg["n_quad"])
        self.in_outer.setCurrentIndex(0 if cfg["outer"] == "+" else 1)
        self._silent = False
        uses_window_f = name in PRESET_F
        for wdg in (self.in_E0, self.in_sigma_E, self.in_sigma_mode,
                    self.in_n_init, self.in_a_lo, self.in_b_hi):
            wdg.setEnabled(not uses_window_f)
            wdg.setToolTip(
                "Ignored by this preset — f is a fixed step-function window and "
                "quadrature runs per E-segment." if uses_window_f else "")
        self.setWindowTitle(f"Maxwell Algorithm — {name.split(' — ')[0]}")
        self._idle_status()

    def _idle_status(self):
        """Cheap cost preview: what this run will actually chew through."""
        try:
            n_t = int(self.in_n_t.text())
            span = int(self.in_M.text()) - int(self.in_N.text()) + 1
            nq = int(self.in_n_quad.text())
        except Exception:
            self._set_status("", "info")
            return
        self._set_status(f"{n_t} frames · {span} sites · n_quad {nq}", "info")

    def _field_edited(self, *_):
        self._idle_status()
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
            self._set_status(f"Input error:  {exc}", "error")
            return

        # Advisory aliasing check (single-interval runs only; the per-window
        # Schober presets use narrow segments and are far below threshold).
        # Under-resolved quadrature folds a phantom mirror packet into psi --
        # the t=0 frame looks fine, the waterfall doubles its mass.
        self._nquad_warning = ""
        try:
            recommended = None
            if spec.E_segments is None:
                recommended = min_nquad(
                    spec.N, spec.M, float(spec.times[0]), float(spec.times[-1]),
                    spec.interval[0], spec.interval[1], spec.a,
                )
            lattice = spec.lattice()
        except Exception as exc:
            self._set_status(f"Input error:  {type(exc).__name__}: {exc}", "error")
            return
        if recommended is not None and spec.n_quad < recommended:
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
        self.lattice = lattice
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
        self._set_status("Computing…" + self._nquad_warning,
                         "warn" if self._nquad_warning else "info")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.line = None
        self.fill = None
        self.water_image = None
        self.water_time_line = None
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None
        self.ax_line.clear()
        self.ax_water.clear()
        self._set_empty(
            True, "Computing…",
            f"{spec.times.size} frames × {spec.M - spec.N + 1} sites"
            f"   ·   n_quad {spec.n_quad}")
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
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        self._set_status(f"Error:  {msg}", "error")

    def on_finished(self, frames, gmax):
        if not frames:
            self.progress_bar.setVisible(False)
            self._set_status("No frames produced.", "warn")
            return
        self.frames = frames
        self.gmax = gmax
        self.ylim = (gmax * 1.10) if gmax > 0 else 1.0
        self.frame_idx = 0
        self.line = None
        self.fill = None
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        n = len(frames)
        self._set_status(
            f"{n} frame{'s' if n != 1 else ''} · {self.lattice.size} sites · "
            f"max ψ = {gmax:.4g}" + self._nquad_warning,
            "warn" if self._nquad_warning else "ok",
        )
        self.stat_max.setText(f"{gmax:.4f}")

        # Restore real axes, then render the spacetime waterfall once
        self._set_empty(False)
        self._render_waterfall()
        self.ax_line.set_title(
            f"ψ(n, t)   ·   {self.preset_combo.currentText().split(' — ')[0]}",
            fontsize=10.5, loc="left", color=TEXT_FAINT, pad=4)
        self._render_frame(0)
        self.frame_idx = 1
        for art in (self.line, self.fill, self.water_time_line):
            if art is not None:
                art.set_animated(True)
        self.canvas.draw()
        self._bg = self.canvas.copy_from_bbox(self.figure.bbox)

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
        self._render_frame(0)
        self.frame_idx = 1
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
        have_ffmpeg = _ffmpeg_available()
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
        self.run_button.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self._set_status("Exporting…", "info")

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
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self._set_status(f"Export saved:  {path}", "ok")
        # Only re-enable if there is still an animation to export (a compute
        # may have started, and cleared frames, while we were writing).
        self.export_btn.setEnabled(self.frames is not None)

    def _on_export_failed(self, msg: str):
        self._inflight_workers = [w for w in self._inflight_workers if w.isRunning()]
        self.progress_bar.setVisible(False)
        self.run_button.setEnabled(True)
        self._set_status(f"Export failed:  {msg}", "error")
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
            cmap="inferno",
            interpolation=("bilinear" if len(self.frames) >= 60 else "nearest"),
            vmin=0.0,
            vmax=max(self.gmax, 1e-12),
        )

        # Potential-site markers on both panels
        for jk in self._j_sites_for_render:
            ax.axvline(jk, color="white", alpha=0.30, lw=0.8, zorder=5)

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

        self._colorbar = self.figure.colorbar(
            self.water_image, ax=ax, pad=0.012, fraction=0.032)
        self._colorbar.ax.tick_params(colors=TEXT_DIM, labelsize=8)
        self._colorbar.outline.set_edgecolor(GRID)

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
            for jk in self._j_sites_for_render:
                self.ax_line.axvline(
                    jk, color=ACCENT, alpha=0.42, lw=0.9, zorder=2,
                )
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

        # Stats strip
        self.timecode.setText(f"t = {t_now:.3f}   ·   {idx + 1} / {len(self.frames)}")
        self.stat_t.setText(f"{t_now:.3f}")
        peak_idx = int(np.argmax(curve))
        self.stat_peak.setText(f"{int(self.lattice[peak_idx])}")
        self.stat_norm.setText(f"{float(np.sum(curve)):.3f}")

        if self._bg is None:
            self.canvas.draw()
            return
        for art in (self.line, self.fill, self.water_time_line):
            if art is not None:
                art.set_animated(True)
        self.canvas.restore_region(self._bg)
        self.ax_line.draw_artist(self.fill)
        self.ax_line.draw_artist(self.line)
        if self.water_time_line is not None:
            self.ax_water.draw_artist(self.water_time_line)
        self.canvas.blit(self.figure.bbox)
        self.canvas.flush_events()

    def resizeEvent(self, event):
        self._bg = None
        super().resizeEvent(event)
        QTimer.singleShot(0, self._recapture_bg)

    def _recapture_bg(self):
        if self.frames is None or self.line is None:
            return
        self.canvas.draw()
        self._bg = self.canvas.copy_from_bbox(self.figure.bbox)

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
            self._set_status(f"Render paused:  {exc}", "warn")

    # ----------------------------------------------------------------- shutdown
    def closeEvent(self, event):
        # Stop animation and let any running worker finish briefly so Qt
        # doesn't print "QThread destroyed while still running".
        self.timer.stop()
        self._compute_token += 1  # invalidate any pending callbacks
        for w in list(self._inflight_workers):
            try:
                if w.isRunning():
                    w.wait(250)
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
        outer   = +1 if self.in_outer.currentIndex() == 0 else -1
        h_plus, h_minus = SIGMA_MODES[self.in_sigma_mode.currentText()]
        if t_min >= t_max:
            raise ValueError("need t_min < t_max")
        if n_t < 2:
            raise ValueError("need at least 2 time frames (n_t ≥ 2)")
        if n_quad < 8:
            raise ValueError("n_quad must be ≥ 8")
        if sigma_E <= 0:
            raise ValueError("σ_E must be > 0")
        if not (N <= n_init <= M):
            raise ValueError(f"n_init must lie in [N, M] = [{N}, {M}]")
        if (M - N + 1) * n_t > 40_000_000:
            raise ValueError(
                f"{(M - N + 1) * n_t:,} lattice×time samples is too large; "
                f"reduce N/M or n_t"
            )

        # Schober window presets carry a fixed step-function f (keyed by preset
        # name); every other preset / Custom builds the Gaussian f from the form.
        window_f = PRESET_F.get(self.preset_combo.currentText())
        if window_f is not None:
            f = window_f
        else:
            # Gaussian f: sigma-mode weights h± scale the two σ
            # channels, and the θ(E) phase parks the packet at lattice site
            # n_init at t=0. Single channel l₀=0; other channels stay zero.
            f = _presets.gaussian_f(L, float(a[0]), E0, sigma_E,
                                    h_plus, h_minus, n_init)

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
