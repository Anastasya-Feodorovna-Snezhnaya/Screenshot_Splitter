from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QInputDialog,
    QLineEdit,
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
        self._shortcuts: dict[str, QShortcut] = {}

        self.setWindowTitle("Screenshot Splitter")
        self.resize(1200, 800)

        self.canvas = ImageCanvas(self)
        self.canvas.set_mask_opacity(self.config.preview.mask_opacity)
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
        fit_action.setToolTip("恢复为适应窗口并将图片整体居中")
        fit_action.triggered.connect(self._fit_window)
        toolbar.addAction(fit_action)

        original_size_action = QAction("原始尺寸", self)
        original_size_action.setToolTip("以原图 1:1 像素比例显示")
        original_size_action.triggered.connect(self._original_size)
        toolbar.addAction(original_size_action)

        mask_action = QAction("遮罩设置", self)
        mask_action.setToolTip("调整删除区域的预览遮罩透明度")
        mask_action.triggered.connect(self.edit_mask_opacity)
        toolbar.addAction(mask_action)

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

    def _fit_window(self) -> None:
        self.canvas.fit_to_window()
        self._refresh_status("已适应窗口并居中")

    def _original_size(self) -> None:
        self.canvas.set_zoom(1.0)
        self._refresh_status("已恢复原始尺寸")

    def edit_mask_opacity(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("遮罩设置")
        dialog.setLabelText("遮罩透明度（输入 0-100，可不输入 %）：")
        dialog.setInputMode(QInputDialog.InputMode.TextInput)
        dialog.setTextValue(str(self.config.preview.mask_opacity))
        dialog.setOkButtonText("确定")
        dialog.setCancelButtonText("取消")

        line_edit = dialog.findChild(QLineEdit)
        if line_edit is not None:
            line_edit.setPlaceholderText("例如：55 或 55%")

        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return

        text = dialog.textValue().strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            value = int(text)
        except ValueError:
            QMessageBox.warning(self, "输入无效", "请输入 0 到 100 之间的整数，可带 %。")
            return

        if not 0 <= value <= 100:
            QMessageBox.warning(self, "输入无效", "请输入 0 到 100 之间的整数。")
            return

        self.config.preview.mask_opacity = value
        self.config.save()
        self.canvas.set_mask_opacity(value)
        self._refresh_status(f"遮罩透明度：{value}%")

    def _toggle_region(self) -> None:
        index = self.canvas._selected_region
        regions = self.state.regions()
        if index is None or not (0 <= index < len(regions)):
            return
        if index in self.state.deleted_regions:
            self.state.deleted_regions.remove(index)
        else:
            self.state.deleted_regions.add(index)
        self.canvas.viewport().update()
        self._refresh_status(
            f"区域 {index + 1}：{'保留' if index not in self.state.deleted_regions else '删除'}"
        )

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

    def edit_shortcuts(self) -> None:
        dialog = ShortcutEditDialog(self.config, self)
        if dialog.exec():
            self._refresh_shortcuts()

    def _refresh_shortcuts(self) -> None:
        for shortcut in self._shortcuts.values():
            shortcut.deleteLater()
        self._shortcuts.clear()

        # 所有可配置快捷键统一使用 QShortcut 注册，而不是依赖某个窗口的
        # keyPressEvent。这样快捷键焦点位于画布、工具栏或输入控件附近时，
        # 行为仍保持一致。
        handlers = {
            "fit_window": self._fit_window,
            "zoom_100": self._original_size,
            "toggle_region": self._toggle_region,
        }
        for name, handler in handlers.items():
            value = getattr(self.config.shortcuts, name).strip()
            if not value:
                continue
            shortcut = QShortcut(QKeySequence(value), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts[name] = shortcut

        value = self.config.shortcuts.add_split_line.strip().upper()
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
