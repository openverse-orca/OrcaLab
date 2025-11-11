import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.ui.camera.camera_selector import CameraSelector, CameraBrief


class TestWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.camera_selector = CameraSelector(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.camera_selector)
        self.setLayout(layout)

        cameras = [CameraBrief(f"Camera {i}", i) for i in range(5)]
        self.camera_selector.set_cameras(cameras, 0)


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
