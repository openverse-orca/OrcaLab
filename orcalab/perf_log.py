import logging
import time
from contextlib import contextmanager
from typing import Generator

_perf_logger = logging.getLogger("orcalab.perf")

PERF_OUTLINE = False
PERF_SERVICE = False
PERF_GRPC = False
PERF_PARSE = False
PERF_PROPERTY = True
PERF_SECTION = False
PERF_TRACE_LIFECYCLE = False

_FEATURE_SWITCHES = {
    "OUTLINE": lambda: PERF_OUTLINE,
    "SERVICE": lambda: PERF_SERVICE,
    "GRPC": lambda: PERF_GRPC,
    "PARSE": lambda: PERF_PARSE,
    "PROPERTY": lambda: PERF_PROPERTY,
    "SECTION": lambda: PERF_SECTION,
    "TRACE_LIFECYCLE": lambda: PERF_TRACE_LIFECYCLE,
}


def _is_enabled(feature: str) -> bool:
    getter = _FEATURE_SWITCHES.get(feature)
    if getter is None:
        return True
    return getter()


def perf_log(message: str, feature: str = "") -> None:
    if feature and not _is_enabled(feature):
        return
    tag = f"[{feature}]" if feature else ""
    _perf_logger.info(f"{tag} {message}" if tag else message)


@contextmanager
def perf_timer(label: str, feature: str = "") -> Generator[None, None, None]:
    if feature and not _is_enabled(feature):
        yield
        return
    tag = f"[{feature}]" if feature else ""
    prefix = f"{tag} " if tag else ""
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    _perf_logger.info(f"{prefix}[PERF] {label}: {elapsed_ms:.2f}ms")
