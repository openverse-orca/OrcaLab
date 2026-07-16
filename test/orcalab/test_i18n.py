import ast
import json
import os
import re
import shutil
import string
import subprocess
import textwrap
import tomllib
from collections import Counter
from pathlib import Path

from PySide6 import QtWidgets

from orcalab.i18n import install_qt_translation_hooks, set_language, tr
from orcalab.translations.en_us import TRANSLATIONS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_qapp = None

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _REPO_ROOT / "orcalab"
_TRANSLATION_FILE = _SOURCE_ROOT / "translations" / "en_us.py"
_HAN_RE = re.compile(r"[\u3400-\u9fff]")
_NSIS_LANG_STRING_RE = re.compile(
    r'^LangString\s+(?P<name>\w+)\s+\$\{LANG_(?P<language>\w+)\}\s+"(?P<value>.*)"$'
)

# Calls whose displayed string arguments are translated by install_qt_translation_hooks(),
# or by a small OrcaLab wrapper which immediately delegates to a hooked Qt text API.
_HOOKED_CONSTRUCTORS = {
    "QAction",
    "QCheckBox",
    "QGroupBox",
    "QLabel",
    "QMenu",
    "QPushButton",
    "QRadioButton",
}
_HOOKED_METHODS = {
    "addAction",
    "addButton",
    "addItem",
    "addMenu",
    "setDetailedText",
    "setHeaderLabel",
    "setHeaderLabels",
    "setHorizontalHeaderLabels",
    "setInformativeText",
    "setPlaceholderText",
    "setText",
    "setTitle",
    "setToolTip",
    "setVerticalHeaderLabels",
    "setWindowTitle",
}
_HOOKED_WRAPPERS = {
    "Panel",
    "TextLabel",
    "_create_info_group",
    "_set_message_impl",
    "_show_scrollable_warning",
    "_vscode_style_setting_row",
    "ask_offline_or_exit",
    "complete_auth",
    "message_bubble",
    "set_detail",
    "set_loading_text",
    "set_status",
    "update_status",
}

# These are UI sinks, but the global Qt hooks do not translate their payloads.
# Chinese literals reaching one of them must therefore be wrapped in tr() before
# formatting/concatenation. Exact names keep ordinary logs and list.append calls out
# of the audit.
_EXPLICIT_TR_METHODS = {
    "addItems",
    "addTab",
    "appendHtml",
    "insertItem",
    "insertItems",
    "insertTab",
    "setHtml",
    "setItemText",
    "setMarkdown",
    "setPlainText",
    "setPrefix",
    "setSpecialValueText",
    "setStatusTip",
    "setSuffix",
    "setTabText",
    "showMessage",
}
_EXPLICIT_TR_CALLS = {
    "_report",
    "progress_dialog.log",
    "self._append_output",
    "self._append_output_safe",
    "self._append_terminal",
    "self._log",
    "self.output_queue.put",
}
_ITEM_CONSTRUCTORS = {
    "QListWidgetItem",
    "QStandardItem",
    "QTableWidgetItem",
    "QTreeWidgetItem",
}

# These lists are ultimately joined and displayed by SceneLayoutService. Restricting
# the rule by path avoids treating every diagnostic errors.append() as UI content.
_DISPLAYED_MESSAGE_LISTS = {
    "scene_layout/scene_layout_helper.py": {"errors.append"},
    "scene_layout/scene_layout_helper_v3.py": {
        "errors.append",
        "warnings.append",
    },
    "scene_layout/scene_layout_service.py": {
        "errors.append",
        "warnings.append",
    },
}
_UI_TEXT_PRODUCER_FUNCTIONS = {
    "gpu_driver_check.py": {
        "_check_driver_generic",
        "_check_driver_intel",
        "_driver_status_text",
        "build_driver_detail_text",
        "build_driver_guidance_text",
    },
    "python_project_installer.py": {"_build_user_friendly_install_error"},
}
_DYNAMICALLY_TRANSLATED_ASSIGNMENTS = {
    "gpu_driver_check.py": {"_VENDOR_DRIVER_GUIDANCE"},
}


def _call_name(call: ast.Call) -> str:
    return ast.unparse(call.func)


def _leaf_name(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1]


def _iter_source_trees():
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(_SOURCE_ROOT)
        if relative == Path("translations/en_us.py"):
            continue
        if relative.parts and relative.parts[0] == "protos":
            continue
        yield relative.as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _translation_dict_node() -> ast.Dict:
    tree = ast.parse(_TRANSLATION_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "TRANSLATIONS" for target in node.targets):
            continue
        assert isinstance(node.value, ast.Dict)
        return node.value
    raise AssertionError("TRANSLATIONS dict was not found in en_us.py")


def _format_fields(text: str) -> Counter[tuple[str, str, str | None]]:
    fields = []
    for _literal, field_name, format_spec, conversion in string.Formatter().parse(text):
        if field_name is not None:
            fields.append((field_name, format_spec, conversion))
    return Counter(fields)


def _contains_chinese(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Constant) and isinstance(child.value, str) and _HAN_RE.search(child.value)
        for child in ast.walk(node)
    )


def _unprotected_chinese(node: ast.AST) -> list[str]:
    """Return Chinese literals not already enclosed by an explicit tr() call."""
    if isinstance(node, ast.Call) and _leaf_name(_call_name(node)) == "tr":
        return []
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str) and _HAN_RE.search(node.value):
            return [node.value]
        return []

    result = []
    for child in ast.iter_child_nodes(node):
        result.extend(_unprotected_chinese(child))
    return result


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _candidate_arguments(call: ast.Call, relative_path: str) -> tuple[str, list[ast.AST]] | None:
    name = _call_name(call)
    leaf = _leaf_name(name)

    # AssetSyncService's failure message is forwarded to SyncProgressWindow and
    # translated there. The success detail is internal bookkeeping and is not shown.
    if (
        relative_path == "asset_sync_service.py"
        and name == "self.callbacks.on_complete"
        and len(call.args) > 1
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value is False
    ):
        return "hooked", [call.args[1]]
    if name.endswith("show_warning_dialog_signal.emit"):
        return "hooked", list(call.args)

    # Static convenience functions: parent, title/caption, message/path, filter.
    if name.endswith(
        (
            "QMessageBox.information",
            "QMessageBox.warning",
            "QMessageBox.critical",
            "QMessageBox.question",
        )
    ):
        return "hooked", call.args[1:3]
    if name.endswith(("QFileDialog.getOpenFileName", "QFileDialog.getSaveFileName")):
        return "hooked", [arg for index, arg in enumerate(call.args) if index in (1, 3)]
    if name.endswith("QFileDialog.getExistingDirectory"):
        return "hooked", call.args[1:2]

    if leaf in _HOOKED_CONSTRUCTORS:
        # Text is the first string argument for the text-only overload and the
        # second string argument for icon + text overloads.
        return "hooked", call.args[:2]
    if leaf in _HOOKED_METHODS:
        return "hooked", call.args[:2]
    if leaf in _HOOKED_WRAPPERS:
        return "hooked", list(call.args)

    if leaf in _ITEM_CONSTRUCTORS or leaf in _EXPLICIT_TR_METHODS:
        return "explicit", list(call.args)
    if name in _EXPLICIT_TR_CALLS:
        return "explicit", list(call.args)

    displayed_lists = _DISPLAYED_MESSAGE_LISTS.get(relative_path, set())
    if name in displayed_lists:
        return "explicit", list(call.args)
    return None


def _audit_ui_expression(
    expression: ast.AST,
    mode: str,
    location: str,
    call_name: str,
) -> list[str]:
    if not _contains_chinese(expression):
        return []
    if isinstance(expression, ast.Call) and _leaf_name(_call_name(expression)) == "tr":
        return []
    if isinstance(expression, (ast.List, ast.Tuple, ast.Set)):
        issues = []
        for element in expression.elts:
            issues.extend(_audit_ui_expression(element, mode, location, call_name))
        return issues
    if isinstance(expression, ast.IfExp):
        return [
            *_audit_ui_expression(expression.body, mode, location, call_name),
            *_audit_ui_expression(expression.orelse, mode, location, call_name),
        ]

    chinese = _unprotected_chinese(expression)
    if not chinese:
        return []

    literal = _constant_string(expression)
    if literal is not None:
        if mode == "explicit":
            return [f"{location}: {call_name} is not hook-covered; wrap {literal!r} in tr()"]
        if literal not in TRANSLATIONS:
            return [f"{location}: {call_name} displays untranslated literal {literal!r}"]
        return []

    return [
        f"{location}: {call_name} builds UI text dynamically from Chinese "
        f"({chinese!r}); translate a {{placeholder}} template before formatting"
    ]


def _audit_text_producer(node: ast.AST, location: str) -> list[str]:
    """Require producer functions to translate text before returning it to a UI."""
    issues = []

    def visit(current: ast.AST) -> None:
        if isinstance(current, ast.Call) and _leaf_name(_call_name(current)) == "tr":
            return
        if isinstance(current, ast.JoinedStr) and _unprotected_chinese(current):
            issues.append(
                f"{location}:{current.lineno}: UI text producer formats Chinese before tr(): "
                f"{_unprotected_chinese(current)!r}"
            )
            return
        if isinstance(current, ast.Constant):
            if isinstance(current.value, str) and _HAN_RE.search(current.value):
                issues.append(
                    f"{location}:{current.lineno}: UI text producer returns unwrapped Chinese: {current.value!r}"
                )
            return
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = current.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            for statement in body:
                visit(statement)
            return
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return issues


def test_about_dialog_translations_and_message_box_title_hook():
    global _qapp
    _qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    set_language("en_US")
    install_qt_translation_hooks()

    expected = {
        "版本": "Version",
        "版权所有": "Copyright",
        "公司主页": "Company Website",
        "GitHub 仓库": "GitHub Repository",
        "松应科技": "Songying Technology",
        "云原生机器人仿真平台，提供先进的UI和资产管理功能": (
            "A cloud-native robotics simulation platform with advanced UI and asset management capabilities"
        ),
    }

    try:
        assert {source: tr(source) for source in expected} == expected

        message_box = QtWidgets.QMessageBox()
        message_box.setWindowTitle("关于 OrcaLab")
        assert message_box.windowTitle() == "About OrcaLab"
    finally:
        set_language("zh_CN")


def test_english_translation_catalog_is_well_formed():
    translation_node = _translation_dict_node()
    source_keys = [ast.literal_eval(key) for key in translation_node.keys]

    duplicates = sorted(source for source, count in Counter(source_keys).items() if count > 1)
    issues = [f"duplicate translation key: {source!r}" for source in duplicates]

    for source, target in TRANSLATIONS.items():
        if not source.strip() or not target.strip():
            issues.append(f"empty translation entry: {source!r} => {target!r}")
        if not _HAN_RE.search(source):
            issues.append(f"translation source has no Chinese text: {source!r}")
        if _HAN_RE.search(target):
            issues.append(f"English translation still contains Chinese: {source!r} => {target!r}")
        if source == target:
            issues.append(f"translation is unchanged: {source!r}")
        if _format_fields(source) != _format_fields(target):
            issues.append(
                f"format placeholders differ: {source!r} => {target!r} "
                f"({_format_fields(source)!r} != {_format_fields(target)!r})"
            )

    assert not issues, "Translation catalog errors:\n" + "\n".join(issues)


def test_explicit_tr_calls_use_static_catalog_keys():
    issues = []
    for relative_path, tree in _iter_source_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _leaf_name(_call_name(node)) != "tr":
                continue
            if not node.args or not _contains_chinese(node.args[0]):
                continue

            location = f"{relative_path}:{node.lineno}"
            source = _constant_string(node.args[0])
            if source is None:
                issues.append(
                    f"{location}: tr() received dynamically constructed Chinese text; "
                    "use a literal {placeholder} catalog key"
                )
            elif source not in TRANSLATIONS:
                issues.append(f"{location}: tr() key is missing from en_us.py: {source!r}")

    assert not issues, "Invalid tr() calls:\n" + "\n".join(issues)


def test_config_values_displayed_by_launch_dialog_have_translations():
    issues = []
    for filename in ("orca.config.toml", "orca.config.template.toml"):
        path = _SOURCE_ROOT / filename
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        programs = config.get("external_programs", {}).get("programs", [])
        for index, program in enumerate(programs):
            for field in ("display_name", "description"):
                value = program.get(field)
                if isinstance(value, str) and _HAN_RE.search(value):
                    if value not in TRANSLATIONS:
                        issues.append(
                            f"{filename}: external_programs.programs[{index}].{field} "
                            f"is displayed in LaunchDialog but has no translation: {value!r}"
                        )

    assert not issues, "Untranslated launch configuration:\n" + "\n".join(issues)


def test_installer_language_resources_have_matching_english_strings():
    installer_dir = _REPO_ROOT / "scripts" / "installer"

    def read_lang_strings(filename: str) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for line in (installer_dir / filename).read_text(encoding="utf-8").splitlines():
            match = _NSIS_LANG_STRING_RE.match(line.strip())
            if match:
                result.setdefault(match.group("language"), {})[
                    match.group("name")
                ] = match.group("value")
        return result

    english = read_lang_strings("strings_en.nsh")["ENGLISH"]
    chinese_resources = read_lang_strings("strings_zh.nsh")
    simplified = chinese_resources["SIMPCHINESE"]
    traditional = chinese_resources["TRADCHINESE"]
    issues = []
    for language, translated in (
        ("SIMPCHINESE", simplified),
        ("TRADCHINESE", traditional),
    ):
        if translated.keys() != english.keys():
            issues.append(
                f"installer {language} keys differ: "
                f"localized-only={sorted(translated.keys() - english.keys())}, "
                f"en-only={sorted(english.keys() - translated.keys())}"
            )
    for name, value in english.items():
        if _HAN_RE.search(value):
            issues.append(f"strings_en.nsh {name} still contains Chinese: {value!r}")
        if simplified.get(name) == value:
            issues.append(f"strings_en.nsh {name} is unchanged from simplified Chinese")
        if traditional.get(name) == value:
            issues.append(f"strings_en.nsh {name} is unchanged from traditional Chinese")

    assert not issues, "Installer translation errors:\n" + "\n".join(issues)


def test_windows_launcher_selects_its_language_and_forwards_arguments():
    installer_dir = _REPO_ROOT / "scripts" / "installer"
    batch_script = (installer_dir / "orcalab.bat").read_text(encoding="utf-8")
    build_script = (installer_dir / "build_installer.sh").read_text(encoding="utf-8")
    vbs_script = (installer_dir / "orcalab.vbs").read_text(encoding="utf-8")

    assert "INITIAL_UI_LANGUAGE" not in batch_script
    assert "__INITIAL_UI_LANGUAGE__" not in build_script
    assert "--initial-lang" not in batch_script
    assert batch_script.count("-m orcalab %*") == 2
    assert '"!LAUNCHER_ARG!"=="--lang"' in batch_script
    assert '"!LAUNCHER_ARG:~0,7!"=="--lang="' in batch_script
    assert "CurrentUICulture.TwoLetterISOLanguageName" in batch_script
    assert 'if /i "%LAUNCHER_LANGUAGE%"=="zh_CN" chcp 65001' in batch_script
    assert 'set "MSG_LAUNCHER_TITLE=OrcaLab 启动器"' in batch_script
    assert 'set "MSG_LAUNCHER_TITLE=OrcaLab Launcher"' in batch_script
    message_definitions = Counter(
        re.findall(r'set "(?P<name>MSG_[A-Z_]+)=', batch_script)
    )
    message_references = set(
        re.findall(r'[!%](?P<name>MSG_[A-Z_]+)[!%]', batch_script)
    )
    assert message_definitions
    assert set(message_definitions.values()) == {2}
    assert set(message_definitions) == message_references
    assert "WScript.Arguments" in vbs_script
    assert "WshShell.Run command" in vbs_script
    assert "ResolveLauncherLanguage(WScript.Arguments, WshShell)" in vbs_script
    assert vbs_script.isascii()
    assert 'LCase(argument) = "--lang"' in vbs_script
    assert 'Left(LCase(argument), 7) = "--lang="' in vbs_script
    assert "CurrentUICulture.TwoLetterISOLanguageName" in vbs_script
    assert "(GetLocale() And &H3FF) = 4" in vbs_script
    assert "WshShell.Popup popupText" in vbs_script


def test_windows_installer_is_single_and_selects_system_language():
    installer_dir = _REPO_ROOT / "scripts" / "installer"
    build_script = (
        installer_dir / "build_installer.sh"
    ).read_text(encoding="utf-8")
    setup_script = (installer_dir / "setup.nsi").read_text(encoding="utf-8")

    assert "[--lang" not in build_script
    assert "INSTALLER_SUFFIX" not in build_script
    assert "ORCALAB_ENGLISH" not in build_script
    assert 'OutFile "..\\..\\dist\\OrcaLab-${PRODUCT_VERSION}-Setup.exe"' in setup_script
    assert "INSTALLER_SUFFIX" not in setup_script
    assert "ORCALAB_ENGLISH" not in setup_script
    assert '!insertmacro MUI_LANGUAGE "English"' in setup_script
    assert '!insertmacro MUI_LANGUAGE "SimpChinese"' in setup_script
    assert '!insertmacro MUI_LANGUAGE "TradChinese"' in setup_script
    assert "GetUserDefaultUILanguage" in setup_script
    assert "IntOp $8 $9 & 0x03FF" in setup_script
    assert 'StrCpy $LANGUAGE ${LANG_ENGLISH}' in setup_script
    assert 'StrCpy $LANGUAGE ${LANG_SIMPCHINESE}' in setup_script
    assert 'StrCpy $LANGUAGE ${LANG_TRADCHINESE}' in setup_script
    assert "MUI_LANGDLL_DISPLAY" not in setup_script
    assert 'Section "Uninstall"' in setup_script


def test_windows_installer_build_script_builds_one_package(tmp_path):
    project_root = tmp_path / "project"
    installer_dir = project_root / "scripts" / "installer"
    icon_dir = project_root / "orcalab" / "assets" / "icons"
    fake_bin = tmp_path / "bin"
    installer_dir.mkdir(parents=True)
    icon_dir.mkdir(parents=True)
    fake_bin.mkdir()

    source_installer_dir = _REPO_ROOT / "scripts" / "installer"
    for filename in ("build_installer.sh", "orcalab.bat", "orcalab.vbs"):
        shutil.copy2(source_installer_dir / filename, installer_dir / filename)
    shutil.copy2(_REPO_ROOT / "pyproject.toml", project_root / "pyproject.toml")
    (icon_dir / "orcalab_logo.ico").write_bytes(b"test icon")

    makensis_log = tmp_path / "makensis.jsonl"
    fake_makensis = fake_bin / "makensis"
    fake_makensis.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            defines = {}
            for arg in args:
                if arg.startswith("-D") and "=" in arg:
                    name, value = arg[2:].split("=", 1)
                    defines[name] = value

            source_dir = Path.cwd() / defines["INSTALLER_SOURCE_DIR"]
            record = {
                "args": args,
                "batch": (source_dir / "orcalab.bat").read_text(encoding="utf-8"),
            }
            with Path(os.environ["FAKE_MAKENSIS_LOG"]).open(
                "a", encoding="utf-8"
            ) as log:
                log.write(json.dumps(record) + "\\n")

            output = (
                Path.cwd()
                / ".."
                / ".."
                / "dist"
                / f"OrcaLab-{defines['PRODUCT_VERSION']}-Setup.exe"
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.touch()
            """
        ),
        encoding="utf-8",
    )
    fake_makensis.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_MAKENSIS_LOG"] = str(makensis_log)
    result = subprocess.run(
        [
            str(installer_dir / "build_installer.sh"),
            "--pip-source",
            "prod",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    records = [
        json.loads(line)
        for line in makensis_log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1

    record = records[0]
    assert not any(arg.startswith("-DINSTALLER_SUFFIX=") for arg in record["args"])
    assert "-DORCALAB_ENGLISH" not in record["args"]
    assert "INITIAL_UI_LANGUAGE" not in record["batch"]
    assert "--initial-lang" not in record["batch"]
    assert "--extra-index-url https://pypi.org/simple" in record["batch"]
    assert "test.pypi.org" not in record["batch"]

    version = tomllib.loads(
        (project_root / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    assert (project_root / "dist" / f"OrcaLab-{version}-Setup.exe").is_file()
    assert not list(installer_dir.glob(".installer-build.*"))

    rejected = subprocess.run(
        [str(installer_dir / "build_installer.sh"), "--lang", "all"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "unknown argument '--lang'" in rejected.stdout


def test_known_ui_text_producers_translate_before_returning_text():
    issues = []
    trees = dict(_iter_source_trees())

    for relative_path, function_names in _UI_TEXT_PRODUCER_FUNCTIONS.items():
        tree = trees[relative_path]
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in function_names:
                continue
            found.add(node.name)
            issues.extend(_audit_text_producer(node, relative_path))
        missing = function_names - found
        issues.extend(f"{relative_path}: configured UI text producer was not found: {name}" for name in sorted(missing))

    for relative_path, assignment_names in _DYNAMICALLY_TRANSLATED_ASSIGNMENTS.items():
        tree = trees[relative_path]
        found = set()
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {target.id for target in targets if isinstance(target, ast.Name)}
            matched = names & assignment_names
            if not matched:
                continue
            found.update(matched)
            for child in ast.walk(node.value):
                if (
                    isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                    and _HAN_RE.search(child.value)
                    and child.value not in TRANSLATIONS
                ):
                    issues.append(
                        f"{relative_path}:{child.lineno}: dynamically translated UI "
                        f"value is missing from en_us.py: {child.value!r}"
                    )
        missing = assignment_names - found
        issues.extend(
            f"{relative_path}: configured translated assignment was not found: {name}" for name in sorted(missing)
        )

    assert not issues, "Untranslated UI text producers:\n" + "\n".join(issues)


def test_direct_ui_chinese_is_translatable_before_display():
    issues = []
    for relative_path, tree in _iter_source_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            candidates = _candidate_arguments(node, relative_path)
            if candidates is None:
                continue
            mode, expressions = candidates
            call_name = _call_name(node)
            location = f"{relative_path}:{node.lineno}"
            for expression in expressions:
                issues.extend(_audit_ui_expression(expression, mode, location, call_name))

            for keyword in node.keywords:
                if keyword.arg in {
                    "caption",
                    "filter",
                    "label",
                    "placeholderText",
                    "text",
                    "title",
                }:
                    # The generic Qt monkey patches only rewrite positional
                    # arguments. OrcaLab wrappers call tr() internally and are
                    # safe with named arguments; direct Qt keyword text is not.
                    keyword_mode = mode if _leaf_name(call_name) in _HOOKED_WRAPPERS else "explicit"
                    issues.extend(_audit_ui_expression(keyword.value, keyword_mode, location, call_name))

    assert not issues, "Untranslated UI strings:\n" + "\n".join(issues)
