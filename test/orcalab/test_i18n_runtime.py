import re

import pytest
import requests

import orcalab.i18n as i18n_module
from orcalab.cli_options import create_argparser, preparse_ui_language
from orcalab.gpu_driver_check import (
    DriverStatus,
    GpuDeviceInfo,
    GpuDriverCheckResult,
    GpuVendor,
    build_driver_detail_text,
    build_driver_guidance_text,
)
from orcalab.i18n import (
    detect_system_language,
    get_language,
    language_from_locale,
    normalize_language,
    resolve_language,
    resolve_startup_language,
    set_language,
    tr,
)
from orcalab.python_project_installer import _build_user_friendly_install_error

_HAN_RE = re.compile(r"[\u3400-\u9fff]")


@pytest.fixture(autouse=True)
def _english_language():
    previous_language = get_language()
    set_language("en_US")
    try:
        yield
    finally:
        set_language(previous_language)


def _assert_english(text: str, *expected_fragments: str) -> None:
    assert not _HAN_RE.search(text), f"English UI text contains Chinese: {text!r}"
    lowered = text.lower()
    for fragment in expected_fragments:
        assert fragment.lower() in lowered


def test_unspecified_language_defaults_to_english():
    assert normalize_language(None) == "en_US"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("变换", "Transform"),
        ("网格", "Mesh"),
        ("方向光源", "Directional Light"),
        ("区域光源", "Area Light"),
        ("材质", "Material"),
        ("碰撞体", "Geometry"),
        ("刚体", "Rigid Body"),
        ("肌腱", "Tendon"),
        ("关节", "Joint"),
        ("标记点", "Site"),
        ("相机", "Camera"),
        ("执行器", "Actuator"),
        ("传感器", "Sensor"),
        ("未加载", "Not Loaded"),
        ("自定义", "Custom"),
        ("钢铁", "Steel"),
        ("铝合金", "Aluminum Alloy"),
        ("木头", "Wood"),
        ("塑料", "Plastic"),
        ("橡胶", "Rubber"),
        ("石头", "Stone"),
        ("玻璃", "Glass"),
        ("冰", "Ice"),
        ("泡沫", "Foam"),
    ],
)
def test_engine_property_metadata_has_english_translations(source, expected):
    translated = tr(source)

    assert translated == expected
    _assert_english(translated)


@pytest.mark.parametrize(
    "locale_name",
    [
        "zh",
        "zh-CN",
        "zh_TW.UTF-8",
        "zh-HK",
        "zh-MO",
        "zh-SG",
        "zh-Hans",
        "zh-Hant-TW",
        "Chinese (Traditional)_Hong Kong",
    ],
)
def test_chinese_locale_variants_use_chinese(locale_name):
    assert language_from_locale(locale_name) == "zh_CN"


@pytest.mark.parametrize(
    "locale_name",
    [None, "", "C", "POSIX", "en-US", "en_GB.UTF-8", "ja_JP", "ko-KR"],
)
def test_non_chinese_locales_use_english(locale_name):
    assert language_from_locale(locale_name) == "en_US"


@pytest.mark.parametrize(
    "language",
    ["zh_TW", "zh-HK", "zh_Hans", "zh-Hant-TW"],
)
def test_explicit_chinese_language_variants_are_normalized(language):
    assert normalize_language(language) == "zh_CN"


@pytest.mark.parametrize(
    ("qt_locale", "expected"),
    [("zh-Hans-CN", "zh_CN"), ("zh-Hant-TW", "zh_CN"), ("en-US", "en_US")],
)
def test_qt_system_ui_language_is_used(monkeypatch, qt_locale, expected):
    monkeypatch.setattr(i18n_module.sys, "platform", "darwin")
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: qt_locale)

    assert detect_system_language() == expected


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({"LANG": "zh_CN.UTF-8"}, "zh_CN"),
        ({"LC_MESSAGES": "zh_TW.UTF-8"}, "zh_CN"),
        ({"LANGUAGE": "zh_Hant_TW:en_US"}, "zh_CN"),
        ({"LANG": "en_US.UTF-8"}, "en_US"),
        ({"LANG": "ja_JP.UTF-8"}, "en_US"),
        ({"LANGUAGE": "en_US:zh_CN", "LANG": "zh_CN.UTF-8"}, "en_US"),
    ],
)
def test_ubuntu_locale_environment_fallback(monkeypatch, environment, expected):
    monkeypatch.setattr(i18n_module.sys, "platform", "linux")
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: "en-US")
    for variable_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(variable_name, raising=False)
    for variable_name, value in environment.items():
        monkeypatch.setenv(variable_name, value)

    assert detect_system_language() == expected


def test_ubuntu_qt_locale_is_used_when_environment_is_empty(monkeypatch):
    monkeypatch.setattr(i18n_module.sys, "platform", "linux")
    for variable_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(variable_name, raising=False)
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: "zh-CN")

    assert detect_system_language() == "zh_CN"


@pytest.mark.parametrize("language_id", [0x0004, 0x0404, 0x0804, 0x0C04, 0x1004, 0x1404])
def test_windows_chinese_ui_language_ids_use_chinese(monkeypatch, language_id):
    monkeypatch.setattr(i18n_module.sys, "platform", "win32")
    monkeypatch.setattr(
        i18n_module, "_windows_ui_language_id", lambda: language_id
    )
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: "en-US")

    assert detect_system_language() == "zh_CN"


def test_windows_native_ui_language_takes_priority_over_qt(monkeypatch):
    monkeypatch.setattr(i18n_module.sys, "platform", "win32")
    monkeypatch.setattr(i18n_module, "_windows_ui_language_id", lambda: 0x0409)
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: "zh-CN")

    assert detect_system_language() == "en_US"


def test_windows_qt_locale_is_used_when_native_detection_fails(monkeypatch):
    monkeypatch.setattr(i18n_module.sys, "platform", "win32")
    monkeypatch.setattr(i18n_module, "_windows_ui_language_id", lambda: None)
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: "zh-CN")

    assert detect_system_language() == "zh_CN"


def test_system_language_detection_fails_safe_to_english(monkeypatch):
    monkeypatch.setattr(i18n_module.sys, "platform", "linux")
    monkeypatch.setattr(i18n_module, "_qt_ui_locale_name", lambda: None)
    for variable_name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(variable_name, raising=False)

    def raise_locale_error():
        raise i18n_module.locale.Error("invalid locale")

    monkeypatch.setattr(i18n_module.locale, "getlocale", raise_locale_error)

    assert detect_system_language() == "en_US"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--lang", "zh_CN"], "zh_CN"),
        (["--lang=en_US"], "en_US"),
        (["--lang", "zh_CN", "--lang=en_US"], "en_US"),
        (["--initial-lang", "zh_CN"], None),
        (
            ["--initial-lang=en_US", "--lang", "zh_CN"],
            "zh_CN",
        ),
    ],
)
def test_launch_language_option_is_preparsed(argv, expected):
    assert preparse_ui_language(argv) == expected


def test_legacy_initial_language_option_is_hidden_and_ignored():
    args = create_argparser().parse_args(["--initial-lang", "zh_CN"])
    help_text = create_argparser().format_help()

    assert args.lang is None
    assert "--lang" in help_text
    assert "--initial-lang" not in help_text
    assert "subsequent launches" in help_text


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        (("zh_CN", "en_US"), "zh_CN"),
        ((None, "zh_CN"), "zh_CN"),
        ((None, None), "en_US"),
    ],
)
def test_language_resolution_uses_the_first_available_source(candidates, expected):
    assert resolve_language(*candidates) == expected


@pytest.mark.parametrize(
    ("explicit", "saved", "detected", "expected", "detection_count"),
    [
        ("en_US", "zh_CN", "zh_CN", "en_US", 0),
        (None, "zh_CN", "en_US", "zh_CN", 0),
        (None, None, "zh_CN", "zh_CN", 1),
        (None, None, "en_US", "en_US", 1),
    ],
)
def test_startup_language_detects_system_only_without_higher_priority_source(
    monkeypatch, explicit, saved, detected, expected, detection_count
):
    calls = 0

    def detect():
        nonlocal calls
        calls += 1
        return detected

    monkeypatch.setattr(i18n_module, "detect_system_language", detect)

    assert resolve_startup_language(explicit, saved) == expected
    assert calls == detection_count


def test_gpu_text_without_detected_hardware_is_english():
    result = GpuDriverCheckResult()

    guidance = build_driver_guidance_text(result)
    detail = build_driver_detail_text(result)

    _assert_english(guidance, "GPU", "RTX 3060")
    _assert_english(detail, "GPU")


@pytest.mark.parametrize(
    ("vendor", "name", "tool", "expected_vendor"),
    [
        (
            GpuVendor.MOORE_THREADS,
            "Moore Threads MTT S80",
            "mthreads-gmi",
            "Moore Threads",
        ),
        (GpuVendor.UNKNOWN, "Mystery Accelerator", "vendor-tool", "Unknown"),
    ],
)
def test_gpu_text_for_unavailable_domestic_or_unknown_driver_is_english(
    vendor: GpuVendor,
    name: str,
    tool: str,
    expected_vendor: str,
):
    device = GpuDeviceInfo(
        vendor=vendor,
        name=name,
        pci_address="0000:01:00.0",
        driver_status=DriverStatus.NOT_INSTALLED,
        driver_cli_tool=tool,
        memory_total_mb="16384",
    )
    result = GpuDriverCheckResult(
        has_gpu_hardware=True,
        has_working_driver=False,
        devices=[device],
    )

    guidance = build_driver_guidance_text(result)
    detail = build_driver_detail_text(result)

    _assert_english(guidance, name, expected_vendor, tool, "driver")
    _assert_english(detail, name, expected_vendor, tool, "driver", "16384")


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(
        f"{status_code} response from download server",
        response=response,
    )


@pytest.mark.parametrize(
    ("error", "expected_fragment"),
    [
        (
            requests.exceptions.ProxyError("proxy at http://localhost:7890 is unavailable"),
            "proxy",
        ),
        (requests.exceptions.SSLError("certificate verify failed"), "certificate"),
        (requests.exceptions.Timeout("request timed out"), "timed out"),
        (_http_error(404), "download"),
        (
            requests.exceptions.ConnectionError("temporary failure in name resolution"),
            "DNS",
        ),
        (requests.exceptions.RequestException("network request failed"), "network"),
        (RuntimeError("archive extraction failed"), "installation"),
    ],
)
def test_python_project_installer_friendly_errors_are_english(
    error: Exception,
    expected_fragment: str,
):
    message = _build_user_friendly_install_error(error)

    _assert_english(message, expected_fragment, str(error))


@pytest.mark.parametrize(
    ("source", "kwargs", "expected_fragments"),
    [
        (
            "终止并继续（{seconds}s）",
            {"seconds": 3},
            ("terminate", "continue", "3s"),
        ),
        (
            "请手动结束以下进程后重新启动 OrcaLab:\n{pids}",
            {"pids": "101, 202"},
            ("OrcaLab", "101, 202"),
        ),
        (
            "加载场景布局时产生 {count} 条警告：",
            {"count": 7},
            ("layout", "warning", "7"),
        ),
        (
            "布局文件版本号 {version} 不支持",
            {"version": "9.9"},
            ("version", "9.9"),
        ),
        (
            "加载布局文件 {filename} 时出错: {error}",
            {"filename": "demo.json", "error": "bad schema"},
            ("demo.json", "bad schema"),
        ),
        (
            "运行中 (PID: {pid})",
            {"pid": 4242},
            ("PID", "4242"),
        ),
        (
            "启动进程失败: {error}\n",
            {"error": "permission denied"},
            ("process", "permission denied"),
        ),
        (
            "\n进程退出，返回码: {return_code}\n",
            {"return_code": 17},
            ("process", "17"),
        ),
    ],
)
def test_high_risk_ui_templates_translate_and_format(
    source: str,
    kwargs: dict[str, object],
    expected_fragments: tuple[str, ...],
):
    rendered = tr(source, **kwargs)

    _assert_english(rendered, *expected_fragments)
    assert "{" not in rendered and "}" not in rendered
