"""沪深300ETF 份额/净申赎 API — 只读, 数据由 services.etf_share 统一拉取与缓存。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.services import etf_share

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/etf-share", tags=["etf-share"])


@router.get("/monthly")
def get_monthly(months: int = Query(12, ge=3, le=36, description="返回最近 N 个月")):
    """月末份额与月度净申赎(亿份)。拿不到任何数据时返回空 rows, 由前端提示。"""
    try:
        return etf_share.get_monthly(months)
    except Exception as e:  # noqa: BLE001
        # 上交所接口不可用时不允许伪造数据; 有缓存则上面已返回缓存, 走到这里说明连缓存都没有
        logger.warning("ETF 份额月度序列不可用: %s", e)
        return {
            "funds": [{"code": c, "name": n} for c, n in etf_share.FUNDS.items()],
            "note": etf_share.SCOPE_NOTE,
            "rows": [],
            "as_of": None,
            "source": "none",
            "error": "上交所基金份额接口不可用, 且无本地缓存",
        }
