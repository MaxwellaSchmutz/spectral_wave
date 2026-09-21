"""Maxwell algorithm viewer entry point."""
from __future__ import annotations

import faulthandler
import sys
import traceback
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from gui.main_window import MainWindow

# Preferred startup size. Deliberately NOT applied blind: at 125% or 150%
# Windows scaling the logical screen can be as small as 826x688, and asking for
# a window larger than the screen leaves the transport bar and stats below the
# bottom edge with no way to drag them back.
PREFERRED = (1480, 920)


def _fit_to_screen(window) -> None:
    """Open as close to PREFERRED as the actual screen allows, then centre."""
    screen = QApplication.primaryScreen()
    if screen is None:
        window.resize(*PREFERRED)
        return
    avail = screen.availableGeometry()
    w = min(PREFERRED[0], max(avail.width() - 80, window.minimumWidth()))
    h = min(PREFERRED[1], max(avail.height() - 80, window.minimumHeight()))
    window.resize(w, h)
    frame = window.frameGeometry()
    frame.moveCenter(avail.center())
    window.move(frame.topLeft())


def main() -> int:
    # Log hard crashes (faulthandler) and startup failures to a file so they
    # cannot vanish silently when there is no console.
    log = Path("maxwell-crash.log")
    try:
        faulthandler.enable(open(log, "a", buffering=1))
    except OSError:
        pass  # unwritable working directory; not worth failing startup over

    app = QApplication(sys.argv)
    app.setApplicationName("Maxwell Algorithm")
    app.setApplicationDisplayName("Maxwell Algorithm")

    try:
        window = MainWindow()
        _fit_to_screen(window)
        window.show()
    except Exception:
        detail = traceback.format_exc()
        try:
            log.write_text(detail, encoding="utf-8")
        except OSError:
            pass
        QMessageBox.critical(None, "Maxwell Algorithm - startup failed", detail)
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
