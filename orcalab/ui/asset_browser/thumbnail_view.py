from typing import List, Dict
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.asset_browser.thumbnail_model import ThumbnailModel
from orcalab.ui.text_util import split_text_to_lines
from orcalab.ui.theme_service import ThemeService


class _ThumbnailViewItem:
    def __init__(self):
        self.index = 0
        self.cell_rect = QtCore.QRect()
        self.content_rect = QtCore.QRect()


class ThumbnailView(QtWidgets.QWidget):

    selection_changed = QtCore.Signal()
    right_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)

        self._scroll_bar = QtWidgets.QScrollBar(self)
        self._scroll_bar.setOrientation(QtCore.Qt.Orientation.Vertical)
        self.scrollbar_width = 8

        self._model: ThumbnailModel | None = None

        self.visible_items: List[_ThumbnailViewItem] = []

        # content padding

        self.cell_padding_left = 4
        self.cell_padding_right = 4
        self.cell_padding_top = 4
        self.cell_padding_bottom = 4
        self.cell_image_text_spacing = 4

        self.cell_content_padding_top = 4
        self.cell_content_padding_bottom = 4

        # thumbnail is square
        self.cell_image_size = 96

        self.cell_text_line = 2
        self.cell_text_width = 96 + 16

        self._compute_cell_size()
        self._update_content_layout()

        theme = ThemeService()
        self.bg_color = theme.get_color("bg")
        self.bg_hover_color = theme.get_color("bg_hover")
        self.text_color = theme.get_color("text")

        self._hover_item: _ThumbnailViewItem | None = None
        self._selected_item: _ThumbnailViewItem | None = None

        self._left_mouse_pressed_pos: QtCore.QPoint | None = None
        self._left_click_item: _ThumbnailViewItem | None = None

        self._dragging = False
        
        self._movies: Dict[int, QtGui.QMovie] = {}
        
        self._loading_text: str | None = None

    def set_model(self, model: ThumbnailModel):
        self._model = model
        self._on_model_updated()
        self._model.data_updated.connect(self._on_model_updated)
        self._model.item_updated.connect(self._on_item_updated)
    
    def set_loading_text(self, text: str | None):
        self._loading_text = text
        self.update()

    def item_count(self) -> int:
        return self._model.size() if self._model else 0

    def _item_at(self, pos: QtCore.QPoint) -> _ThumbnailViewItem | None:
        for item in self.visible_items:
            if item.content_rect.contains(pos):
                return item
        return None

    def item_at(self, pos: QtCore.QPoint) -> int:
        item = self._item_at(pos)
        return item.index if item else -1

    def selected_index(self) -> int:
        return self._selected_item.index if self._selected_item else -1

    def hovered_index(self) -> int:
        return self._hover_item.index if self._hover_item else -1

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setPen(self.text_color)

        self._draw_background(painter, self.rect())
        
        if self._loading_text:
            font = painter.font()
            font.setPointSize(14)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self._loading_text)
            return

        for item in self.visible_items:
            self._draw_cell(painter, item)

    def resizeEvent(self, event):
        self._update_content_layout()
        self._update_scrollbar()
        self._update_visible_items()
        self.update()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if self._scroll_bar.isVisible():
            delta = event.angleDelta().y()
            if delta > 0:
                step = -self._scroll_bar.pageStep()
            else:
                step = self._scroll_bar.pageStep()
            new_value = self._scroll_bar.value() + step
            self._scroll_bar.setValue(new_value)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        pos = event.position().toPoint()

        item = self._item_at(pos)
        if item and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._left_mouse_pressed_pos = pos
            self._left_click_item = item

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            assert self._dragging == False

            # update selection
            if self._selected_item != self._left_click_item:
                self._selected_item = self._left_click_item
                self.selection_changed.emit()
                self._update_playing_state()  # 更新动画播放状态
                self.update()

            self._left_mouse_pressed_pos = None
            self._left_click_item = None

        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            self.right_clicked.emit()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        pos = event.position().toPoint()
        item = self._item_at(pos)
        if self._hover_item != item:
            self._hover_item = item
            self._update_playing_state()  # 更新动画播放状态
            self.update()

        if not self._dragging and self._left_mouse_pressed_pos:
            distance = (pos - self._left_mouse_pressed_pos).manhattanLength()
            if distance >= QtWidgets.QApplication.startDragDistance():
                self._dragging = True
                self._drag_started()
    
    def leaveEvent(self, event: QtCore.QEvent):
        """鼠标离开时停止所有动画"""
        if self._hover_item:
            self._hover_item = None
            self._update_playing_state()
            self.update()

    # Override `_drag_started`` to start a drag operation.
    # Dragging end when mouse release. However, there is no mouse release event.
    # (Because dragging is handled by the OS once started.)
    # After dragging ends, make sure to call `_drag_ended`` to clean up.

    def _drag_started(self):
        # print("Drag started")

        self._drag_ended()

    def _drag_ended(self):
        # print("Drag ended")

        self._dragging = False
        self._left_mouse_pressed_pos = None
        self._left_click_item = None

    def _compute_cell_size(self):
        self.cell_width = self.cell_padding_left + self.cell_padding_right
        self.cell_width = self.cell_width + self.cell_text_width

        self.cell_height = self.cell_padding_top + self.cell_padding_bottom
        self.cell_height = self.cell_height + self.cell_content_padding_top
        self.cell_height = self.cell_height + self.cell_content_padding_bottom
        self.cell_height = self.cell_height + self.cell_image_size
        self.cell_height = self.cell_height + self.cell_image_text_spacing

        font_metrics = QtGui.QFontMetrics(self.font())
        self.cell_text_height = font_metrics.height() * self.cell_text_line
        self.cell_height = self.cell_height + self.cell_text_height

    def _update_content_layout(self):
        content_width = self.width() - self.scrollbar_width

        self.column_count = max(1, content_width // self.cell_width)
        self.row_count = (
            self.item_count() + self.column_count - 1
        ) // self.column_count

        # 把剩余空间均分到间隙中
        total_spacing = content_width - (self.column_count * self.cell_width)
        spacing_per_column = total_spacing // (self.column_count + 1)

        self.column_lefts = []
        for col in range(self.column_count):
            left = col * (self.cell_width + spacing_per_column)
            self.column_lefts.append(left)

    def _update_scrollbar(self):
        visible_height = self.height()
        total_content_height = self.row_count * self.cell_height

        if total_content_height > visible_height:
            self._scroll_bar.setVisible(True)
            self._scroll_bar.setGeometry(
                self.width() - self.scrollbar_width,
                0,
                self.scrollbar_width,
                self.height(),
            )
            self._scroll_bar.setMinimum(0)
            self._scroll_bar.setMaximum(total_content_height - visible_height)
            self._scroll_bar.setPageStep(self.cell_height // 2)
            self._scroll_bar.valueChanged.connect(self._on_scrollbar_value_changed)
        else:
            self._scroll_bar.setVisible(False)
            self._scroll_bar.setValue(0)

    def _update_visible_items(self):
        self.visible_items.clear()

        offset_y = self._scroll_bar.value()

        start_row = offset_y // self.cell_height
        end_row = (offset_y + self.height()) // self.cell_height + 1

        visible_indices = set()
        for row in range(start_row, min(end_row, self.row_count)):
            for col in range(self.column_count):
                index = row * self.column_count + col
                if index < self.item_count():
                    item = _ThumbnailViewItem()
                    item.index = index
                    item.cell_rect = QtCore.QRect(
                        self.column_lefts[col],
                        row * self.cell_height - offset_y,
                        self.cell_width,
                        self.cell_height,
                    )
                    item.content_rect = item.cell_rect.adjusted(
                        self.cell_padding_left,
                        self.cell_padding_top,
                        -self.cell_padding_right,
                        -self.cell_padding_bottom,
                    )
                    self.visible_items.append(item)
                    visible_indices.add(index)
        
        self._update_movies(visible_indices)

    def _draw_background(self, painter: QtGui.QPainter, rect: QtCore.QRect):
        painter.fillRect(rect, self.bg_color)

    def _draw_cell(self, painter: QtGui.QPainter, item: _ThumbnailViewItem):
        content_rect = item.content_rect

        bg_color = self.bg_color
        if self._selected_item == item:
            bg_color = self.bg_hover_color
        elif self._hover_item == item:
            bg_color = self.bg_hover_color

        painter.fillRect(content_rect, bg_color)

        if self._selected_item == item:
            painter.drawRect(item.cell_rect)

        content_center = content_rect.center()

        image_rect = QtCore.QRect(0, 0, self.cell_image_size, self.cell_image_size)
        image_rect.moveCenter(content_center)
        image_rect.moveTop(content_rect.top() + self.cell_content_padding_top)

        self._draw_image(painter, image_rect, item)

        text_rect = QtCore.QRect(
            content_rect.left(),
            image_rect.bottom() + self.cell_image_text_spacing,
            self.cell_text_width,
            self.cell_text_height,
        )

        self._draw_text(painter, text_rect, item)

    def _draw_image(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, item: _ThumbnailViewItem
    ):

        if not self._model:
            return

        if item.index in self._movies:
            player = self._movies[item.index]
            pixmap = player.current_pixmap()
            if not pixmap.isNull():  
                x = rect.x() + (rect.width() - pixmap.width()) // 2
                y = rect.y() + (rect.height() - pixmap.height()) // 2             
                painter.drawPixmap(x, y, pixmap)
                return
        
        image = self._model.image_at(item.index)
        if not image or image.isNull():
            return

        # 静态图片也进行等比缩放和居中绘制
        scaled_image = image.scaled(
            rect.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        x = rect.x() + (rect.width() - scaled_image.width()) // 2
        y = rect.y() + (rect.height() - scaled_image.height()) // 2
        painter.drawImage(x, y, scaled_image)

    def _draw_text(
        self, painter: QtGui.QPainter, rect: QtCore.QRect, item: _ThumbnailViewItem
    ):
        if not self._model:
            return

        text = self._model.text_at(item.index)
        if not text:
            return

        font_metrics = QtGui.QFontMetrics(self.font())
        text_height = font_metrics.height()

        lines = split_text_to_lines(
            text,
            self.font(),
            rect.width(),
            self.cell_text_line,
        )

        for i, line in enumerate(lines):
            line_rect = QtCore.QRect(
                rect.left(),
                rect.top() + i * text_height,
                rect.width(),
                text_height,
            )

            painter.drawText(
                line_rect,
                QtCore.Qt.AlignmentFlag.AlignCenter,
                line,
            )

    def _on_scrollbar_value_changed(self, value: int):
        self._update_visible_items()
        self.update()

    def _on_model_updated(self):
        self._clear_all_movies()
        self._update_content_layout()
        self._update_scrollbar()
        self._update_visible_items()
        self.update()
    
    def _on_item_updated(self, index: int):
        for item in self.visible_items:
            if item.index == index:
                self.update(item.cell_rect)
                break
    
    def _update_movies(self, visible_indices: set):
        """更新可见的动画（加载但不启动）"""
        indices_to_remove = set(self._movies.keys()) - visible_indices
        for index in indices_to_remove:
            self._unload_movie(index)
        
        if not self._model:
            return
        
        # 加载可见的动画（但不启动）
        for index in visible_indices:
            if index not in self._movies:
                player = self._model.movie_at(index)
                if player:
                    self._load_movie(index, player)
        
        # 更新播放状态（只播放选中或悬停的）
        self._update_playing_state()
    
    def _load_movie(self, index: int, player):
        """加载动画但不启动播放"""
        self._movies[index] = player
        player.frame_changed.connect(lambda: self._on_movie_frame_changed(index))
    
    def _unload_movie(self, index: int):
        """卸载动画"""
        if index in self._movies:
            player = self._movies[index]
            player.stop()
            try:
                player.frame_changed.disconnect()
            except:
                pass
            del self._movies[index]
    
    def _update_playing_state(self):
        """更新动画播放状态：只播放选中或悬停的"""
        should_play_indices = set()
        
        # 选中的项应该播放
        if self._selected_item:
            should_play_indices.add(self._selected_item.index)
        
        # 悬停的项应该播放
        if self._hover_item:
            should_play_indices.add(self._hover_item.index)
        
        # 停止不应该播放的动画
        for index, player in self._movies.items():
            if index in should_play_indices:
                if not player.is_playing:
                    player.start()
            else:
                if player.is_playing:
                    player.stop()
    
    def _clear_all_movies(self):
        for index in list(self._movies.keys()):
            self._unload_movie(index)
    
    def _on_movie_frame_changed(self, index: int):
        for item in self.visible_items:
            if item.index == index:
                self.update(item.cell_rect)
                break
