import asyncio
from typing import List
from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop

from orcalab.application_bus import ApplicationRequest, ApplicationRequestBus
from orcalab.local_scene import LocalScene

# echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope


class TestMainWindow(QtWidgets.QWidget, ApplicationRequest):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Main Window")

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)

        self.local_scene = LocalScene()

        self.setStyleSheet(
            """
            QWidget {
                background-color: #181818;
                color: #ffffff;
            }
            """
        )

        ApplicationRequestBus.connect(self)

    def get_local_scene(self, output: List[LocalScene]):
        output.append(self.local_scene)


async def test_async_main(q_app: QtWidgets.QApplication, window: QtWidgets.QWidget):

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)

    window.resize(1200, 800)
    window.show()

    await app_close_event.wait()


def test_main(q_app: QtWidgets.QApplication, window: QtWidgets.QWidget):
    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    event_loop.run_until_complete(test_async_main(q_app, window))

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
