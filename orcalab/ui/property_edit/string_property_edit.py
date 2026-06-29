import asyncio
import logging
from typing import List
from typing_extensions import override
from PySide6 import QtCore, QtWidgets

from orcalab.actor import AssetActor
from orcalab.actor_property import ActorEntities, ActorPropertyGroup, ActorPropertyKey
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.scene_edit_bus import SceneEditRequestBus
from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.edit.string_edit import StringEdit
from orcalab.ui.edit.multiline_string_edit import MultilineStringEdit
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.joint_rename_dialog import JointRenameDialog

logger = logging.getLogger(__name__)


def _normalize_float_vec(text: str) -> str | None:
    parts = text.split(",")
    if len(parts) not in (2, 3, 4):
        return None
    try:
        values = [float(p.strip()) for p in parts]
        return ",".join(f"{v:.6f}" for v in values)
    except ValueError:
        return None


def _is_name_property(prop_name: str) -> bool:
    lower = prop_name.lower()
    return lower.endswith(".name") or lower == "name"


def _is_mujoco_valid_name(name: str) -> tuple[bool, str]:
    if not name:
        return False, "名称不能为空。"
    if not name.isascii():
        return False, "名称只能包含ASCII字符。"
    if not name.isidentifier():
        return False, "名称只能包含字母、数字和下划线，且不能以数字开头。"
    return True, ""


def _collect_names_from_groups(
    groups: List[ActorPropertyGroup], exclude_key: ActorPropertyKey | None = None
) -> set[str]:
    result: set[str] = set()
    for group in groups:
        for prop in group.properties:
            if not _is_name_property(prop.name()):
                continue
            if exclude_key is not None:
                if (
                    group.entity_id == exclude_key.entity_id
                    and group.component_type_id == exclude_key.component_type_id
                    and group.component_type_index == exclude_key.component_type_index
                    and prop.name() == exclude_key.property_name
                ):
                    continue

            val = prop.value()
            if isinstance(val, str) and val:
                result.add(val)
    return result


async def _fetch_all_existing_names(
    actor_path, exclude_key: ActorPropertyKey | None = None
) -> set[str]:
    names = set()
    local_scene = get_local_scene()
    entity_root = local_scene.get_entity_root(actor_path)
    if entity_root is None:
        return set()

    entity_ids = entity_root.root_entity_info.collect_entity_ids()

    remote_scene = get_remote_scene()
    ll = await remote_scene.get_entity_property_groups(
        ActorEntities(actor_path, entity_ids)
    )

    for groups in ll:
        for group in groups:
            names.update(_collect_names_from_groups([group], exclude_key))

    return names


class StringPropertyEdit(BasePropertyEdit[str]):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
    ):
        super().__init__(parent, context)

        is_multiline = context.prop.editor_hint() == "multi_line"
        is_name_prop = _is_name_property(context.prop.name()) and isinstance(
            context.actor, AssetActor
        )

        if is_name_prop:
            root_layout = QtWidgets.QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(4)

            label = self._create_label(label_width)

            editor = StringEdit()
            editor.setText(context.prop.value())
            editor.setReadOnly(True)
            editor.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            editor.setStyleSheet(self.base_style)
            FontService().bind_widget_font(editor, "property_edit")

            rename_btn = QtWidgets.QPushButton("✎")
            rename_btn.setFixedWidth(28)
            rename_btn.setToolTip("重命名")
            rename_btn.clicked.connect(self._on_rename_clicked)
            FontService().bind_widget_font(rename_btn, "property_edit")

            root_layout.addWidget(label)
            root_layout.addWidget(editor)
            root_layout.addWidget(rename_btn)

            self._rename_btn = rename_btn
        elif is_multiline:
            root_layout = QtWidgets.QVBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(4)

            label = self._create_label(label_width)
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )

            editor = MultilineStringEdit()
            editor.setText(context.prop.value())
            editor.value_changed.connect(self._on_text_changed)
            FontService().bind_widget_font(editor, "property_edit")

            root_layout.addWidget(label)
            root_layout.addWidget(editor)
        else:
            root_layout = QtWidgets.QHBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(4)

            label = self._create_label(label_width)

            editor = StringEdit()
            editor.setText(context.prop.value())
            editor.value_changed.connect(self._on_text_changed)
            editor.setStyleSheet(self.base_style)
            editor.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
            FontService().bind_widget_font(editor, "property_edit")

            root_layout.addWidget(label)
            root_layout.addWidget(editor)

        self._editor = editor
        self._block_events = False
        self._is_multiline = is_multiline
        self._is_name_prop = is_name_prop
        self._all_existing_names: set[str] | None = None

    def _validate_joint_name(self, new_name: str) -> tuple[bool, str]:
        valid, reason = _is_mujoco_valid_name(new_name)
        if not valid:
            return False, reason

        if self._all_existing_names is None:
            logger.warning(
                "重名检查被跳过（未能获取已有名称列表），关节名称 '%s' 可能重复",
                new_name,
            )
        elif new_name in self._all_existing_names:
            return False, f"关节名称 '{new_name}' 已存在，无法使用重复名称。"

        return True, ""

    def _show_rename_dialog(self, current_name: str):
        dialog = JointRenameDialog(
            current_name=current_name,
            validate=self._validate_joint_name,
            parent=QtWidgets.QApplication.activeWindow(),
        )

        if (
            dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
            and dialog.new_name is not None
        ):
            old_text = self.context.prop.value()
            self._block_events = True
            self.context.prop.set_value(dialog.new_name)
            self._editor.set_value(dialog.new_name)
            self._block_events = False

            task = SceneEditRequestBus().set_property(
                property_key=self.context.key,
                value=dialog.new_name,
                undo=True,
                old_value=old_text,
                source="ui",
            )
            asyncio.create_task(task)

        self._all_existing_names = None
        self._rename_btn.setEnabled(True)

    def _on_rename_clicked(self):
        current_name = self.context.prop.value()
        if not isinstance(current_name, str):
            current_name = str(current_name)

        self._rename_btn.setEnabled(False)

        async def _fetch_and_show():
            try:
                self._all_existing_names = await _fetch_all_existing_names(
                    self.context.actor_path, exclude_key=self.context.key
                )
                logger.info(
                    "_on_rename_clicked: current_name='%s', existing_names=%s",
                    current_name,
                    self._all_existing_names,
                )
            except Exception as e:
                logger.warning(
                    "Failed to fetch existing names, dialog will skip duplicate check: %s",
                    e,
                )
                self._all_existing_names = None

            QtCore.QTimer.singleShot(0, lambda: self._show_rename_dialog(current_name))

        asyncio.create_task(_fetch_and_show())

    def _on_text_changed(self):
        if self._block_events:
            return

        old_text = self.context.prop.value()
        text = self._editor.text()
        normalized = _normalize_float_vec(text)
        commit_text = normalized if normalized is not None else text

        self.context.prop.set_value(commit_text)

        task = SceneEditRequestBus().set_property(
            property_key=self.context.key,
            value=text,
            undo=True,
            old_value=old_text,
            source="ui",
        )
        asyncio.create_task(task)

        if normalized is not None and normalized != text:
            self._block_events = True
            self._editor.set_value(normalized)
            self._block_events = False

    @override
    def set_value(self, value: str):
        self._block_events = True

        normalized = _normalize_float_vec(value)
        display = normalized if normalized is not None else value
        self.context.prop.set_value(display)
        self._editor.setText(display)

        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        if self._is_name_prop:
            if hasattr(self, "_rename_btn"):
                self._rename_btn.setEnabled(not read_only)
            return

        self._editor.setReadOnly(read_only)

        if self._is_multiline and read_only:
            from orcalab.ui.theme_service import ThemeService

            theme = ThemeService()
            bg_color = theme.get_color_hex("property_group_bg")
            text_color = theme.get_color_hex("text")

            self._editor.setStyleSheet(
                f"""
                QPlainTextEdit {{
                    background-color: {bg_color};
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 4px;
                    color: {text_color};
                }}
            """
            )
