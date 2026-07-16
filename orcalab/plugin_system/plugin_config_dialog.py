from __future__ import annotations

import logging
import pathlib

from PySide6 import QtCore, QtWidgets

from orcalab.plugin_system.plugin_manifest import PluginManifest

logger = logging.getLogger(__name__)


class PluginConfigDialog(QtWidgets.QDialog):
    """插件配置文件编辑对话框。

    在插件管理对话框中双击某行或点击"编辑配置"按钮打开。
    显示 plugin.toml 中声明的 config_files，支持在线编辑和保存。
    """

    def __init__(self, manifest: PluginManifest, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"插件配置 - {manifest.name}")
        self.setModal(True)
        self.resize(700, 500)
        self._manifest = manifest
        self._config_paths = manifest.get_config_file_paths()
        self._init_ui()
        self._load_current_file()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 文件选择栏
        file_layout = QtWidgets.QHBoxLayout()
        file_layout.addWidget(QtWidgets.QLabel("配置文件:"))

        self._file_combo = QtWidgets.QComboBox()
        for p in self._config_paths:
            self._file_combo.addItem(p.name, p)
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        file_layout.addWidget(self._file_combo, 1)

        self._btn_open_external = QtWidgets.QPushButton("在外部编辑器打开")
        self._btn_open_external.clicked.connect(self._open_external)
        file_layout.addWidget(self._btn_open_external)
        layout.addLayout(file_layout)

        # 编辑器
        self._editor = QtWidgets.QPlainTextEdit()
        self._editor.setFont(QtWidgets.QApplication.font("QPlainTextEdit"))
        layout.addWidget(self._editor, 1)

        # 提示
        self._hint = QtWidgets.QLabel("")
        self._hint.setStyleSheet("color: #888888;")
        layout.addWidget(self._hint)

        # 按钮栏
        btn_layout = QtWidgets.QHBoxLayout()
        self._btn_save = QtWidgets.QPushButton("保存")
        self._btn_save.clicked.connect(self._save)
        btn_layout.addWidget(self._btn_save)

        self._btn_reload = QtWidgets.QPushButton("重新加载")
        self._btn_reload.clicked.connect(self._load_current_file)
        btn_layout.addWidget(self._btn_reload)

        btn_layout.addStretch(1)
        self._btn_close = QtWidgets.QPushButton("关闭")
        self._btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_close)
        layout.addLayout(btn_layout)

        if not self._config_paths:
            self._editor.setPlainText(
                "此插件未声明配置文件。\n\n"
                "在 plugin.toml 中添加 config_files 字段即可支持配置编辑：\n"
                '  config_files = ["bundleMcp.yaml", "config/settings.toml"]'
            )
            self._editor.setReadOnly(True)
            self._btn_save.setEnabled(False)
            self._btn_reload.setEnabled(False)
            self._btn_open_external.setEnabled(False)

    def _on_file_changed(self, _index: int):
        self._load_current_file()

    def _load_current_file(self):
        path = self._current_path()
        if path is None:
            return
        try:
            text = path.read_text(encoding="utf-8")
            self._editor.setPlainText(text)
            self._hint.setText(f"已加载: {path}")
        except Exception as e:
            self._editor.setPlainText("")
            self._hint.setText(f"加载失败: {e}")
            logger.error("加载配置文件 %s 失败: %s", path, e)

    def _save(self):
        path = self._current_path()
        if path is None:
            return
        try:
            path.write_text(self._editor.toPlainText(), encoding="utf-8")
            self._hint.setText(f"已保存: {path}")
            logger.info("配置文件已保存: %s", path)
            QtWidgets.QMessageBox.information(self, "保存成功", f"配置文件已保存:\n{path}")
        except Exception as e:
            self._hint.setText(f"保存失败: {e}")
            logger.error("保存配置文件 %s 失败: %s", path, e)
            QtWidgets.QMessageBox.critical(self, "保存失败", f"无法保存配置文件:\n{e}")

    def _open_external(self):
        path = self._current_path()
        if path is None:
            return
        # 先保存当前编辑内容
        self._save()
        try:
            QtCore.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        except Exception as e:
            logger.warning("无法打开外部编辑器: %s", e)

    def _current_path(self) -> pathlib.Path | None:
        idx = self._file_combo.currentIndex()
        if idx < 0 or idx >= len(self._config_paths):
            return None
        return self._config_paths[idx]
