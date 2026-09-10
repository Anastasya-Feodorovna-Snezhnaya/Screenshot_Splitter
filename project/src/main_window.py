from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox, QToolBar, QVBoxLayout, QWidget, QInputDialog, QLineEdit

from .config import ConfigManager
from .exporter import export_regions
from .image_canvas import ImageCanvas
from .logger import DebugLogger
from .model import DocumentState
from .shortcut_dialog import ShortcutEditDialog


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigManager, logger: DebugLogger | None = None) -> None:
        super().__init__()
        self.config = config
        self.logger = logger or DebugLogger(Path.cwd())
        self.state = DocumentState()
        self.source_image = QImage()
        self._shortcuts: dict[str, QShortcut] = {}
        self._history: list[DocumentState] = []
        self._history_index = -1
        self._history_restoring = False
        self._close_image_action: QAction | None = None
        self.setWindowTitle("Screenshot Splitter")
        self.setAcceptDrops(True)
        self.resize(1200, 800)
        self._restore_window_state()
        self.canvas = ImageCanvas(self)
        self.canvas.set_mask_opacity(self.config.preview.mask_opacity)
        self.canvas.zoomChanged.connect(lambda _zoom: self._refresh_status("已缩放"))
        self.status = QLabel("未打开图片")
        self._build_ui()
        self._refresh_shortcuts()
        self._log_state("window_initialized")

    def _restore_window_state(self) -> None:
        width, height = self.config.window.width, self.config.window.height
        if width < 200 or height < 150:
            width, height = 1200, 800
        self.resize(width, height)
        if self.config.window.fullscreen:
            self.showFullScreen()
            return
        saved = QRect(self.config.window.x, self.config.window.y, width, height)
        screens = QGuiApplication.screens()
        if self.config.window.x < 0 or self.config.window.y < 0 or not any(saved.intersects(s.availableGeometry()) for s in screens):
            self._center_window()
        else:
            self.move(self.config.window.x, self.config.window.y)

    def _center_window(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.left() + (area.width() - self.width()) // 2, area.top() + (area.height() - self.height()) // 2)

    def _save_window_state(self) -> None:
        self.config.window.fullscreen = self.isFullScreen()
        if not self.isFullScreen():
            self.config.window.x, self.config.window.y = self.x(), self.y()
            self.config.window.width, self.config.window.height = self.width(), self.height()
        self.config.save()

    def closeEvent(self, event) -> None:
        self._save_window_state()
        super().closeEvent(event)

    def _log_state(self, name: str) -> None:
        if not self.logger.state_enabled:
            return
        self.logger.state(name, {
            "image_path": self.state.image_path,
            "image_size": [self.state.image_width, self.state.image_height],
            "zoom": self.canvas.zoom,
            "selected_line": self.canvas._selected_line,
            "split_lines": self.state.normalized_lines(),
            "deleted_regions": [list(x) for x in sorted(self.state.deleted_regions)],
            "regions": [{"top": r.top, "bottom": r.bottom, "keep": r.keep} for r in self.state.regions()],
            "mask_opacity": self.canvas.mask_opacity,
        })

    def _build_ui(self) -> None:
        toolbar = QToolBar("工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        open_action = QAction("打开", self)
        open_action.triggered.connect(lambda _checked=False: self.open_image())
        toolbar.addAction(open_action)
        self._close_image_action = QAction("关闭图片", self)
        self._close_image_action.setToolTip("关闭当前图片并放弃当前所有编辑状态")
        self._close_image_action.setEnabled(False)
        self._close_image_action.triggered.connect(self.close_image)
        toolbar.addAction(self._close_image_action)
        fit_action = QAction("适应窗口", self)
        fit_action.setToolTip("恢复为适应窗口并将图片整体居中")
        fit_action.triggered.connect(self._fit_window)
        toolbar.addAction(fit_action)
        original = QAction("原始尺寸", self)
        original.setToolTip("以原图 1:1 像素比例显示")
        original.triggered.connect(self._original_size)
        toolbar.addAction(original)
        mask = QAction("遮罩设置", self)
        mask.setToolTip("调整删除区域的预览遮罩透明度")
        mask.triggered.connect(self.edit_mask_opacity)
        toolbar.addAction(mask)
        export = QAction("导出全部", self)
        export.triggered.connect(self.export_all)
        toolbar.addAction(export)
        shortcuts = QAction("设置快捷键", self)
        shortcuts.triggered.connect(self.edit_shortcuts)
        toolbar.addAction(shortcuts)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        layout.addWidget(self.status)
        self.setCentralWidget(central)
        self.canvas.splitLineSelected.connect(self._on_line_selected)
        self.canvas.splitLineCreated.connect(self._on_split_line_created)
        self.canvas.splitLineMoved.connect(self._on_split_line_moved)
        self.canvas.splitLineMoveFinished.connect(self._on_split_line_move_finished)
        self.canvas.splitLineDeleted.connect(self._on_split_line_deleted)

    def _refresh_status(self, message: str | None = None) -> None:
        if not self.state.image_path:
            self.status.setText(message or "未打开图片")
            return
        regions = self.state.regions()
        kept = sum(r.keep for r in regions)
        self.status.setText(f"{message or '就绪'}    区域：{len(regions)}  保留：{kept}  删除：{len(regions)-kept}  分割线：{len(self.state.normalized_lines())}  缩放：{self.canvas.zoom*100:.1f}%")

    def open_image(self, path: str | None = None) -> None:
        if path is None:
            last_directory = self.config.recent.last_open_directory
            directory = last_directory if Path(last_directory).is_dir() else ""
            path, _ = QFileDialog.getOpenFileName(self, "选择 PNG 长截图", directory, "PNG 图片 (*.png)")
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.critical(self, "打开失败", "无法读取该 PNG 文件。")
            return
        resolved_path = Path(path).resolve()
        self.config.recent.last_open_directory = str(resolved_path.parent)
        self.config.save()
        self.source_image = image
        self.state = DocumentState(image_path=str(resolved_path), image_width=image.width(), image_height=image.height())
        self.canvas.set_document(image, self.state)
        self.canvas.fit_to_window()
        self._reset_history()
        self._refresh_status()
        if self._close_image_action is not None:
            self._close_image_action.setEnabled(True)
        self._log_state("image_opened")

    def close_image(self) -> None:
        if not self.state.image_path:
            return
        self.source_image = QImage()
        self.state = DocumentState()
        self.canvas.set_document(self.source_image, self.state)
        self._reset_history()
        self._refresh_status("已关闭图片")
        if self._close_image_action is not None:
            self._close_image_action.setEnabled(False)
        self._log_state("image_closed")

    def _reset_edit_state(self) -> None:
        if not self.state.image_path:
            return
        if not self.state.split_lines and not self.state.deleted_regions:
            self._refresh_status("已恢复初始状态")
            return
        self.state.split_lines.clear()
        self.state.deleted_regions.clear()
        self.canvas._selected_line = None
        self._record_history()
        self.canvas.viewport().update()
        self._refresh_status("已恢复初始状态")
        self._log_state("edit_state_reset")

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
        if line_edit:
            line_edit.setPlaceholderText("例如：55 或 55%")
        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return
        text = dialog.textValue().strip().rstrip("%").strip()
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
        if not self.state.image_path or QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            return
        pos = self.canvas.viewport().mapFromGlobal(QCursor.pos())
        if not self.canvas.viewport().rect().contains(pos):
            return
        p = self.canvas.image_point(pos)
        if not (0 <= p.x() < self.state.image_width and 0 <= p.y() < self.state.image_height):
            return
        index = self.canvas._region_at_y(int(p.y()))
        regions = self.state.regions()
        if index is None or not 0 <= index < len(regions):
            return
        region = regions[index]
        key = (region.top, region.bottom)
        keep = key in self.state.deleted_regions
        if keep:
            self.state.deleted_regions.remove(key)
        else:
            self.state.deleted_regions.add(key)
        self._record_history()
        self.canvas.viewport().update()
        self._refresh_status(f"区域 {index + 1}：{'保留' if keep else '删除'}")
        self._log_state("region_toggled")

    def _on_line_selected(self, index: int) -> None:
        lines = self.state.normalized_lines()
        if 0 <= index < len(lines):
            self._refresh_status(f"选中分割线：Y={lines[index]} px")

    def _on_split_line_created(self, y: int) -> None:
        self.state.discard_invalid_deleted_regions()
        self._record_history()
        self._refresh_status()
        self._log_state("split_line_created")

    def _on_split_line_moved(self, old_y: int, new_y: int) -> None:
        self.state.update_deleted_region_boundary(old_y, new_y)
        self.state.discard_invalid_deleted_regions()
        self._refresh_status()

    def _on_split_line_move_finished(self, old_y: int, new_y: int) -> None:
        if old_y != new_y:
            self._record_history()
        self._log_state("split_line_moved")

    def _on_split_line_deleted(self, y: int) -> None:
        self.state.discard_invalid_deleted_regions()
        self._record_history()
        self._refresh_status()
        self._log_state("split_line_deleted")

    def _clone_state(self) -> DocumentState:
        return deepcopy(self.state)

    def _reset_history(self) -> None:
        self._history = [self._clone_state()]
        self._history_index = 0

    def _record_history(self) -> None:
        if self._history_restoring:
            return
        snapshot = self._clone_state()
        if self._history and self._history[self._history_index] == snapshot:
            return
        self._history = self._history[:self._history_index + 1]
        self._history.append(snapshot)
        self._history_index += 1

    def _apply_history_snapshot(self, snapshot: DocumentState) -> None:
        zoom = self.canvas.zoom
        h, v = self.canvas.horizontalScrollBar().value(), self.canvas.verticalScrollBar().value()
        selected = self.canvas._selected_line
        self.state = deepcopy(snapshot)
        self.canvas.set_document(self.source_image, self.state)
        self.canvas.zoom = zoom
        self.canvas._update_scrollbars()
        self.canvas.horizontalScrollBar().setValue(h)
        self.canvas.verticalScrollBar().setValue(v)
        lines = self.state.normalized_lines()
        self.canvas._selected_line = selected if selected is not None and selected < len(lines) else None
        self.canvas.viewport().update()

    def _undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_restoring = True
        try:
            self._history_index -= 1
            self._apply_history_snapshot(self._history[self._history_index])
        finally:
            self._history_restoring = False
        self._refresh_status("已撤销")
        self._log_state("undo")

    def _redo(self) -> None:
        if self._history_index + 1 >= len(self._history):
            return
        self._history_restoring = True
        try:
            self._history_index += 1
            self._apply_history_snapshot(self._history[self._history_index])
        finally:
            self._history_restoring = False
        self._refresh_status("已重做")
        self._log_state("redo")

    def edit_shortcuts(self) -> None:
        dialog = ShortcutEditDialog(self.config, self)
        if dialog.exec():
            self._refresh_shortcuts()

    def _refresh_shortcuts(self) -> None:
        for shortcut in self._shortcuts.values():
            shortcut.deleteLater()
        self._shortcuts.clear()
        handlers = {
            "add_split_line": self._add_split_line_at_cursor,
            "toggle_region": self._toggle_region,
            "delete_split_line": self._delete_selected_line,
            "undo": self._undo,
            "redo": self._redo,
            "move_line_up": lambda: self._move_selected_line(-1),
            "move_line_down": lambda: self._move_selected_line(1),
            "move_line_up_fast": lambda: self._move_selected_line(-10),
            "move_line_down_fast": lambda: self._move_selected_line(10),
            "fit_window": self._fit_window,
            "zoom_100": self._original_size,
        }
        for name, handler in handlers.items():
            value = getattr(self.config.shortcuts, name).strip()
            if value:
                shortcut = QShortcut(QKeySequence(value), self)
                shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
                shortcut.activated.connect(handler)
                self._shortcuts[name] = shortcut

    def _add_split_line_at_cursor(self) -> None:
        if not self.state.image_path:
            return
        pos = self.canvas.viewport().mapFromGlobal(QCursor.pos())
        if self.canvas.viewport().rect().contains(pos):
            self.canvas._create_line(round(self.canvas.image_point(pos).y()))

    def _delete_selected_line(self) -> None:
        self.canvas.delete_selected_line()

    def _move_selected_line(self, delta: int) -> None:
        if not self.state.image_path or self.canvas._selected_line is None:
            return
        before = self._clone_state()
        self.canvas.move_selected_line(delta)
        if self.state != before:
            self._record_history()
            self._log_state("split_line_moved_by_shortcut")

    def export_all(self) -> None:
        if not self.state.image_path:
            QMessageBox.information(self, "没有图片", "请先打开一张 PNG 图片。")
            return
        output_dir = Path(self.config.export.output_directory).expanduser() if self.config.export.output_directory else Path(self.state.image_path).parent
        if not output_dir.is_dir():
            output_dir = Path(self.state.image_path).parent

        prefix = ""
        suffix = None
        if not self.config.export.use_default_naming:
            from .custom_exporter import export_regions_named
            from .rename_dialog import RenameDialog

            dialog = RenameDialog(self.config.export.custom_prefix, self.config.export.custom_suffix, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            prefix, suffix = dialog.prefix, dialog.suffix

        try:
            if suffix is None:
                outputs = export_regions(self.state, output_dir)
            else:
                outputs = export_regions_named(self.state, output_dir, prefix, suffix)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        if suffix is not None:
            self.config.export.custom_prefix = prefix
            self.config.export.custom_suffix = suffix
        self.config.save()

        deleted = False
        if self.config.export.delete_source_after_export:
            from .file_utils import move_to_recycle_bin
            try:
                move_to_recycle_bin(Path(self.state.image_path))
                deleted = True
            except Exception as exc:
                QMessageBox.warning(self, "原图处理失败", f"切片已经导出，但原图未能移至回收站。\n{exc}")

        message = f"已导出 {len(outputs)} 个区域。\n目录：{output_dir}"
        if deleted:
            self.close_image()
            message += "\n原图已移至回收站。"
        QMessageBox.information(self, "导出完成", message)

    def dragEnterEvent(self, event) -> None:
        if self.state.image_path or not event.mimeData().hasUrls():
            event.ignore()
            return
        if any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() == ".png" for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if self.state.image_path or not event.mimeData().hasUrls():
            event.ignore()
            return
        for u in event.mimeData().urls():
            if u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() == ".png":
                self.open_image(u.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()


# 在主窗口既有功能基础上追加“重置到初始化状态”和“设置”，避免改变已有控件的实现顺序。
_original_build_ui = MainWindow._build_ui


def _build_ui_with_settings(self: MainWindow) -> None:
    _original_build_ui(self)
    toolbar = self.findChildren(QToolBar)[0]
    self._reset_action = QAction("重置", self)
    self._reset_action.setToolTip("清除全部分割线和删除区域，恢复到刚打开图片时的编辑状态")
    self._reset_action.setEnabled(bool(self.state.image_path))
    self._reset_action.triggered.connect(self._reset_edit_state)
    toolbar.insertAction(toolbar.actions()[-2], self._reset_action)
    settings = QAction("设置", self)
    settings.triggered.connect(self.edit_settings)
    toolbar.addAction(settings)


MainWindow._build_ui = _build_ui_with_settings

_original_close_image = MainWindow.close_image


def _close_image_with_reset_button(self: MainWindow) -> None:
    _original_close_image(self)
    if hasattr(self, "_reset_action"):
        self._reset_action.setEnabled(False)


MainWindow.close_image = _close_image_with_reset_button

_original_open_image = MainWindow.open_image


def _open_image_with_reset_button(self: MainWindow, path: str | None = None) -> None:
    _original_open_image(self, path)
    if hasattr(self, "_reset_action"):
        self._reset_action.setEnabled(bool(self.state.image_path))


MainWindow.open_image = _open_image_with_reset_button


def _edit_settings(self: MainWindow) -> None:
    from .settings_dialog import SettingsDialog
    dialog = SettingsDialog(self.config, self)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        self._refresh_status("设置已保存")


MainWindow.edit_settings = _edit_settings
