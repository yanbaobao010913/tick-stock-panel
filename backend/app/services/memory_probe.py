"""进程 RSS 采样与重任务阶段日志 — 交易时段内存增长/OOM 事后取证。

周期采样给出时间曲线; ``rss_phase`` 给出具体重任务前后的增量。峰值取自内核
维护的 ``ru_maxrss``(不依赖采样间隔), 短命分配尖峰也能在事后看到。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psutil

from app.config import settings

try:
    import resource
except ImportError:  # Windows 无 resource 模块
    resource = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_process = psutil.Process(os.getpid())
_state_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None


def rss_mb() -> float | None:
    try:
        return _process.memory_info().rss / (1024 * 1024)
    except (psutil.Error, OSError):
        return None


def peak_rss_mb() -> float | None:
    """进程自启动以来的 RSS 高水位; Linux 单位 KiB, macOS 单位字节。"""
    if resource is None:
        return None
    try:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (OSError, ValueError):
        return None
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def _format_sample() -> str:
    current = rss_mb()
    if current is None:
        return "unavailable"
    peak = peak_rss_mb()
    return f"{current:.0f}MB" if peak is None else f"{current:.0f}MB (peak {peak:.0f}MB)"


def log_rss(tag: str) -> None:
    logger.info("RSS %s: %s", tag, _format_sample())


@contextmanager
def rss_phase(tag: str) -> Iterator[None]:
    """记录阶段前后 RSS 与耗时; 异常路径同样记录, 便于归因峰值来源。"""
    before = rss_mb()
    started = time.monotonic()
    try:
        yield
    finally:
        after = rss_mb()
        elapsed = time.monotonic() - started
        if before is None or after is None:
            logger.info("RSS %s: unavailable, %.1fs", tag, elapsed)
        else:
            peak = peak_rss_mb()
            peak_text = "" if peak is None else f", peak {peak:.0f}MB"
            logger.info(
                "RSS %s: %.0f -> %.0fMB (%+.0fMB), %.1fs%s",
                tag, before, after, after - before, elapsed, peak_text,
            )


def _sample_loop(interval_s: float) -> None:
    while not _stop.wait(interval_s):
        log_rss("sample")


def start_sampler(interval_s: float | None = None) -> None:
    """启动周期采样线程 (幂等); interval<=0 时不启动。"""
    global _thread
    interval = settings.memory_probe_interval_s if interval_s is None else interval_s
    if interval <= 0:
        return
    with _state_lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(
            target=_sample_loop,
            args=(float(interval),),
            name="memory-probe",
            daemon=True,
        )
        _thread.start()
    logger.info("RSS sampler started: every %.0fs", interval)


def stop_sampler() -> None:
    global _thread
    _stop.set()
    with _state_lock:
        thread = _thread
        _thread = None
    if thread is not None:
        thread.join(timeout=1.0)
