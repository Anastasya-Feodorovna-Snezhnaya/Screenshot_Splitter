from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication


class DebugLogger:
    """可选的调试日志。

    日志文件位于工作目录 logs/ 下，采用 JSON Lines 格式，便于人工查看和后续脚本分析。
    """

    def __init__(self, base_dir: Path, enabled: bool = False,
                 events: bool = False, api: bool = False, state: bool = False) -> None:
        self.enabled = enabled
        self.events_enabled = events
        self.api_enabled = api
        self.state_enabled = state
        self.log_dir = base_dir / "logs"
        self.path: Optional[Path] = None
        self._event_filter: Optional[_DebugEventFilter] = None

        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.path = self.log_dir / f"debug_{stamp}.jsonl"
            self.write("app", "logger_started", {
                "pid": __import__("os").getpid(),
                "python": sys.version,
                "categories": self.categories(),
            })

    def categories(self) -> list[str]:
        result = []
        if self.events_enabled:
            result.append("events")
        if self.api_enabled:
            result.append("api")
        if self.state_enabled:
            result.append("state")
        return result

    def write(self, category: str, name: str, data: Optional[dict[str, Any]] = None) -> None:
        if not self.enabled or self.path is None:
            return
        record = {
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "monotonic": round(time.monotonic(), 6),
            "category": category,
            "name": name,
        }
        if data:
            record["data"] = data
        try:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError:
            # 日志故障不应影响主程序。
            pass

    def event(self, name: str, data: dict[str, Any]) -> None:
        if self.events_enabled:
            self.write("events", name, data)

    def api(self, name: str, data: Optional[dict[str, Any]] = None) -> None:
        if self.api_enabled:
            self.write("api", name, data)

    def state(self, name: str, data: dict[str, Any]) -> None:
        if self.state_enabled:
            self.write("state", name, data)

    def install_event_filter(self, app: QApplication) -> None:
        if not self.enabled or not self.events_enabled:
            return
        self._event_filter = _DebugEventFilter(self)
        app.installEventFilter(self._event_filter)

    def close(self) -> None:
        self.write("app", "logger_stopped")


class _DebugEventFilter(QObject):
    """记录程序收到的键盘、鼠标和滚轮事件。"""

    _interesting = {
        QEvent.Type.KeyPress: "key_press",
        QEvent.Type.KeyRelease: "key_release",
        QEvent.Type.MouseButtonPress: "mouse_press",
        QEvent.Type.MouseButtonRelease: "mouse_release",
        QEvent.Type.MouseMove: "mouse_move",
        QEvent.Type.Wheel: "wheel",
    }

    def __init__(self, logger: DebugLogger) -> None:
        super().__init__()
        self.logger = logger

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        name = self._interesting.get(event.type())
        if name is not None:
            data: dict[str, Any] = {
                "target": type(watched).__name__,
                "event_type": int(event.type()),
            }
            if isinstance(event, QKeyEvent):
                data.update({
                    "key": event.key(),
                    "modifiers": int(event.modifiers()),
                    "text": event.text(),
                    "auto_repeat": event.isAutoRepeat(),
                })
            elif isinstance(event, QMouseEvent):
                data.update({
                    "button": int(event.button()),
                    "buttons": int(event.buttons()),
                    "modifiers": int(event.modifiers()),
                    "position": [event.position().x(), event.position().y()],
                })
            elif isinstance(event, QWheelEvent):
                data.update({
                    "buttons": int(event.buttons()),
                    "modifiers": int(event.modifiers()),
                    "position": [event.position().x(), event.position().y()],
                    "angle_delta": [event.angleDelta().x(), event.angleDelta().y()],
                    "pixel_delta": [event.pixelDelta().x(), event.pixelDelta().y()],
                })
            self.logger.event(name, data)
        return False


def build_logger(base_dir: Path, args) -> DebugLogger:
    """根据命令行参数创建日志器。"""
    enabled = bool(args.log)
    if not enabled:
        return DebugLogger(base_dir)

    any_category = args.log_events or args.log_api or args.log_state
    return DebugLogger(
        base_dir,
        enabled=True,
        events=args.log_events or not any_category,
        api=args.log_api or not any_category,
        state=args.log_state or not any_category,
    )
