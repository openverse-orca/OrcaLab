"""上次异常退出（abnormal exit）：准备上报元数据、解析日志路径，并可写入本地 crash_reports 供核对。"""

from __future__ import annotations

import io
import json
import logging
import shutil
import aiohttp
from datetime import datetime, timezone
from pathlib import Path
from platform import python_version
from typing import Any, Dict, List, Optional, Tuple

from orcalab.config_service import ConfigService
from orcalab.logging_util import get_log_file_path
from orcalab.project_util import get_user_folder, get_user_log_folder
from orcalab.report.report import collect_diagnostic_summary
from orcalab.token_storage import TokenStorage

logger = logging.getLogger(__name__)

_pending_abnormal_exit_report = False

def schedule_abnormal_exit_report() -> None:
    global _pending_abnormal_exit_report
    _pending_abnormal_exit_report = True


def take_pending_abnormal_exit_report() -> bool:
    global _pending_abnormal_exit_report
    p = _pending_abnormal_exit_report
    _pending_abnormal_exit_report = False
    return p


def _resolve_username(config: ConfigService) -> str:
    token = TokenStorage.load_token()
    if token and token.get("username"):
        return str(token["username"])
    return (config.datalink_username() or "").strip()


def _newest_orcalab_log_path(
    log_dir: Path, exclude_resolved: Optional[str] = None
) -> Optional[Path]:
    """按修改时间取最新的 orcalab_*.log；exclude 通常为当前会话正在写的文件。"""
    if not log_dir.is_dir():
        return None
    try:
        files = [p for p in log_dir.glob("orcalab_*.log") if p.is_file()]
    except OSError:
        return None
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if exclude_resolved:
        for p in files:
            try:
                if str(p.resolve()) != exclude_resolved:
                    return p
            except OSError:
                continue
        return None
    return files[0]


def _game_log_candidate_paths(config_service: ConfigService) -> List[Path]:
    ws = config_service.workspace()
    proj = Path(config_service.orca_project_folder())
    return [
        get_user_log_folder() / "Game.log",
        get_user_folder() / "Game.log",
        proj / "Saved" / "Logs" / "Game.log",
        ws / "Saved" / "Logs" / "Game.log",
    ]


def resolve_game_log_path(config_service: ConfigService) -> tuple[Optional[Path], List[str]]:
    candidates = _game_log_candidate_paths(config_service)
    tried = [str(p) for p in candidates]
    for c in candidates:
        try:
            if c.is_file():
                return c.resolve(), tried
        except OSError:
            continue
    return None, tried


def prepare_abnormal_exit_upload(
    config_service: ConfigService,
) -> Tuple[Dict[str, Any], Optional[Path], Optional[Path]]:
    log_dir = get_user_log_folder()
    cur = get_log_file_path()
    exclude = None
    if cur:
        try:
            exclude = str(Path(cur).resolve())
        except OSError:
            exclude = None

    # 获取上一次运行的 Orcalab 日志文件
    orcalab_path = _newest_orcalab_log_path(log_dir, exclude)
    if orcalab_path is None and exclude:
        orcalab_path = _newest_orcalab_log_path(log_dir, None)

    # 获取上一次运行的 Game 日志文件
    game_path, game_searched = resolve_game_log_path(config_service)

    meta: Dict[str, Any] = {
        "orcalab_version": config_service.app_version(),
        "python_version": python_version(),
        "username": _resolve_username(config_service),
        "diagnostic": collect_diagnostic_summary(),
        "orcalab_log": (
            {
                "file_name": orcalab_path.name,
                "path": str(orcalab_path.resolve()),
            }
            if orcalab_path
            else {"missing": True}
        ),
        "game_log": (
            {
                "file_name": game_path.name,
                "path": str(game_path.resolve()),
            }
            if game_path
            else {"missing": True, "searched_paths": game_searched}
        ),
    }

    return meta, orcalab_path, game_path


async def send_abnormal_exit_report():
    config_service = ConfigService()
    meta, orcalab_path, game_path = prepare_abnormal_exit_upload(config_service)

    token_data = TokenStorage.load_token()
    username = token_data.get("username", "") if token_data else ""
    access_token = token_data.get("access_token", "") if token_data else ""

    url = f"http://47.100.47.219/api/orcalab/abnormal_report/"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'username': username,
    }

    form = aiohttp.FormData()
    form.add_field(
        "report_json",
        json.dumps(meta, ensure_ascii=False, default=str),
    )
    # game_log 放在 orcalab_log 之前：若 orcalab 日志正文中含与 multipart boundary
    # 相同的字节序列，部分解析器会截断后续 part，导致 game_log 被判缺失。
    _octet = "application/octet-stream"
    if game_path:
        try:
            form.add_field(
                "game_log",
                io.BytesIO(game_path.read_bytes()),
                filename=game_path.name,
                content_type=_octet,
            )
        except OSError as e:
            logger.warning("无法读取 game 日志: %s", e)
    if orcalab_path:
        try:
            form.add_field(
                "orcalab_log",
                io.BytesIO(orcalab_path.read_bytes()),
                filename=orcalab_path.name,
                content_type=_octet,
            )
        except OSError as e:
            logger.warning("无法读取 orcalab 日志: %s", e)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                logger.info(
                    "Abnormal exit report sent, status=%s", response.status
                )
                if response.status >= 400:
                    body = (await response.text())[:2000]
                    logger.warning(
                        "Abnormal exit report rejected: status=%s body=%s",
                        response.status,
                        body,
                    )
                else:
                    try:
                        await response.json()
                        
                    except Exception:
                        pass
    except aiohttp.ClientError as e:
        logger.warning(
            "Failed to send abnormal exit report (network): %s. OrcaLab will continue.",
            e,
        )
    except OSError as e:
        logger.warning(
            "Failed to send abnormal exit report (OS error): %s. OrcaLab will continue.",
            e,
        )