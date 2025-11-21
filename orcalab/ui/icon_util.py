from PySide6 import QtCore, QtWidgets, QtGui, QtSvg

import orcalab.assets.rc_assets

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
    painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)

    painter.end()

    return pixmap


def make_icon(svg_file: str, color: QtGui.QColor) -> QtGui.QIcon:
    pixmap = make_color_svg(svg_file, color)
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
