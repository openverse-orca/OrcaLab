from __future__ import annotations

import logging
from typing import List

from PySide6 import QtCore, QtWidgets

from orcalab.i18n import tr
from orcalab.plugin_system.plugin_config_dialog import PluginConfigDialog
from orcalab.plugin_system.plugin_installer import PluginInstaller
from orcalab.plugin_system.plugin_manager import PluginManager
from orcalab.plugin_system.plugin_manifest import PluginManifest
from orcalab.ui.fonts.font_service import FontService

logger = logging.getLogger(__name__)


class PluginManagerDialog(QtWidgets.QDialog):
    """插件管理对话框：查看已安装插件、启用/禁用、卸载。"""

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("插件管理")
        self.setModal(True)
        self.resize(680, 500)
        self._plugin_manager = plugin_manager
        self._installer = PluginInstaller(plugin_manager.registry)
        self._manifests: List[PluginManifest] = []
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("已安装的插件")
        FontService().bind_widget_font(title, "panel_title")
        layout.addWidget(title)

        self._table = QtWidgets.QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["启用", "名称", "版本", "描述"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QtWidgets.QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self._table)

        hint = QtWidgets.QLabel("修改启用状态后需重启 OrcaLab 生效")
        hint.setStyleSheet("color: #888888;")
        layout.addWidget(hint)

        btn_layout = QtWidgets.QHBoxLayout()
        self._btn_uninstall = QtWidgets.QPushButton("卸载选中插件")
        self._btn_uninstall.clicked.connect(self._on_uninstall)
        btn_layout.addWidget(self._btn_uninstall)

        self._btn_config = QtWidgets.QPushButton("编辑配置")
        self._btn_config.clicked.connect(self._on_edit_config)
        btn_layout.addWidget(self._btn_config)

        self._table.doubleClicked.connect(self._on_double_click)

        btn_layout.addStretch(1)
        self._btn_close = QtWidgets.QPushButton("关闭")
        self._btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_close)
        layout.addLayout(btn_layout)

    def _refresh(self):
        self._manifests = self._plugin_manager.discover()
        self._table.setRowCount(len(self._manifests))
        for row, manifest in enumerate(self._manifests):
            enabled = self._plugin_manager.registry.is_enabled(manifest.name)
            check = QtWidgets.QCheckBox()
            check.setChecked(enabled)
            check.toggled.connect(
                lambda checked, name=manifest.name: self._on_toggle(name, checked)
            )
            self._table.setCellWidget(row, 0, check)

            name_item = QtWidgets.QTableWidgetItem(manifest.name)
            name_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 1, name_item)

            version_item = QtWidgets.QTableWidgetItem(manifest.version)
            version_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 2, version_item)

            desc_item = QtWidgets.QTableWidgetItem(manifest.get_description())
            desc_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 3, desc_item)

            self._table.setRowHeight(row, 28)

    def _on_toggle(self, plugin_name: str, enabled: bool):
        try:
            self._plugin_manager.registry.set_enabled(plugin_name, enabled)
            actual = self._plugin_manager.registry.is_enabled(plugin_name)
            logger.info("插件 %s 已%s (registry 状态: %s)", plugin_name, "启用" if enabled else "禁用", actual)
        except Exception as e:
            logger.exception("保存插件 %s 启用状态失败: %s", plugin_name, e)
            QtWidgets.QMessageBox.critical(
                self,
                "保存失败",
                tr(
                    "无法保存插件 {plugin_name} 的启用状态:\n{error}",
                    plugin_name=plugin_name,
                    error=e,
                ),
            )

    def _on_uninstall(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "卸载插件", "请先选择要卸载的插件")
            return

        row = rows[0].row()
        plugin_name = self._table.item(row, 1).text()

        reply = QtWidgets.QMessageBox.question(
            self,
            "卸载插件",
            tr(
                "确定要卸载插件 {plugin_name} 吗？\n"
                "这将删除插件目录和所有文件。",
                plugin_name=plugin_name,
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        if self._installer.uninstall(plugin_name):
            QtWidgets.QMessageBox.information(
                self,
                "卸载完成",
                tr("插件 {plugin_name} 已卸载", plugin_name=plugin_name),
            )
            self._refresh()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "卸载失败",
                tr(
                    "插件 {plugin_name} 卸载失败，请查看日志",
                    plugin_name=plugin_name,
                ),
            )

    def _get_selected_manifest(self) -> PluginManifest | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "提示", "请先选择一个插件")
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._manifests):
            return None
        return self._manifests[row]

    def _on_edit_config(self):
        manifest = self._get_selected_manifest()
        if manifest is None:
            return
        self._open_config_dialog(manifest)

    def _on_double_click(self, index: QtCore.QModelIndex):
        row = index.row()
        if row < 0 or row >= len(self._manifests):
            return
        manifest = self._manifests[row]
        self._open_config_dialog(manifest)

    def _open_config_dialog(self, manifest: PluginManifest):
        """打开插件配置对话框。

        优先使用插件自定义的配置控件（PluginBase.create_config_widget），
        回退到通用文本编辑器（PluginConfigDialog）。
        """
        plugin = self._plugin_manager.get_plugin(manifest.name)
        custom_widget = None
        if plugin is not None:
            try:
                custom_widget = plugin.create_config_widget(self)
            except Exception as e:
                logger.exception("插件 %s 创建配置控件失败: %s", manifest.name, e)

        if custom_widget is not None:
            # 插件提供自定义配置 UI
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle(tr("插件配置 - {name}", name=manifest.name))
            dialog.setModal(True)
            dialog.resize(700, 500)
            layout = QtWidgets.QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(custom_widget)
            dialog.exec()
            return

        # 回退到通用文本编辑器
        if not manifest.get_config_file_paths():
            QtWidgets.QMessageBox.information(
                self, "无配置文件",
                tr(
                    "插件 {plugin_name} 未声明配置文件。\n\n"
                    "插件可选两种方式提供配置 UI:\n"
                    "1. 覆写 PluginBase.create_config_widget() 返回自定义控件\n"
                    "2. 在 plugin.toml 中添加 config_files 字段使用通用编辑器",
                    plugin_name=manifest.name,
                ),
            )
            return
        dialog = PluginConfigDialog(manifest, self)
        dialog.exec()
