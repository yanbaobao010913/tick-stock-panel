// @vitest-environment jsdom
// AI 标签「草稿」分区只列 AI 来源的 research_only 草稿: 发布闸 (POST /{id}/publish)
// 仅接受 source=ai, 内置研究模板 (factor_rank_research, research_only) 混入会渲染出
// 点了必然 400「仅 AI 策略可经发布端点上线」的「发布」按钮, 属误导性 UI。
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { StrategyPoolDialog } from './StrategyPoolDialog'
import type { StrategyDetail } from '@/lib/api'

const mockStrategyList = vi.fn()
const mockStrategyPublish = vi.fn(async (id: string) => ({ ok: true, strategy_id: id }))
vi.mock('@/lib/api', () => ({
  api: {
    strategyList: (...args: unknown[]) => mockStrategyList(...args),
    strategyPublish: (id: string) => mockStrategyPublish(id),
  },
}))

function mkStrategy(p: Partial<StrategyDetail> & Pick<StrategyDetail, 'id' | 'name' | 'source'>): StrategyDetail {
  return {
    description: '', tags: [], research_only: false,
    execution_backend: 'polars_expr', asset_types: ['stock'], timeframes: ['1d'],
    version: '1', basic_filter: {}, params: [], params_defaults: {},
    scoring: {}, scoring_directions: {}, entry_signals: [], exit_signals: [],
    minute_exit_trigger_supported_signals: [], stop_loss: null, take_profit: null,
    trailing_stop: null, trailing_take_profit_activate: null,
    trailing_take_profit_drawdown: null, max_hold_days: null,
    order_by: '', descending: true, limit: 50,
    ...p,
  }
}

const aiDraft = mkStrategy({ id: 'ai_breakout_v1', name: 'AI突破', source: 'ai', research_only: true })
const builtinResearch = mkStrategy({ id: 'factor_rank_research', name: '因子排名研究', source: 'custom', research_only: true })
const builtinPublic = mkStrategy({ id: 'trend_follow', name: '趋势跟随', source: 'custom' })
const compositePublic = mkStrategy({ id: 'composite_mix_v1', name: '混合叠加', source: 'composite' })

let root: Root | null = null
const container = document.createElement('div')
document.body.appendChild(container)

async function render() {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  root = createRoot(container)
  await act(async () => {
    root!.render(
      <StrategyPoolDialog pool={[]} onConfirm={() => {}} onClose={() => {}} />,
    )
  })
}

function clickTab(label: string) {
  const tab = Array.from(container.querySelectorAll('button'))
    .find(b => b.textContent?.startsWith(label))
  expect(tab).toBeTruthy()
  act(() => { tab!.click() })
}

const clickAiTab = () => clickTab('AI')

beforeEach(() => {
  mockStrategyList.mockReset()
  mockStrategyList.mockResolvedValue({ strategies: [aiDraft, builtinResearch, builtinPublic, compositePublic] })
  mockStrategyPublish.mockClear()
})
afterEach(() => {
  if (root) { act(() => { root!.unmount() }); root = null }
  container.innerHTML = ''
})

it('AI tab lists only ai-source drafts with a publish button', async () => {
  await render()
  clickAiTab()

  expect(container.textContent).toContain('AI突破')
  const publishButtons = Array.from(container.querySelectorAll('button'))
    .filter(b => b.textContent?.trim() === '发布')
  expect(publishButtons).toHaveLength(1)
  expect(container.textContent).toContain('1 个待发布')

  await act(async () => { publishButtons[0].click() })
  expect(mockStrategyPublish).toHaveBeenCalledWith('ai_breakout_v1')
})

it('builtin research template is not offered for publish anywhere in the pool', async () => {
  await render()

  // 默认「全部」分组: research_only 项不进待选, 模板应完全不出现
  expect(container.textContent).not.toContain('因子排名研究')
  expect(container.textContent).toContain('趋势跟随')

  clickAiTab()
  // 草稿分区同样不列非 AI 来源的 research 项
  expect(container.textContent).not.toContain('因子排名研究')
})

it('keeps composite strategies in the custom group with their own badge', async () => {
  await render()

  expect([...container.querySelectorAll('button')]
    .some(b => b.textContent?.startsWith('叠加'))).toBe(false)

  // fork 将叠加策略并入「自定义」, 同时保留叠加徽标。
  clickTab('自定义')
  expect(container.textContent).toContain('趋势跟随')
  expect(container.textContent).toContain('混合叠加')
  const composite = [...container.querySelectorAll('button')]
    .find(b => b.textContent?.includes('混合叠加'))!
  expect([...composite.querySelectorAll('span')]
    .some(s => s.textContent === '叠加')).toBe(true)

  // 「全部」分组仍同时可见两类
  clickTab('全部')
  expect(container.textContent).toContain('趋势跟随')
  expect(container.textContent).toContain('混合叠加')
})

it('does not offer publishing when only non-AI research templates exist', async () => {
  mockStrategyList.mockResolvedValue({ strategies: [builtinResearch] })
  await render()
  clickAiTab()

  expect(container.textContent).not.toContain('因子排名研究')
  expect([...container.querySelectorAll('button')]
    .some(b => b.textContent?.trim() === '发布')).toBe(false)
  expect(mockStrategyPublish).not.toHaveBeenCalled()
})
