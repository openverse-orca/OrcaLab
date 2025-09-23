import asyncio
import sys

from orcalab.config_service import ConfigService
from orcalab.project_util import check_project_folder
from orcalab.url_service.url_util import register_protocol
from orcalab.ui.main_window import MainWindow1

import os

# import PySide6.QtAsyncio as QtAsyncio
from PySide6 import QtWidgets

from qasync import QEventLoop


async def main(q_app):

    app_close_event = asyncio.Event()
    q_app.aboutToQuit.connect(app_close_event.set)
    main_window = MainWindow1()
    await main_window.init()

    await app_close_event.wait()


if __name__ == "__main__":
    check_project_folder()

    register_protocol()

    config_service = ConfigService()
    config_service.init_config(os.path.dirname(__file__))

    q_app = QtWidgets.QApplication(sys.argv)

    event_loop = QEventLoop(q_app)
    asyncio.set_event_loop(event_loop)

    event_loop.run_until_complete(main(q_app))
    event_loop.close()

    # magic!
    # AttributeError: 'NoneType' object has no attribute 'POLLER'
    # https://github.com/google-gemini/deprecated-generative-ai-python/issues/207#issuecomment-2601058191
    exit(0)
