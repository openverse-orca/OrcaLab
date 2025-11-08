from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.ui.theme_service import ThemeService


def make_horizontal_line(size: int = 1) -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.HLine)
    line.setFrameShadow(QtWidgets.QFrame.Plain)
    line.setFixedHeight(size)
    color = ThemeService().get_color_hex("split_line")
    line.setStyleSheet(
        f"""
        QFrame {{
            background-color: {color};
            color: {color};
        }}
        """
    )
    return line


def make_vertical_line(size: int = 1) -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    line.setFrameShape(QtWidgets.QFrame.VLine)
    line.setFrameShadow(QtWidgets.QFrame.Plain)
    line.setFixedWidth(size)
    color = ThemeService().get_color_hex("split_line")
    line.setStyleSheet(
        f"""
        QFrame {{
            background-color: {color};
            color: {color};
        }}
        """
    )
    return line
