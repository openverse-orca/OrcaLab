import logging
import time
from contextlib import contextmanager
from typing import Generator

_perf_logger = logging.getLogger("orcalab.perf")

PERF_MASTER_ON = False
PERF_MASTER_OFF = False

PERF_OUTLINE = False
PERF_SERVICE = False
PERF_GRPC = False
PERF_PARSE = False
PERF_PROPERTY = False
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
    if PERF_MASTER_ON:
        return True
    if PERF_MASTER_OFF:
        return False
    getter = _FEATURE_SWITCHES.get(feature)
    if getter is None:
        return True
    return getter()


def perf_log(message: str, feature: str = "") -> None:
    if feature and not _is_enabled(feature):
        return
    tag = f"[{feature}]" if feature else ""
    _perf_logger.info(f"{tag} {message}" if tag else message)


class PerfLogger:
    """不使用with，保持代码可读性"""

    def __init__(self, feature: str, prefix: str):
        self.feature = feature
        self.enabled = _is_enabled(feature)
        self._start_time: float = 0.0
        self._labels: list[str] = [prefix]
        self._start = False

    def scoped(self, prefix: str) -> "PerfLogger":
        if prefix:
            _prefix = f"{self._compose_label()}.{prefix}"
        else:
            _prefix = self._compose_label()
        return PerfLogger(self.feature, _prefix)

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        _perf_logger.info(f"{self.feature} {message}")

    def start(self, label: str = "") -> None:
        if not self.enabled:
            return

        if self._start:
            self._log()
            self._start_time = time.perf_counter()
            if self._labels:
                self._labels[-1] = label
        else:
            self._start = True
            self._start_time = time.perf_counter()
            self._labels.append(label)

    def end(self) -> None:
        if not self.enabled:
            return

        if self._start:
            self._log()

        self._start = False

    def _log(self) -> None:
        if not self.enabled:
            return

        now = time.perf_counter()
        elapsed_ms = (now - self._start_time) * 1000
        label = self._compose_label()
        _perf_logger.info(f"[{self.feature}][PERF] {label}: {elapsed_ms:.2f}ms")

    def _compose_label(self) -> str:
        return ".".join(self._labels)


def perf_logger(feature: str, prefix: str) -> PerfLogger:
    return PerfLogger(feature=feature, prefix=prefix)


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
