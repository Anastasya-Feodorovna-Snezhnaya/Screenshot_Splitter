from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPalette, QGuiApplication, QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QAbstractScrollArea, QWidget

from .model import DocumentState, SplitLine


class _CanvasViewport(QWidget):
    def __init__(self, canvas: "ImageCanvas") -> None:
        super().__init__(canvas)
        self.canvas = canvas

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.canvas._handle_wheel_event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.canvas._handle_mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.canvas._handle_mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.canvas._handle_mouse_release(event)


class ImageCanvas(QAbstractScrollArea):
    """图片预览与分割线交互区域。"""

    splitLineSelected = Signal(int)
    splitLineMoved = Signal(int, int)
    splitLineMoveFinished = Signal(int, int)
    splitLineCreated = Signal(int)
    splitLineDeleted = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self.setViewport(_CanvasViewport(self))
        self._image: Optional[QImage] = None
        self._state: Optional[DocumentState] = None
        self.zoom = 1.0
        self.mask_opacity = 55
        self._pan_active = False
        self._pan_last = QPointF()
        self._pan_button: Optional[Qt.MouseButton] = None
        self._line_drag_index: Optional[int] = None
        self._line_drag_old_y: Optional[int] = None
        self._selected_line: Optional[int] = None

    def set_document(self, image: QImage, state: DocumentState) -> None:
        self._stop_pan()
        self._image = image
        self._state = state
        self.zoom = 1.0
        self._selected_line = None
        self._line_drag_index = None
        self._line_drag_old_y = None
        self._update_scrollbars()
        self.center_image()
        self.viewport().update()

    def set_mask_opacity(self, opacity: int) -> None:
        self.mask_opacity = max(0, min(100, int(opacity)))
        self.viewport().update()

    def image_point(self, pos: QPointF) -> QPointF:
        return QPointF((pos.x() + self.horizontalScrollBar().value()) / self.zoom, (pos.y() + self.verticalScrollBar().value()) / self.zoom)

    def _update_scrollbars(self) -> None:
        if not self._image:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        width = max(1, round(self._image.width() * self.zoom))
        height = max(1, round(self._image.height() * self.zoom))
        half_w = self.viewport().width() // 2
        half_h = self.viewport().height() // 2
        self.horizontalScrollBar().setRange(-half_w, width - half_w)
        self.verticalScrollBar().setRange(-half_h, height - half_h)
        self.horizontalScrollBar().setPageStep(self.viewport().width())
        self.verticalScrollBar().setPageStep(self.viewport().height())
        self.horizontalScrollBar().setSingleStep(20)
        self.verticalScrollBar().setSingleStep(20)

    def center_image(self) -> None:
        if not self._image:
            return
        width = round(self._image.width() * self.zoom)
        height = round(self._image.height() * self.zoom)
        self.horizontalScrollBar().setValue(round((width - self.viewport().width()) / 2))
        self.verticalScrollBar().setValue(round((height - self.viewport().height()) / 2))
        self.viewport().update()

    def resizeEvent(self, event) -> None:
        old_h = self.horizontalScrollBar().value()
        old_v = self.verticalScrollBar().value()
        self._update_scrollbars()
        self.horizontalScrollBar().setValue(old_h)
        self.verticalScrollBar().setValue(old_v)
        super().resizeEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._handle_wheel_event(event)

    def _handle_wheel_event(self, event: QWheelEvent) -> None:
        """Alt+滚轮缩放；普通滚轮明确不执行任何操作。"""
        if not self._image:
            event.accept()
            return
        modifiers = event.modifiers() | QGuiApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.AltModifier:
            delta = event.angleDelta().y() or event.angleDelta().x() or event.pixelDelta().y() or event.pixelDelta().x()
            if delta:
                anchor = QPointF(event.position())
                self._set_zoom(self.zoom * (1.1 ** (delta / 120.0)), anchor, self.image_point(anchor))
        event.accept()

    def _handle_mouse_press(self, event: QMouseEvent) -> None:
        if not self._image or not self._state:
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_pan(event)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            image_point = self.image_point(event.position())
            line_index = self._hit_line(image_point.y())
            if line_index is not None:
                self._selected_line = line_index
                self._line_drag_index = line_index
                self._line_drag_old_y = self._state.normalized_lines()[line_index]
                self.splitLineSelected.emit(line_index)
            else:
                self._selected_line = None
                self._start_pan(event)
            self.viewport().update()
            event.accept()
            return
        event.ignore()

    def _handle_mouse_move(self, event: QMouseEvent) -> None:
        if not self._image or not self._state:
            event.ignore()
            return
        if self._line_drag_index is not None:
            self._move_line(self._line_drag_index, round(self.image_point(event.position()).y()))
            event.accept()
            return
        if self._pan_active:
            delta = event.position() - self._pan_last
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
            self._pan_last = event.position()
            event.accept()
            return
        event.ignore()

    def _handle_mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == self._pan_button:
            self._stop_pan()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._line_drag_index is not None:
            old_y = self._line_drag_old_y
            new_y = self._state.normalized_lines()[self._line_drag_index] if self._state else old_y
            self._line_drag_index = None
            self._line_drag_old_y = None
            if old_y is not None and new_y is not None:
                self.splitLineMoveFinished.emit(old_y, new_y)
            event.accept()
            return
        event.ignore()

    def _start_pan(self, event: QMouseEvent) -> None:
        self._pan_active = True
        self._pan_button = event.button()
        self._pan_last = event.position()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _stop_pan(self) -> None:
        self._pan_active = False
        self._pan_button = None
        self.unsetCursor()

    def _hit_line(self, y: float) -> Optional[int]:
        if not self._state:
            return None
        tolerance = max(5, int(5 / max(self.zoom, 0.01)))
        for i, line_y in enumerate(self._state.normalized_lines()):
            if abs(y - line_y) <= tolerance:
                return i
        return None

    def _region_at_y(self, y: int) -> Optional[int]:
        if not self._state:
            return None
        regions = self._state.regions()
        for i, region in enumerate(regions):
            if region.top <= y < region.bottom:
                return i
        return len(regions) - 1 if regions else None

    def _create_line(self, y: int) -> None:
        if not self._state:
            return
        y = max(1, min(self._state.image_height - 1, y))
        if y not in self._state.normalized_lines():
            self._state.split_lines.append(SplitLine(y))
            self._state.split_lines.sort(key=lambda item: item.y)
            self.splitLineCreated.emit(y)
            self.viewport().update()

    def delete_selected_line(self) -> None:
        if not self._state or self._selected_line is None:
            return
        lines = self._state.normalized_lines()
        if not 0 <= self._selected_line < len(lines):
            return
        y = lines[self._selected_line]
        self._state.split_lines = [line for line in self._state.split_lines if line.y != y]
        self._selected_line = None
        self.splitLineDeleted.emit(y)
        self.viewport().update()

    def move_selected_line(self, delta: int) -> None:
        if not self._state or self._selected_line is None:
            return
        lines = self._state.normalized_lines()
        if 0 <= self._selected_line < len(lines):
            self._move_line(self._selected_line, lines[self._selected_line] + delta)

    def _move_line(self, index: int, y: int) -> None:
        if not self._state:
            return
        lines = self._state.normalized_lines()
        if not 0 <= index < len(lines):
            return
        lower = lines[index - 1] + 1 if index > 0 else 1
        upper = lines[index + 1] - 1 if index + 1 < len(lines) else self._state.image_height - 1
        new_y = max(lower, min(upper, int(y)))
        old_y = lines[index]
        if new_y == old_y:
            return
        for line in self._state.split_lines:
            if line.y == old_y:
                line.y = new_y
                break
        self._state.split_lines.sort(key=lambda item: item.y)
        self._selected_line = self._state.normalized_lines().index(new_y)
        self.splitLineMoved.emit(old_y, new_y)
        self.viewport().update()

    def _set_zoom(self, zoom: float, viewport_anchor: QPointF, image_anchor: QPointF) -> None:
        if not self._image:
            return
        new_zoom = max(0.05, min(8.0, zoom))
        if abs(new_zoom - self.zoom) < 1e-9:
            return
        self.zoom = new_zoom
        self._update_scrollbars()
        self.horizontalScrollBar().setValue(round(image_anchor.x() * self.zoom - viewport_anchor.x()))
        self.verticalScrollBar().setValue(round(image_anchor.y() * self.zoom - viewport_anchor.y()))
        self.viewport().update()

    def set_zoom(self, zoom: float) -> None:
        center = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        self._set_zoom(zoom, center, self.image_point(center))

    def fit_to_window(self) -> None:
        if not self._image or not self._image.width() or not self._image.height():
            return
        zx = self.viewport().width() / self._image.width()
        zy = self.viewport().height() / self._image.height()
        self.zoom = max(0.05, min(1.0, min(zx, zy)))
        self._update_scrollbars()
        self.center_image()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.viewport().rect(), self.palette().dark())
        if not self._image or not self._state:
            return
        image_width = round(self._image.width() * self.zoom)
        image_height = round(self._image.height() * self.zoom)
        left = -self.horizontalScrollBar().value()
        top_offset = -self.verticalScrollBar().value()
        target = self._image.rect()
        target.setWidth(image_width)
        target.setHeight(image_height)
        target.translate(left, top_offset)
        painter.drawImage(target, self._image)
        if self.mask_opacity > 0:
            mask = self.palette().mid().color()
            mask.setAlpha(round(255 * self.mask_opacity / 100))
            for region in self._state.regions():
                if not region.keep:
                    region_top = round(region.top * self.zoom) + top_offset
                    region_bottom = round(region.bottom * self.zoom) + top_offset
                    painter.fillRect(left, region_top, image_width, region_bottom - region_top, mask)
        for i, y in enumerate(self._state.normalized_lines()):
            screen_y = round(y * self.zoom) + top_offset
            painter.setPen(QPen(self.palette().highlight(), 2 if i == self._selected_line else 1))
            painter.drawLine(left, screen_y, left + image_width, screen_y)
