// @vitest-environment jsdom
// 回归: 分析任务 id 持久化到 localStorage — 刷新/切页重挂载后恢复进度条;
// 任务进入终态或轮询 404 (后端重启清空内存任务表) 时从列表移除, 不再"幽灵追踪"。
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { storage } from '@/lib/storage'
import { dsaApi, type AnalysisTask, type ReportSummary } from '../api'
import { DsaAnalysisSection } from './DsaAnalysisSection'

vi.mock('@/components/Toast', () => ({ toast: vi.fn() }))

vi.mock('@/lib/api', () => ({
  api: { watchlistList: vi.fn(async () => ({ symbols: [] })) },
}))

vi.mock('../api', () => ({
  dsaApi: {
    health: vi.fn(async () => ({ status: 'ok', dsa_db_found: true, analysis_history_count: 0 })),
    analysisTask: vi.fn(),
    analysisTasks: vi.fn(async () => ({ tasks: [] })),
    reports: vi.fn(async () => ({ total: 0, items: [] })),
    legacyReports: vi.fn(async () => ({ total: 0, items: [] })),
  },
}))

const analysisTask = vi.mocked(dsaApi.analysisTask)
const analysisTasks = vi.mocked(dsaApi.analysisTasks)

const task = (id: string, status: AnalysisTask['status']): AnalysisTask => ({
  task_id: id,
  status,
  total: 2,
  done: status === 'running' ? 1 : 2,
  items: [
    { symbol: '600519.SH', status: 'done' },
    { symbol: '000001.SZ', status: status === 'running' ? 'running' : 'done' },
  ],
})

let root: Root | null = null
let host: HTMLElement

async function renderSection() {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  host = document.createElement('div')
  document.body.appendChild(host)
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  root = createRoot(host)
  await act(async () => {
    root!.render(
      <QueryClientProvider client={qc}>
        <DsaAnalysisSection />
      </QueryClientProvider>,
    )
  })
  await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
}

beforeEach(() => {
  localStorage.clear()
  analysisTask.mockReset()
  analysisTasks.mockResolvedValue({ tasks: [] })
})

afterEach(async () => {
  if (root) {
    await act(async () => root!.unmount())
    root = null
  }
  host?.remove()
})

it('localStorage 里有进行中任务 id → 重挂载后恢复进度条并继续轮询', async () => {
  storage.dsaAnalysisTasks.set(['task-1'])
  analysisTask.mockResolvedValue(task('task-1', 'running'))

  await renderSection()

  expect(analysisTask).toHaveBeenCalledWith('task-1')
  expect(host.textContent).toContain('分析任务 task-1')
  expect(host.textContent).toContain('进行中')
  // 恢复不丢 id, 下次刷新仍可再恢复
  expect(storage.dsaAnalysisTasks.get([])).toEqual(['task-1'])
})

it('后端任务列表接口找回仍在跑的任务 (换浏览器/清缓存场景)', async () => {
  analysisTasks.mockResolvedValue({ tasks: [task('task-r', 'running'), task('task-old', 'done')] })
  analysisTask.mockResolvedValue(task('task-r', 'running'))

  await renderSection()
  await act(async () => { await new Promise((r) => setTimeout(r, 0)) })

  expect(host.textContent).toContain('分析任务 task-r')
  expect(host.textContent).not.toContain('分析任务 task-old')
  expect(storage.dsaAnalysisTasks.get([])).toEqual(['task-r'])
})

it('无持久化任务 → 不渲染进度卡', async () => {
  await renderSection()

  expect(host.textContent).not.toContain('分析任务')
  expect(analysisTask).not.toHaveBeenCalled()
})

it('任务进入终态 → 卡片移除并从 localStorage 清除', async () => {
  storage.dsaAnalysisTasks.set(['task-2'])
  analysisTask.mockResolvedValue(task('task-2', 'done'))

  await renderSection()
  await act(async () => { await new Promise((r) => setTimeout(r, 0)) })

  expect(host.textContent).not.toContain('分析任务 task-2')
  expect(storage.dsaAnalysisTasks.get([])).toEqual([])
})

it('轮询返回 404 (任务已丢失) → 卡片移除并清理 localStorage', async () => {
  storage.dsaAnalysisTasks.set(['task-gone'])
  analysisTask.mockRejectedValue(Object.assign(new Error('任务不存在'), { status: 404 }))

  await renderSection()
  await act(async () => { await new Promise((r) => setTimeout(r, 0)) })

  expect(host.textContent).not.toContain('分析任务 task-gone')
  expect(storage.dsaAnalysisTasks.get([])).toEqual([])
})

it.each(['今日', '往期', 'DSA 历史（只读）'])('%s 报告按评分降序，同分按时间倒序，缺评分排末尾', async (view) => {
  const items: ReportSummary[] = [
    { id: 'missing', symbol: '000001.SZ', created_at: '2026-10-15T20:00:00' },
    { id: 'low', symbol: '000002.SZ', created_at: '2026-10-15T19:00:00', sentiment_score: 15 },
    { id: 'tie-old', symbol: '000003.SZ', created_at: '2026-10-15T17:00:00', sentiment_score: 60 },
    { id: 'high', symbol: '000004.SZ', created_at: '2026-10-15T16:00:00', sentiment_score: 90 },
    { id: 'tie-new', symbol: '000005.SZ', created_at: '2026-10-15T18:00:00', sentiment_score: 60 },
    { id: 'null', symbol: '000006.SZ', created_at: '2026-10-15T21:00:00', sentiment_score: null },
    { id: 'zero', symbol: '000007.SZ', created_at: '2026-10-15T15:00:00', sentiment_score: 0 },
  ]
  vi.mocked(dsaApi.reports).mockResolvedValue({ total: items.length, items })
  vi.mocked(dsaApi.legacyReports).mockResolvedValue({ total: items.length, items })
  try {
    await renderSection()
    if (view !== '今日') {
      await act(async () => {
        Array.from(host.querySelectorAll('button')).find((b) => b.textContent === view)!.click()
      })
      await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
    }

    expect(Array.from(host.querySelectorAll('tbody tr')).map((row) => row.children[1].textContent?.trim()))
      .toEqual(['000004.SZ', '000005.SZ', '000003.SZ', '000002.SZ', '000007.SZ', '000006.SZ', '000001.SZ'])
    expect(items.map((item) => item.id)).toEqual(['missing', 'low', 'tie-old', 'high', 'tie-new', 'null', 'zero'])
  } finally {
    vi.mocked(dsaApi.reports).mockResolvedValue({ total: 0, items: [] })
    vi.mocked(dsaApi.legacyReports).mockResolvedValue({ total: 0, items: [] })
  }
})

it('跨日期时先按日期倒序，再按同一天评分降序、同分时间倒序', async () => {
  // 高分的旧报告不能压过今天的新报告
  const items: ReportSummary[] = [
    { id: 'd14-high', symbol: '000001.SZ', created_at: '2026-10-14T09:00:00', sentiment_score: 95 },
    { id: 'd15-low', symbol: '000002.SZ', created_at: '2026-10-15T09:00:00', sentiment_score: 10 },
    { id: 'd15-tie-old', symbol: '000003.SZ', created_at: '2026-10-15T08:00:00', sentiment_score: 70 },
    { id: 'd13-missing', symbol: '000004.SZ', created_at: '2026-10-13T10:00:00' },
    { id: 'd15-tie-new', symbol: '000005.SZ', created_at: '2026-10-15T11:00:00', sentiment_score: 70 },
    { id: 'd14-low', symbol: '000006.SZ', created_at: '2026-10-14T23:00:00', sentiment_score: 20 },
  ]
  vi.mocked(dsaApi.reports).mockResolvedValue({ total: items.length, items })
  try {
    await renderSection()

    expect(Array.from(host.querySelectorAll('tbody tr')).map((row) => row.children[1].textContent?.trim()))
      .toEqual(['000005.SZ', '000003.SZ', '000002.SZ', '000001.SZ', '000006.SZ', '000004.SZ'])
    expect(items.map((item) => item.id)).toEqual(['d14-high', 'd15-low', 'd15-tie-old', 'd13-missing', 'd15-tie-new', 'd14-low'])
  } finally {
    vi.mocked(dsaApi.reports).mockResolvedValue({ total: 0, items: [] })
  }
})
