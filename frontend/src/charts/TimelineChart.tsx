import { useId, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Legend, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatDate } from '@/utils/format'

interface TimelinePoint {
  date: string
  successful: number
  hard_bounces: number
  soft_bounces: number
}

type ChartMouseEvent = { activeLabel?: string | number } | null

// Deliberately high-contrast against each other (blue / red / violet) rather
// than the semantic-but-similar green/amber/red used elsewhere, since these
// three lines are read side by side on the same chart.
const SERIES = [
  { key: 'successful', name: 'Successful', color: '#2563eb' },
  { key: 'hard_bounces', name: 'Hard bounces', color: '#dc2626' },
  { key: 'soft_bounces', name: 'Soft bounces', color: '#7c3aed' },
] as const

// Pixels of drag needed to double (or halve) the visible range -- tuned by
// feel, matches the "grab the axis and stretch it" feel of trading platforms.
const AXIS_DRAG_SENSITIVITY = 150

export function TimelineChart({ data, height = 280 }: { data: TimelinePoint[]; height?: number }) {
  const gradientPrefix = useId()
  const [dragStart, setDragStart] = useState<string | null>(null)
  const [dragEnd, setDragEnd] = useState<string | null>(null)
  const [zoomDomain, setZoomDomain] = useState<[string, string] | null>(null)
  const [yDomain, setYDomain] = useState<[number, number] | null>(null)
  const [activeKey, setActiveKey] = useState<string | null>(null)

  const dateIndex = useMemo(() => new Map(data.map((d, i) => [d.date, i])), [data])
  const [dataMin, dataMax] = useMemo(() => {
    const values = data.flatMap((d) => [d.successful, d.hard_bounces, d.soft_bounces])
    return [Math.min(0, ...values), Math.max(1, ...values)]
  }, [data])

  // Drag-select inside the plot area: pick an explicit date range to zoom to.
  const handleMouseDown = (e: ChartMouseEvent) => {
    if (e?.activeLabel !== undefined) setDragStart(String(e.activeLabel))
  }
  const handleMouseMove = (e: ChartMouseEvent) => {
    if (dragStart && e?.activeLabel !== undefined) setDragEnd(String(e.activeLabel))
  }
  const finishDrag = () => {
    if (dragStart && dragEnd && dragStart !== dragEnd) {
      const i1 = dateIndex.get(dragStart)!
      const i2 = dateIndex.get(dragEnd)!
      const [lo, hi] = i1 < i2 ? [i1, i2] : [i2, i1]
      setZoomDomain([data[lo].date, data[hi].date])
    }
    setDragStart(null)
    setDragEnd(null)
  }

  // Grab the time axis and drag horizontally to stretch/compress it in place.
  const handleXAxisMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    const [lo, hi] = zoomDomain ? [dateIndex.get(zoomDomain[0])!, dateIndex.get(zoomDomain[1])!] : [0, data.length - 1]
    const startX = e.clientX

    const onMove = (ev: MouseEvent) => {
      const factor = Math.pow(2, -(ev.clientX - startX) / AXIS_DRAG_SENSITIVITY)
      const center = (lo + hi) / 2
      const halfRange = Math.max(0.5, ((hi - lo) / 2) * factor)
      let newLo = Math.max(0, Math.round(center - halfRange))
      let newHi = Math.min(data.length - 1, Math.round(center + halfRange))
      if (newHi <= newLo) newHi = Math.min(data.length - 1, newLo + 1)
      setZoomDomain(newLo <= 0 && newHi >= data.length - 1 ? null : [data[newLo].date, data[newHi].date])
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  // Grab the value axis and drag vertically to stretch/compress it in place.
  const handleYAxisMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    const [baseMin, baseMax] = yDomain ?? [dataMin, dataMax]
    const startY = e.clientY

    const onMove = (ev: MouseEvent) => {
      const factor = Math.pow(2, (ev.clientY - startY) / AXIS_DRAG_SENSITIVITY)
      const center = (baseMin + baseMax) / 2
      const halfRange = Math.max(1, ((baseMax - baseMin) / 2) * factor)
      setYDomain([center - halfRange, center + halfRange])
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const resetView = () => {
    setZoomDomain(null)
    setYDomain(null)
  }

  const orderedSeries = activeKey ? [...SERIES.filter((s) => s.key !== activeKey), ...SERIES.filter((s) => s.key === activeKey)] : SERIES

  return (
    <div>
      <div className="mb-1 flex h-5 items-center justify-between text-[11px] text-slate-400">
        <span>Drag the chart or its axes to zoom · click a legend item to isolate it</span>
        {(zoomDomain || yDomain) && (
          <button className="font-medium text-slate-600 hover:text-slate-900" onClick={resetView}>
            Reset view
          </button>
        )}
      </div>
      <div className="flex items-stretch gap-1">
        <div
          className="w-3 shrink-0 cursor-ns-resize rounded bg-slate-50 hover:bg-slate-200"
          style={{ height }}
          title="Drag up/down to zoom the value axis"
          onMouseDown={handleYAxisMouseDown}
        />
        <div className="min-w-0 flex-1">
          <ResponsiveContainer width="100%" height={height}>
            <AreaChart
              data={data}
              margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={finishDrag}
              onMouseLeave={() => (dragStart ? finishDrag() : undefined)}
              style={{ cursor: 'crosshair' }}
            >
              <defs>
                {SERIES.map((s) => (
                  <linearGradient key={s.key} id={`${gradientPrefix}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={s.color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={s.color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="date"
                type="category"
                allowDataOverflow={!!zoomDomain}
                domain={zoomDomain ?? undefined}
                tickFormatter={(d) => formatDate(d)}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
              />
              <YAxis
                allowDataOverflow={!!yDomain}
                domain={yDomain ?? ['auto', 'auto']}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
              />
              <Tooltip labelFormatter={(d) => formatDate(d as string)} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend
                wrapperStyle={{ fontSize: 12, cursor: 'pointer' }}
                onClick={(e) => setActiveKey((prev) => (prev === e.dataKey ? null : (e.dataKey as string)))}
                formatter={(value, entry) => {
                  const isActive = activeKey === entry.dataKey
                  return (
                    <span style={{ opacity: !activeKey || isActive ? 1 : 0.4, fontWeight: isActive ? 700 : 400 }}>{value}</span>
                  )
                }}
              />
              {orderedSeries.map((s) => {
                const dimmed = activeKey !== null && activeKey !== s.key
                return (
                  <Area
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={s.color}
                    fill={`url(#${gradientPrefix}-${s.key})`}
                    strokeWidth={2}
                    strokeOpacity={dimmed ? 0.15 : 1}
                    fillOpacity={dimmed ? 0.05 : 1}
                  />
                )
              })}
              {dragStart && dragEnd && <ReferenceArea x1={dragStart} x2={dragEnd} strokeOpacity={0.3} fill="#3b82f6" fillOpacity={0.1} />}
            </AreaChart>
          </ResponsiveContainer>
          <div
            className="mt-1 h-3 cursor-ew-resize rounded bg-slate-50 hover:bg-slate-200"
            title="Drag left/right to zoom the time axis"
            onMouseDown={handleXAxisMouseDown}
          />
        </div>
      </div>
    </div>
  )
}
