from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen, QPalette
from PySide6.QtWidgets import QAbstractScrollArea

from .model import DocumentState, SplitLine


class ImageCanvas(QAbstractScrollArea):
    """图片预览与交互区域。"""

    regionSelected = Signal(int)
    splitLineSelected = Signal(int)
    splitLineMoved = Signal(int, int)
    splitLineCreated = Signal(int)
    splitLineDeleted = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self._image: Optional[QImage] = None
        self._state: Optional[DocumentState] = None
        self.zoom = 1.0

        self._pan_active = False
        self._pan_last = QPointF()
        self._pan_button: Optional[Qt.MouseButton] = None
        self._line_drag_index: Optional[int] = None
        self._selected_line: Optional[int] = None
        self._selected_region: Optional[int] = None

        self._add_line_modifier = Qt.KeyboardModifier.NoModifier
        self._add_line_key = Qt.Key.Key_S

    def set_document(self, image: QImage, state: DocumentState) -> None:
        self._image = image
        self._state = state
        self.zoom = 1.0
        self._selected_line = None
        self._selected_region = None
        self._update_scrollbars()
        self.viewport().update()

    def set_add_line_shortcut(self, key: Qt.Key, modifier: Qt.KeyboardModifier) -> None:
        self._add_line_key = key
        self._add_line_modifier = modifier

    def image_point(self, pos: QPointF) -> QPointF:
        """把预览区域坐标转换为原图像素坐标。"""
        x = (pos.x() + self.horizontalScrollBar().value()) / self.zoom
        y = (pos.y() + self.verticalScrollBar().value()) / self.zoom
        return QPointF(x, y)

    def viewport_point_from_image_y(self, y: int) -> float:
        return y * self.zoom - self.verticalScrollBar().value()

    def _update_scrollbars(self) -> None:
        if not self._image:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        width = max(1, round(self._image.width() * self.zoom))
        height = max(1, round(self._image.height() * self.zoom))
        self.horizontalScrollBar().setRange(0, max(0, width - self.viewport().width()))
        self.verticalScrollBar().setRange(0, max(0, height - self.viewport().height()))
        self.horizontalScrollBar().setPageStep(self.viewport().width())
        self.verticalScrollBar().setPageStep(self.viewport().height())

    def resizeEvent(self, event) -> None:
        self._update_scrollbars()
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:
        if not self._image:
            return

        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()
            if delta != 0:
                anchor = event.position()
                image_anchor = self.image_point(anchor)
                factor = 1.1 if delta > 0 else 1.0 / 1.1
                self._set_zoom(self.zoom * factor, anchor, image_anchor)
            event.accept()
            return

        delta = event.angleDelta()
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
        event.accept()

    def mousePressEvent(self, event) -> None:
        if not self._image or not self._state:
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_pan(event)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            image_y = self.image_point(event.position()).y()
            line_index = self._hit_line(image_y)
            if line_index is not None:
                self._selected_line = line_index
                self._line_drag_index = line_index
                self.splitLineSelected.emit(line_index)
            else:
                self._selected_line = None
                self._selected_region = self._region_at_y(int(image_y))
                if self._selected_region is not None:
                    self.regionSelected.emit(self._selected_region)
                # 左键拖动图片，单击仍然保留区域选择功能。
                self._start_pan(event)
            self.viewport().update()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._image or not self._state:
            return

        if self._line_drag_index is not None:
            y = round(self.image_point(event.position()).y())
            self._move_line(self._line_drag_index, y)
            event.accept()
            return

        if self._pan_active:
            delta = event.position() - self._pan_last
            # 滚动条向鼠标移动的反方向移动，从而产生直接拖动画布的效果。
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - round(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - round(delta.y())
            )
            self._pan_last = event.position()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == self._pan_button:
            self._stop_pan()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._line_drag_index = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if not self._state:
            return super().keyPressEvent(event)

        if event.key() == self._add_line_key and event.modifiers() == self._add_line_modifier:
            y = round(self.image_point(self.mapFromGlobal(self.cursor().pos())).y())
            self._create_line(y)
            event.accept()
            return

        if self._selected_line is not None:
            if event.key() == Qt.Key.Key_Up:
                step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
                self._move_line(
                    self._selected_line,
                    self._state.normalized_lines()[self._selected_line] - step,
                )
                event.accept()
                return
            if event.key() == Qt.Key.Key_Down:
                step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
                self._move_line(
                    self._selected_line,
                    self._state.normalized_lines()[self._selected_line] + step,
                )
                event.accept()
                return
            if event.key() == Qt.Key.Key_Delete:
                y = self._state.normalized_lines()[self._selected_line]
                self._state.split_lines = [line for line in self._state.split_lines if line.y != y]
                self._selected_line = None
                self.splitLineDeleted.emit(y)
                self.viewport().update()
                event.accept()
                return

        super().keyPressEvent(event)

    def _start_pan(self, event) -> None:
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
        lines = self._state.normalized_lines()
        tolerance = max(5, int(5 / max(self.zoom, 0.01)))
        for i, line_y in enumerate(lines):
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
        zoom = max(0.05, min(8.0, zoom))
        self.zoom = zoom
        self._update_scrollbars()
        target_x = round(image_anchor.x() * zoom - viewport_anchor.x())
        target_y = round(image_anchor.y() * zoom - viewport_anchor.y())
        self.horizontalScrollBar().setValue(max(0, target_x))
        self.verticalScrollBar().setValue(max(0, target_y))
        self.viewport().update()

    def set_zoom(self, zoom: float) -> None:
        center = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        anchor = self.image_point(center)
        self._set_zoom(zoom, center, anchor)

    def fit_to_window(self) -> None:
        if not self._image:
            return
        if self._image.width() == 0 or self._image.height() == 0:
            return
        zx = self.viewport().width() / self._image.width()
        zy = self.viewport().height() / self._image.height()
        self.zoom = max(0.05, min(1.0, min(zx, zy)))
        self._update_scrollbars()
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)
        self.viewport().update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.viewport().rect(), self.palette().dark())

        if not self._image or not self._state:
            return

        image_rect = self._image.rect()
        target = image_rect
        target.setWidth(round(image_rect.width() * self.zoom))
        target.setHeight(round(image_rect.height() * self.zoom))
        target.translate(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())
        painter.drawImage(target, self._image)

        # 删除区域只作为预览层显示，不修改原图。
        for region in self._state.regions():
            if not region.keep:
                top = round(region.top * self.zoom) - self.verticalScrollBar().value()
                bottom = round(region.bottom * self.zoom) - self.verticalScrollBar().value()
                painter.fillRect(0, top, self.viewport().width(), bottom - top, self.palette().mid())

        # 在原图上方绘制分割线。
        for i, y in enumerate(self._state.normalized_lines()):
            screen_y = round(y * self.zoom) - self.verticalScrollBar().value()
            pen = QPen(self.palette().highlight(), 2 if i == self._selected_line else 1)
            painter.setPen(pen)
            painter.drawLine(0, screen_y, self.viewport().width(), screen_y)

        # 当前选中区域只绘制边框，不修改原图。
        if self._selected_region is not None:
            regions = self._state.regions()
            if 0 <= self._selected_region < len(regions):
                r = regions[self._selected_region]
                top = round(r.top * self.zoom) - self.verticalScrollBar().value()
                bottom = round(r.bottom * self.zoom) - self.verticalScrollBar().value()
                painter.setPen(QPen(self.palette().highlight(), 1))
                painter.drawRect(
                    0,
                    top,
                    max(0, round(self._image.width() * self.zoom) - 1),
                    bottom - top - 1,
                )
