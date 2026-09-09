from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QToolBar, QVBoxLayout,
    QWidget, QInputDialog, QLineEdit,
)

from .config import ConfigManager
from .exporter import export_regions
from .image_canvas import ImageCanvas
from .logger import DebugLogger
from .model import DocumentState
from .shortcut_dialog import ShortcutEditDialog


class MainWindow(QMainWindow):
    """主编辑窗口。"""

    def __init__(self, config: ConfigManager, logger: DebugLogger | None = None) -> None:
        super().__init__()
        self.config = config
        self.logger = logger or DebugLogger(Path.cwd())
        self.state = DocumentState()
        self.source_image = QImage()
        self._shortcuts: dict[str, QShortcut] = {}

        self.setWindowTitle("Screenshot Splitter")
        self.resize(1200, 800)

        self.canvas = ImageCanvas(self)
        self.canvas.logger = self.logger
        self.canvas.set_mask_opacity(self.config.preview.mask_opacity)
        self.status = QLabel("未打开图片")
        self._build_ui()
        self._refresh_shortcuts()
        self._log_state("window_initialized")

    def _log_api(self, name: str, data: dict | None = None) -> None:
        self.logger.api(name, data)

    def _log_state(self, name: str) -> None:
        if not self.logger.state_enabled:
            return
        regions = self.state.regions()
        self.logger.state(name, {
            "image_path": self.state.image_path,
            "image_size": [self.state.image_width, self.state.image_height],
            "zoom": self.canvas.zoom,
            "selected_region": self.canvas._selected_region,
            "selected_line": self.canvas._selected_line,
            "split_lines": self.state.normalized_lines(),
            "deleted_regions": [list(item) for item in sorted(self.state.deleted_regions)],
            "regions": [{"top": r.top, "bottom": r.bottom, "keep": r.keep} for r in regions],
            "mask_opacity": self.canvas.mask_opacity,
        })

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
        self.canvas.splitLineCreated.connect(self._on_split_line_created)
        self.canvas.splitLineMoved.connect(self._on_split_line_moved)
        self.canvas.splitLineDeleted.connect(self._on_split_line_deleted)

    def open_image(self) -> None:
        self._log_api("open_image.begin")
        path, _ = QFileDialog.getOpenFileName(self, "选择 PNG 长截图", "", "PNG 图片 (*.png)")
        if not path:
            self._log_api("open_image.cancelled")
            return
        image = QImage(path)
        if image.isNull():
            self._log_api("open_image.failed", {"path": path, "reason": "invalid_image"})
            QMessageBox.critical(self, "打开失败", "无法读取该 PNG 文件。")
            return
        self.source_image = image
        self.state = DocumentState(image_path=str(Path(path).resolve()), image_width=image.width(), image_height=image.height())
        self.canvas.set_document(image, self.state)
        self.canvas.fit_to_window()
        self._refresh_status()
        self._log_api("open_image.success", {"path": str(Path(path).resolve()), "size": [image.width(), image.height()]})
        self._log_state("image_opened")

    def _fit_window(self) -> None:
        self._log_api("fit_window.begin")
        self.canvas.fit_to_window()
        self._refresh_status("已适应窗口并居中")
        self._log_api("fit_window.end", {"zoom": self.canvas.zoom})
        self._log_state("fit_window")

    def _original_size(self) -> None:
        self._log_api("original_size.begin")
        self.canvas.set_zoom(1.0)
        self._refresh_status("已恢复原始尺寸")
        self._log_api("original_size.end", {"zoom": self.canvas.zoom})
        self._log_state("original_size")

    def edit_mask_opacity(self) -> None:
        self._log_api("edit_mask_opacity.begin")
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
            self._log_api("edit_mask_opacity.cancelled")
            return
        text = dialog.textValue().strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            value = int(text)
        except ValueError:
            self._log_api("edit_mask_opacity.invalid", {"input": text})
            QMessageBox.warning(self, "输入无效", "请输入 0 到 100 之间的整数，可带 %。")
            return
        if not 0 <= value <= 100:
            self._log_api("edit_mask_opacity.invalid", {"input": text, "value": value})
            QMessageBox.warning(self, "输入无效", "请输入 0 到 100 之间的整数。")
            return
        self.config.preview.mask_opacity = value
        self.config.save()
        self.canvas.set_mask_opacity(value)
        self._refresh_status(f"遮罩透明度：{value}%")
        self._log_api("edit_mask_opacity.success", {"value": value})
        self._log_state("mask_opacity_changed")

    def _toggle_region(self) -> None:
        self._log_api("toggle_region.begin", {"selected_region": self.canvas._selected_region})
        index = self.canvas._selected_region
        regions = self.state.regions()
        if index is None or not (0 <= index < len(regions)):
            self._log_api("toggle_region.ignored", {"reason": "no_selected_region"})
            return

        region = regions[index]
        key = (region.top, region.bottom)
        if key in self.state.deleted_regions:
            self.state.deleted_regions.remove(key)
            keep = True
        else:
            self.state.deleted_regions.add(key)
            keep = False
        self.canvas.viewport().update()
        self._refresh_status(f"区域 {index + 1}：{'保留' if keep else '删除'}")
        self._log_api("toggle_region.end", {"region": index, "bounds": list(key), "keep": keep})
        self._log_state("region_toggled")

    def _on_region_selected(self, index: int) -> None:
        self._refresh_status(f"当前区域：{index + 1}")
        self._log_api("region_selected", {"index": index})
        self._log_state("region_selected")

    def _on_line_selected(self, index: int) -> None:
        lines = self.state.normalized_lines()
        if 0 <= index < len(lines):
            self._refresh_status(f"选中分割线：Y={lines[index]} px")
            self._log_api("split_line_selected", {"index": index, "y": lines[index]})
            self._log_state("split_line_selected")

    def _on_split_line_created(self, y: int) -> None:
        # 新增内部边界不会影响已有区域的删除状态；边界记录保持在原有上下界上。
        self.state.discard_invalid_deleted_regions()
        self._refresh_status()
        self._log_api("split_line_created", {"y": y})
        self._log_state("split_line_created")

    def _on_split_line_moved(self, old_y: int, new_y: int) -> None:
        self.state.update_deleted_region_boundary(old_y, new_y)
        self.state.discard_invalid_deleted_regions()
        self._refresh_status()
        self._log_api("split_line_moved", {"old_y": old_y, "new_y": new_y})
        self._log_state("split_line_moved")

    def _on_split_line_deleted(self, y: int) -> None:
        # 删除边界后，所有不再对应实际区域的删除状态自动失效。
        self.state.discard_invalid_deleted_regions()
        self._refresh_status()
        self._log_api("split_line_deleted", {"y": y})
        self._log_state("split_line_deleted")

    def _refresh_status(self, prefix: str | None = None) -> None:
        regions = self.state.regions()
        kept = sum(r.keep for r in regions)
        self.status.setText(
            f"{prefix or '就绪'}    区域：{len(regions)}    保留：{kept}    "
            f"删除：{len(regions) - kept}    分割线：{len(self.state.normalized_lines())}    "
            f"缩放：{self.canvas.zoom * 100:.1f}%"
        )

    def edit_shortcuts(self) -> None:
        self._log_api("edit_shortcuts.begin")
        dialog = ShortcutEditDialog(self.config, self)
        if dialog.exec():
            self._refresh_shortcuts()
            self._log_api("edit_shortcuts.saved", {"shortcuts": self.config.shortcuts.__dict__})
        else:
            self._log_api("edit_shortcuts.cancelled")

    def _refresh_shortcuts(self) -> None:
        self._log_api("refresh_shortcuts.begin", {"shortcuts": self.config.shortcuts.__dict__})
        for shortcut in self._shortcuts.values():
            shortcut.deleteLater()
        self._shortcuts.clear()
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
        key_map = {"S": Qt.Key.Key_S, "A": Qt.Key.Key_A, "D": Qt.Key.Key_D, "L": Qt.Key.Key_L, "X": Qt.Key.Key_X}
        self.canvas.set_add_line_shortcut(key_map.get(value, Qt.Key.Key_S), Qt.KeyboardModifier.NoModifier)
        self._log_api("refresh_shortcuts.end", {"registered": list(self._shortcuts)})

    def export_all(self) -> None:
        self._log_api("export_all.begin", {"image_path": self.state.image_path})
        if not self.state.image_path:
            self._log_api("export_all.ignored", {"reason": "no_image"})
            QMessageBox.information(self, "没有图片", "请先打开一张 PNG 图片。")
            return
        output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not output_dir:
            self._log_api("export_all.cancelled")
            return
        try:
            outputs = export_regions(self.state, Path(output_dir))
        except Exception as exc:
            self._log_api("export_all.failed", {"error": str(exc), "output_dir": output_dir})
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self._log_api("export_all.success", {"count": len(outputs), "output_dir": output_dir})
        self._log_state("export_completed")
        QMessageBox.information(self, "导出完成", f"已导出 {len(outputs)} 个区域。\n目录：{output_dir}")
