import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getOverview, getDailyTimeline, getInsights, listEntities } from '@/services/analytics'
import { StatTile, rateTone } from '@/components/StatTile'
import { TimelineChart } from '@/charts/TimelineChart'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { SeverityBadge } from '@/components/Badges'
import { formatNumber, formatPercent } from '@/utils/format'
import { DataQualityCard } from './DataQualityCard'

export function OverviewTab() {
  const { datasetId } = useParams()
  const navigate = useNavigate()

  const overview = useQuery({ queryKey: ['overview', datasetId], queryFn: () => getOverview(datasetId!), enabled: !!datasetId })
  const timeline = useQuery({ queryKey: ['daily-timeline', datasetId], queryFn: () => getDailyTimeline(datasetId!), enabled: !!datasetId })
  const insights = useQuery({ queryKey: ['insights', datasetId], queryFn: () => getInsights(datasetId!), enabled: !!datasetId })
  const topDomains = useQuery({
    queryKey: ['top-domains', datasetId],
    queryFn: () => listEntities(datasetId!, 'domains', { sort_by: 'bounce_rate', page_size: 5 }),
    enabled: !!datasetId,
  })
  const topRecipients = useQuery({
    queryKey: ['top-recipients', datasetId],
    queryFn: () => listEntities(datasetId!, 'recipients', { sort_by: 'bounce_rate', page_size: 5 }),
    enabled: !!datasetId,
  })

  if (overview.isLoading) return <LoadingState label="Loading overview…" />
  if (overview.error || !overview.data) return <ErrorState message="Could not load overview metrics." onRetry={() => overview.refetch()} />

  const ov = overview.data

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Total Emails" value={formatNumber(ov.total_emails)} />
        <StatTile label="Unique Recipients" value={formatNumber(ov.unique_recipients)} />
        <StatTile label="Delivery Rate" value={formatPercent(ov.delivery_rate)} tone={rateTone(ov.delivery_rate, 'delivery')} />
        <StatTile label="Hard Bounce" value={formatPercent((ov.hard_bounces / ov.total_emails) * 100 || 0)} tone={rateTone(ov.bounce_rate, 'bounce')} />
        <StatTile label="Soft Bounce" value={formatPercent((ov.soft_bounces / ov.total_emails) * 100 || 0)} tone="neutral" />
        <StatTile label="Failure Rate" value={formatPercent(ov.failure_rate)} tone={rateTone(ov.failure_rate, 'failure')} />
      </div>

      <div className="card p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Email Volume Trend</h2>
        {timeline.isLoading && <LoadingState />}
        {timeline.data && <TimelineChart data={timeline.data} />}
      </div>

      <DataQualityCard />

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Anomalies &amp; Recommendations</h2>
        {insights.isLoading && <LoadingState />}
        {insights.data && insights.data.length === 0 && (
          <EmptyState title="No anomalies detected" description="There are no statistically significant anomalies for this dataset." />
        )}
        <div className="space-y-2">
          {insights.data?.map((insight) => (
            <div key={insight.id} className="card cursor-pointer p-4 hover:border-slate-300" onClick={() => navigate('anomalies')}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={insight.severity} />
                    <p className="text-sm font-medium text-slate-800">{insight.title}</p>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">{insight.explanation}</p>
                  {insight.recommendations.length > 0 && (
                    <ul className="mt-2 list-inside list-disc text-xs text-slate-400">
                      {insight.recommendations.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  )}
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Top Problem Domains</h2>
          <table className="table-base">
            <tbody>
              {topDomains.data?.items.map((d) => (
                <tr key={d.id} className="cursor-pointer" onClick={() => navigate(`domains/${d.id}`)}>
                  <td className="font-medium text-slate-700">{d.name}</td>
                  <td>{formatNumber(d.total_emails)} emails</td>
                  <td className="text-red-600">{formatPercent(d.bounce_rate)} bounce</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card overflow-hidden">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Top Problem Recipients</h2>
          <table className="table-base">
            <tbody>
              {topRecipients.data?.items.map((r) => (
                <tr key={r.id} className="cursor-pointer" onClick={() => navigate(`recipients/${r.id}`)}>
                  <td className="font-medium text-slate-700">{r.name}</td>
                  <td>{formatNumber(r.total_emails)} emails</td>
                  <td className="text-red-600">{formatPercent(r.bounce_rate)} bounce</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
