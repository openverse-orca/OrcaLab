import asyncio

from PySide6 import QtCore, QtWidgets, QtGui
from qasync import QEventLoop


from orcalab.ui.asset_browser.asset_browser import AssetBrowser
from orcalab.ui.asset_browser.asset_info import AssetInfo


class TestWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)

        assets = []

        for i in range(100):
            asset = AssetInfo()
            asset.name = f"Sample Asset {i + 1}"
            asset.path = f"/path/to/asset{i + 1}"
            assets.append(asset)

        asset_browser = AssetBrowser()
        asset_browser.set_assets(assets=assets)
        layout.addWidget(asset_browser)


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
