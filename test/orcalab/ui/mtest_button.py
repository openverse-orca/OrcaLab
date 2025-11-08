import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.ui.button import Button
from orcalab.ui.icon_util import make_text_icon

# echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope


class TestWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        btn1 = Button("Default Button")
        layout.addWidget(btn1)

        icon = make_text_icon("Bt", self.font())
        btn2 = Button(icon=icon)
        layout.addWidget(btn2)

        btn3 = Button("Icon Button", icon=icon)
        layout.addWidget(btn3)


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
