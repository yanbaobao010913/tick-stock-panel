#!/usr/bin/env python3
"""同步后自检: fork 独有的测试与实现标记是否仍完整。

合并上游时把冲突文件整体取上游, git 不会报错, 但 fork 定制和守着
它们的测试可能一起消失, CI 依然是绿的。本脚本把 fork 的核心保证
固化成可执行清单, 由 CI 与升级流程强制校验。

清单变更(新增/删除契约项)必须显式修改本文件, 从而在评审里可见。

用法:
    python scripts/fork_sync_check.py
    python scripts/fork_sync_check.py --root /path/to/repo
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# fork 独有的回归测试: 删掉任何一个都会让 CI 失去对应行为的守护。
REQUIRED_TESTS = (
    "backend/tests/backtest/test_dsa_points_strategy.py",
    "backend/tests/test_cnfree_provider.py",
    "backend/tests/test_daily_pipeline_minute_gate.py",
    "backend/tests/test_desktop_startup.py",
    "backend/tests/test_fork_sync_check.py",
    "backend/tests/test_dsa_alerts.py",
    "backend/tests/test_dsa_analysis.py",
    "backend/tests/test_dsa_backtest.py",
    "backend/tests/test_dsa_legacy_bridge.py",
    "backend/tests/test_dsa_paper_bridge.py",
    "backend/tests/test_dsa_portfolio.py",
    "backend/tests/test_dsa_watch.py",
    "backend/tests/test_dsa_watch_ladder.py",
    "backend/tests/test_instrument_sync_failclosed.py",
    "backend/tests/test_minute_custom_streaming_persist.py",
    "backend/tests/test_paper_bar_read_schema.py",
    "backend/tests/test_paper_conditional.py",
    "backend/tests/test_price_path_boundaries.py",
    "backend/tests/test_price_path_merge_paper.py",
    "backend/tests/test_price_path_monitor.py",
    "backend/tests/test_stocksdk_provider.py",
)

# fork 独有的模块与扩展注册目录: 路径消失即功能消失。
REQUIRED_PATHS = (
    "backend/app/strategy/price_path.py",
    "frontend/src/custom/abnormal/extension.tsx",
    "frontend/src/custom/concept-analysis/extension.tsx",
    "frontend/src/custom/financials/extension.tsx",
    "frontend/src/custom/industry-analysis/extension.tsx",
    "frontend/src/custom/limit-ladder/extension.tsx",
    "frontend/src/custom/lots/extension.tsx",
    "frontend/src/custom/monitor/extension.tsx",
    "frontend/src/custom/paper/extension.tsx",
    "frontend/src/custom/review/extension.tsx",
    "frontend/src/custom/signals/extension.tsx",
    "frontend/src/custom/stock-analysis/extension.tsx",
)


@dataclass(frozen=True)
class Marker:
    path: str
    pattern: str
    label: str
    # True 表示该模式必须"不存在" (如被故意隐藏的导航项)
    absent: bool = False


# 关键实现标记: 符号还在但调用链被绕开时, 行为测试才是主防线;
# 这里拦住的是"整段实现被上游覆盖"这类最常见的事故。
REQUIRED_MARKERS = (
    Marker("backend/app/desktop.py", r"def _failed_html\(", "桌面启动失败页"),
    Marker("backend/app/desktop.py", r"def _precheck_mining_lock\(", "挖掘锁预检"),
    Marker("backend/app/desktop.py", r"_open_static_window\(", "失败页窗口接线"),
    Marker("backend/app/services/kline_sync.py", r"_CUSTOM_MINUTE_CHUNK", "自定义分钟源分块落盘"),
    Marker("backend/app/services/instrument_sync.py", r"_EXCHANGE_RETRIES", "标的维表分交易所重试"),
    Marker("backend/app/jobs/daily_pipeline.py", r"minute_allowed", "分钟同步能力门控"),
    Marker("backend/app/backtest/matrix.py", r'timing_ms\["axes"\]', "矩阵分段计时"),
    # v0.3.9 同步中曾被整文件取上游吞掉, 补标记防止再次静默丢失
    Marker("frontend/index.html", r"tf-page-zoom", "页面缩放预渲染脚本"),
    Marker("frontend/src/main.tsx", r"installTspExtBridge", "运行时扩展桥"),
    Marker("frontend/src/components/Layout.tsx", r"layout\.header\.quick", "侧栏快捷入口插槽"),
    Marker("frontend/src/components/Layout.tsx", r"defaultNavIndex", "默认导航排序"),
    Marker("frontend/src/pages/settings/System.tsx", r"UpgradeGuardCard", "升级保护设置卡"),
    # fork 在上游扩展上的定制
    Marker("frontend/src/custom/paper/extension.tsx", r"100000", "模拟盘默认资金 10 万"),
    Marker("frontend/src/custom/stock-analysis/extension.tsx", r"DsaAnalysisSection", "个股分析 DSA 区块"),
    Marker("frontend/src/custom/lots/extension.tsx", r"navigation\s*:", "持仓提醒导航项(已按拍板隐藏)", absent=True),
)


def run_checks(root: Path) -> list[str]:
    """返回失败项描述; 空列表表示通过。"""
    failures: list[str] = []

    for rel in REQUIRED_TESTS:
        path = root / rel
        if not path.is_file():
            failures.append(f"缺少 fork 回归测试: {rel}")
        elif path.stat().st_size == 0:
            failures.append(f"fork 回归测试为空文件: {rel}")

    for rel in REQUIRED_PATHS:
        if not (root / rel).is_file():
            failures.append(f"缺少 fork 模块/扩展注册: {rel}")

    for marker in REQUIRED_MARKERS:
        path = root / marker.path
        if not path.is_file():
            failures.append(f"缺少实现文件 ({marker.label}): {marker.path}")
            continue
        found = re.search(marker.pattern, path.read_text(encoding="utf-8")) is not None
        if marker.absent and found:
            failures.append(
                f"不应出现的实现 ({marker.label}): {marker.path} 中匹配到 /{marker.pattern}/"
            )
        elif not marker.absent and not found:
            failures.append(
                f"实现标记丢失 ({marker.label}): {marker.path} 中找不到 /{marker.pattern}/"
            )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="仓库根目录 (默认脚本所在仓库)",
    )
    args = parser.parse_args(argv)

    failures = run_checks(args.root)
    if failures:
        print(f"fork 契约自检失败 ({len(failures)} 项):", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        print(
            "若确认某项已废弃, 请在同一提交中更新 scripts/fork_sync_check.py "
            "并说明替代的验证方式。",
            file=sys.stderr,
        )
        return 1

    print(
        f"fork 契约自检通过: {len(REQUIRED_TESTS)} 个回归测试, "
        f"{len(REQUIRED_PATHS)} 个模块/注册, {len(REQUIRED_MARKERS)} 个实现标记。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
