import pytest

from orcalab.physical_material import (
    CUSTOM_MATERIAL_NAME,
    PhysicalMaterialManager,
    PhysicalMaterialParams,
    apply_hardness,
    compute_effective_params,
    infer_material_from_params,
)

SIMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PhysicalMaterials version="2.0">
  <Material name="钢铁" display_name="钢铁" category="金属">
    <density value="7800" />
    <friction slide="0.6" spin="0.005" roll="0.0001" />
    <solref timeconst="0.005" dampratio="1.0" />
    <solimp dmin="0.95" dmax="0.99" width="0.001" />
    <condim value="3" />
  </Material>
  <Material name="木头" display_name="木头" category="有机物">
    <density value="600" />
    <friction slide="0.5" spin="0.004" roll="0.0002" />
    <solref timeconst="0.02" dampratio="1.0" />
    <solimp dmin="0.9" dmax="0.95" width="0.001" />
    <condim value="3" />
  </Material>
  <Material name="橡胶" display_name="橡胶" category="聚合物">
    <density value="1100" />
    <friction slide="1.0" spin="0.008" roll="0.0005" />
    <solref timeconst="0.05" dampratio="1.0" />
    <solimp dmin="0.8" dmax="0.9" width="0.002" />
    <condim value="3" />
  </Material>
</PhysicalMaterials>
"""

MALFORMED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PhysicalMaterials version="1.0">
  <Material name="坏材质">
    <density value="not_a_number" />
    <friction slide="0.5" spin="0.004" roll="0.0002" />
    <solref timeconst="0.02" dampratio="1.0" />
    <solimp dmin="0.9" dmax="0.95" width="0.001" />
    <condim value="3" />
  </Material>
  <Material name="好材质" display_name="好材质" category="测试">
    <density value="1000" />
    <friction slide="0.5" spin="0.004" roll="0.0002" />
    <solref timeconst="0.02" dampratio="1.0" />
    <solimp dmin="0.9" dmax="0.95" width="0.001" />
    <condim value="3" />
  </Material>
</PhysicalMaterials>
"""

MISSING_FIELDS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PhysicalMaterials version="1.0">
  <Material name="缺字段">
    <density value="500" />
  </Material>
  <Material name="完整材质" display_name="完整材质" category="测试">
    <density value="2000" />
    <friction slide="0.3" spin="0.002" roll="0.0001" />
    <solref timeconst="0.01" dampratio="1.0" />
    <solimp dmin="0.92" dmax="0.97" width="0.001" />
    <condim value="3" />
  </Material>
</PhysicalMaterials>
"""

NO_NAME_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<PhysicalMaterials version="1.0">
  <Material display_name="无名" category="测试">
    <density value="500" />
    <friction slide="0.3" spin="0.002" roll="0.0001" />
    <solref timeconst="0.01" dampratio="1.0" />
    <solimp dmin="0.92" dmax="0.97" width="0.001" />
    <condim value="3" />
  </Material>
</PhysicalMaterials>
"""


@pytest.fixture
def fresh_manager():
    PhysicalMaterialManager._instance = None
    mgr = PhysicalMaterialManager.instance()
    mgr.load_from_string(SIMPLE_XML)
    yield mgr
    PhysicalMaterialManager._instance = None


@pytest.fixture
def steel_params(fresh_manager):
    return fresh_manager.get_material("钢铁")


@pytest.fixture
def wood_params(fresh_manager):
    return fresh_manager.get_material("木头")


@pytest.fixture
def rubber_params(fresh_manager):
    return fresh_manager.get_material("橡胶")


class TestPhysicalMaterialParams:
    def test_dataclass_fields(self):
        p = PhysicalMaterialParams(
            density=7800,
            friction_slide=0.6,
            friction_spin=0.005,
            friction_roll=0.0001,
            solref_timeconst=0.005,
            solref_dampratio=1.0,
            solimp_dmin=0.95,
            solimp_dmax=0.99,
            solimp_width=0.001,
            condim=3,
            display_name="钢铁",
            category="金属",
        )
        assert p.density == 7800
        assert p.friction_slide == 0.6
        assert p.condim == 3
        assert p.display_name == "钢铁"
        assert p.category == "金属"

    def test_default_optional_fields(self):
        p = PhysicalMaterialParams(
            density=1000,
            friction_slide=0.5,
            friction_spin=0.003,
            friction_roll=0.0001,
            solref_timeconst=0.02,
            solref_dampratio=1.0,
            solimp_dmin=0.9,
            solimp_dmax=0.95,
            solimp_width=0.001,
            condim=3,
        )
        assert p.display_name == ""
        assert p.category == ""


class TestPhysicalMaterialManagerLoad:
    def test_load_from_string(self, fresh_manager):
        assert len(fresh_manager.materials) == 3
        assert fresh_manager.version == "2.0"

    def test_material_names(self, fresh_manager):
        names = fresh_manager.material_names()
        assert "钢铁" in names
        assert "木头" in names
        assert "橡胶" in names

    def test_material_display_names(self, fresh_manager):
        display_names = fresh_manager.material_display_names()
        assert "钢铁" in display_names
        assert "木头" in display_names

    def test_categories(self, fresh_manager):
        cats = fresh_manager.categories()
        assert "金属" in cats
        assert "有机物" in cats
        assert "聚合物" in cats

    def test_materials_by_category(self, fresh_manager):
        metals = fresh_manager.materials_by_category("金属")
        assert len(metals) == 1
        assert "钢铁" in metals

    def test_get_material(self, fresh_manager):
        steel = fresh_manager.get_material("钢铁")
        assert steel is not None
        assert steel.density == 7800
        assert steel.friction_slide == 0.6
        assert steel.friction_spin == 0.005
        assert steel.friction_roll == 0.0001
        assert steel.solref_timeconst == 0.005
        assert steel.solref_dampratio == 1.0
        assert steel.solimp_dmin == 0.95
        assert steel.solimp_dmax == 0.99
        assert steel.solimp_width == 0.001
        assert steel.condim == 3

    def test_get_nonexistent_material(self, fresh_manager):
        assert fresh_manager.get_material("不存在的材质") is None

    def test_singleton(self):
        PhysicalMaterialManager._instance = None
        a = PhysicalMaterialManager.instance()
        b = PhysicalMaterialManager.instance()
        assert a is b
        PhysicalMaterialManager._instance = None

    def test_load_malformed_xml_skips_bad_material(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_string(MALFORMED_XML)
        assert mgr.get_material("坏材质") is None
        assert mgr.get_material("好材质") is not None
        assert mgr.get_material("好材质").density == 1000
        PhysicalMaterialManager._instance = None

    def test_load_missing_fields_skips_material(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_string(MISSING_FIELDS_XML)
        assert mgr.get_material("缺字段") is None
        assert mgr.get_material("完整材质") is not None
        PhysicalMaterialManager._instance = None

    def test_load_no_name_material_skipped(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_string(NO_NAME_XML)
        assert len(mgr.materials) == 0
        PhysicalMaterialManager._instance = None

    def test_load_nonexistent_file(self, tmp_path):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_file(tmp_path / "nonexistent.xml")
        assert len(mgr.materials) == 0
        PhysicalMaterialManager._instance = None

    def test_load_from_file(self, tmp_path):
        xml_file = tmp_path / "test_materials.xml"
        xml_file.write_text(SIMPLE_XML, encoding="utf-8")
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_file(str(xml_file))
        assert len(mgr.materials) == 3
        assert mgr.get_material("钢铁").density == 7800
        PhysicalMaterialManager._instance = None

    def test_reload(self, tmp_path):
        xml_file = tmp_path / "test_materials.xml"
        xml_file.write_text(SIMPLE_XML, encoding="utf-8")
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_file(str(xml_file))
        assert len(mgr.materials) == 3

        updated_xml = SIMPLE_XML.replace("7800", "8000")
        xml_file.write_text(updated_xml, encoding="utf-8")
        mgr.reload()
        assert mgr.get_material("钢铁").density == 8000
        PhysicalMaterialManager._instance = None

    def test_reload_without_previous_load(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.reload()
        assert len(mgr.materials) == 0
        PhysicalMaterialManager._instance = None


class TestApplyHardness:
    def test_hardness_1_returns_base(self, steel_params):
        result = apply_hardness(steel_params, 1.0)
        assert result["solref_timeconst"] == pytest.approx(steel_params.solref_timeconst)
        assert result["solref_dampratio"] == pytest.approx(steel_params.solref_dampratio)
        assert result["solimp_dmin"] == pytest.approx(steel_params.solimp_dmin)
        assert result["solimp_dmax"] == pytest.approx(steel_params.solimp_dmax)
        assert result["solimp_width"] == pytest.approx(steel_params.solimp_width)

    def test_hardness_2_doubles_solref_time(self, steel_params):
        result = apply_hardness(steel_params, 2.0)
        assert result["solref_timeconst"] == pytest.approx(steel_params.solref_timeconst / 2.0)

    def test_hardness_05_doubles_solref_time(self, steel_params):
        result = apply_hardness(steel_params, 0.5)
        assert result["solref_timeconst"] == pytest.approx(steel_params.solref_timeconst / 0.5)

    def test_hardness_above_1_increases_solimp(self, steel_params):
        result = apply_hardness(steel_params, 1.5)
        assert result["solimp_dmin"] > steel_params.solimp_dmin
        assert result["solimp_dmax"] > steel_params.solimp_dmax

    def test_hardness_below_1_decreases_solimp(self, steel_params):
        result = apply_hardness(steel_params, 0.5)
        assert result["solimp_dmin"] < steel_params.solimp_dmin
        assert result["solimp_dmax"] < steel_params.solimp_dmax

    def test_hardness_2_solimp_clamped_near_1(self, steel_params):
        result = apply_hardness(steel_params, 2.0)
        raw_dmin = 1.0 - (1.0 - steel_params.solimp_dmin) * 0.0
        raw_dmax = 1.0 - (1.0 - steel_params.solimp_dmax) * 0.0
        assert result["solimp_dmin"] == pytest.approx(min(raw_dmin, 0.999))
        assert result["solimp_dmax"] == pytest.approx(min(raw_dmax, 0.999))

    def test_hardness_0_solimp_clamped_at_floor(self, steel_params):
        result = apply_hardness(steel_params, 0.0)
        assert result["solimp_dmin"] == 0.01
        assert result["solimp_dmax"] == 0.01

    def test_hardness_reduces_solimp_width(self, steel_params):
        result = apply_hardness(steel_params, 1.5)
        assert result["solimp_width"] < steel_params.solimp_width

    def test_hardness_increases_solimp_width(self, steel_params):
        result = apply_hardness(steel_params, 0.5)
        assert result["solimp_width"] > steel_params.solimp_width

    def test_solref_timeconst_clamped_to_minimum(self, steel_params):
        result = apply_hardness(steel_params, 100.0)
        assert result["solref_timeconst"] >= 0.001

    def test_solimp_dmin_dmax_clamped(self, steel_params):
        result = apply_hardness(steel_params, 0.0)
        assert result["solimp_dmin"] >= 0.01
        assert result["solimp_dmax"] >= 0.01
        assert result["solimp_dmin"] <= 0.999
        assert result["solimp_dmax"] <= 0.999

    def test_solimp_width_clamped(self, steel_params):
        result = apply_hardness(steel_params, 100.0)
        assert result["solimp_width"] >= 0.0001

    def test_solimp_dmin_leq_dmax(self, steel_params):
        for h in [0.0, 0.1, 0.5, 1.0, 1.5, 2.0]:
            result = apply_hardness(steel_params, h)
            assert result["solimp_dmin"] <= result["solimp_dmax"]


class TestComputeEffectiveParams:
    def test_default_params_match_base(self, fresh_manager, steel_params):
        result = compute_effective_params("钢铁", 1.0, 1.0, 1.0)
        assert result["density"] == pytest.approx(steel_params.density)
        assert result["friction.x"] == pytest.approx(steel_params.friction_slide)
        assert result["friction.y"] == pytest.approx(steel_params.friction_spin)
        assert result["friction.z"] == pytest.approx(steel_params.friction_roll)
        assert result["condim"] == steel_params.condim

    def test_custom_material_returns_empty(self, fresh_manager):
        result = compute_effective_params(CUSTOM_MATERIAL_NAME, 1.0, 1.0, 1.0)
        assert result == {}

    def test_nonexistent_material_returns_empty(self, fresh_manager):
        result = compute_effective_params("不存在的材质", 1.0, 1.0, 1.0)
        assert result == {}

    def test_solidity_affects_density(self, fresh_manager, steel_params):
        result_half = compute_effective_params("钢铁", 0.5, 1.0, 1.0)
        assert result_half["density"] == pytest.approx(steel_params.density * 0.5)

    def test_solidity_zero_density_clamped(self, fresh_manager):
        result = compute_effective_params("钢铁", 0.0, 1.0, 1.0)
        assert result["density"] > 0

    def test_roughness_affects_friction(self, fresh_manager, steel_params):
        result = compute_effective_params("钢铁", 1.0, 1.5, 1.0)
        assert result["friction.x"] == pytest.approx(steel_params.friction_slide * 1.5)
        assert result["friction.y"] == pytest.approx(steel_params.friction_spin * 1.5)
        assert result["friction.z"] == pytest.approx(steel_params.friction_roll * 1.5)

    def test_roughness_zero_friction_clamped(self, fresh_manager):
        result = compute_effective_params("钢铁", 1.0, 0.0, 1.0)
        assert result["friction.x"] >= 1e-5
        assert result["friction.y"] >= 1e-5
        assert result["friction.z"] >= 1e-5

    def test_hardness_affects_solref_and_solimp(self, fresh_manager, steel_params):
        result = compute_effective_params("钢铁", 1.0, 1.0, 0.5)
        assert result["solref.x"] != pytest.approx(steel_params.solref_timeconst)
        assert result["solimp.x"] != pytest.approx(steel_params.solimp_dmin)

    def test_combined_params(self, fresh_manager, wood_params):
        result = compute_effective_params("木头", 0.5, 2.0, 0.5)
        assert result["density"] == pytest.approx(wood_params.density * 0.5)
        assert result["friction.x"] == pytest.approx(wood_params.friction_slide * 2.0)
        assert result["condim"] == wood_params.condim

    def test_result_has_all_keys(self, fresh_manager):
        result = compute_effective_params("钢铁", 1.0, 1.0, 1.0)
        expected_keys = {
            "density",
            "friction.x", "friction.y", "friction.z",
            "solref.x", "solref.y",
            "solimp.x", "solimp.y", "solimp.z",
            "condim",
        }
        assert set(result.keys()) == expected_keys


class TestInferMaterialFromParams:
    def test_exact_steel_params(self, fresh_manager):
        steel = fresh_manager.get_material("钢铁")
        result = infer_material_from_params(
            steel.density,
            (steel.friction_slide, steel.friction_spin, steel.friction_roll),
            (steel.solref_timeconst, steel.solref_dampratio),
            (steel.solimp_dmin, steel.solimp_dmax, steel.solimp_width),
        )
        assert result == "钢铁"

    def test_exact_wood_params(self, fresh_manager):
        wood = fresh_manager.get_material("木头")
        result = infer_material_from_params(
            wood.density,
            (wood.friction_slide, wood.friction_spin, wood.friction_roll),
            (wood.solref_timeconst, wood.solref_dampratio),
            (wood.solimp_dmin, wood.solimp_dmax, wood.solimp_width),
        )
        assert result == "木头"

    def test_slightly_modified_still_matches(self, fresh_manager):
        steel = fresh_manager.get_material("钢铁")
        result = infer_material_from_params(
            steel.density * 1.05,
            (steel.friction_slide * 1.05, steel.friction_spin, steel.friction_roll),
            (steel.solref_timeconst, steel.solref_dampratio),
            (steel.solimp_dmin, steel.solimp_dmax, steel.solimp_width),
        )
        assert result == "钢铁"

    def test_greatly_modified_returns_custom(self, fresh_manager):
        result = infer_material_from_params(
            99999,
            (99.0, 0.5, 0.1),
            (1.0, 0.1),
            (0.1, 0.2, 0.5),
        )
        assert result == CUSTOM_MATERIAL_NAME

    def test_empty_manager_returns_custom(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        result = infer_material_from_params(
            7800,
            (0.6, 0.005, 0.0001),
            (0.005, 1.0),
            (0.95, 0.99, 0.001),
        )
        assert result == CUSTOM_MATERIAL_NAME
        PhysicalMaterialManager._instance = None


class TestLoadFromActualXML:
    def test_load_default_xml(self):
        PhysicalMaterialManager._instance = None
        mgr = PhysicalMaterialManager.instance()
        mgr.load_from_file()
        assert len(mgr.materials) == 9
        assert mgr.version == "1.0"
        steel = mgr.get_material("钢铁")
        assert steel is not None
        assert steel.density == 7800
        assert steel.category == "金属"
        foam = mgr.get_material("泡沫")
        assert foam is not None
        assert foam.density == 50
        assert foam.category == "聚合物"
        PhysicalMaterialManager._instance = None
