import logging
from datetime import datetime
from typing import Optional, Union

from orcalab.project_util import get_user_log_folder

_logger: Optional[logging.Logger] = None
_log_file_path: Optional[str] = None

DEFAULT_FILE_LEVEL = logging.INFO
DEFAULT_CONSOLE_LEVEL = logging.WARNING


def _ensure_log_directory() -> str:
    log_dir = get_user_log_folder()
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir)


def _build_log_file_path() -> str:
    log_dir = _ensure_log_directory()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{log_dir}/orcalab_{timestamp}.log"


def resolve_log_level(level: Optional[Union[str, int]]) -> Optional[int]:
    """Convert a user-provided level (name or int) to logging constants."""
    if level is None:
        return None
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        normalized = level.strip().upper()
        if normalized.isdigit():
            return int(normalized)
        if normalized in logging._nameToLevel:
            return logging._nameToLevel[normalized]
    raise ValueError(f"Invalid log level: {level}")


def setup_logging(
    file_level: Optional[int] = None,
    console_level: Optional[int] = None,
) -> logging.Logger:
    """Initialize or update OrcaLab logging configuration."""
    global _logger, _log_file_path

    resolved_file_level = file_level if file_level is not None else DEFAULT_FILE_LEVEL
    resolved_console_level = (
        console_level if console_level is not None else DEFAULT_CONSOLE_LEVEL
    )

    if _logger is None:
        logger = logging.getLogger("orcalab")
        logger.propagate = False
        _logger = logger
    else:
        logger = _logger

    logger.setLevel(min(resolved_file_level, resolved_console_level))

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    log_file_path = _build_log_file_path()
    _log_file_path = log_file_path

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s")

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(resolved_file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(
        "Logging initialized. File level=%s, console level=%s, log file=%s",
        logging.getLevelName(resolved_file_level),
        logging.getLevelName(resolved_console_level),
        log_file_path,
    )

    return logger


def get_logger() -> logging.Logger:
    """Get the shared OrcaLab logger instance."""
    if _logger is None:
        return setup_logging()
    return _logger


def get_log_file_path() -> Optional[str]:
    """Return the log file path if logging has been initialized."""
    return _log_file_path

