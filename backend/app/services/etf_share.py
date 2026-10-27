"""沪深300ETF 份额与月度净申赎 — 上交所每日基金份额公开披露。

口径:
- 存量: 上交所「ETF 基金份额」日频披露的 TOT_VOL(万份), 换算为亿份。
- 月度点: 取当月最后一个有披露的交易日; 月度净申赎 = 本月末份额 − 上月末份额。
  ETF 无分红拆分, 份额差额即当期净申赎, 不受净值涨跌影响。
- 覆盖沪市头部 4 只沪深300ETF; 159919(嘉实)在深交所, 无免费日频份额接口, 未计入,
  由 note 字段显式告知调用方, 不做静默补全。
- 缺数据即缺失: 某个整月拿不到披露就跳过该月, 不插值、不猜日期、不拿上一月顶替。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, timedelta

import httpx
import polars as pl

from app.config import settings
from app.market_time import cn_today
from app.services.fs_utils import atomic_write_parquet

logger = logging.getLogger(__name__)

# 沪市沪深300ETF 头部 4 只(按 2026Q3 规模排序)
FUNDS: dict[str, str] = {
    "510300": "华泰柏瑞",
    "510310": "易方达",
    "510330": "华夏",
    "515330": "天弘",
}
SCOPE_NOTE = "沪市 4 只, 不含 159919(深交所无免费日频份额)"

SSE_URL = "http://query.sse.com.cn/commonQuery.do"
SSE_SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "http://www.sse.com.cn/"}
# 月末候选日最多往前回退的自然日数(长假/周末)
_MAX_BACKTRACK_DAYS = 7
# 当月未收盘时重复探测的最小间隔(秒)
_PROBE_TTL = 600.0

_lock = threading.Lock()
_probe_ts: dict[str, float] = {}


def _cache_path():
    return settings.data_dir / "etf_share" / "sse_shares.parquet"


def _empty() -> pl.DataFrame:
    return pl.DataFrame(schema={"date": pl.String, "code": pl.String, "share": pl.Float64})


def _load_cache() -> pl.DataFrame:
    path = _cache_path()
    if not path.exists():
        return _empty()
    try:
        return pl.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        # 半截文件/旧 schema 不应让整条链路不可用, 视为无缓存并重建
        logger.warning("ETF 份额缓存读取失败, 忽略: %s", e)
        return _empty()


def _fetch_day(day: date) -> dict[str, float]:
    """拉取某个交易日全部沪市 ETF 份额(亿份), 只保留 FUNDS 内的标的。"""
    params = {
        "sqlId": SSE_SQL_ID,
        "STAT_DATE": day.isoformat(),
        "pageHelp.pageSize": 2000,
        "pageHelp.pageNo": 1,
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(SSE_URL, params=params, headers=_HEADERS)
        resp.raise_for_status()
        payload = resp.json()
    out: dict[str, float] = {}
    for row in payload.get("result") or []:
        code = str(row.get("SEC_CODE") or "")
        if code not in FUNDS:
            continue
        try:
            out[code] = float(row["TOT_VOL"]) / 10000.0  # 万份 → 亿份
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _month_last_day(month: str, today: date) -> date:
    year, mon = int(month[:4]), int(month[5:7])
    nxt = date(year + (mon == 12), mon % 12 + 1, 1)
    return min(nxt - timedelta(days=1), today)


def _recent_months(count: int, today: date) -> list[str]:
    months: list[str] = []
    y, m = today.year, today.month
    for _ in range(count):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


def _prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def _cached_month(cache: pl.DataFrame, month: str) -> tuple[str, dict[str, float]] | None:
    if cache.is_empty():
        return None
    hit = cache.filter(pl.col("date").str.starts_with(month))
    if hit.is_empty():
        return None
    latest = str(hit["date"].max())
    rows = hit.filter(pl.col("date") == latest)
    return latest, {r["code"]: float(r["share"]) for r in rows.iter_rows(named=True)}


def _probe_month(month: str, today: date) -> tuple[str, dict[str, float]] | None:
    """从当月最后一个自然日往前找最近一个有完整披露的交易日。"""
    start = _month_last_day(month, today)
    for back in range(_MAX_BACKTRACK_DAYS):
        day = start - timedelta(days=back)
        if day.weekday() >= 5:
            continue
        try:
            shares = _fetch_day(day)
        except Exception as e:  # noqa: BLE001
            logger.warning("ETF 份额拉取失败 %s: %s", day, e)
            return None
        if len(shares) == len(FUNDS):
            return day.isoformat(), shares
    return None


def _append_cache(day: str, shares: dict[str, float]) -> None:
    with _lock:
        cache = _load_cache()
        if not cache.is_empty() and day in set(cache["date"].to_list()):
            return
        add = pl.DataFrame(
            {"date": [day] * len(shares), "code": list(shares), "share": list(shares.values())},
            schema={"date": pl.String, "code": pl.String, "share": pl.Float64},
        )
        merged = add if cache.is_empty() else pl.concat([cache, add])
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_parquet(merged, path)


def get_monthly(months: int = 12) -> dict:
    """最近 N 个月的份额与净申赎。首月前多取一个月作为差额基准。"""
    today = cn_today()
    months = max(1, min(months, 36))
    wanted = _recent_months(months + 1, today)
    current = wanted[-1]

    cache = _load_cache()
    series: list[tuple[str, str, dict[str, float]]] = []
    fetched = False
    for month in wanted:
        got = _cached_month(cache, month)
        # 当月仍在披露: 缓存不是今天的数据时按 TTL 重新探测, 拿到更新的日期就覆盖
        if got and month == current and got[0] < today.isoformat():
            now = time.time()
            if now - _probe_ts.get(month, 0.0) >= _PROBE_TTL:
                _probe_ts[month] = now
                fresh = _probe_month(month, today)
                if fresh and fresh[0] > got[0]:
                    _append_cache(*fresh)
                    cache = _load_cache()
                    got = fresh
                    fetched = True
        if not got:
            got = _probe_month(month, today)
            if got:
                _append_cache(*got)
                cache = _load_cache()
                fetched = True
        if got:
            series.append((month, got[0], got[1]))

    rows: list[dict] = []
    prev_total: float | None = None
    prev_month: str | None = None
    for month, day, shares in series:
        total = round(sum(shares.values()), 2)
        # 只有紧邻的上一自然月也在序列里, 差额才是「当月」净申赎; 断月不给数, 不合并两个月
        contiguous = prev_month is not None and _prev_month(month) == prev_month
        rows.append({
            "month": month,
            "date": day,
            "share": total,
            "flow": round(total - prev_total, 2) if contiguous and prev_total is not None else None,
        })
        prev_total, prev_month = total, month

    # 丢掉仅作差额基准的首月
    if len(rows) > months:
        rows = rows[-months:]

    return {
        "funds": [{"code": code, "name": name} for code, name in FUNDS.items()],
        "note": SCOPE_NOTE,
        "rows": rows,
        "as_of": rows[-1]["date"] if rows else None,
        "source": "live" if fetched else ("cache" if rows else "none"),
    }
