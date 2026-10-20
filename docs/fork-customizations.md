# fork 定制台账与同步流程

本文件记录 fork 相对上游的**行为保证**,用于每次同步上游时逐项核对,避免"文本无冲突但行为丢失"。

基线:上游 `v0.3.9`(合并提交 `3b069bda`,回补提交 `8372a2e4`)。上游仓库 `origin` = `shy3130/tick-stock-panel`,fork = `yanbaobao010913/tick-stock-panel`。

## 1. 同步流程

```bash
# 0) 在独立分支操作, 不直接动 main
git switch -c sync/upstream-vX.Y.Z fork/main

# 1) 合并前预检: 双方同改文件 + 文本冲突预演 (只读)
python3 scripts/upgrade_check.py vX.Y.Z

# 2) 合并。注意: 无冲突 ≠ 正确。冲突文件逐个人工判断,
#    不要整文件取上游 —— fork 定制和守着它的测试会一起消失。
git merge vX.Y.Z

# 3) fork 契约自检: 回归测试/模块/关键实现标记是否仍完整
python3 scripts/fork_sync_check.py

# 4) 全量验证
cd backend && uv run --frozen pytest tests -q
cd ../frontend && pnpm build
```

第 3 步由 CI 的 `fork-contract` job 强制执行。清单在 `scripts/fork_sync_check.py` 顶部;**废弃任何一项契约,必须在同一提交里显式修改该清单**,并说明替代验证方式。

## 2. 核心行为保证

| 保证 | 实现 | 守护测试 |
| --- | --- | --- |
| 桌面版启动失败页(后端提前退出/超时) | `backend/app/desktop.py` `_failed_html` / `_precheck_mining_lock` / `_open_static_window` | `test_desktop_startup.py` |
| 自定义分钟源分块流式落盘(内存峰值从全量降到单段) | `backend/app/services/kline_sync.py` `_CUSTOM_MINUTE_CHUNK` | `test_minute_custom_streaming_persist.py` |
| 标的维表 fail-closed(部分交易所失败不覆盖旧表) | `backend/app/services/instrument_sync.py` `_EXCHANGE_RETRIES` + `sync_instruments` | `test_instrument_sync_failclosed.py` |
| 分钟同步门控与 `api/kline._minute_allowed` 一致(自定义源声明 dataset 即放行) | `backend/app/jobs/daily_pipeline.py` `minute_allowed` | `test_daily_pipeline_minute_gate.py` |
| 矩阵构建分段计时 | `backend/app/backtest/matrix.py` `timing_ms["axes"]` | 既有矩阵测试 |
| 价格路径模式(接近/止损路径状态机, 单 close 阈值契约) | `backend/app/strategy/price_path.py` + `monitor_rules` 校验 + `api/monitor_rules` | `test_price_path_*.py` |
| 纸质交易条件单(依赖日线 high/low) | `backend/app/strategy/paper.py` `read_daily_bar` 返回完整 OHLC | `test_paper_conditional.py` `test_paper_bar_read_schema.py` |
| DSA 桥接(分析/回测/组合/自选/提醒) | `backend/app/custom/dsa_bridge.py` 等 | `test_dsa_*.py` |

### 已提交上游的通用修复 (2026-10-20)

以下修复与 DSA/cnfree 无关, 已作为独立 PR 提交上游。上游合并后, 同步时直接采用上游实现并删除本文件的对应条目:

| 修复 | 上游 PR |
| --- | --- |
| 标的维表 fail-closed(部分交易所失败不覆盖旧表) | #495 |
| 自定义分钟源按块流式落盘 | #496 |
| 桌面启动失败页 + 挖掘锁预检 | #497 |
| 盘后分钟门控与 `api/kline` 对齐 | #498 |

## 3. 前端页面注册(v0.3.9 起已迁移到扩展)

v0.3.6 起上游采用「核心 + 扩展」架构:页面、路由、侧栏导航统一由 `frontend/src/custom/<ns>/extension.tsx` 单文件声明,构建时自动发现。fork 曾另有 11 份 `frontend/src/pages/<X>.tsx` 副本并手工注册进 `router.tsx`,导致双重注册、重复导航和扩展被 `CORE_ROUTE_PATHS` 拒绝;这些副本已在 v0.3.9 同步中删除。

迁移后:

- `router.tsx`、`Layout.tsx` 的 `nav` 与上游一致(核心 8 项 + 扩展自动追加),同步时不再需要手工改这两个文件;
- 扩展页面的路径与导航改动一律进 `custom/<ns>/extension.tsx`;
- fork 在扩展上的三处定制必须保留(契约自检已覆盖):
  - `custom/paper/extension.tsx`:新账户默认资金 10 万;
  - `custom/stock-analysis/extension.tsx`:页面底部注入 `DsaAnalysisSection`;
  - `custom/lots/extension.tsx`:仅保留路由,不注册「持仓提醒」导航项(DSA 报告点位已覆盖手动批次提醒)。

## 4. 已知 L3 改动区(每次同步必须人工复核)

按相对上游的改动量排序,前若干项:

| 文件 | 说明 |
| --- | --- |
| `frontend/src/components/ext-data/ExtDataPullPanel.tsx` | 扩展数据拉取面板 |
| `frontend/src/components/screener/StrategySettingsDialog.tsx` | 策略参数与叠加条件(`overlay_filter`) |
| `frontend/src/components/signals/CustomSignalDialog.tsx` | 自定义信号(AI 提示词含因子分组) |
| `backend/app/backtest/engine.py` | 回测引擎 |
| `frontend/src/pages/settings/AI.tsx` | AI 设置 |
| `frontend/src/components/ext-data/CreateExtDialog.tsx` / `EditExtDialog.tsx` / `ExtDataStatCard.tsx` | 扩展数据对话框 |
| `frontend/src/lib/signals.ts` | 自定义信号定义 |
| `backend/app/backtest/strategy.py` | 策略回测(含 `factor_attribution`) |
| `frontend/src/pages/Onboarding.tsx` / `pages/backtest/StrategyBacktest.tsx` | 引导与策略回测页 |
| `backend/app/strategy/paper.py` | 纸质交易(条件单) |
| `backend/app/strategy/monitor.py` / `monitor_rules.py` / `api/monitor_rules.py` | 监控(价格路径) |
| `backend/app/desktop.py` / `Dockerfile` | 桌面版启动与打包 |
| `backend/app/backtest/matrix.py` | 矩阵分段计时 |

重新生成完整清单(同步时作为核对表):

```bash
git diff --name-status origin/main...HEAD   # fork 全部差异
git diff --numstat origin/main...HEAD | sort -k1,1nr   # 按改动量排序
```

## 5. 上游 PR 候选

通用改进,上游吸收后即可删除本地回补(删除前须确认**正式发布版本**包含,而不是只看上游默认分支):

- 标的维表同步 fail-closed(部分失败不覆盖旧表);
- 自定义分钟源分块流式落盘;
- 桌面启动失败页与挖掘锁预检;
- 分钟同步门控与 `api/kline._minute_allowed` 对齐(上游自身口径不一致)。

## 6. 版本与发布

- 上游基线记 Git tag(`v0.3.9`),不等于发行版本。
- Docker 走 `fork/main` push 自动构建;桌面安装包走 `release.yml`(`workflow_dispatch`),要求传入版本等于 `frontend/package.json`。
- 当前 `frontend/package.json` 0.3.5、`backend/pyproject.toml` 0.3.3、上游 0.3.9,发桌面包前先对齐。
