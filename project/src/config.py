from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ShortcutConfig:
    """用户可配置的快捷键。"""

    add_split_line: str = "S"
    toggle_region: str = "SPACE"
    delete_split_line: str = "DELETE"
    undo: str = "CTRL+Z"
    redo: str = "CTRL+SHIFT+Z"
    move_line_up: str = "UP"
    move_line_down: str = "DOWN"
    move_line_up_fast: str = "SHIFT+UP"
    move_line_down_fast: str = "SHIFT+DOWN"
    fit_window: str = "F"
    zoom_100: str = "Y"


@dataclass
class PreviewConfig:
    """预览层的显示配置。"""

    mask_opacity: int = 55


@dataclass
class WindowConfig:
    """主窗口关闭时保存的窗口状态。"""

    fullscreen: bool = False
    x: int = -1
    y: int = -1
    width: int = 1200
    height: int = 800


@dataclass
class RecentConfig:
    """最近使用的路径。"""

    last_open_directory: str = ""


class ConfigManager:
    """负责应用配置的加载和持久化。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.path = self.base_dir / "settings.json"
        self.shortcuts = ShortcutConfig()
        self.preview = PreviewConfig()
        self.window = WindowConfig()
        self.recent = RecentConfig()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            shortcut_data = data.get("shortcuts", {})
            valid_shortcuts = set(asdict(self.shortcuts))
            for key, value in shortcut_data.items():
                if key in valid_shortcuts and isinstance(value, str) and value:
                    setattr(self.shortcuts, key, value.upper())

            preview_data = data.get("preview", {})
            opacity = preview_data.get("mask_opacity", self.preview.mask_opacity)
            if isinstance(opacity, int) and 0 <= opacity <= 100:
                self.preview.mask_opacity = opacity

            window_data = data.get("window", {})
            if isinstance(window_data.get("fullscreen"), bool):
                self.window.fullscreen = window_data["fullscreen"]
            for key in ("x", "y", "width", "height"):
                value = window_data.get(key)
                if isinstance(value, int):
                    setattr(self.window, key, value)

            recent_data = data.get("recent", {})
            last_open_directory = recent_data.get("last_open_directory", self.recent.last_open_directory)
            if isinstance(last_open_directory, str):
                self.recent.last_open_directory = last_open_directory
        except (OSError, ValueError, TypeError):
            # 配置文件无效时恢复默认配置，不阻止程序启动。
            self.shortcuts = ShortcutConfig()
            self.preview = PreviewConfig()
            self.window = WindowConfig()
            self.recent = RecentConfig()

    def save(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "shortcuts": asdict(self.shortcuts),
            "preview": asdict(self.preview),
            "window": asdict(self.window),
            "recent": asdict(self.recent),
        }
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
