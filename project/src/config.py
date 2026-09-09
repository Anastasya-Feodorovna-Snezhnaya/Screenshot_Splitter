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
    zoom_100: str = "1"


class ConfigManager:
    """负责应用配置的加载和持久化。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.path = self.base_dir / "settings.json"
        self.shortcuts = ShortcutConfig()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            shortcut_data = data.get("shortcuts", {})
            valid = set(asdict(self.shortcuts))
            for key, value in shortcut_data.items():
                if key in valid and isinstance(value, str) and value:
                    setattr(self.shortcuts, key, value.upper())
        except (OSError, ValueError, TypeError):
            # 配置文件无效时恢复默认配置，不阻止程序启动。
            self.shortcuts = ShortcutConfig()

    def save(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        data = {"shortcuts": asdict(self.shortcuts)}
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
