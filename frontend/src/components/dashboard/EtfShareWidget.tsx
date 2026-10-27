/**
 * 头部沪深300ETF 月末份额与净申赎 — 看板组件。
 *
 * 数据: GET /api/etf-share/monthly (上交所每日基金份额 → 月末聚合)。
 * 柱=当月净申赎(亿份, 红入绿出), 线=月末合计份额; 断月 flow 为 null, 图上留空不做插值。
 */
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as echarts from 'echarts'
import { Coins } from 'lucide-react'
import { api } from '@/lib/api'
import { QK } from '@/lib/queryKeys'
import { useChartTheme } from '@/lib/theme'
import { MiniMetric, SectionTitle } from './shared'

const MONTHS = 12

export function EtfShareWidget() {
  const ct = useChartTheme()
  const elRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: QK.etfShareMonthly(MONTHS),
    queryFn: () => api.etfShareMonthly(MONTHS),
    // 份额按日披露, 月频看板不需要高频刷新
    staleTime: 10 * 60_000,
    refetchInterval: 30 * 60_000,
  })

  const rows = data?.rows ?? []
  const last = rows[rows.length - 1]
  const lastFlow = last?.flow
  const fmt = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 1 })

  useEffect(() => {
    const el = elRef.current
    if (!el) return
    const chart = echarts.init(el, undefined, { renderer: 'canvas' })
    chartRef.current = chart
    const ro = new ResizeObserver(() => chart.resize())
    ro.observe(el)
    return () => {
      ro.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || rows.length === 0) return
    const labels = rows.map(r => r.month.slice(5) + '月')
    chart.setOption({
      animation: false,
      grid: { left: 42, right: 42, top: 14, bottom: 18 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: ct.tooltipBg,
        borderColor: ct.tooltipBorder,
        textStyle: { color: ct.tooltipText, fontSize: 11 },
        formatter: (p: any) => {
          const i = p[0].dataIndex
          const r = rows[i]
          const flow = r.flow == null ? '—' : (r.flow > 0 ? '+' : '') + r.flow.toLocaleString()
          return r.month + ' (' + r.date + ')<br>净申赎 <b>' + flow + '</b> 亿份<br>月末份额 <b>' + r.share.toLocaleString() + '</b> 亿份'
        },
      },
      xAxis: {
        type: 'category',
        data: labels,
        axisLine: { lineStyle: { color: ct.border } },
        axisTick: { show: false },
        axisLabel: { color: ct.text, fontSize: 9, interval: 0 },
      },
      yAxis: [
        {
          type: 'value',
          axisLine: { lineStyle: { color: ct.border } },
          axisLabel: { color: ct.text, fontSize: 9 },
          splitLine: { lineStyle: { color: ct.grid } },
        },
        {
          type: 'value',
          axisLine: { lineStyle: { color: ct.border } },
          axisLabel: { color: ct.text, fontSize: 9 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '净申赎',
          type: 'bar',
          barMaxWidth: 18,
          data: rows.map(r => ({
            value: r.flow,
            itemStyle: {
              color: (r.flow ?? 0) >= 0 ? '#ef4444' : '#22c55e',
              borderRadius: (r.flow ?? 0) >= 0 ? [2, 2, 0, 0] : [0, 0, 2, 2],
            },
          })),
        },
        {
          name: '月末份额',
          type: 'line',
          yAxisIndex: 1,
          data: rows.map(r => r.share),
          smooth: true,
          symbolSize: 4,
          lineStyle: { width: 1.8, color: '#3b82f6' },
          itemStyle: { color: '#3b82f6' },
        },
      ],
    })
  }, [rows, ct])

  return (
    <section className="flex h-full flex-col overflow-hidden rounded-card border border-border bg-surface/80 p-1.5 shadow-[0_1px_2px_hsl(var(--border)/0.4)] backdrop-blur-sm transition-shadow hover:shadow-[0_2px_8px_hsl(var(--border)/0.5)]">
      <SectionTitle icon={Coins} title="300ETF 份额申赎" hint={data?.as_of ?? undefined} />
      {isLoading && <div className="flex flex-1 items-center justify-center text-[11px] text-muted">加载中…</div>}
      {isError && <div className="flex flex-1 items-center justify-center text-[11px] text-muted">数据获取失败</div>}
      {!isLoading && !isError && rows.length === 0 && (
        <div className="flex flex-1 items-center justify-center text-[11px] text-muted">{data?.error ?? '暂无数据'}</div>
      )}
      {last && (
        <div className="mb-1 grid shrink-0 grid-cols-2 gap-1.5">
          <MiniMetric
            label="最新月净申赎"
            value={lastFlow == null ? '—' : (lastFlow > 0 ? '+' : '') + fmt(lastFlow) + ' 亿份'}
            cls={lastFlow == null ? 'text-foreground' : lastFlow >= 0 ? 'text-red-500' : 'text-green-500'}
          />
          <MiniMetric label="月末份额" value={fmt(last.share) + ' 亿份'} />
        </div>
      )}
      <div ref={elRef} className="min-h-0 flex-1" />
      {data?.note && (
        <p className="truncate text-[9px] text-muted" title={data.note}>{data.note}</p>
      )}
    </section>
  )
}
