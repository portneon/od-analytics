import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDailyTimeline, getHourlyTimeline, getDayOfWeekTimeline, getApplicationMetrics } from '@/services/analytics'
import { TimelineChart } from '@/charts/TimelineChart'
import { RateBarChart } from '@/charts/RateBarChart'
import { LoadingState, ErrorState } from '@/components/Feedback'
import { formatNumber, formatPercent } from '@/utils/format'

export function AnalyticsTab() {
  const { datasetId } = useParams()

  const daily = useQuery({ queryKey: ['daily-timeline', datasetId], queryFn: () => getDailyTimeline(datasetId!), enabled: !!datasetId })
  const hourly = useQuery({ queryKey: ['hourly-timeline', datasetId], queryFn: () => getHourlyTimeline(datasetId!), enabled: !!datasetId })
  const dow = useQuery({ queryKey: ['dow-timeline', datasetId], queryFn: () => getDayOfWeekTimeline(datasetId!), enabled: !!datasetId })
  const apps = useQuery({ queryKey: ['applications', datasetId], queryFn: () => getApplicationMetrics(datasetId!), enabled: !!datasetId })

  if (daily.isLoading) return <LoadingState label="Loading analytics…" />
  if (daily.error) return <ErrorState message="Could not load analytics." onRetry={() => daily.refetch()} />

  return (
    <div className="space-y-6">
      <div className="card p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Daily Volume &amp; Delivery Outcomes</h2>
        {daily.data && <TimelineChart data={daily.data} />}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Volume by Hour of Day</h2>
          {hourly.data && (
            <RateBarChart data={hourly.data} xKey="hour" yKey="total_emails" label="Emails" color="#334155" xFormatter={(h) => `${h}:00`} />
          )}
        </div>
        <div className="card p-4">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">Volume by Day of Week</h2>
          {dow.data && <RateBarChart data={dow.data} xKey="day_of_week" yKey="total_emails" label="Emails" color="#475569" />}
        </div>
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
          Application / Workflow Breakdown
        </h2>
        <table className="table-base">
          <thead>
            <tr>
              <th>Category</th>
              <th>Emails</th>
              <th>Delivery Rate</th>
              <th>Bounce Rate</th>
              <th>Failure Rate</th>
            </tr>
          </thead>
          <tbody>
            {apps.data?.map((row) => (
              <tr key={row.category}>
                <td className="font-medium text-slate-700">{row.category}</td>
                <td>{formatNumber(row.total_emails)}</td>
                <td>{formatPercent(row.delivery_rate)}</td>
                <td>{formatPercent(row.bounce_rate)}</td>
                <td>{formatPercent(row.failure_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
