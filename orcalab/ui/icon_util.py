import os

from PySide6 import QtCore, QtWidgets, QtGui, QtSvg

import orcalab.assets.rc_assets

APP_WINDOW_ICON_QRC = ":/icons/orcalab_logo.png"

def app_window_icon() -> QtGui.QIcon:
    return QtGui.QIcon(APP_WINDOW_ICON_QRC)

def schedule_windows_taskbar_icon_refresh(window: QtWidgets.QWidget) -> None:
    if os.name != "nt":
        return

    def _reapply() -> None:
        icon = window.windowIcon()
        window.setWindowIcon(QtGui.QIcon())
        window.setWindowIcon(icon)

    QtCore.QTimer.singleShot(0, _reapply)

def make_color_svg(svg_file: str, color: QtGui.QColor) -> QtGui.QPixmap:
    # Load the SVG file
    svg_renderer = QtSvg.QSvgRenderer(svg_file)

    # Create a QPixmap to render the SVG onto
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    # Render the SVG onto the QPixmap
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    svg_renderer.render(painter)

    # Use svg as a mask to apply the color
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)

    painter.end()

    return pixmap


def make_color_image(file: str, color: QtGui.QColor) -> QtGui.QPixmap:
    pixmap = QtGui.QPixmap(file)
    painter = QtGui.QPainter(pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return pixmap


def make_icon(file: str, color: QtGui.QColor) -> QtGui.QIcon:
    if file.endswith(".svg"):
        pixmap = make_color_svg(file, color)
    else:
        pixmap = make_color_image(file, color)
    icon = QtGui.QIcon(pixmap)
    return icon


def make_text_icon(
    text: str,
    font: QtGui.QFont,
    text_color: QtGui.QColor = QtGui.QColor("black"),
) -> QtGui.QIcon:
    pixmap = QtGui.QPixmap(64, 64)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    rect = pixmap.rect()
    fm = QtGui.QFontMetrics(font)
    scale = rect.width() / fm.horizontalAdvance(text)

    painter = QtGui.QPainter(pixmap)
    painter.setPen(text_color)
    painter.translate(rect.center())
    painter.scale(scale, scale)
    painter.translate(-rect.center())
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, text)

    painter.end()

    icon = QtGui.QIcon(pixmap)
    return icon
