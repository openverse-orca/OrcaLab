from __future__ import annotations

from typing import Callable, List

from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.perf_log import perf_timer
from orcalab.ui.icon_util import make_color_svg
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

        self._chevron_down: QtGui.QPixmap | None = None
        self._chevron_right: QtGui.QPixmap | None = None
        self._init_pixmaps()

        fm = self.fontMetrics()
        self._row_height = max(fm.height() + 8, 24)
        self.setFixedHeight(self._row_height)
        self.setMouseTracking(True)

    def _init_pixmaps(self):
        theme = ThemeService()
        text_color = theme.get_color("text")
        self._chevron_down = make_color_svg(":/icons/chevron_down.svg", text_color)
        self._chevron_right = make_color_svg(":/icons/chevron_right.svg", text_color)

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
            chevron = self._chevron_down if not self._collapsed else self._chevron_right
            if chevron is not None:
                chevron_rect = QtCore.QRect(x, (rect.height() - self._CHEVRON_SIZE) // 2, self._CHEVRON_SIZE, self._CHEVRON_SIZE)
                scaled = chevron.scaled(
                    self._CHEVRON_SIZE, self._CHEVRON_SIZE,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(chevron_rect, scaled)
            x += self._CHEVRON_SIZE + 4
        else:
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
        available_width = rect.width() - x - self._HPADDING
        badge_width = 0
        if self._badge:
            badge_fm = QtGui.QFontMetrics(font)
            badge_width = badge_fm.horizontalAdvance(self._badge) + 8
            available_width -= badge_width

        title_text = fm.elidedText(self._title, QtCore.Qt.TextElideMode.ElideRight, available_width)
        text_rect = QtCore.QRect(x, 0, rect.width() - x - self._HPADDING, rect.height())
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, title_text)

        if self._badge and badge_width > 0:
            badge_x = rect.width() - self._HPADDING - badge_width
            painter.setPen(QtGui.QPen(theme.get_color("text_disable")))
            badge_font = font
            badge_font.setItalic(True)
            painter.setFont(badge_font)
            badge_rect = QtCore.QRect(badge_x, 0, badge_width, rect.height())
            badge_text = fm.elidedText(self._badge, QtCore.Qt.TextElideMode.ElideLeft, badge_width)
            painter.drawText(badge_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, badge_text)
            badge_font.setItalic(False)

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
    ):
        theme = ThemeService()

        if selected:
            painter.fillRect(rect, theme.get_color("bg_selection"))
        elif hovered:
            painter.fillRect(rect, theme.get_color("bg_hover"))

        text_color = theme.get_color("text")
        chevron_down = make_color_svg(":/icons/chevron_down.svg", text_color)
        chevron_right = make_color_svg(":/icons/chevron_right.svg", text_color)

        x = 4 + indent_level * 20
        chevron_size = 16
        icon_size = 16

        if has_children:
            chevron = chevron_down if not collapsed else chevron_right
            if chevron is not None:
                scaled = chevron.scaled(
                    chevron_size, chevron_size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                chevron_rect = QtCore.QRect(x, (rect.height() - chevron_size) // 2, chevron_size, chevron_size)
                painter.drawPixmap(chevron_rect, scaled)
            x += chevron_size + 4
        else:
            x += chevron_size + 4

        if icon is not None:
            icon_pixmap = icon.pixmap(icon_size, icon_size)
            icon_rect = QtCore.QRect(x, (rect.height() - icon_size) // 2, icon_size, icon_size)
            painter.drawPixmap(icon_rect, icon_pixmap)
            x += icon_size + 4

        painter.setPen(QtGui.QPen(text_color))
        font = painter.font()
        fm = QtGui.QFontMetrics(font)
        available_width = rect.width() - x - 4
        badge_width = 0
        if badge:
            badge_width = fm.horizontalAdvance(badge) + 8
            available_width -= badge_width

        title_text = fm.elidedText(title, QtCore.Qt.TextElideMode.ElideRight, available_width)
        text_rect = QtCore.QRect(x, rect.y(), rect.width() - x - 4, rect.height())
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, title_text)

        if badge and badge_width > 0:
            badge_x = rect.width() - 4 - badge_width
            painter.setPen(QtGui.QPen(theme.get_color("text_disable")))
            badge_font = font
            badge_font.setItalic(True)
            painter.setFont(badge_font)
            badge_rect = QtCore.QRect(badge_x, rect.y(), badge_width, rect.height())
            badge_text = fm.elidedText(badge, QtCore.Qt.TextElideMode.ElideLeft, badge_width)
            painter.drawText(badge_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, badge_text)
            badge_font.setItalic(False)


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

        self._content_area = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._content_area)

        if collapsed:
            self._content_area.hide()
        else:
            self._lazy_create_content()

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

    def expand(self):
        if not self._collapsed:
            return
        self._lazy_create_content()
        self._collapsed = False
        self._content_area.show()
        self._header.set_collapsed(False)
        self.collapsed_changed.emit(False)

    def collapse(self):
        if self._collapsed:
            return
        self._collapsed = True
        self._content_area.hide()
        self._header.set_collapsed(True)
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
