from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder
from orcalab.ui.main_window import MainWindow1

import os
import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

if __name__ == "__main__":
    check_project_folder()

    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))

    q_app = QtWidgets.QApplication([])

    main_window = MainWindow1()

    # 在这之后，Qt的event_loop变成asyncio的event_loop。
    # 这是目前统一Qt和asyncio最好的方法。
    # 所以不要保存loop，统一使用asyncio.xxx()。
    # https://doc.qt.io/qtforpython-6/PySide6/QtAsyncio/index.html
    QtAsyncio.run(main_window.init())

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
