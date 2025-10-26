from PySide6 import QtCore, QtWidgets, QtGui


def clear_layout(layout: QtWidgets.QLayout = None):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            widget = item.widget()
            layout.removeWidget(widget)
            widget.setParent(None)
        elif item.layout():
            clear_layout(item.layout())
            layout.removeItem(item)