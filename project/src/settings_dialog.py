from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


# main_window.py keeps the dialog dependency local; expose QDialog there when this module is loaded.
_main_window = sys.modules.get("src.main_window")
if _main_window is not None:
    _main_window.QDialog = QDialog


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

        self.fixed_radio = QRadioButton("固定增加位数", self)
        self.threshold_radio = QRadioButton("自动按容量阈值增加位数", self)
        self.fixed_radio.setChecked(config.export.number_width_mode == "fixed")
        self.threshold_radio.setChecked(config.export.number_width_mode == "threshold")

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.fixed_radio)
        self.mode_group.addButton(self.threshold_radio)

        self.extra_spin = QSpinBox(self)
        self.extra_spin.setRange(0, 5)
        self.extra_spin.setValue(config.export.number_width_extra)
        self.extra_spin.setSuffix(" 位")
        self.extra_spin.setToolTip("在表示全部导出切片所需的最少位数基础上，再增加 0~5 位。")

        self.threshold_spin = QSpinBox(self)
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(config.export.number_width_threshold)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setToolTip("当前位数容量使用率超过该百分比时，编号位数增加 1 位。")

        self.fixed_detail = QLabel("例如：11 个切片需要 2 位；增加 1 位后使用 3 位。")
        self.fixed_detail.setWordWrap(True)
        self.threshold_detail = QLabel(
            "例如：阈值 50% 时，6 个切片使用 2 位，49 个切片使用 2 位，"
            "80 个切片使用 3 位；100% 表示始终使用表示总数所需的最少位数。"
        )
        self.threshold_detail.setWordWrap(True)

        fixed_row = QHBoxLayout()
        fixed_row.addWidget(QLabel("额外位数："))
        fixed_row.addWidget(self.extra_spin)
        fixed_row.addStretch()

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("容量阈值："))
        threshold_row.addWidget(self.threshold_spin)
        threshold_row.addStretch()

        numbering_widget = QWidget(self)
        numbering_layout = QVBoxLayout(numbering_widget)
        numbering_layout.setContentsMargins(0, 0, 0, 0)
        numbering_layout.addWidget(self.fixed_radio)
        numbering_layout.addLayout(fixed_row)
        numbering_layout.addWidget(self.fixed_detail)
        numbering_layout.addSpacing(8)
        numbering_layout.addWidget(self.threshold_radio)
        numbering_layout.addLayout(threshold_row)
        numbering_layout.addWidget(self.threshold_detail)

        self.fixed_radio.toggled.connect(self._update_numbering_controls)
        self.threshold_radio.toggled.connect(self._update_numbering_controls)
        self._update_numbering_controls()

        form = QFormLayout(self)
        form.addRow("导出位置：", output_row)
        form.addRow("", self.delete_source)
        form.addRow("", self.default_naming)
        form.addRow("编号数位数：", numbering_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _update_numbering_controls(self) -> None:
        fixed = self.fixed_radio.isChecked()
        self.extra_spin.setEnabled(fixed)
        self.threshold_spin.setEnabled(not fixed)

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
        self.config.export.number_width_mode = "fixed" if self.fixed_radio.isChecked() else "threshold"
        self.config.export.number_width_extra = self.extra_spin.value()
        self.config.export.number_width_threshold = self.threshold_spin.value()
        self.config.save()
        self.accept()
