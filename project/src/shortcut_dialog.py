from __future__ import annotations

from dataclasses import fields

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout
)

from .config import ConfigManager, ShortcutConfig


DISPLAY_NAMES = {
    "add_split_line": "添加水平分割线",
    "toggle_region": "切换区域保留/删除",
    "delete_split_line": "删除选中分割线",
    "undo": "撤销",
    "redo": "重做",
    "move_line_up": "分割线向上 1px",
    "move_line_down": "分割线向下 1px",
    "move_line_up_fast": "分割线向上 10px",
    "move_line_down_fast": "分割线向下 10px",
    "fit_window": "适应窗口",
    "zoom_100": "100% 缩放",
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
            edit.setPlaceholderText("例如 Ctrl+Z、Space、S")
            self.edits[key] = edit
            form.addRow(DISPLAY_NAMES.get(key, key), edit)

        note = QLabel("可直接输入 Qt 支持的快捷键文本。保存前会检查重复绑定。")
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

    def _save(self) -> None:
        values = {key: edit.text().strip().upper() for key, edit in self.edits.items()}
        values = {key: value for key, value in values.items() if value}

        duplicates = {}
        for key, value in values.items():
            duplicates.setdefault(value, []).append(key)
        duplicate_values = [value for value, keys in duplicates.items() if len(keys) > 1]
        if duplicate_values:
            QMessageBox.warning(
                self,
                "快捷键冲突",
                "以下快捷键被多个功能使用：\n" + "\n".join(duplicate_values),
            )
            return

        for key, value in values.items():
            setattr(self.config.shortcuts, key, value)
        self.config.save()
        self.accept()
