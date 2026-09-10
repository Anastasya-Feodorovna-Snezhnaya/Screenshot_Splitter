from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QPushButton


class SettingsDialog(QDialog):
    """应用设置窗口，目前提供导出相关设置。"""

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置")
        self.setModal(True)

        self.output_edit = QLineEdit(config.export.output_directory, self)
        self.output_edit.setPlaceholderText("留空：使用原图所在目录")
        browse = QPushButton("浏览…", self)
        browse.clicked.connect(self._browse_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        output_row.addWidget(browse)

        self.delete_source = QCheckBox("导出成功后将原图移至回收站", self)
        self.delete_source.setChecked(config.export.delete_source_after_export)
        self.default_naming = QCheckBox("切片导出使用默认命名", self)
        self.default_naming.setChecked(config.export.use_default_naming)

        form = QFormLayout(self)
        form.addRow("导出位置：", output_row)
        form.addRow("", self.delete_source)
        form.addRow("", self.default_naming)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse_output(self) -> None:
        current = self.output_edit.text().strip()
        directory = current if Path(current).is_dir() else ""
        selected = QFileDialog.getExistingDirectory(self, "选择导出位置", directory)
        if selected:
            self.output_edit.setText(str(Path(selected).resolve()))

    def _save(self) -> None:
        value = self.output_edit.text().strip()
        if value and not Path(value).is_dir():
            Path(value).mkdir(parents=True, exist_ok=True)
        self.config.export.output_directory = value
        self.config.export.delete_source_after_export = self.delete_source.isChecked()
        self.config.export.use_default_naming = self.default_naming.isChecked()
        self.config.save()
        self.accept()
