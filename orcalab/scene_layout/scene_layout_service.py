import asyncio
import json
import logging
import os
import pathlib
import time
from typing import List

from qasync import asyncWrap
from PySide6 import QtCore, QtWidgets, QtGui

from orcalab.application_bus import ApplicationRequestBus
from orcalab.config_service import ConfigService
from orcalab.i18n import tr
from orcalab.local_scene import LocalScene
from orcalab.transform import Transform
from orcalab.remote_scene import RemoteScene
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.scene_layout.scene_layout_helper import SceneLayoutHelper
from orcalab.scene_layout.scene_layout_helper_v3 import SceneLayoutHelperV3
from orcalab.ui.fonts.font_service import FontService
from orcalab.undo_service.undo_service_bus import UndoRequestBus

logger = logging.getLogger(__name__)

def _show_scrollable_warning(parent, title: str, message: str, detail: str):
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(600, 400)

    layout = QtWidgets.QVBoxLayout(dialog)

    msg_label = QtWidgets.QLabel(message)
    msg_label.setWordWrap(True)
    layout.addWidget(msg_label)

    text_edit = QtWidgets.QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setPlainText(detail)
    layout.addWidget(text_edit)

    button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    button_box.accepted.connect(dialog.accept)
    layout.addWidget(button_box)

    dialog.exec()

class SceneLayoutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.MSWindowsFixedSizeDialogHint
            & ~QtCore.Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Orcalab")
        self.setMinimumSize(220, 136)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()
        row_label = QtWidgets.QHBoxLayout()
        row_label.addStretch()
        label = QtWidgets.QLabel("场景加载中", self)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        FontService().bind_widget_font(label, "loading_dialog")
        row_label.addWidget(label)
        row_label.addStretch()
        layout.addLayout(row_label)
        layout.addStretch()

        self.installEventFilter(self)

    def eventFilter(self, obj, event: QtCore.QEvent):
        """布局加载期间禁止用户关闭弹窗，忽略关闭操作。"""
        if obj is self and event.type() == QtCore.QEvent.Type.Close:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class SceneLayoutService:
    def __init__(
        self,
        local_scene: LocalScene,
        remote_scene: RemoteScene,
        main_window: QtWidgets.QWidget,
    ) -> None:
        self.local_scene = local_scene
        self.remote_scene = remote_scene
        self.config_service = ConfigService()
        self.main_window = main_window
        self.default_layout_path: str | None = None
        self.current_layout_path: str | None = None
        self.flycamera_transform = Transform()
        self.cwd = os.getcwd()
        self.layout_modified = False

    def _resolve_path(self, path: str | None) -> str | None:
        if not path:
            return None
        try:
            return str(pathlib.Path(path).expanduser().resolve())
        except Exception:
            return str(path)

    def _is_default_layout(self, path: str | None) -> bool:
        if not path or not self.default_layout_path:
            return False
        try:
            return (
                pathlib.Path(path).expanduser().resolve()
                == pathlib.Path(self.default_layout_path).expanduser().resolve()
            )
        except Exception:
            return False

    async def _write_scene_layout_file(self, filename: str):
        try:
            helper = SceneLayoutHelperV3(self.local_scene, self.remote_scene)
            await helper.save_scene_layout(filename)
            self.current_layout_path = self._resolve_path(filename)
            self._infer_scene_and_layout_names()
            self._mark_layout_clean()
            logger.debug("保存场景布局至 %s", self.current_layout_path)
            ApplicationRequestBus().update_title()
        except Exception as e:
            logger.exception("保存场景布局失败: %s", e)

    async def save_scene_layout(self):
        if not self.current_layout_path or self._is_default_layout(
            self.current_layout_path
        ):
            await self.save_scene_layout_as()
            return

        await self._write_scene_layout_file(self.current_layout_path)

    async def save_scene_layout_as(self):
        def select_file():
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.main_window,
                "保存场景布局",
                self.cwd,
                "布局文件 (*.json);;所有文件 (*)",
            )
            return filename

        filename = await asyncWrap(select_file)

        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"

        await self._write_scene_layout_file(filename)
        self.cwd = os.path.dirname(filename)

    async def create_scene_layout(self):
        def select_file():
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.main_window,
                "新建场景布局",
                self.cwd,
                "布局文件 (*.json);;所有文件 (*)",
            )
            return filename

        filename = await asyncWrap(select_file)

        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename += ".json"

        if not await self.confirm_discard_changes(close_after_save=False):
            return

        helper = SceneLayoutHelperV3(self.local_scene, self.remote_scene)
        await helper.create_empty_layout(filename)
        await helper.clear_layout()

        self.cwd = os.path.dirname(filename)
        self.current_layout_path = filename
        self._infer_scene_and_layout_names()
        self._mark_layout_clean()
        logger.debug("create_scene_layout: 用户新建布局 path=%s", filename)

        UndoRequestBus().clear_history()

    async def open_scene_layout(self):
        def select_file():
            return QtWidgets.QFileDialog.getOpenFileName(
                self.main_window,
                "打开场景布局",
                self.cwd,
                "布局文件 (*.json);;所有文件 (*)",
            )

        filename, _ = await asyncWrap(select_file)
        if not filename:
            return
        if not await self.confirm_discard_changes(close_after_save=False):
            return

        await self._load_scene_layout(filename)

        self.cwd = os.path.dirname(filename)
        self._infer_scene_and_layout_names()
        self._mark_layout_clean()
        logger.debug("open_scene_layout: 用户打开 path=%s", filename)

        await self.save_flycamera_transform()

    async def start_up_open_layout(self):
        self.default_layout_path = self._resolve_path(
            self.config_service.default_layout_file()
        )
        if self.default_layout_path and pathlib.Path(self.default_layout_path).exists():
            _layout_start = time.monotonic()
            try:
                await self._load_scene_layout(self.default_layout_path)
                logger.info(
                    "load_scene_layout 完成, 耗时: %.2f 秒",
                    time.monotonic() - _layout_start,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("加载默认布局失败: %s", exc)
                import traceback

                detail_text = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )
                QtWidgets.QMessageBox.critical(
                    self.main_window,
                    tr("加载默认布局失败"),
                    tr(
                        "所选场景的默认布局加载失败。\n"
                        "请复制下方错误信息寻求帮助，并重新启动程序选择“空白布局”。\n\n"
                    )
                    + detail_text,
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                QtWidgets.QApplication.quit()
                return
            else:
                self._mark_layout_clean()

        self.layout_modified = False
        self._infer_scene_and_layout_names()
        ApplicationRequestBus().update_title()
        await self.save_flycamera_transform()

    async def _load_scene_layout(self, filename):
        show_loading = self.main_window.isVisible()
        dialog = SceneLayoutDialog(self.main_window)

        if show_loading:
            dialog.resize(220, 136)
            dialog.show()
            self.main_window.setEnabled(False)

        errors: List[str] = []
        warnings: List[str] = []
        await self._load_scene_layout_internal(filename, errors, warnings)
        dialog.accept()
        self.main_window.setEnabled(True)

        hide_actor_paths = []
        lock_actor_paths = []
        for actor_path, actor in self.local_scene.actors.items():
            if not actor.is_visible:
                hide_actor_paths.append(actor_path)
            if actor.is_locked:
                lock_actor_paths.append(actor_path)

        if hide_actor_paths:
            await self.remote_scene.actor_visible_change(False, hide_actor_paths)
        if lock_actor_paths:
            await self.remote_scene.actor_locked_change(True, lock_actor_paths)

        def show_error_dialog():
            QtWidgets.QMessageBox.critical(
                self.main_window,
                tr("场景布局加载错误"),
                "\n".join(errors),
            )

        def show_warning_dialog():
            _show_scrollable_warning(
                self.main_window,
                tr("场景布局加载警告"),
                tr(
                    "加载场景布局时产生 {count} 条警告：",
                    count=len(warnings),
                ),
                "\n".join(warnings),
            )

        if errors:
            await asyncWrap(show_error_dialog)
            return

        if warnings:
            await asyncWrap(show_warning_dialog)

    async def _load_scene_layout_internal(
        self, filename: str, errors: List[str], warnings: List[str]
    ):
        try:
            resolved = self._resolve_path(filename)
            if resolved is None:
                errors.append(tr("布局文件路径无效"))
                return

            with open(resolved, "r", encoding="utf-8") as f:
                layout_dict = json.load(f)

            if not isinstance(layout_dict, dict):
                errors.append(tr("布局文件格式错误"))
                return

            version = layout_dict.get("version", "")
            if version == "":
                errors.append(tr("布局文件版本号缺失"))
                return

            if version == "1.0" or version == "2.0":
                warnings.append(
                    tr(
                        "加载旧版(v1.0/v2.0)场景布局，建议重新保存以升级到 v3.0 格式"
                    )
                )
                helper = SceneLayoutHelper(self.local_scene)
                await helper.load_scene_layout(layout_dict, errors)
            elif version == "3.0":
                helper = SceneLayoutHelperV3(self.local_scene, self.remote_scene)
                await helper.load_scene_layout(layout_dict, errors, warnings)
            else:
                errors.append(
                    tr("布局文件版本号 {version} 不支持", version=version)
                )
                return

            self.current_layout_path = resolved
            self._infer_scene_and_layout_names()
            self._mark_layout_clean()
            UndoRequestBus().clear_history()

        except Exception as e:
            errors.append(
                tr(
                    "加载布局文件 {filename} 时出错: {error}",
                    filename=filename,
                    error=e,
                )
            )
            return

    @property
    def current_scene_name(self) -> str | None:
        return self._current_scene_name

    @property
    def current_layout_name(self) -> str | None:
        return self._current_layout_name

    def _infer_scene_and_layout_names(self):
        level_info = self.config_service.current_level_info()
        self._current_scene_name = None
        if level_info:
            name = level_info.get("name") or level_info.get("path")
            self._current_scene_name = name

        if self.current_layout_path:
            self._current_layout_name = pathlib.Path(self.current_layout_path).stem
        else:
            self._current_layout_name = None

    async def restore_flycamera_transform(self):
        await self.remote_scene.set_flycamera_transform(self.flycamera_transform)
        logger.info("恢复视角")

    async def save_flycamera_transform(self):
        self.flycamera_transform = await self.remote_scene.get_flycamera_transform()
        logger.info("保存视角")

    async def confirm_discard_changes(self, close_after_save: bool = True) -> bool:
        if not self.layout_modified:
            return True

        logger.debug("布局已修改，弹窗确认")
        message_box = QtWidgets.QMessageBox(self.main_window)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        message_box.setWindowTitle("未保存的修改")
        message_box.setText("当前布局有未保存的修改")

        cancel_button = message_box.addButton(
            "取消", QtWidgets.QMessageBox.ButtonRole.RejectRole
        )
        discard_button = message_box.addButton(
            "放弃修改", QtWidgets.QMessageBox.ButtonRole.DestructiveRole
        )
        save_button = message_box.addButton(
            "保存修改", QtWidgets.QMessageBox.ButtonRole.AcceptRole
        )
        message_box.setDefaultButton(save_button)

        await asyncWrap(message_box.exec)
        clicked = message_box.clickedButton()

        if clicked == cancel_button:
            return False
        if clicked == save_button:
            logger.debug("用户选择保存修改")
            await self.save_scene_layout()
            self._mark_layout_clean()
            if close_after_save:
                self.main_window.close()
                return False
            return True

        logger.debug("用户选择放弃修改，重置状态")
        return True

    def _mark_layout_clean(self):
        self.layout_modified = False
        ApplicationRequestBus().update_title()
