import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.ui.asset_browser.thumbnail_model import ThumbnailModel
from orcalab.ui.asset_browser.thumbnail_view import ThumbnailView


class TestModel(ThumbnailModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._size = 100

    def size(self) -> int:
        return self._size

    def image_at(self, index: int) -> QtGui.QImage:
        image = QtGui.QImage(128, 128, QtGui.QImage.Format_ARGB32)
        random_color = QtGui.QColor(
            (index * 25) % 256, (index * 50) % 256, (index * 75) % 256
        )
        image.fill(random_color)
        return image

    def text_at(self, index: int) -> str:
        if index % 3 == 0:
            return f"Item {index} with a very long name that should be elided"
        return f"Item {index}"


class TestWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        self.model = TestModel()
        thumbnail_view = ThumbnailView()
        thumbnail_view.set_model(self.model)
        layout.addWidget(thumbnail_view)


async def main(q_app: QtWidgets.QApplication):

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)

    window = TestWindow()
    window.resize(1200, 800)
    window.show()

    await app_close_event.wait()


if __name__ == "__main__":

    q_app = QtWidgets.QApplication()

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    event_loop.run_until_complete(main(q_app))

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
