from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.config import ConfigManager
from src.logger import build_logger
from src.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    """解析调试日志相关命令行参数。"""
    parser = argparse.ArgumentParser(description="Screenshot Splitter")
    parser.add_argument("--log", action="store_true", help="启用调试日志；未指定类别时记录全部日志类别。")
    parser.add_argument("--log-events", action="store_true", help="记录程序收到的键盘、鼠标和滚轮事件。")
    parser.add_argument("--log-api", action="store_true", help="记录主要程序接口调用及结果。")
    parser.add_argument("--log-state", action="store_true", help="记录当前文档、选区、分割线和预览状态。")
    return parser.parse_args()


def main() -> int:
    """程序入口。"""
    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("Screenshot Splitter")
    app.setOrganizationName("ScreenshotSplitter")

    # 开发环境使用项目目录，打包后使用 EXE 所在目录保存配置和日志。
    base_dir = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    logger = build_logger(base_dir, args)
    logger.api("application_start", {"argv": sys.argv})

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        logger.write("app", "uncaught_exception", {
            "exception_type": getattr(exc_type, "__name__", str(exc_type)),
            "message": str(exc_value),
        })
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception
    logger.install_event_filter(app)

    config = ConfigManager(base_dir)
    config.load()

    window = MainWindow(config, logger)
    window.show()
    result = app.exec()
    logger.api("application_exit", {"exit_code": result})
    logger.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
