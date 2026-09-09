from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication


def _enum_value(value: Any) -> Any:
    """兼容 PySide6 枚举对象和普通整数。"""
    return getattr(value, "value", value)


class DebugLogger:
    """可选的运行时调试日志。"""

    def __init__(self, base_dir: Path, enabled: bool = False,
                 events: bool = False, api: bool = False, state: bool = False,
                 mouse_move: bool = False) -> None:
        self.enabled = enabled
        self.events_enabled = events
        self.api_enabled = api
        self.state_enabled = state
        self.mouse_move_enabled = mouse_move
        self.log_dir = base_dir / "logs"
        self.path: Optional[Path] = None
        self._event_filter: Optional[_DebugEventFilter] = None

        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self.path = self.log_dir / f"debug_{stamp}.jsonl"
            self.write("app", "logger_started", {
                "pid": os.getpid(),
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
        if self.mouse_move_enabled:
            result.append("mouse_move")
        return result

    def write(self, category: str, name: str, data: Optional[dict[str, Any]] = None) -> None:
        if not self.enabled or self.path is None:
            return
        record: dict[str, Any] = {
            "time": datetime.now().isoformat(timespec="milliseconds"),
            "monotonic": round(time.monotonic(), 6),
            "category": category,
            "name": name,
        }
        if data is not None:
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

    def set_startup_shortcuts(self, shortcuts: dict[str, str]) -> None:
        """记录程序启动时的完整快捷键配置快照。该记录独立于日志分类开关。"""
        if not self.enabled:
            return
        self.write("config", "startup_shortcuts", {"shortcuts": dict(shortcuts)})

    def close(self) -> None:
        if self._event_filter is not None:
            self._event_filter.flush_mouse_move()
        self.write("app", "logger_stopped")


class _DebugEventFilter(QObject):
    """记录 QApplication 实际收到的键盘、鼠标和滚轮事件。"""

    _interesting = {
        QEvent.Type.KeyPress: "key_press",
        QEvent.Type.KeyRelease: "key_release",
        QEvent.Type.MouseButtonPress: "mouse_press",
        QEvent.Type.MouseButtonRelease: "mouse_release",
        QEvent.Type.Wheel: "wheel",
    }

    def __init__(self, logger: DebugLogger) -> None:
        super().__init__()
        self.logger = logger
        self._move_start_time: Optional[str] = None
        self._move_start_monotonic: Optional[float] = None
        self._move_start_position: Optional[list[float]] = None
        self._move_end_time: Optional[str] = None
        self._move_end_monotonic: Optional[float] = None
        self._move_end_position: Optional[list[float]] = None
        self._move_target: Optional[str] = None
        self._move_buttons: Optional[int] = None
        self._move_modifiers: Optional[int] = None
        self._move_count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            if self.logger.mouse_move_enabled:
                self._collect_mouse_move(watched, event)
            return False

        name = self._interesting.get(event.type())
        if name is not None:
            self.flush_mouse_move()
            self._record_event(watched, event, name)
        return False

    def _record_event(self, watched: QObject, event: QEvent, name: str) -> None:
        data: dict[str, Any] = {
            "target": type(watched).__name__,
            "event_type": _enum_value(event.type()),
        }
        if isinstance(event, QKeyEvent):
            data.update({
                "key": _enum_value(event.key()),
                "modifiers": _enum_value(event.modifiers()),
                "text": event.text(),
                "auto_repeat": event.isAutoRepeat(),
            })
        elif isinstance(event, QMouseEvent):
            data.update({
                "button": _enum_value(event.button()),
                "buttons": _enum_value(event.buttons()),
                "modifiers": _enum_value(event.modifiers()),
                "position": [event.position().x(), event.position().y()],
            })
        elif isinstance(event, QWheelEvent):
            data.update({
                "buttons": _enum_value(event.buttons()),
                "modifiers": _enum_value(event.modifiers()),
                "position": [event.position().x(), event.position().y()],
                "angle_delta": [event.angleDelta().x(), event.angleDelta().y()],
                "pixel_delta": [event.pixelDelta().x(), event.pixelDelta().y()],
            })
        self.logger.event(name, data)

    def _collect_mouse_move(self, watched: QObject, event: QEvent) -> None:
        if not isinstance(event, QMouseEvent):
            return
        now = datetime.now().isoformat(timespec="milliseconds")
        monotonic = time.monotonic()
        position = [event.position().x(), event.position().y()]
        target = type(watched).__name__
        buttons = _enum_value(event.buttons())
        modifiers = _enum_value(event.modifiers())

        if (self._move_count == 0 or target != self._move_target
                or buttons != self._move_buttons or modifiers != self._move_modifiers):
            self.flush_mouse_move()
            self._move_start_time = now
            self._move_start_monotonic = monotonic
            self._move_start_position = position
            self._move_target = target
            self._move_buttons = buttons
            self._move_modifiers = modifiers
            self._move_count = 0

        self._move_end_time = now
        self._move_end_monotonic = monotonic
        self._move_end_position = position
        self._move_count += 1

    def flush_mouse_move(self) -> None:
        if self._move_count == 0:
            return
        self.logger.event("mouse_move_segment", {
            "target": self._move_target,
            "start_time": self._move_start_time,
            "end_time": self._move_end_time,
            "duration_ms": round((self._move_end_monotonic - self._move_start_monotonic) * 1000, 3),
            "start_position": self._move_start_position,
            "end_position": self._move_end_position,
            "buttons": self._move_buttons,
            "modifiers": self._move_modifiers,
            "event_count": self._move_count,
        })
        self._move_start_time = None
        self._move_start_monotonic = None
        self._move_start_position = None
        self._move_end_time = None
        self._move_end_monotonic = None
        self._move_end_position = None
        self._move_target = None
        self._move_buttons = None
        self._move_modifiers = None
        self._move_count = 0


def build_logger(base_dir: Path, args) -> DebugLogger:
    """根据命令行参数创建日志器。"""
    if not args.log:
        return DebugLogger(base_dir)

    any_category = args.log_events or args.log_api or args.log_state
    return DebugLogger(
        base_dir,
        enabled=True,
        events=args.log_events or not any_category,
        api=args.log_api or not any_category,
        state=args.log_state or not any_category,
        mouse_move=args.log_mouse_move,
    )
