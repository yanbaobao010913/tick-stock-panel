"""enriched 换代冷却 (P0 止血) — 丢弃后不得立刻重复全量重算。

盘中 quote 刷新每 10~20s 提交一次 enriched 分区, 300 天重算 (~19s) 必然在
算完时发现世代已变; 无冷却时 warmup 三连试 + 懒加载路径会背靠背重复分配
百万行宽表, 线上表现为内存冲顶后被 cgroup OOM。
"""
from __future__ import annotations

import time
from datetime import date

import polars as pl

from app.enriched_generation import EnrichedGenerationUnavailableError
from app.tickflow.repository import (
    _ENRICHED_REFRESH_COOLDOWN_SECONDS,
    KlineRepository,
)


def _bare_repo() -> KlineRepository:
    """跳过 __init__ (避免 DataStore/目录依赖), 只装配冷却涉及的属性。"""
    repo = KlineRepository.__new__(KlineRepository)
    repo._enriched_cache = None
    repo._enriched_cache_date = None
    repo._enriched_history_cache = None
    repo._enriched_history_generation = None
    repo._enriched_warming = False
    repo._enriched_refresh_cooldown_until = 0.0
    return repo


def test_generation_drift_starts_cooldown():
    repo = _bare_repo()

    def _drift() -> None:
        raise EnrichedGenerationUnavailableError("drift")

    repo._refresh_enriched_impl = _drift  # type: ignore[method-assign]

    assert repo._refresh_enriched() is True
    remaining = repo._enriched_refresh_cooldown_until - time.monotonic()
    assert 0 < remaining <= _ENRICHED_REFRESH_COOLDOWN_SECONDS


def test_success_clears_cooldown():
    repo = _bare_repo()
    repo._enriched_refresh_cooldown_until = time.monotonic() + 60
    repo._refresh_enriched_impl = lambda: None  # type: ignore[method-assign]

    assert repo._refresh_enriched() is False
    assert repo._enriched_refresh_cooldown_until == 0.0


def test_latest_skips_refresh_during_cooldown():
    repo = _bare_repo()
    repo._enriched_refresh_cooldown_until = time.monotonic() + 60
    calls: list[int] = []
    repo._refresh_enriched = lambda: calls.append(1) or False  # type: ignore[method-assign]

    df, day = repo.get_enriched_latest()

    assert df.is_empty()
    assert day is None
    assert calls == [], "冷却期内不得触发同步全量重算"


def test_range_skips_refresh_during_cooldown():
    repo = _bare_repo()
    repo._enriched_refresh_cooldown_until = time.monotonic() + 60
    calls: list[int] = []
    repo._refresh_enriched = lambda: calls.append(1) or False  # type: ignore[method-assign]

    assert repo.get_enriched_range(date(2026, 1, 1), date(2026, 8, 14)) is None
    assert calls == []


def test_warmup_stops_after_first_discard():
    repo = _bare_repo()
    calls: list[int] = []

    def _drift() -> None:
        calls.append(1)
        raise EnrichedGenerationUnavailableError("drift")

    repo._refresh_enriched_impl = _drift  # type: ignore[method-assign]

    repo._warmup_enriched()

    assert len(calls) == 1, "换代丢弃后应进入冷却, 不再三连试"


def test_latest_retries_after_cooldown_expires():
    repo = _bare_repo()
    repo._enriched_refresh_cooldown_until = time.monotonic() - 1
    calls: list[int] = []

    def _refresh() -> bool:
        calls.append(1)
        repo._enriched_cache = pl.DataFrame({"symbol": ["600000.SH"]})
        repo._enriched_cache_date = date(2026, 10, 23)
        return False

    repo._refresh_enriched = _refresh  # type: ignore[method-assign]

    df, day = repo.get_enriched_latest()

    assert len(calls) == 1
    assert df.height == 1
    assert day == date(2026, 10, 23)


def test_clear_cache_resets_cooldown():
    repo = _bare_repo()
    repo._enriched_refresh_cooldown_until = time.monotonic() + 60

    repo.clear_cache()

    assert repo._enriched_refresh_cooldown_until == 0.0
