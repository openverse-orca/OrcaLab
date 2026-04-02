"""终端通过 HTTP 调用已运行 OrcaLab 进程内的 MCP 工具（与 Cursor / fastmcp Client 同源）。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from fastmcp import Client

from orcalab.config_service import ConfigService


def _default_mcp_url(workspace: pathlib.Path) -> str:
    pkg_root = pathlib.Path(__file__).resolve().parent.parent
    project_root = pkg_root.parent
    config = ConfigService()
    config.init_config(project_root, workspace.resolve())
    port = config.mcp_port()
    return f"http://127.0.0.1:{port}/mcp"


def _serialize_content_block(block) -> dict:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return {"repr": str(block)}


def _print_tool_result(result) -> int:
    payload = {
        "isError": result.isError,
        "structuredContent": result.structuredContent,
        "content": [_serialize_content_block(c) for c in result.content],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if result.isError else 0


def _parse_arguments(json_arg: str | None) -> dict:
    if not json_arg:
        return {}
    raw = sys.stdin.read() if json_arg == "-" else json_arg
    if not raw.strip():
        return {}
    return json.loads(raw)


def _doc_for_list(description: str | None) -> str:
    """保留 Args / Returns 等全文，换行与连续空白压成单空格，便于 JSON 单行展示。"""
    if not description:
        return ""
    return " ".join(description.split())


def _format_schema_default(val: Any) -> str:
    if val is None:
        return "None"
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, (int, float)):
        return repr(val)
    if isinstance(val, str):
        return json.dumps(val, ensure_ascii=False)
    return json.dumps(val, ensure_ascii=False)


def _json_schema_to_py_type(spec: dict[str, Any]) -> str:
    if not isinstance(spec, dict):
        return "Any"
    if "$ref" in spec:
        return "Any"
    if "anyOf" in spec and isinstance(spec["anyOf"], list):
        non_null: list[dict[str, Any]] = [
            s for s in spec["anyOf"] if isinstance(s, dict) and s.get("type") != "null"
        ]
        if len(non_null) == 1:
            return f"{_json_schema_to_py_type(non_null[0])} | None"
        return "Any"
    t = spec.get("type")
    if t == "string":
        return "str"
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "array":
        items = spec.get("items")
        if isinstance(items, dict):
            return f"list[{_json_schema_to_py_type(items)}]"
        return "list[Any]"
    if t == "object":
        return "dict[str, Any]"
    if isinstance(t, list):
        non_null = [x for x in t if x != "null"]
        if len(non_null) == 1:
            return f"{_json_schema_to_py_type({'type': non_null[0]})} | None"
    return "Any"


def _format_param(pname: str, spec: dict[str, Any], is_required: bool) -> str:
    ann = _json_schema_to_py_type(spec)
    if "default" in spec:
        return f"{pname}: {ann} = {_format_schema_default(spec['default'])}"
    if not is_required:
        if ann.endswith(" | None"):
            return f"{pname}: {ann} = None"
        return f"{pname}: {ann} | None = None"
    return f"{pname}: {ann}"


def _build_function_signature(tool) -> str:
    schema = tool.inputSchema if isinstance(getattr(tool, "inputSchema", None), dict) else {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = set(schema.get("required") or [])
    parts: list[str] = []
    for pname in props:
        pspec = props[pname]
        if not isinstance(pspec, dict):
            pspec = {}
        parts.append(_format_param(pname, pspec, pname in required))

    out_schema = getattr(tool, "outputSchema", None)
    ret = "str"
    if isinstance(out_schema, dict) and out_schema:
        blob = json.dumps(out_schema, ensure_ascii=False).lower()
        if "image" in blob:
            ret = "Image"

    return f"{tool.name}({', '.join(parts)}) -> {ret}"


def _tools_list_as_json_list(tools: list) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for t in tools:
        rows.append(
            {
                "function": _build_function_signature(t),
                "description": _doc_for_list(getattr(t, "description", None)),
            }
        )
    return rows


async def _async_main(url: str, tool: str, json_arg: str | None) -> int:
    if tool == "list":
        client = Client(url)
        async with client:
            tools = await client.list_tools()
        payload = _tools_list_as_json_list(tools)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    arguments = _parse_arguments(json_arg)
    client = Client(url)
    async with client:
        result = await client.call_tool_mcp(name=tool, arguments=arguments)
    return _print_tool_result(result)


def mcp_main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="orcalab-cli",
        description="调用已启动 OrcaLab 图形界面暴露的 MCP HTTP 服务（工具列表与界面内 MCP 一致）。",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        default=".",
        help="工作目录，用于读取配置中的 mcp.port（默认与启动 GUI 时一致），默认当前目录",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        default=None,
        help="覆盖 MCP 地址，例如 http://127.0.0.1:8000/mcp",
    )
    parser.add_argument(
        "tool",
        help="工具名；使用 list 列出全部工具",
    )
    parser.add_argument(
        "--json",
        metavar="STR",
        dest="json_arg",
        help="工具参数（JSON 对象）；使用 - 从 stdin 读取",
    )
    args = parser.parse_args(argv)

    workspace = pathlib.Path(args.workspace).resolve()
    url = args.url if args.url else _default_mcp_url(workspace)

    import asyncio

    try:
        return asyncio.run(_async_main(url, args.tool, args.json_arg))
    except json.JSONDecodeError as e:
        print(f"orcalab-cli: JSON 解析失败: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"orcalab-cli: {e}", file=sys.stderr)
        print(
            "请确认 OrcaLab 已启动且 MCP 已监听（检查配置 mcp.port 或 --url）。",
            file=sys.stderr,
        )
        return 1
