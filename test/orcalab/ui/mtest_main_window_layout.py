import asyncio
import pathlib

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop
import json


from orcalab.ui.panel_manager import PanelManager
from orcalab.ui.panel import Panel

# echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope


class ColorWidget(QtWidgets.QWidget):
    def __init__(self, color: QtGui.QColor, text: str = ""):
        super().__init__()
        self.color = color
        self.text = text

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.color)
        if self.text:
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, self.text)


class TestPanelManager(PanelManager):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self._menu_bar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        menu_bar = QtWidgets.QMenuBar(self._menu_bar_area)
        layout.addWidget(menu_bar)

        file_menu = menu_bar.addMenu("File")
        test_action = file_menu.addAction("Test")
        test_action.triggered.connect(self.on_test_action_triggered)

        layout = QtWidgets.QVBoxLayout(self._tool_bar_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        tool_bar = QtWidgets.QToolBar(self._tool_bar_area)
        layout.addWidget(tool_bar)

        test_tool_action = tool_bar.addAction(QtGui.QIcon(), "Test Tool")
        test_tool_action.triggered.connect(self.on_test_tool_action_triggered)

        panel_color = QtGui.QColor("lightblue")

        panel_left_1 = Panel("L1", ColorWidget(panel_color, "Panel Left 1"))
        panel_left_2 = Panel("L2", ColorWidget(panel_color, "Panel Left 2"))

        panel_right_1 = Panel("R1", ColorWidget(panel_color, "Panel Right 1"))

        panel_bottom_1 = Panel("B1", ColorWidget(panel_color, "Panel Bottom 1"))

        central_widget = ColorWidget(QtGui.QColor("green"), "Main Content Area")

        self.add_panel(panel_left_1, "left")
        self.add_panel(panel_left_2, "left")
        self.add_panel(panel_right_1, "right")
        self.add_panel(panel_bottom_1, "bottom")

        layout = QtWidgets.QVBoxLayout(self._main_content_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(central_widget)

    def on_test_action_triggered(self):
        print("Test action triggered")

    def on_test_tool_action_triggered(self):
        print("Test tool action triggered")

    def _panel_layout_file_path(self) -> pathlib.Path:
        return pathlib.Path.home() / "Orca" / "OrcaLab" / "test_panel_layout.json"

    def save_layout(self):
        layout_data: dict = {}
        self.save_layout_to_dict(layout_data)
        with open(self._panel_layout_file_path(), "w", encoding="utf-8") as f:
            json.dump(layout_data, f, indent=4)

    def load_layout(self):
        try:
            with open(self._panel_layout_file_path(), "r", encoding="utf-8") as f:
                layout_data: dict = json.load(f)

            self.load_layout_from_dict(layout_data)
        except Exception as e:
            self.restore_default_layout()


async def main(q_app: QtWidgets.QApplication):

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)

    window = TestPanelManager()
    window.connect_buses()
    window.resize(1200, 800)
    window.restore_default_layout()
    window.show()

    await app_close_event.wait()

    window.save_layout()


if __name__ == "__main__":

    q_app = QtWidgets.QApplication()

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    event_loop.run_until_complete(main(q_app))

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
