from __future__ import annotations

from typing import Callable, List

from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.perf_log import perf_timer
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.styled_widget import StyledWidget
from orcalab.ui.theme_service import ThemeService


class SectionHeader(QtWidgets.QWidget):

    clicked = QtCore.Signal()

    _CHEVRON_SIZE = 16
    _ICON_SIZE = 16
    _HPADDING = 4

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        title: str = "",
        icon: QtGui.QIcon | None = None,
        badge: str = "",
        indent_level: int = 0,
        has_children: bool = True,
    ):
        super().__init__(parent)
        self._title = title
        self._icon = icon
        self._badge = badge
        self._indent_level = indent_level
        self._has_children = has_children
        self._collapsed = True
        self._hovered = False
        self._selected = False

        self._fs = FontService()
        self._fs_cb_id = self._fs.on_scale_changed(self._on_font_scale_changed)
        self._fs.bind_widget_font(self, "collapsible_header")

        fm = self.fontMetrics()
        self._row_height = max(fm.height() + 8, 24)
        self.setFixedHeight(self._row_height)
        self.setMouseTracking(True)

    def _on_font_scale_changed(self):
        fm = self.fontMetrics()
        self._row_height = max(fm.height() + 8, 24)
        self.setFixedHeight(self._row_height)

    def _draw_branch_indicator(self, painter: QtGui.QPainter, x: int, rect: QtCore.QRect):
        indicator_size = self._CHEVRON_SIZE
        indicator_rect = QtCore.QRect(x, (rect.height() - indicator_size) // 2, indicator_size, indicator_size)

        option = QtWidgets.QStyleOptionViewItem()
        option.rect = indicator_rect  # type: ignore[assignment]
        option.state = QtWidgets.QStyle.StateFlag.State_Children  # type: ignore[assignment]

        if not self._collapsed:
            option.state |= QtWidgets.QStyle.StateFlag.State_Open  # type: ignore[assignment]

        if self._hovered:
            option.state |= QtWidgets.QStyle.StateFlag.State_MouseOver  # type: ignore[assignment]

        if self._selected:
            option.state |= QtWidgets.QStyle.StateFlag.State_Selected  # type: ignore[assignment]

        self.style().drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_IndicatorBranch,
            option,
            painter,
            self,
        )

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def set_title(self, title: str):
        self._title = title
        self.update()

    def set_badge(self, badge: str):
        self._badge = badge
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        theme = ThemeService()
        rect = self.rect()

        if self._selected:
            painter.fillRect(rect, theme.get_color("bg_selection"))
        elif self._hovered:
            painter.fillRect(rect, theme.get_color("bg_hover"))

        x = self._HPADDING + self._indent_level * 20

        if self._has_children:
            self._draw_branch_indicator(painter, x, rect)
        x += self._CHEVRON_SIZE + 4

        if self._icon is not None:
            icon_pixmap = self._icon.pixmap(self._ICON_SIZE, self._ICON_SIZE)
            icon_rect = QtCore.QRect(x, (rect.height() - self._ICON_SIZE) // 2, self._ICON_SIZE, self._ICON_SIZE)
            painter.drawPixmap(icon_rect, icon_pixmap)
            x += self._ICON_SIZE + 4

        painter.setPen(QtGui.QPen(theme.get_color("text")))
        font = self.font()
        painter.setFont(font)

        fm = QtGui.QFontMetrics(font)
        total_available = rect.width() - x - self._HPADDING

        title_width = fm.horizontalAdvance(self._title)
        badge_width = 0
        if self._badge:
            badge_full_width = fm.horizontalAdvance(self._badge) + 8
            badge_width = min(badge_full_width, max(total_available - title_width - 4, 0))

        title_available = total_available - badge_width if self._badge else total_available
        title_text = fm.elidedText(self._title, QtCore.Qt.TextElideMode.ElideRight, title_available)
        text_rect = QtCore.QRect(x, 0, title_available, rect.height())
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, title_text)

        if self._badge and badge_width > 0:
            badge_x = rect.width() - self._HPADDING - badge_width
            painter.setPen(QtGui.QPen(theme.get_color("text_disable")))
            badge_font = FontService().apply_font_modifiers("badge_text", font)
            painter.setFont(badge_font)
            badge_rect = QtCore.QRect(badge_x, 0, badge_width, rect.height())
            badge_text = fm.elidedText(self._badge, QtCore.Qt.TextElideMode.ElideMiddle, badge_width)
            painter.drawText(badge_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, badge_text)

        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def paint_at(
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        title: str,
        icon: QtGui.QIcon | None = None,
        badge: str = "",
        collapsed: bool = True,
        has_children: bool = True,
        hovered: bool = False,
        selected: bool = False,
        indent_level: int = 0,
        widget: QtWidgets.QWidget | None = None,
        tail_items: list[tuple[str, QtGui.QIcon]] | None = None,
        show_divider: bool = True,
    ) -> dict[str, QtCore.QRect]:
        theme = ThemeService()

        if selected:
            painter.fillRect(rect, theme.get_color("bg_selection"))
        elif hovered:
            painter.fillRect(rect, theme.get_color("bg_hover"))

        if show_divider:
            split_color = theme.get_color("split_line")
            painter.setPen(QtGui.QPen(split_color))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        x = rect.x() + 4 + indent_level * 20
        chevron_size = 16
        icon_size = 16

        if has_children:
            indicator_rect = QtCore.QRect(x, rect.y() + (rect.height() - chevron_size) // 2, chevron_size, chevron_size)
            option = QtWidgets.QStyleOptionViewItem()
            option.rect = indicator_rect  # type: ignore[assignment]
            option.state = QtWidgets.QStyle.StateFlag.State_Children  # type: ignore[assignment]
            if not collapsed:
                option.state |= QtWidgets.QStyle.StateFlag.State_Open  # type: ignore[assignment]
            if hovered:
                option.state |= QtWidgets.QStyle.StateFlag.State_MouseOver  # type: ignore[assignment]
            if selected:
                option.state |= QtWidgets.QStyle.StateFlag.State_Selected  # type: ignore[assignment]

            style = QtWidgets.QApplication.style() if widget is None else widget.style()
            style.drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_IndicatorBranch,
                option,
                painter,
                widget,
            )
            x += chevron_size + 4

        if icon is not None:
            icon_pixmap = icon.pixmap(icon_size, icon_size)
            icon_rect = QtCore.QRect(x, rect.y() + (rect.height() - icon_size) // 2, icon_size, icon_size)
            painter.drawPixmap(icon_rect, icon_pixmap)
            x += icon_size + 4

        tail_rects: dict[str, QtCore.QRect] = {}
        tail_width = 0
        if tail_items:
            tail_icon_size = max(12, rect.height() - 8)
            gap = 2
            right_edge = rect.x() + rect.width() - 4
            for item_id, item_icon in reversed(tail_items):
                right_edge -= tail_icon_size
                item_rect = QtCore.QRect(right_edge, rect.y() + (rect.height() - tail_icon_size) // 2, tail_icon_size, tail_icon_size)
                item_pixmap = item_icon.pixmap(tail_icon_size, tail_icon_size)
                painter.drawPixmap(item_rect, item_pixmap)
                tail_rects[item_id] = item_rect
                right_edge -= gap
            tail_width = len(tail_items) * tail_icon_size + (len(tail_items) - 1) * gap

        painter.setPen(QtGui.QPen(theme.get_color("text")))
        font = painter.font()
        fm = QtGui.QFontMetrics(font)
        total_available = rect.width() - (x - rect.x()) - 4 - tail_width

        title_width = fm.horizontalAdvance(title)
        badge_width = 0
        if badge:
            badge_full_width = fm.horizontalAdvance(badge) + 8
            badge_width = min(badge_full_width, max(total_available - title_width - 4, 0))

        title_available = total_available - badge_width if badge else total_available
        title_text = fm.elidedText(title, QtCore.Qt.TextElideMode.ElideRight, title_available)
        text_rect = QtCore.QRect(x, rect.y(), title_available, rect.height())
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, title_text)

        if badge and badge_width > 0:
            badge_x = rect.x() + rect.width() - 4 - tail_width - badge_width
            painter.setPen(QtGui.QPen(theme.get_color("text_disable")))
            badge_font = FontService().apply_font_modifiers("badge_text", font)
            painter.setFont(badge_font)
            badge_rect = QtCore.QRect(badge_x, rect.y(), badge_width, rect.height())
            badge_text = fm.elidedText(badge, QtCore.Qt.TextElideMode.ElideMiddle, badge_width)
            painter.drawText(badge_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, badge_text)

        return tail_rects


class CollapsibleSection(StyledWidget):

    collapsed_changed = QtCore.Signal(bool)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        title: str = "",
        icon: QtGui.QIcon | None = None,
        badge: str = "",
        collapsed: bool = True,
        content_factory: Callable[[], QtWidgets.QWidget] | None = None,
        children_factory: Callable[[], List["CollapsibleSection"]] | None = None,
        indent_level: int = 0,
    ):
        super().__init__(parent)

        self._title = title
        self._icon = icon
        self._badge = badge
        self._indent_level = indent_level
        self._content_factory = content_factory
        self._children_factory = children_factory
        self._content_widget: QtWidgets.QWidget | None = None
        self._children: List["CollapsibleSection"] | None = None
        self._collapsed = collapsed

        has_children = content_factory is not None or children_factory is not None

        self._header = SectionHeader(
            self,
            title=title,
            icon=icon,
            badge=badge,
            indent_level=indent_level,
            has_children=has_children,
        )
        self._header.set_collapsed(collapsed)
        self._header.clicked.connect(self._on_header_clicked)

        # 创建分隔线
        self._divider = QtWidgets.QFrame()
        self._divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self._divider.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self._divider.hide()

        self._content_area = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(4, 2, 4, 2)
        self._content_layout.setSpacing(1)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._divider)
        root_layout.addWidget(self._content_area)

        if collapsed:
            self._content_area.hide()
        else:
            self._lazy_create_content()
            self._update_divider()

    @property
    def header(self) -> SectionHeader:
        return self._header

    @property
    def content_widget(self) -> QtWidgets.QWidget | None:
        return self._content_widget

    @property
    def children_sections(self) -> List["CollapsibleSection"] | None:
        return self._children

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def _on_header_clicked(self):
        self.toggle_collapse()

    def _lazy_create_content(self):
        if self._content_factory is not None and self._content_widget is None:
            with perf_timer(f"CollapsibleSection.lazy_create({self._title})", feature="SECTION"):
                self._content_widget = self._content_factory()
                self._content_layout.addWidget(self._content_widget)

        if self._children_factory is not None and self._children is None:
            with perf_timer(f"CollapsibleSection.lazy_children({self._title})", feature="SECTION"):
                self._children = self._children_factory()
                for child in self._children:
                    self._content_layout.addWidget(child)
        
        self._update_divider()

    def _update_divider(self):
        # 只有当展开且有内容时才显示分隔线
        has_content = self._content_widget is not None or (self._children and len(self._children) > 0)
        if not self._collapsed and has_content:
            self._divider.show()
            # 设置分隔线颜色 - 使用样式表，参考 line.py
            theme = ThemeService()
            color = theme.get_color_hex("split_line")
            self._divider.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {color};
                    color: {color};
                }}
                """
            )
        else:
            self._divider.hide()

    def expand(self):
        if not self._collapsed:
            return
        self._lazy_create_content()
        self._collapsed = False
        self._content_area.show()
        self._header.set_collapsed(False)
        self._update_divider()
        self.collapsed_changed.emit(False)

    def collapse(self):
        if self._collapsed:
            return
        self._collapsed = True
        self._content_area.hide()
        self._header.set_collapsed(True)
        self._update_divider()
        self.collapsed_changed.emit(True)

    def toggle_collapse(self):
        if self._collapsed:
            self.expand()
        else:
            self.collapse()

    def set_title(self, title: str):
        self._title = title
        self._header.set_title(title)

    def set_badge(self, badge: str):
        self._badge = badge
        self._header.set_badge(badge)

    def set_selected(self, selected: bool):
        self._header.set_selected(selected)
