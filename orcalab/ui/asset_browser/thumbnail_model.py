from PySide6 import QtCore, QtWidgets, QtGui


class ThumbnailModel(QtCore.QObject):
    data_updated = QtCore.Signal()
    item_updated = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

    def size(self) -> int:
        return 0

    def image_at(self, index: int) -> QtGui.QImage:
        return QtGui.QImage()

    def text_at(self, index: int) -> str:
        return ""
    
    def movie_at(self, index: int):
        """返回动画播放器对象（ApngPlayer 或其他）"""
        return None
