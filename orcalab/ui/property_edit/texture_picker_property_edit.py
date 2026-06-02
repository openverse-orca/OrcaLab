from typing import override
from PySide6 import QtCore, QtWidgets

from orcalab.ui.property_edit.base_property_edit import (
    BasePropertyEdit,
    PropertyEditContext,
)
from orcalab.ui.fonts.font_service import FontService
from orcalab.ui.theme_service import ThemeService
from orcalab.texture_asset_cache import TextureAssetCache


def _extract_texture_display_name(path: str) -> str:
    filename = path.replace("\\", "/").split("/")[-1]
    if filename.endswith(".streamingimage"):
        filename = filename[:-len(".streamingimage")]
    for ext in (".png", ".jpg", ".jpeg", ".tga", ".dds", ".bmp", ".tif", ".tiff", ".exr", ".hdr"):
        if filename.lower().endswith(ext):
            filename = filename[:-len(ext)]
            break
    return filename


class TexturePickerPropertyEdit(BasePropertyEdit[str]):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        context: PropertyEditContext,
        label_width: int,
        cache: TextureAssetCache,
    ):
        super().__init__(parent, context)
        self._cache = cache

        root_layout = QtWidgets.QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        label = self._create_label(label_width)
        root_layout.addWidget(label)

        self._path_edit = QtWidgets.QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self._path_edit.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        FontService().bind_widget_font(self._path_edit, "property_edit")
        root_layout.addWidget(self._path_edit)

        self._pick_button = QtWidgets.QPushButton("•••")
        self._pick_button.setFixedWidth(32)
        self._pick_button.setToolTip("选择纹理")
        self._pick_button.clicked.connect(self._on_pick_clicked)
        FontService().bind_widget_font(self._pick_button, "property_edit")
        root_layout.addWidget(self._pick_button)

        self._block_events = False
        self._update_display()

    def _update_display(self):
        uuid_str = self.context.prop.value()
        if not uuid_str:
            self._path_edit.setText("")
            self._path_edit.setStyleSheet("")
            return

        path = self._cache.get_path(uuid_str)
        if path:
            self._path_edit.setText(_extract_texture_display_name(path))
            self._path_edit.setStyleSheet("")
        else:
            self._path_edit.setText(uuid_str)
            theme = ThemeService()
            gray_color = theme.get_color_hex("text_disabled")
            self._path_edit.setStyleSheet(f"color: {gray_color};")

    def _on_pick_clicked(self):
        from orcalab.ui.property_edit.texture_select_dialog import (
            TextureSelectDialog,
        )

        dialog = TextureSelectDialog(self._cache, self.window())
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            uuid_str = dialog.selected_uuid()
            if uuid_str is not None:
                self._block_events = True
                self.context.prop.set_value(uuid_str)
                self._update_display()
                self._block_events = False
                self._do_set_value(uuid_str, undo=True)

    @override
    def set_value(self, value: str):
        self._block_events = True
        self.context.prop.set_value(value)
        self._update_display()
        self._block_events = False

    @override
    def set_read_only(self, read_only: bool):
        self._pick_button.setEnabled(not read_only)