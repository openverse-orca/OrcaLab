"""上次异常退出（abnormal exit）：准备上报元数据、解析日志路径，并可写入本地 crash_reports 供核对。"""

from __future__ import annotations

import json
import logging
import shutil
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
        "metadata": {
            "type": "abnormal_exit_report",
            "schema_version": "4.0",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "orcalab_version": config_service.app_version(),
        "python_version": python_version(),
        "account": {"username": _resolve_username(config_service)},
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


def save_abnormal_exit_report_local(
    config_service: ConfigService,
) -> Optional[Path]:
    """将 report.json 与选中的日志文件副本写入 ``<用户目录>/crash_reports/abnormal_exit_<时间戳>/``。"""
    meta, orcalab_path, game_path = prepare_abnormal_exit_upload(config_service)
    root = get_user_folder() / "crash_reports"
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out_dir = root / f"abnormal_exit_{ts}"
    out_dir.mkdir(parents=False, exist_ok=True)

    try:
        report_file = out_dir / "report.json"
        with report_file.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

        if orcalab_path and orcalab_path.is_file():
            shutil.copy2(orcalab_path, out_dir / orcalab_path.name)
        if game_path and game_path.is_file():
            shutil.copy2(game_path, out_dir / game_path.name)

        logger.info("异常退出报告已写入本地目录: %s", out_dir)
        return out_dir
    except OSError:
        logger.exception("写入 crash_reports 失败: %s", out_dir)
        return None