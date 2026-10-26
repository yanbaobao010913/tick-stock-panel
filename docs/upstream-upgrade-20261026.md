# v0.3.18 升级核查与交接

核查日期：2026-10-26。已通过 `git fetch --no-tags` 刷新 origin/fork,并查询作者 Release 和修复 PR 状态。作者最新发布仍为 [v0.3.18](https://github.com/shy3130/tick-stock-panel/releases/tag/v0.3.18),上游 HEAD 为 `b08a267a`。本轮未检查或变更云端运行状态。

## 当前结论

已在独立适配分支 `sync/upstream-v0.3.18-codex` 将上游 v0.3.18 与定制版整合,19 处冲突全部解决,没有整文件取上游覆盖定制。尚未提交、推送或部署。用户追问前端失败项后确认:继承问题中包含真实配置保存与草稿发布缺陷,不能仅按旧测试忽略;处理前不建议上线。

上一轮停在差异调查。用户随后明确要求“更新一下我们的”“注意我们自己的修改”,本轮据现有定制台账完成源码适配与验证。

| 对象 | 当前提交 | 状态 |
| --- | --- | --- |
| 当前适配分支 | 起点 `fcc8cf8b`,合入目标 `b08a267a` | 合并结果在工作区与索引,尚未生成合并提交 |
| 原 `yanbaobao010913/mandarin` | `b08a267a` | 原纯上游分支保持原指向 |
| 定制版 `fork/main` | `fcc8cf8b` | 前端版本与 VERSION 均为 0.3.9；含定制台账与契约检查 |
| 正式目录的 `main` | `073b56d6` | 是 `fork/main` 的祖先，落后 931 个提交；有未提交修改 |
| 云端 | 本轮未验证 | 上轮记录为定制版 0.3.9，不能当成本轮实测 |

正式目录已有修改：`backend/app/plugins/cnfree/provider.py`、`backend/tests/test_cnfree_provider.py`,另有两篇未跟踪的事故文档。已把两份代码文件的未提交补丁应用到适配分支,保留 fork 额外测试;正式目录文件原样保留,前后 SHA256 一致。没有覆盖或清除原修改。

## 纠正上一轮的判断

1. “代码已经是最新版，不用合并”只适用于当前纯上游工作区，不适用于定制版。
2. 不能再拿七月份共同祖先和约千个差异文件，直接断言本次无法同步。定制版已经同步过 v0.3.9，并有 `docs/fork-customizations.md`、`scripts/fork_sync_check.py` 规定的同步及验收流程。
3. 当前共同祖先是 `05817654`。相对此基线，定制侧改动 180 个文件，上游改动 269 个文件，双方交集 40 个；Git 合并预演报告 19 个冲突文件。文本冲突数量不代表剩余语义风险，也不能代替回归验证。
4. `v0.3.9..origin/main` 有 79 个非合并提交。只有 `05817654` 已是定制版祖先，不能据此声称另外 78 项功能都缺失：定制版可能已有不同提交实现的等效行为。
5. 上游 `frontend/package.json` 为 0.3.18,而其他版本标记仍为 0.3.17。本轮将后端项目版本、uv.lock 本项目条目、VERSION、后端回退版本与 release 默认值统一到 0.3.18,未升级无关依赖。
6. 四项已提交上游的修复并非都已合并:#495 仍 OPEN,必须保留 fork 标的维表重试/失败保护;#496/#497/#498 已合并且包含于 v0.3.18。

## 版本差异与优先核查项

79 个非合并提交按标题分类：28 fix、27 feat、11 chore、6 docs、2 test、1 perf、1 wip、3 其他。不能仅按标题选取补丁，涉及扩展定义与回测的修复可能依赖同窗口新增架构。

| 核查组 | 代表提交 | 适配要求 |
| --- | --- | --- |
| 分钟源与落盘 | `62affd5a`、`3d29ff99`、`ddaab1fb`、`7812c02e`、`7fadaa90` | 保留分块落盘；采用自定义源失败不跨源回退的边界；校验写锁、原子写、缺口及时间字段归一 |
| 分钟门控 | `9d0769dd` | 定制版已有相同门控逻辑；两侧当前文件差异在实验室调度，不能把同名修复当成全部缺失再重复摘取 |
| 启动诊断与日志 | `55d9e116`、`c286af70`、`5d6ac5c7`、`b573ca43` | 定制版已有失败页；检查上游新增日志、锁降级及定制预检的行为兼容 |
| enriched 正确性 | `648bab1b`、`7f34a523` | 覆盖发布标记残留与孤儿分区，不破坏 generation 和缓存失效 |
| 自定义数据源 | `eab70c40`、`24ce7719`、`2c6f03da` | 保留维表 fail-closed、股本字段、指数/ETF 路由及 cnfree/stocksdk |
| 策略与回测 | `62c8a8bd`、`8cedb67c`、`a5e9d8fd`、`a3fcf99c` | 核对扩展时序、列依赖和 P0–P4 依赖；同时守住 DSA 回测与价格路径行为 |
| 配置与扩展 | `cce38f2c`、`9d554a51`、`a40c0780`、`a3c26134` | 检查后端持久化、删除后不复活、schema/分页以及凭据和调度边界 |
| 列表与分时 | `5f644427`、`60081d1e`、`2056c5c3`、`aa295224` | 检查实时口径、补拉失败的本地回退、停牌与竞价；保留现有前端定制 |

## 合并预演

执行：`git merge-tree --write-tree --name-only --no-messages fork/main origin/main`。

退出码 1 表示预演存在冲突，并非执行失败。命令只创建 Git 对象，不改变工作区、索引、分支或合并状态。冲突文件如下：

```text
backend/app/backtest/strategy.py
backend/app/desktop.py
backend/app/services/kline_sync.py
backend/tests/test_daily_pipeline_minute_gate.py
backend/tests/test_desktop_startup.py
backend/uv.lock
docs/deployment.md
docs/features.md
frontend/src/components/SectorRotationCard.tsx
frontend/src/components/ext-data/ExtDataPullPanel.tsx
frontend/src/components/screener/ScreenerTable.tsx
frontend/src/custom/assistant/ui/AssistantDrawer.tsx
frontend/src/lib/queryKeys.ts
frontend/src/pages/Screener.tsx
frontend/src/pages/Settings.tsx
frontend/src/pages/Watchlist.tsx
frontend/src/pages/backtest/StrategyBacktest.tsx
frontend/src/pages/settings/MenuSettings.tsx
frontend/src/pages/settings/System.tsx
```

## 适配与验收边界

本次按用户后续明确指示进行完整源码适配,沿用定制版台账流程;当前工作区本身已隔离,正式目录及运行服务未动。

### 定制保留与合并修正

- DSA 分析/组合/自选/提醒及回测入口,cnfree/stocksdk,价格路径监控与模拟盘条件单保留。DSA 后端与前端独立扩展文件、stocksdk、价格路径核心相对适配前基线没有改动。
- 模拟盘默认本金仍为 10 万;持仓提醒仅保留路由而隐藏导航;保留 DSA 导航与分析区块、雷达配置、分时基准线着色、布局快捷插槽、缩放和运行时扩展桥、升级保护设置卡。
- 助手继续默认非模态,保留上游新增遮罩开关作为显式选择,前后端默认均关闭。
- 内联扩展拉取表单保留,接入上游 `since_param`;设置接入页面管理、定义目录与配置备份,旧菜单深链正常迁移。
- 回测同时保留 DSA 逐格价格与上游共享准备/编码。修正自动合并造成的未定义变量与 overlay 二维掩码重复应用,覆盖直接运行及共享准备两条路径。
- 桌面锁冲突随上游改为降级启动,保留具体诊断、提前退出感知和 panel 停止指引;日志位置对齐 `data/logs/desktop.log`。
- 自定义分钟源按 50 标的分块落盘;失败不跨源回退,已经落盘的成功块保留;维表交易所失败不覆盖旧表,并采用上游新增股本补齐。

### 验证中发现并修复的上游 Windows 问题

- 备份中的 CRLF 经文本写入二次转换为 CRCRLF。保留 UTF-8 与 AST 安全校验,复用原子字节写入以原样恢复;新增 LF/CRLF 导出、导入、再导出的字节一致性回归。
- 发布锁与挖掘锁诊断使用 `os.kill(pid, 0)` 探测存活,在 Windows 会终止目标进程。改用已依赖的 `psutil.pid_exists`,新增“不发送任何信号”的存活/不存在回归。[Python 官方语义](https://docs.python.org/3/library/os.html#os.kill)。
- Windows 锁住第 0 字节后,另一句柄整文件读取会失败,导致持有者显示未知。读取该模块固定 JSON 记录时从第 1 字节读取并补回固定首字符,不释放或绕过实际锁。原先两个持有者状态回归由失败变为通过。

### 实际验证

- `python -X utf8 scripts/fork_sync_check.py`:21 个 fork 测试、6 个上游测试、12 个模块/注册、17 个实现标记均通过;检查脚本和 CI 门禁与原定制版无差异。
- 后端依赖按现有 uv.lock 冻结安装,Windows Python 3.14.5,Polars 1.44.1。Python 3.12 联网下载未完成后停止,改用已有缓存的受支持 Python 3.14,未改依赖锁解析结果。
- 回测目录 422 passed,overlay/DSA 定向组合 81 passed;数据源/分钟/提醒/模拟盘等定向组合 248 passed;备份/发布锁/助手偏好组合 56 passed;挖掘锁与桌面组合 28 passed、4 skipped。
- 前端冻结安装成功,`pnpm build` 通过。新增 ExtDataPullPanel 回归 3 passed;两个 Node 测试文件按 `node --test` 执行共 5 passed。
- Playwright 以 mock API 检查菜单旧链迁移、DSA 导航/管理、隐藏 lots、系统版本/关于/升级保护、运行时扩展桥、默认非模态及遮罩切换,0 未捕获页面异常。拦截所有外部请求,未接真实行情。
- 额外全量 Vitest:38 文件通过、4 文件失败,305 测试通过、12 失败。两个失败文件实际使用 Node 测试框架,按正确 runner 通过;另两个为 StrategySettingsDialog/StrategyPoolDialog。相关组件和测试与原 fork 完全一致,仅能证明问题不是本次升级新引入,不能证明失败都无关紧要。详见下方复核。
- `git diff --check` 与暂存区检查通过,无未解决冲突。

### 最终后端全量结果

`cd backend && uv run --frozen pytest tests -q --tb=short -o faulthandler_timeout=60`:**3803 passed、16 skipped、1 xfailed**,耗时 113.17 秒,退出码 0。跳过及预期失败保留项目既有平台/能力限制,没有用新 skip/xfail 掩盖升级问题。333 条警告主要为既存 Polars/Python 弃用与性能提示。

本轮实际改动的发布锁、挖掘锁和新增/调整测试文件 Ruff 通过;回测核心三文件与旧定制版诊断对比未新增诊断,仍有既存告警。`uv lock --check --offline` 通过。

### 剩余边界

尚未验证真实行情、打包桌面窗口、Linux/macOS 或云端运行。窄屏设置页可渲染但仍有既存导航挤压,Vite 保留既有大 chunk 提示。部署前仍需提交/推送授权、数据备份与实际服务加载新代码后的验收。

### 12 个前端失败项复核与结论更正

用户追问后重跑两个测试文件,结果 **12 failed、1 passed**。这 12 项集中于两个组件,并不是 12 个互不相关的缺陷。

| 位置 | 失败数 | 实际发现 |
| --- | ---: | --- |
| StrategySettingsDialog | 10 | 测试期待分区导航、未保存提示、完整风控、叠加条件编辑/保存、分钟策略限制提示与组合策略说明;定制版当前为简化表单,多项入口不存在 |
| StrategyPoolDialog | 2 | 组合策略并入自定义而测试期待独立分组;另有非 AI 研究模板被列入 AI 待发布草稿的真实错误 |

需要区分两类:

- 布局/文案差异:导航分区、组合策略说明、组合策略分组。这些不能仅为了测试恢复整套上游界面,应按定制版真实行为验证。
- 功能缺口:设置页只有止损与持仓天数,没有止盈、移动止损、回撤止盈或叠加条件编辑;保存 payload 也未携带上述字段。`api.strategySaveConfig` 调用 POST `/api/strategies/config`,后端 `save_config` 对 override 做整份保存,因此编辑其他字段有清除既有叠加/风控覆盖值的风险。草稿列表只按 `research_only` 过滤,未限制 `source === 'ai'`,给非 AI 模板显示的发布按钮会被后端 `publish_ai_strategy` 以 400 拒绝。

结论:前轮“旧 UI 断言”的统一归类不充分。“升级前就有”只说明来源,不等于无害。至少应在上线前修复配置丢失风险与误导发布入口;功能编辑缺口和布局差异需分开处理。本次追问仅核查并更正文档,尚未修改这两个组件。

### 两个组件的修复结果

保留定制版简化分栏(不恢复上游分区导航),只补齐真实缺口:

- 策略设置弹窗改用 `api.strategyPatchConfig`(PATCH `/api/strategies/config`) 保存,后端按字段合并 override;编辑名称等单字段不再覆盖已有叠加条件与风控覆盖值。首次加载与「重置默认」共用同一份状态恢复入口。
- 交易参数补齐止盈、移动止损、回撤止盈启动/回撤四个字段,百分比口径显示、小数口径保存,回撤止盈回撤与启动值联动收敛;叠加条件区接入 `ConditionEditor`(含「最新/前N日」offset),composite 与 minute_filter 显示不支持提示且不提交该字段。
- 恢复「有未保存的改动」底部提示(基于加载快照比对),重置失败原因回显。
- 股票池草稿列表只收录 `source === 'ai' && research_only`,非 AI 研究模板不再出现误导性「发布」按钮。
- 测试按定制版真实行为改写:删除分区导航相关断言,新增 PATCH 保留既有风控/叠加、完整风控字段保存、叠加条件 offset 保存、草稿发布过滤等回归;后端新增 `test_strategy_saved_params.py::test_dialog_patch_preserves_existing_risk_overlay_and_unedited_fields`(合并保留、显式清空、非法条件 400 且不落盘)。

验证:两个弹窗测试 15 passed(整个 screener 目录 29 passed);前端全量 Vitest 41 文件、322 测试通过,仅剩 `DimensionMembersDialog.test.ts`、`neighborPrefetch.test.ts` 两个 `node:test` 文件被 Vitest 误收(与本次改动无关,按 `node --test` 执行通过);`tsc -b` 无错误;后端全量 3803 passed、16 skipped、1 xfailed,唯一失败 `test_spawn_walkforward_skips_folds_before_available_matrix_data` 单独重跑通过(全量并发下的进程启动抖动)。
