import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ASSETS_PHYSICS_DIR = Path(__file__).parent / "assets" / "physics"
DEFAULT_XML_PATH = ASSETS_PHYSICS_DIR / "physical_materials.xml"

CUSTOM_MATERIAL_NAME = "自定义"


@dataclass
class PhysicalMaterialParams:
    density: float
    friction_slide: float
    friction_spin: float
    friction_roll: float
    solref_timeconst: float
    solref_dampratio: float
    solimp_dmin: float
    solimp_dmax: float
    solimp_width: float
    condim: int
    display_name: str = ""
    category: str = ""


class PhysicalMaterialManager:
    _instance: Optional["PhysicalMaterialManager"] = None

    def __init__(self):
        self._materials: dict[str, PhysicalMaterialParams] = {}
        self._version: str = ""
        self._loaded_path: Path | None = None

    @classmethod
    def instance(cls) -> "PhysicalMaterialManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_from_file(self, xml_path: Path | str | None = None) -> None:
        path = Path(xml_path) if xml_path else DEFAULT_XML_PATH
        if not path.exists():
            logger.warning("Physical materials XML not found: %s", path)
            return

        try:
            tree = ET.parse(path)
            root = tree.getroot()
            self._parse_root(root)
            self._loaded_path = path
            logger.info(
                "Loaded %d physical materials from %s (version=%s)",
                len(self._materials), path, self._version,
            )
        except Exception as e:
            logger.error("Failed to load physical materials XML: %s", e)

    def load_from_string(self, xml_string: str) -> None:
        try:
            root = ET.fromstring(xml_string)
            self._parse_root(root)
        except Exception as e:
            logger.error("Failed to parse physical materials XML string: %s", e)

    async def load_from_url(self, url: str) -> None:
        pass

    def reload(self) -> None:
        if self._loaded_path is not None:
            self.load_from_file(self._loaded_path)

    def _parse_root(self, root: ET.Element) -> None:
        self._version = root.get("version", "1.0")
        materials: dict[str, PhysicalMaterialParams] = {}

        for mat_elem in root.findall("Material"):
            name = mat_elem.get("name")
            if not name:
                continue

            try:
                density = float(mat_elem.find("density").get("value"))

                friction_elem = mat_elem.find("friction")
                friction_slide = float(friction_elem.get("slide"))
                friction_spin = float(friction_elem.get("spin"))
                friction_roll = float(friction_elem.get("roll"))

                solref_elem = mat_elem.find("solref")
                solref_timeconst = float(solref_elem.get("timeconst"))
                solref_dampratio = float(solref_elem.get("dampratio"))

                solimp_elem = mat_elem.find("solimp")
                solimp_dmin = float(solimp_elem.get("dmin"))
                solimp_dmax = float(solimp_elem.get("dmax"))
                solimp_width = float(solimp_elem.get("width"))

                condim = int(mat_elem.find("condim").get("value"))

                materials[name] = PhysicalMaterialParams(
                    density=density,
                    friction_slide=friction_slide,
                    friction_spin=friction_spin,
                    friction_roll=friction_roll,
                    solref_timeconst=solref_timeconst,
                    solref_dampratio=solref_dampratio,
                    solimp_dmin=solimp_dmin,
                    solimp_dmax=solimp_dmax,
                    solimp_width=solimp_width,
                    condim=condim,
                    display_name=mat_elem.get("display_name", name),
                    category=mat_elem.get("category", ""),
                )
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning("Skipping material '%s': parse error: %s", name, e)
                continue

        self._materials = materials

    @property
    def materials(self) -> dict[str, PhysicalMaterialParams]:
        return self._materials

    @property
    def version(self) -> str:
        return self._version

    def get_material(self, name: str) -> PhysicalMaterialParams | None:
        return self._materials.get(name)

    def material_names(self) -> list[str]:
        return list(self._materials.keys())

    def material_display_names(self) -> list[str]:
        return [m.display_name or name for name, m in self._materials.items()]

    def categories(self) -> list[str]:
        return list(set(m.category for m in self._materials.values() if m.category))

    def materials_by_category(self, category: str) -> dict[str, PhysicalMaterialParams]:
        return {k: v for k, v in self._materials.items() if v.category == category}


def apply_hardness(base: PhysicalMaterialParams, hardness: float) -> dict:
    effective_solref_timeconst = base.solref_timeconst / max(hardness, 0.01)
    effective_solref_dampratio = base.solref_dampratio

    if hardness >= 1.0:
        t = min((hardness - 1.0) / 1.0, 1.0)
        effective_solimp_dmin = base.solimp_dmin + (1.0 - base.solimp_dmin) * t
        effective_solimp_dmax = base.solimp_dmax + (1.0 - base.solimp_dmax) * t
    else:
        t = min((1.0 - hardness) / 1.0, 1.0)
        effective_solimp_dmin = base.solimp_dmin * (1.0 - t)
        effective_solimp_dmax = base.solimp_dmax * (1.0 - t)

    effective_solimp_width = base.solimp_width * max(2.0 - hardness, 0.01)

    effective_solref_timeconst = max(effective_solref_timeconst, 0.001)
    effective_solimp_dmin = max(min(effective_solimp_dmin, 0.999), 0.01)
    effective_solimp_dmax = max(min(effective_solimp_dmax, 0.999), 0.01)
    if effective_solimp_dmin > effective_solimp_dmax:
        effective_solimp_dmin, effective_solimp_dmax = effective_solimp_dmax, effective_solimp_dmin
    effective_solimp_width = max(effective_solimp_width, 0.0001)

    return {
        "solref_timeconst": effective_solref_timeconst,
        "solref_dampratio": effective_solref_dampratio,
        "solimp_dmin": effective_solimp_dmin,
        "solimp_dmax": effective_solimp_dmax,
        "solimp_width": effective_solimp_width,
    }


def compute_effective_params(
    material_name: str,
    solidity: float,
    roughness: float,
    hardness: float,
) -> dict:
    if material_name == CUSTOM_MATERIAL_NAME:
        return {}

    base = PhysicalMaterialManager.instance().get_material(material_name)
    if base is None:
        return {}

    effective_density = base.density * max(solidity, 0.001)

    effective_friction_slide = max(base.friction_slide * roughness, 1e-5)
    effective_friction_spin = max(base.friction_spin * roughness, 1e-5)
    effective_friction_roll = max(base.friction_roll * roughness, 1e-5)

    hardness_params = apply_hardness(base, hardness)

    return {
        "density": effective_density,
        "friction.x": effective_friction_slide,
        "friction.y": effective_friction_spin,
        "friction.z": effective_friction_roll,
        "solref.x": hardness_params["solref_timeconst"],
        "solref.y": hardness_params["solref_dampratio"],
        "solimp.x": hardness_params["solimp_dmin"],
        "solimp.y": hardness_params["solimp_dmax"],
        "solimp.z": hardness_params["solimp_width"],
        "condim": base.condim,
    }


def infer_material_from_params(
    current_density: float,
    current_friction: tuple,
    current_solref: tuple,
    current_solimp: tuple,
) -> str:
    best_match = CUSTOM_MATERIAL_NAME
    best_score = float("inf")

    for name, base in PhysicalMaterialManager.instance().materials.items():
        score = 0.0
        if base.density > 0:
            score += ((current_density - base.density) / base.density) ** 2
        if base.friction_slide > 0:
            score += ((current_friction[0] - base.friction_slide) / base.friction_slide) ** 2
        if base.solref_timeconst > 0:
            score += ((current_solref[0] - base.solref_timeconst) / base.solref_timeconst) ** 2
        if base.solimp_dmax > 0:
            score += ((current_solimp[1] - base.solimp_dmax) / base.solimp_dmax) ** 2

        if score < best_score:
            best_score = score
            best_match = name

    if best_score > 0.5:
        return CUSTOM_MATERIAL_NAME

    return best_match
