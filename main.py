# codeeditor/main.py
# Application entry point.

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from codeeditor.themes import apply_theme
from codeeditor.settings import Settings
from codeeditor.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CodeEditor")
    app.setApplicationVersion("2.0.0")

    # Apply saved theme preference (defaults to dark)
    apply_theme(app, Settings.instance().theme())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
