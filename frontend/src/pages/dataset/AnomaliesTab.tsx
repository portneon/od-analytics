import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getAnomalies, getRootCause } from '@/services/analytics'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { SeverityBadge } from '@/components/Badges'
import { formatDate, formatDateTime } from '@/utils/format'

export function AnomaliesTab() {
  const { datasetId } = useParams()
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['anomalies', datasetId],
    queryFn: () => getAnomalies(datasetId!),
    enabled: !!datasetId,
  })

  if (isLoading) return <LoadingState label="Loading anomalies…" />
  if (error) return <ErrorState message="Could not load anomalies." onRetry={() => refetch()} />
  if (!data || data.length === 0) {
    return <EmptyState title="No anomalies detected" description="There are no statistically significant anomalies for this dataset." />
  }

  return (
    <div className="space-y-3">
      {data.map((a) => (
        <div key={a.id} className="card p-4">
          <div className="flex cursor-pointer items-start justify-between gap-3" onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
            <div>
              <div className="flex items-center gap-2">
                <SeverityBadge severity={a.severity} />
                <p className="text-sm font-medium text-slate-800">{a.metric.replace('_', ' ')}</p>
                <span className="text-xs text-slate-400">{a.entity_type}</span>
              </div>
              <p className="mt-1 text-sm text-slate-500">{a.explanation}</p>
              <p className="mt-1 text-xs text-slate-400">Detected {formatDateTime(a.detected_at)}</p>
            </div>
          </div>
          {expanded === a.id && a.entity_type === 'overall' && (a.metric === 'bounce_rate' || a.metric === 'failure_rate') && (
            <RootCauseDetail datasetId={datasetId!} metric={a.metric as 'bounce_rate' | 'failure_rate'} onDate={a.period_start ?? undefined} />
          )}
        </div>
      ))}
    </div>
  )
}

function RootCauseDetail({ datasetId, metric, onDate }: { datasetId: string; metric: 'bounce_rate' | 'failure_rate'; onDate?: string }) {
  const date = onDate ? onDate.slice(0, 10) : undefined
  const { data, isLoading } = useQuery({
    queryKey: ['root-cause', datasetId, metric, date],
    queryFn: () => getRootCause(datasetId, metric, date),
    enabled: !!datasetId,
  })

  if (isLoading) return <LoadingState label="Analyzing root cause…" />
  const result = data as { dimensions?: { dimension: string; contributors: { value: string; contribution_percent: number }[] }[]; note?: string } | undefined
  if (!result?.dimensions?.length) return <p className="mt-3 text-xs text-slate-400">No root-cause breakdown available.</p>

  return (
    <div className="mt-4 border-t border-slate-100 pt-4">
      <p className="mb-2 text-xs text-slate-400">Root-cause breakdown{date ? ` for ${formatDate(date)}` : ''} — association, not confirmed causation.</p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {result.dimensions.map((dim) => (
          <div key={dim.dimension}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{dim.dimension.replace('_', ' ')}</p>
            <ul className="space-y-1">
              {dim.contributors.map((c, i) => (
                <li key={i} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{c.value}</span>
                  <span className="font-medium text-slate-800">{c.contribution_percent}%</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
