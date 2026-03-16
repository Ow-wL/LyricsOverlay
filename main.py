"""
Lyrics Overlay MVP - main.py
Entry point for the application.
"""

import sys
from PyQt6.QtWidgets import QApplication
from control_panel import ControlPanel


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LyricsOverlay")
    app.setQuitOnLastWindowClosed(False)   # keep alive even if control panel closes

    panel = ControlPanel()
    panel.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
