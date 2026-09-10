from __future__ import annotations

from dataclasses import fields

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout,
)

from .config import ConfigManager, ShortcutConfig


DISPLAY_NAMES = {
    "add_split_line": "添加水平分割线",
    "toggle_region": "切换区域保留/删除",
    "delete_split_line": "删除选中分割线",
    "undo": "撤销",
    # 保留 redo 配置键以兼容已有 settings.json；当前快捷键执行恢复初始编辑状态。
    "redo": "恢复初始状态",
    "move_line_up": "分割线向上 1px",
    "move_line_down": "分割线向下 1px",
    "move_line_up_fast": "分割线向上 10px",
    "move_line_down_fast": "分割线向下 10px",
    "fit_window": "适应窗口",
    "zoom_100": "原始尺寸",
}


class ShortcutEditDialog(QDialog):
    """快捷键查看和编辑对话框。"""

    def __init__(self, config: ConfigManager, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("快捷键设置")
        self.resize(520, 460)

        self.edits: dict[str, QLineEdit] = {}
        form = QFormLayout()

        for field in fields(ShortcutConfig):
            key = field.name
            edit = QLineEdit(getattr(config.shortcuts, key))
            edit.setPlaceholderText("例如 Ctrl+Z、Space、S；留空表示禁用")
            self.edits[key] = edit
            form.addRow(DISPLAY_NAMES.get(key, key), edit)

        note = QLabel(
            "保存前会检查快捷键格式和重复绑定。留空可禁用对应快捷键；"
            "保存失败时会保留原配置。"
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        sequence = QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText)
        if sequence.isEmpty():
            return ""
        return sequence.toString(QKeySequence.SequenceFormat.PortableText).upper()

    def _save(self) -> None:
        values: dict[str, str] = {}
        invalid: list[str] = []
        for field in fields(ShortcutConfig):
            key = field.name
            raw = self.edits[key].text().strip()
            if not raw:
                values[key] = ""
                continue
            normalized = self._normalize(raw)
            if not normalized:
                invalid.append(f"{DISPLAY_NAMES.get(key, key)}：{raw}")
            else:
                values[key] = normalized

        if invalid:
            QMessageBox.warning(
                self,
                "快捷键无效",
                "以下快捷键无法解析：\n" + "\n".join(invalid),
            )
            return

        duplicates: dict[str, list[str]] = {}
        for key, value in values.items():
            if value:
                duplicates.setdefault(value, []).append(key)
        duplicate_values = [value for value, keys in duplicates.items() if len(keys) > 1]
        if duplicate_values:
            QMessageBox.warning(
                self,
                "快捷键冲突",
                "以下快捷键被多个功能使用：\n" + "\n".join(duplicate_values),
            )
            return

        old_values = {field.name: getattr(self.config.shortcuts, field.name) for field in fields(ShortcutConfig)}
        for key, value in values.items():
            setattr(self.config.shortcuts, key, value)
        try:
            self.config.save()
        except OSError as exc:
            for key, value in old_values.items():
                setattr(self.config.shortcuts, key, value)
            QMessageBox.critical(self, "保存失败", f"无法保存快捷键配置：{exc}")
            return
        self.accept()
