from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.config import ConfigManager
from src.main_window import MainWindow


def main() -> int:
    """程序入口。"""
    app = QApplication(sys.argv)
    app.setApplicationName("Screenshot Splitter")
    app.setOrganizationName("ScreenshotSplitter")

    # 开发环境使用项目目录，打包后使用 EXE 所在目录保存配置。
    base_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    config = ConfigManager(base_dir)
    config.load()

    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
