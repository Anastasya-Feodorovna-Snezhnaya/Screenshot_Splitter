from __future__ import annotations

import re

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QLabel, QMessageBox


_WINDOWS_INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def validate_component(text: str, field_name: str) -> str | None:
    if any(ord(ch) < 32 for ch in text):
        return f"{field_name}包含 Windows 文件名不允许的控制字符。"
    match = _WINDOWS_INVALID_CHARS.search(text)
    if match:
        return f"{field_name}包含 Windows 文件名非法字符“{match.group(0)}”。\n非法字符：< > : \" / \\ | ? *"
    return None


class RenameDialog(QDialog):
    """输入本次导出的文件名前缀和后缀。"""

    def __init__(self, prefix: str, suffix: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出文件命名")
        self.setModal(True)

        self.prefix_edit = QLineEdit(prefix, self)
        self.suffix_edit = QLineEdit(suffix, self)
        self.suffix_edit.setPlaceholderText("例如：(n)")

        form = QFormLayout(self)
        form.addRow("前缀：", self.prefix_edit)
        form.addRow("后缀：", self.suffix_edit)
        form.addRow(QLabel("n 会替换为切片序号，例如：变长实参(n).png"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validate_and_accept(self) -> None:
        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()

        error = validate_component(prefix, "前缀")
        if error:
            QMessageBox.warning(self, "输入无效", error)
            self.prefix_edit.setFocus()
            return

        error = validate_component(suffix, "后缀")
        if error:
            QMessageBox.warning(self, "输入无效", error)
            self.suffix_edit.setFocus()
            return

        if "n" not in suffix:
            QMessageBox.warning(self, "输入无效", "后缀必须包含小写字母 n，n 会被替换为切片序号。")
            self.suffix_edit.setFocus()
            return

        stem = f"{prefix}{suffix.replace('n', '1')}"
        if not stem or stem.endswith((".", " ")):
            QMessageBox.warning(self, "输入无效", "生成的 Windows 文件名不能以空格或句点结尾。")
            self.suffix_edit.setFocus()
            return

        if stem.split(".", 1)[0].upper() in _RESERVED_NAMES:
            QMessageBox.warning(self, "输入无效", "生成的文件名不能使用 Windows 保留设备名，例如 CON、PRN、AUX、NUL、COM1、LPT1。")
            self.prefix_edit.setFocus()
            return

        self.accept()

    @property
    def prefix(self) -> str:
        return self.prefix_edit.text()

    @property
    def suffix(self) -> str:
        return self.suffix_edit.text()
