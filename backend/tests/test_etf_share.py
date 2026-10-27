"""沪深300ETF 份额服务: 月度聚合口径、断月缺口、单位换算与失败路径。"""

from __future__ import annotations

from datetime import date

import pytest

from app.services import etf_share


@pytest.fixture()
def cache_file(tmp_path, monkeypatch):
    path = tmp_path / "etf_share" / "sse_shares.parquet"
    monkeypatch.setattr(etf_share, "_cache_path", lambda: path)
    monkeypatch.setattr(etf_share, "_probe_ts", {})
    return path


def _fake_fetch(table):
    """table: {date_str: {code: share}}; 未命中的日期返回空(模拟非交易日/无披露)。"""
    def _fetch(day: date):
        return table.get(day.isoformat(), {})
    return _fetch


def test_monthly_share_and_flow(cache_file, monkeypatch):
    monkeypatch.setattr(etf_share, "cn_today", lambda: date(2026, 3, 31))
    table = {
        "2025-12-31": {"510300": 100.0, "510310": 50.0, "510330": 30.0, "515330": 20.0},
        "2026-01-30": {"510300": 90.0, "510310": 45.0, "510330": 30.0, "515330": 20.0},
        "2026-02-27": {"510300": 80.0, "510310": 45.0, "510330": 30.0, "515330": 20.0},
        "2026-03-31": {"510300": 70.0, "510310": 45.0, "510330": 30.0, "515330": 25.0},
    }
    monkeypatch.setattr(etf_share, "_fetch_day", _fake_fetch(table))

    out = etf_share.get_monthly(2)
    rows = out["rows"]
    assert [r["month"] for r in rows] == ["2026-02", "2026-03"]
    assert rows[0]["share"] == 175.0
    assert rows[0]["flow"] == -10.0     # 175 - 185(2026-01)
    assert rows[1]["share"] == 170.0
    assert rows[1]["flow"] == -5.0
    assert out["as_of"] == "2026-03-31"
    assert out["source"] == "live"


def test_missing_month_is_gap_not_merged(cache_file, monkeypatch):
    monkeypatch.setattr(etf_share, "cn_today", lambda: date(2026, 3, 31))
    table = {
        "2025-12-31": {"510300": 100.0, "510310": 50.0, "510330": 30.0, "515330": 20.0},
        # 2026-01 整月无披露
        "2026-02-27": {"510300": 80.0, "510310": 45.0, "510330": 30.0, "515330": 20.0},
        "2026-03-31": {"510300": 70.0, "510310": 45.0, "510330": 30.0, "515330": 20.0},
    }
    monkeypatch.setattr(etf_share, "_fetch_day", _fake_fetch(table))

    rows = etf_share.get_monthly(3)["rows"]
    assert [r["month"] for r in rows] == ["2025-12", "2026-02", "2026-03"]
    assert rows[1]["flow"] is None       # 断月: 不能拿 12 月的值算两个月合并差额
    assert rows[2]["flow"] == -10.0      # 165 - 175


def test_fetch_failure_returns_empty(cache_file, monkeypatch):
    monkeypatch.setattr(etf_share, "cn_today", lambda: date(2026, 3, 31))

    def boom(day: date):
        raise RuntimeError("sse down")

    monkeypatch.setattr(etf_share, "_fetch_day", boom)
    out = etf_share.get_monthly(3)
    assert out["rows"] == []
    assert out["source"] == "none"
    assert out["as_of"] is None


def test_partial_day_is_rejected(cache_file, monkeypatch):
    """缺任一标的的日期视为不完整, 不能只拿部分基金算合计。"""
    monkeypatch.setattr(etf_share, "cn_today", lambda: date(2026, 2, 27))
    table = {
        "2026-01-30": {"510300": 100.0, "510310": 50.0, "510330": 30.0, "515330": 20.0},
        "2026-02-27": {"510300": 90.0, "510310": 45.0},  # 少两只
    }
    monkeypatch.setattr(etf_share, "_fetch_day", _fake_fetch(table))
    rows = etf_share.get_monthly(2)["rows"]
    assert [r["month"] for r in rows] == ["2026-01"]


def test_fetch_day_converts_wan_shares(monkeypatch):
    """TOT_VOL 单位为万份, 必须换算成亿份; 非目标标的丢弃。"""
    payload = {
        "result": [
            {"SEC_CODE": "510300", "TOT_VOL": "2411958.77"},
            {"SEC_CODE": "999999", "TOT_VOL": "123"},
            {"SEC_CODE": "510310", "TOT_VOL": "-"},
        ]
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            return _Resp()

    monkeypatch.setattr(etf_share.httpx, "Client", _Client)
    out = etf_share._fetch_day(date(2026, 9, 30))
    assert out == {"510300": 241.195877}


def test_cache_roundtrip(cache_file, monkeypatch):
    monkeypatch.setattr(etf_share, "cn_today", lambda: date(2026, 2, 27))
    table = {
        "2026-01-30": {"510300": 100.0, "510310": 50.0, "510330": 30.0, "515330": 20.0},
        "2026-02-27": {"510300": 90.0, "510310": 45.0, "510330": 30.0, "515330": 20.0},
    }
    monkeypatch.setattr(etf_share, "_fetch_day", _fake_fetch(table))
    etf_share.get_monthly(2)
    assert cache_file.exists()

    # 断网后仍能从缓存出数
    def boom(day: date):
        raise RuntimeError("offline")

    monkeypatch.setattr(etf_share, "_fetch_day", boom)
    out = etf_share.get_monthly(2)
    assert [r["month"] for r in out["rows"]] == ["2026-01", "2026-02"]
    assert out["source"] == "cache"


def test_api_contract(monkeypatch):
    """API 透传服务结果; months 越界由 Query 约束拦下。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.etf_share import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    monkeypatch.setattr(etf_share, "get_monthly", lambda months: {
        "funds": [{"code": "510300", "name": "华泰柏瑞"}],
        "note": etf_share.SCOPE_NOTE,
        "rows": [{"month": "2026-01", "date": "2026-01-30", "share": 1065.21, "flow": -1017.43}],
        "as_of": "2026-01-30",
        "source": "cache",
    })

    resp = client.get("/api/etf-share/monthly", params={"months": 6})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"][0]["flow"] == -1017.43
    assert body["note"] == etf_share.SCOPE_NOTE

    assert client.get("/api/etf-share/monthly", params={"months": 1}).status_code == 422
    assert client.get("/api/etf-share/monthly", params={"months": 99}).status_code == 422
