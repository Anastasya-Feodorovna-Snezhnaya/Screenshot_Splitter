from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.config import ConfigManager
from src.main_window import MainWindow


def main() -> int:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Screenshot Splitter")
    app.setOrganizationName("ScreenshotSplitter")

    base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    config = ConfigManager(base_dir)
    config.load()

    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
