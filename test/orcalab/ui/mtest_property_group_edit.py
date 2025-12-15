import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.actor import AssetActor
from orcalab.path import Path
from orcalab.actor_property import ActorProperty, ActorPropertyGroup, ActorPropertyType
from orcalab.ui.actor_editor import ActorEditor
from orcalab.ui.property_edit.property_group_edit import PropertyGroupEdit
from test.orcalab.ui.mtest_main_window import TestMainWindow, test_main


class TestWindow(TestMainWindow):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)

        actor = AssetActor("TestActor", "", None)
        self.local_scene.add_actor(actor, Path.root_path())

        for i in range(10):
            group = ActorPropertyGroup(
                "/xxx/xxxx/xxx:aaaa", f"Group {i}", "/xxx/xxxx/xxx"
            )
            group.properties.append(
                ActorProperty(f"Bool {i}", None, ActorPropertyType.BOOL, True)
            )
            group.properties.append(
                ActorProperty(f"Int {i}", None, ActorPropertyType.INTEGER, 42)
            )
            group.properties.append(
                ActorProperty(f"Float {i}", None, ActorPropertyType.FLOAT, 3.14)
            )
            group.properties.append(
                ActorProperty(
                    f"String {i}", None, ActorPropertyType.STRING, "Hello World"
                )
            )
            actor.property_groups.append(group)

        e = ActorEditor(self)
        e.set_actor(actor)

        layout.addWidget(scroll_area)
        scroll_area.setWidget(e)


if __name__ == "__main__":
    q_app = QtWidgets.QApplication()
    window = TestWindow()
    test_main(q_app, window)
