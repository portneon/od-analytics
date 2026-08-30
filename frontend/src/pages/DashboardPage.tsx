import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getExecutiveSummary, getExecutiveTimeline } from '@/services/executive'
import { StatTile, rateTone } from '@/components/StatTile'
import { TimelineChart } from '@/charts/TimelineChart'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { SeverityBadge, DatasetStatusBadge } from '@/components/Badges'
import { formatDate, formatNumber, formatPercent } from '@/utils/format'

/** The executive landing page: a rollup across every dataset, not scoped to
 * any one import. Per-dataset detail lives under /datasets/:id. */
export function DashboardPage() {
  const navigate = useNavigate()
  const summary = useQuery({ queryKey: ['executive-summary'], queryFn: getExecutiveSummary })
  const timeline = useQuery({ queryKey: ['executive-timeline'], queryFn: getExecutiveTimeline })

  if (summary.isLoading) return <LoadingState label="Loading executive dashboard…" />
  if (summary.error || !summary.data) return <ErrorState message="Could not load the executive dashboard." onRetry={() => summary.refetch()} />

  const s = summary.data

  if (s.total_datasets === 0) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <h1 className="mb-4 text-lg font-semibold text-slate-900">Executive Dashboard</h1>
        <EmptyState
          title="No datasets yet"
          description="Upload your first Zoho Mail CSV export to see delivery analytics and executive insights here."
        />
        <div className="mt-4 text-center">
          <button className="btn-primary" onClick={() => navigate('/datasets')}>
            Go to Datasets
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Executive Dashboard</h1>
          <p className="text-sm text-slate-400">
            Rolled up across {formatNumber(s.usable_datasets)} of {formatNumber(s.total_datasets)} dataset
            {s.total_datasets === 1 ? '' : 's'} with usable data.
          </p>
        </div>
        {s.needs_attention > 0 && (
          <button
            className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
            onClick={() => navigate('/datasets')}
          >
            {s.needs_attention} dataset{s.needs_attention === 1 ? '' : 's'} need attention
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Total Emails" value={formatNumber(s.total_emails)} />
        <StatTile label="Unique Recipients" value={formatNumber(s.unique_recipients)} />
        <StatTile label="Unique Domains" value={formatNumber(s.unique_domains)} />
        <StatTile label="Delivery Rate" value={formatPercent(s.delivery_rate)} tone={rateTone(s.delivery_rate, 'delivery')} />
        <StatTile label="Bounce Rate" value={formatPercent(s.bounce_rate)} tone={rateTone(s.bounce_rate, 'bounce')} />
        <StatTile label="Failure Rate" value={formatPercent(s.failure_rate)} tone={rateTone(s.failure_rate, 'failure')} />
      </div>

      <div className="card p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Email Volume Trend (all datasets)</h2>
        {timeline.isLoading && <LoadingState />}
        {timeline.data && timeline.data.length > 0 && <TimelineChart data={timeline.data} />}
        {timeline.data && timeline.data.length === 0 && (
          <EmptyState title="No timeline data yet" description="Daily metrics appear once a dataset finishes processing." />
        )}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Top Insights Across All Datasets</h2>
        {s.insights.length === 0 && (
          <EmptyState title="No anomalies detected" description="There are no statistically significant anomalies across your datasets." />
        )}
        <div className="space-y-2">
          {s.insights.map((insight) => (
            <div
              key={insight.id}
              className="card cursor-pointer p-4 hover:border-slate-300"
              onClick={() => navigate(`/datasets/${insight.dataset_id}/anomalies`)}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={insight.severity} />
                    <p className="text-sm font-medium text-slate-800">{insight.title}</p>
                    {insight.dataset_name && <span className="text-xs text-slate-400">· {insight.dataset_name}</span>}
                  </div>
                  <p className="mt-1 text-sm text-slate-500">{insight.explanation}</p>
                </div>
                {insight.change_percent !== null && (
                  <span className={`text-sm font-semibold ${insight.change_percent > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                    {insight.change_percent > 0 ? '+' : ''}
                    {insight.change_percent}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Recent Datasets</h2>
        <table className="table-base">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Rows</th>
              <th>Period</th>
              <th>Uploaded</th>
            </tr>
          </thead>
          <tbody>
            {s.recent_datasets.map((d) => (
              <tr key={d.id} className="cursor-pointer" onClick={() => navigate(`/datasets/${d.id}`)}>
                <td className="font-medium text-slate-800">{d.name}</td>
                <td>
                  <DatasetStatusBadge status={d.status} />
                </td>
                <td>{formatNumber(d.row_count)}</td>
                <td>
                  {formatDate(d.date_start)} – {formatDate(d.date_end)}
                </td>
                <td className="text-slate-400">{formatDate(d.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
