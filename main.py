"""Maxwell algorithm viewer entry point."""
import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("Maxwell Algorithm")
window = MainWindow()
window.resize(1480, 920)
window.show()
sys.exit(app.exec())
