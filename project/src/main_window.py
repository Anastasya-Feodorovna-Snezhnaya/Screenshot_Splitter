from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QToolBar, QVBoxLayout, QWidget
)

from .config import ConfigManager
from .exporter import export_regions
from .image_canvas import ImageCanvas
from .model import DocumentState
from .shortcut_dialog import ShortcutEditDialog


class MainWindow(QMainWindow):
    """主编辑窗口。"""

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self.config = config
        self.state = DocumentState()
        self.source_image = QImage()
        self._fit_shortcut: QShortcut | None = None

        self.setWindowTitle("Screenshot Splitter")
        self.resize(1200, 800)

        self.canvas = ImageCanvas(self)
        self.status = QLabel("未打开图片")
        self._build_ui()
        self._refresh_shortcuts()

    def _build_ui(self) -> None:
        toolbar = QToolBar("工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("打开", self)
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)

        fit_action = QAction("适应窗口", self)
        fit_action.triggered.connect(self.canvas.fit_to_window)
        toolbar.addAction(fit_action)

        zoom_action = QAction("100%", self)
        zoom_action.triggered.connect(lambda: self.canvas.set_zoom(1.0))
        toolbar.addAction(zoom_action)

        export_action = QAction("导出全部", self)
        export_action.triggered.connect(self.export_all)
        toolbar.addAction(export_action)

        shortcut_action = QAction("设置快捷键", self)
        shortcut_action.triggered.connect(self.edit_shortcuts)
        toolbar.addAction(shortcut_action)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        layout.addWidget(self.status)
        self.setCentralWidget(central)

        self.canvas.regionSelected.connect(self._on_region_selected)
        self.canvas.splitLineSelected.connect(self._on_line_selected)
        self.canvas.splitLineCreated.connect(lambda _y: self._refresh_status())
        self.canvas.splitLineMoved.connect(lambda _a, _b: self._refresh_status())
        self.canvas.splitLineDeleted.connect(lambda _y: self._refresh_status())

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 PNG 长截图", "", "PNG 图片 (*.png)"
        )
        if not path:
            return

        image = QImage(path)
        if image.isNull():
            QMessageBox.critical(self, "打开失败", "无法读取该 PNG 文件。")
            return

        self.source_image = image
        self.state = DocumentState(
            image_path=str(Path(path).resolve()),
            image_width=image.width(),
            image_height=image.height(),
        )
        self.canvas.set_document(image, self.state)
        self.canvas.fit_to_window()
        self._refresh_status()

    def _on_region_selected(self, index: int) -> None:
        self._refresh_status(f"当前区域：{index + 1}")

    def _on_line_selected(self, index: int) -> None:
        lines = self.state.normalized_lines()
        if 0 <= index < len(lines):
            self._refresh_status(f"选中分割线：Y={lines[index]} px")

    def _refresh_status(self, prefix: str | None = None) -> None:
        regions = self.state.regions()
        kept = sum(r.keep for r in regions)
        text = (
            f"{prefix or '就绪'}    "
            f"区域：{len(regions)}    "
            f"保留：{kept}    "
            f"删除：{len(regions) - kept}    "
            f"分割线：{len(self.state.normalized_lines())}    "
            f"缩放：{self.canvas.zoom * 100:.1f}%"
        )
        self.status.setText(text)

    def keyPressEvent(self, event) -> None:
        # QMainWindow 统一处理未被画布消耗的全局快捷键。
        key = self._shortcut_text(event)
        shortcuts = self.config.shortcuts

        if key == shortcuts.toggle_region:
            index = self.canvas._selected_region
            if index is not None and 0 <= index < len(self.state.regions()):
                if index in self.state.deleted_regions:
                    self.state.deleted_regions.remove(index)
                else:
                    self.state.deleted_regions.add(index)
                self.canvas.viewport().update()
                self._refresh_status(
                    f"区域 {index + 1}：{'保留' if index not in self.state.deleted_regions else '删除'}"
                )
                event.accept()
                return

        if key == shortcuts.fit_window:
            self.canvas.fit_to_window()
            self._refresh_status("已适应窗口")
            event.accept()
            return
        if key == shortcuts.zoom_100:
            self.canvas.set_zoom(1.0)
            self._refresh_status("缩放：100%")
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _shortcut_text(event) -> str:
        sequence = QKeySequence(event.modifiers() | event.key())
        return sequence.toString(QKeySequence.SequenceFormat.NativeText).upper().replace(" ", "")

    def edit_shortcuts(self) -> None:
        dialog = ShortcutEditDialog(self.config, self)
        if dialog.exec():
            self._refresh_shortcuts()

    def _refresh_shortcuts(self) -> None:
        # 使用 QShortcut，使 F 在画布获得键盘焦点时也能触发。
        if self._fit_shortcut is not None:
            self._fit_shortcut.deleteLater()
        self._fit_shortcut = QShortcut(QKeySequence(self.config.shortcuts.fit_window), self)
        self._fit_shortcut.activated.connect(self._fit_window_from_shortcut)

        # 当前添加分割线功能只支持简单的单键快捷键。
        value = self.config.shortcuts.add_split_line
        key_map = {
            "S": Qt.Key.Key_S,
            "A": Qt.Key.Key_A,
            "D": Qt.Key.Key_D,
            "L": Qt.Key.Key_L,
            "X": Qt.Key.Key_X,
        }
        self.canvas.set_add_line_shortcut(
            key_map.get(value, Qt.Key.Key_S),
            Qt.KeyboardModifier.NoModifier,
        )

    def _fit_window_from_shortcut(self) -> None:
        self.canvas.fit_to_window()
        self._refresh_status("已适应窗口")

    def export_all(self) -> None:
        if not self.state.image_path:
            QMessageBox.information(self, "没有图片", "请先打开一张 PNG 图片。")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            return

        try:
            outputs = export_regions(self.state, Path(output_dir))
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {len(outputs)} 个区域。\n目录：{output_dir}",
        )
