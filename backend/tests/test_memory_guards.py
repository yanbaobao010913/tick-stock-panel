"""OOM 防护: DuckDB 上限、Webhook 队列上限与两个访问缓存的有界性。"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api import ext_data as ext_api
from app.api import screener as screener_api
from app.config import Settings
from app.services import quote_service
from app.tickflow.repository import DataStore


def test_datastore_duckdb_uses_bounded_memory_and_temp_dir(tmp_path: Path) -> None:
    store = DataStore(data_dir=tmp_path)
    try:
        limit = store.db.execute("SELECT current_setting('memory_limit')").fetchone()[0]
        temp_dir = store.db.execute("SELECT current_setting('temp_directory')").fetchone()[0]
        assert limit
        assert Path(temp_dir).resolve() == (tmp_path / "duckdb_tmp").resolve()
        assert (tmp_path / "duckdb_tmp").is_dir()
    finally:
        store.db.close()


def test_empty_duckdb_memory_limit_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(duckdb_memory_limit=" ")


def test_bounded_webhook_executor_drops_when_pending_full() -> None:
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(5)

    executor = quote_service._BoundedWebhookExecutor(max_workers=1, max_pending=1)
    try:
        executor.submit(block)
        assert started.wait(5)

        with pytest.raises(quote_service._WebhookQueueFull):
            executor.submit(lambda: None)

        release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                executor.submit(lambda: None)
                break
            except quote_service._WebhookQueueFull:
                time.sleep(0.01)
        else:
            pytest.fail("webhook queue slot was not released after task completion")
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_dimension_intraday_cache_is_bounded_and_expires() -> None:
    ext_api._DIMENSION_INTRADAY_CACHE.clear()
    try:
        for i in range(ext_api._DIMENSION_INTRADAY_CACHE_MAX + 5):
            ext_api._dimension_intraday_cache_put((f"k{i}",), now=1000.0, payload={"i": i})

        assert len(ext_api._DIMENSION_INTRADAY_CACHE) == ext_api._DIMENSION_INTRADAY_CACHE_MAX
        assert ("k0",) not in ext_api._DIMENSION_INTRADAY_CACHE
        assert ext_api._dimension_intraday_cache_get(("k68",), 1000.0) == {"i": 68}

        assert ext_api._dimension_intraday_cache_get(("k5",), 1000.0 + 61) is None
        assert ("k5",) not in ext_api._DIMENSION_INTRADAY_CACHE
    finally:
        ext_api._DIMENSION_INTRADAY_CACHE.clear()


def test_ext_value_map_cache_is_bounded() -> None:
    screener_api._ext_value_map_cache.clear()
    try:
        for i in range(screener_api._EXT_VALUE_MAP_CACHE_MAX + 3):
            screener_api._remember_ext_value_map(
                (f"c{i}", "f", ""), (("part.parquet", i),), {"600000.SH": i}
            )

        assert len(screener_api._ext_value_map_cache) == screener_api._EXT_VALUE_MAP_CACHE_MAX
        assert ("c0", "f", "") not in screener_api._ext_value_map_cache
        assert ("c34", "f", "") in screener_api._ext_value_map_cache
    finally:
        screener_api._ext_value_map_cache.clear()
