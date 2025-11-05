import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.ui.user_event_util import convert_key_code


class TestWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.isAutoRepeat():
            return

        qt_key = QtCore.Qt.Key(event.key())

        try:
            our_key = convert_key_code(event)
            print(f"Key Pressed: {qt_key.name} => {our_key}")
        except ValueError:
            print(f"Unsupported key: {qt_key.name}")
            return

    def mousePressEvent(self, event):
        return super().mousePressEvent(event)


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
