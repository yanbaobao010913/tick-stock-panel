// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ExtDataConfig } from '@/lib/api'
import { ExtDataPullPanel } from './ExtDataPullPanel'

const mocks = vi.hoisted(() => ({
  extDataApiKey: vi.fn(async () => ({ key_set: false, masked_key: '' })),
  extDataPullConfig: vi.fn(async () => ({})),
}))
vi.mock('@/lib/api', () => ({ api: mocks }))
vi.mock('@/components/Toast', () => ({ toast: vi.fn() }))

let root: Root
let host: HTMLDivElement
const saved = vi.fn()

function config(timeField: string | null = 'ts'): ExtDataConfig {
  return {
    id: 'auction', label: '竞价', mode: 'timeseries', fields: [],
    created_at: '', updated_at: '',
    pull: {
      url: 'https://example.invalid/quotes', method: 'GET', response_path: 'data',
      schedule_minutes: 5, enabled: false, time_field: timeField,
      since_param: 'since', page_start: 0,
    },
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

async function render(timeField: string | null = 'ts') {
  await act(async () => root.render(<ExtDataPullPanel config={config(timeField)} onSaved={saved} />))
}

it('keeps the inline editor and saves the upstream incremental cursor with existing paging', async () => {
  await render()
  const cursor = host.querySelector<HTMLInputElement>('input[placeholder="since · 留空=每次全量"]')!
  expect(cursor.value).toBe('since')
  expect(cursor.disabled).toBe(false)
  const save = [...host.querySelectorAll('button')].find(b => b.textContent?.includes('保存配置'))!
  await act(async () => save.click())
  expect(mocks.extDataPullConfig).toHaveBeenCalledWith('auction', expect.objectContaining({
    time_field: 'ts', since_param: 'since', page_start: 0,
  }))
  expect(saved).toHaveBeenCalledOnce()
})

it('retains the incremental cursor when auto-saving the schedule toggle', async () => {
  await render()
  await act(async () => host.querySelector<HTMLButtonElement>('[role="switch"]')!.click())
  expect(mocks.extDataPullConfig).toHaveBeenCalledWith('auction', expect.objectContaining({
    enabled: true, time_field: 'ts', since_param: 'since',
  }))
})

it('disables incremental editing until a time field is configured', async () => {
  await render(null)
  expect(host.querySelector<HTMLInputElement>('input[placeholder="since · 留空=每次全量"]')!.disabled).toBe(true)
  expect(host.textContent).toContain('需先填「时间字段」才能增量续传')
})
