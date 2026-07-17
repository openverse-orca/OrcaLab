from __future__ import annotations

import logging
import pathlib

from PySide6 import QtCore, QtWidgets

from orcalab.i18n import tr
from orcalab.plugin_system.plugin_installer import PluginInstaller
from orcalab.plugin_system.plugin_manager import PluginManager
from orcalab.ui.fonts.font_service import FontService

logger = logging.getLogger(__name__)


class PluginInstallDialog(QtWidgets.QDialog):
    """插件安装对话框：选择压缩包、显示安装进度。"""

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("安装插件")
        self.setModal(True)
        self.setFixedSize(520, 360)
        self._plugin_manager = plugin_manager
        self._installer = PluginInstaller(plugin_manager.registry)
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel("安装插件")
        FontService().bind_widget_font(title, "panel_title")
        layout.addWidget(title)

        file_layout = QtWidgets.QHBoxLayout()
        self._path_edit = QtWidgets.QLineEdit()
        self._path_edit.setPlaceholderText("选择插件压缩包 (.tar.xz / .tar.gz)")
        self._path_edit.setReadOnly(True)
        file_layout.addWidget(self._path_edit)

        self._btn_browse = QtWidgets.QPushButton("浏览…")
        self._btn_browse.clicked.connect(self._on_browse)
        file_layout.addWidget(self._btn_browse)
        layout.addLayout(file_layout)

        self._status_label = QtWidgets.QLabel("请选择插件压缩包")
        self._status_label.setStyleSheet("color: #666666;")
        layout.addWidget(self._status_label)

        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._log_text = QtWidgets.QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(120)
        self._log_text.setVisible(False)
        layout.addWidget(self._log_text)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        self._btn_install = QtWidgets.QPushButton("安装")
        self._btn_install.setEnabled(False)
        self._btn_install.clicked.connect(self._on_install)
        btn_layout.addWidget(self._btn_install)

        self._btn_close = QtWidgets.QPushButton("关闭")
        self._btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_close)
        layout.addLayout(btn_layout)

    def _on_browse(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "选择插件压缩包",
            str(pathlib.Path.home()),
            "插件压缩包 (*.tar.xz *.tar.gz *.tgz);;所有文件 (*)",
        )
        if file_path:
            self._path_edit.setText(file_path)
            self._btn_install.setEnabled(True)
            self._status_label.setText("点击「安装」开始安装")

    def _log(self, msg: str):
        self._log_text.append(msg)

    def _on_install(self):
        archive_path_str = self._path_edit.text().strip()
        if not archive_path_str:
            return

        archive_path = pathlib.Path(archive_path_str)
        if not archive_path.is_file():
            QtWidgets.QMessageBox.warning(
                self,
                "安装插件",
                tr("文件不存在: {path}", path=archive_path),
            )
            return

        self._btn_install.setEnabled(False)
        self._btn_browse.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._log_text.setVisible(True)
        self._progress_bar.setValue(0)

        self._install_thread = _InstallWorker(
            self._installer, archive_path, self
        )
        self._install_thread.progress.connect(self._on_progress)
        self._install_thread.finished_ok.connect(self._on_install_ok)
        self._install_thread.finished_error.connect(self._on_install_error)
        self._install_thread.start()

    def _on_progress(self, percent: int, detail: str):
        self._progress_bar.setValue(percent)
        self._status_label.setText(detail)
        self._log(detail)

    def _on_install_ok(self, plugin_name: str, version: str):
        self._progress_bar.setValue(100)
        self._status_label.setText(
            tr(
                "安装完成: {plugin_name} v{version}",
                plugin_name=plugin_name,
                version=version,
            )
        )
        self._log(tr("✓ 插件 {plugin_name} 安装成功", plugin_name=plugin_name))
        QtWidgets.QMessageBox.information(
            self,
            "安装完成",
            tr(
                "插件 {plugin_name} v{version} 安装成功！\n"
                "请在插件管理中启用后重启 OrcaLab 生效。",
                plugin_name=plugin_name,
                version=version,
            ),
        )
        self._btn_close.setText("完成")

    def _on_install_error(self, error_msg: str):
        self._status_label.setText(tr("安装失败: {error}", error=error_msg))
        self._log(f"✗ {error_msg}")
        QtWidgets.QMessageBox.critical(self, "安装失败", error_msg)
        self._btn_install.setEnabled(True)
        self._btn_browse.setEnabled(True)


class _InstallWorker(QtCore.QThread):
    """安装工作线程，避免阻塞 UI。"""

    progress = QtCore.Signal(int, str)
    finished_ok = QtCore.Signal(str, str)
    finished_error = QtCore.Signal(str)

    def __init__(
        self,
        installer: PluginInstaller,
        archive_path: pathlib.Path,
        parent=None,
    ):
        super().__init__(parent)
        self._installer = installer
        self._archive_path = archive_path

    def run(self):
        try:
            manifest = self._installer.install_from_archive(
                self._archive_path,
                progress_callback=lambda p, d: self.progress.emit(p, d),
            )
            self.finished_ok.emit(manifest.name, manifest.version)
        except Exception as e:
            logger.exception("插件安装失败")
            self.finished_error.emit(str(e))
