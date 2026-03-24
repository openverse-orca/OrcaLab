"""终端通过 HTTP 调用已运行 OrcaLab 进程内的 MCP 工具（与 Cursor / fastmcp Client 同源）。"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

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


async def _async_main(url: str, tool: str, json_arg: str | None) -> int:
    if tool == "list":
        client = Client(url)
        async with client:
            tools = await client.list_tools()
            data = [t.model_dump(exclude_none=True) for t in tools]
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    arguments = _parse_arguments(json_arg)
    client = Client(url)
    async with client:
        result = await client.call_tool_mcp(name=tool, arguments=arguments)
    return _print_tool_result(result)


def mcp_main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="orcalab mcp",
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
        print(f"orcalab mcp: JSON 解析失败: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"orcalab mcp: {e}", file=sys.stderr)
        print(
            "请确认 OrcaLab 已启动且 MCP 已监听（检查配置 mcp.port 或 --url）。",
            file=sys.stderr,
        )
        return 1
