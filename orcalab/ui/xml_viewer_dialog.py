import asyncio
import copy
import logging
import xml.etree.ElementTree as ET

from PySide6 import QtCore, QtWidgets, QtGui
import grpc
from orca_gym.protos import mjc_message_pb2, mjc_message_pb2_grpc

from orcalab.actor import AssetActor
from orcalab.application_util import get_local_scene, get_remote_scene
from orcalab.config_service import ConfigService
from orcalab.i18n import tr
from orcalab.metadata_service_bus import MetadataServiceRequestBus
from orcalab.path import Path
from orcalab.pyside_util import connect
from orcalab.simulation.simulation_bus import (
    SimulationRequestBus,
    SimulationState,
)

logger = logging.getLogger(__name__)


def _is_robot_actor(actor: AssetActor) -> bool:
    try:
        output: list[dict] = []
        MetadataServiceRequestBus().get_asset_map(output)
        asset_map: dict = output[0] if output else {}

        actor_asset_path = (actor.asset_path or "").strip()
        for map_key, metadata in asset_map.items():
            if map_key.lower() == actor_asset_path:
                if metadata and (
                    metadata.get("projectName", "") == "robot_adapt"
                    or metadata.get("categoryPath", "") == "/robot"
                ):
                    return True
                break
        return False
    except Exception:
        logger.exception("检查 Actor 是否为机器人失败")
        return False


class XmlViewerDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MuJoCo XML 查看器")
        self.resize(1000, 750)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        self._full_xml: str | None = None
        self._is_fetching = False
        self._init_ui()

    def closeEvent(self, event):
        if self._is_fetching:
            event.ignore()
            return
        super().closeEvent(event)

    def _get_asset_actors(self) -> list[tuple[str, Path]]:
        try:
            local_scene = get_local_scene()
            actors = local_scene.actors

            result: list[tuple[str, Path]] = []
            for actor_path, actor in actors.items():
                if isinstance(actor, AssetActor) and _is_robot_actor(actor):
                    result.append((actor.name, actor_path))

            result.sort(key=lambda x: x[0])
            return result
        except Exception:
            logger.exception("获取 Actor 列表失败")
            return []

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # ── 顶部：Actor 选择 + 文件按钮 ──
        top_layout = QtWidgets.QHBoxLayout()

        top_layout.addWidget(QtWidgets.QLabel("选择机器人:"))
        self.actor_combo = QtWidgets.QComboBox()

        actors = self._get_asset_actors()
        if actors:
            for name, path in actors:
                self.actor_combo.addItem(f"{name}", path)
        else:
            self.actor_combo.addItem(tr("（场景中无 AssetActor）"), None)
        self.actor_combo.setMinimumWidth(300)
        top_layout.addWidget(self.actor_combo, 1)

        top_layout.addStretch()

        layout.addLayout(top_layout)

        # ── XML 文本编辑区 ──
        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        font_db = QtGui.QFontDatabase()
        if font_db.hasFamily("Courier New"):
            font = QtGui.QFont("Courier New", 10)
        else:
            font = QtGui.QFont("monospace", 10)
        self.text_edit.setFont(font)
        self.text_edit.setLineWrapMode(
            QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.text_edit.setPlaceholderText("选择机器人后点击「查看 XML」...")
        layout.addWidget(self.text_edit, 1)

        # ── 按钮区 ──
        button_layout = QtWidgets.QHBoxLayout()

        self.fetch_btn = QtWidgets.QPushButton("查看 XML")
        self.fetch_btn.setMinimumWidth(120)

        self.copy_btn = QtWidgets.QPushButton("复制")


        button_layout.addWidget(self.fetch_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.copy_btn)

        layout.addLayout(button_layout)

        # ── 连接信号 ──
        connect(self.fetch_btn.clicked, self._on_fetch_async)
        self.copy_btn.clicked.connect(self._on_copy)

    def fetch_for_actor(self, actor_path: Path):
        for i in range(self.actor_combo.count()):
            if self.actor_combo.itemData(i) == actor_path:
                self.actor_combo.setCurrentIndex(i)
                break
        asyncio.create_task(self._on_fetch_async())

    def _get_simulation_state(self) -> SimulationState:
        out: list[SimulationState] = []
        SimulationRequestBus().get_simulation_state(out)
        return out[0] if out else SimulationState.Stopped

    async def _on_fetch_async(self):
        self._is_fetching = True
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("加载中...")
        self.text_edit.setPlainText("")

        try:
            state = self._get_simulation_state()
            is_running = state == SimulationState.Running

            actor_path: Path | None = self.actor_combo.currentData()
            actor_name = get_local_scene().find_actor_by_path(actor_path).name

            if is_running:
                self._full_xml = self._call_load_local_env_sync()
            else:
                self._full_xml = await self._fetch_xml_in_edit_mode_async()

            if actor_name is not None:
                self.text_edit.setPlainText(
                    self._extract_actor_xml(self._full_xml, actor_name)
                )
            else:
                self.text_edit.setPlainText(tr("获取XML失败"))

            self.fetch_btn.setText("刷新 XML")
            logger.info("成功获取 XML")

        except Exception as e:
            logger.exception("获取 XML 失败")
            QtWidgets.QMessageBox.warning(
                self, "获取失败", tr("无法获取 XML：\n{error}", error=e)
            )
        finally:
            self.fetch_btn.setEnabled(True)
            self._is_fetching = False
            if not self.text_edit.toPlainText():
                self.fetch_btn.setText("生成 XML")

    def _on_copy(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())

    async def _fetch_xml_in_edit_mode_async(self) -> str:
        remote_scene = get_remote_scene()

        await remote_scene.publish_scene()
        await asyncio.sleep(0.5)
        await remote_scene.save_state()
        await asyncio.sleep(0.5)

        success = await remote_scene.change_sim_state(True)
        await asyncio.sleep(0.5)
        if not success:
            raise RuntimeError(tr("启动仿真引擎失败"))

        try:
            logger.info("读取 MJCF...")
            full_xml = await asyncio.to_thread(self._call_load_local_env_sync)
            
            return full_xml
        finally:
            logger.info("停止仿真引擎...")
            await remote_scene.change_sim_state(False)

    def _call_load_local_env_sync(self) -> str:
        config_service = ConfigService()
        sim_port = config_service.sim_port()

        channel = grpc.insecure_channel(f"localhost:{sim_port}")
        try:
            stub = mjc_message_pb2_grpc.GrpcServiceStub(channel)
            request = mjc_message_pb2.LoadLocalEnvRequest()
            request.req_type = (
                mjc_message_pb2.LoadLocalEnvRequest.XML_FILE_CONTENT
            )
            response = stub.LoadLocalEnv(request, timeout=30)
            if (
                response.status
                != mjc_message_pb2.LoadLocalEnvResponse.SUCCESS
            ):
                error_msg = response.error_message or tr("未知错误")
                raise RuntimeError(
                    tr(
                        "引擎返回错误（status={status}）：{error}",
                        status=response.status,
                        error=error_msg,
                    )
                )
            return response.xml_content.decode("utf-8")
        finally:
            channel.close()


    def _extract_actor_xml(
        self, full_xml: str, actor_name: str
    ) -> str:
        try:
            root = ET.fromstring(full_xml)
        except ET.ParseError as e:
            logger.warning("XML 解析失败，返回完整 XML: %s", e)
            return full_xml
        
        prefix = f"{actor_name}_"
        
        output = ET.Element("mujoco", attrib={"model": actor_name})
        actor_worldbody = ET.Element("worldbody")
        actor_contact = ET.Element('contact')
        actor_equality = ET.Element('equality')
        actor_tendon = ET.Element('tendon')

        worldbody = root.find("worldbody")
        if worldbody is None:
            return full_xml

        def _clear_whitespace(elem):
            elem.text = None
            elem.tail = None
            for child in elem:
                _clear_whitespace(child)

        for body in worldbody.findall(".//body"):
            bname = body.get("name", "")
            if bname.startswith(prefix):
                body_copy = copy.deepcopy(body)
                _clear_whitespace(body_copy)
                actor_worldbody.append(body_copy)

        for tag in ("compiler", "option", "size", "visual", "default"):
            src = root.find(tag)
            if src is not None:
                output.append(src)

        for child in root.find('contact'):
            if child.tag == 'exclude' and child.get('body1').startswith(prefix):
                actor_contact.append(child)

        for child in root.find('equality'):
            if child.tag == 'connect' and child.get('body1').startswith(prefix):
                actor_equality.append(child)
            elif child.tag == 'weld' and child.get('body1').startswith(prefix):
                actor_equality.append(child)
            elif child.tag == 'joint' and child.get('joint1').startswith(prefix):
                actor_equality.append(child)

        for child in root.find('tendon'):
            if child.get('name').startswith(prefix):
                actor_tendon.append(child)

        output.append(actor_worldbody)
        output.append(actor_contact)
        output.append(actor_equality)
        output.append(actor_tendon)

        ET.indent(output, space="  ")
        return ET.tostring(output, encoding="unicode")
