import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDailyTimeline, getHourlyTimeline, getDayOfWeekTimeline, getApplicationMetrics } from '@/services/analytics'
import { TimelineChart } from '@/charts/TimelineChart'
import { RateBarChart } from '@/charts/RateBarChart'
import { ChartCard } from '@/components/ChartCard'
import { LoadingState, ErrorState } from '@/components/Feedback'
import { formatNumber, formatPercent } from '@/utils/format'
import { channelLabels } from '@/utils/channel'
import type { Dataset } from '@/types/api'

export function AnalyticsTab() {
  const { datasetId } = useParams()
  const { dataset } = useOutletContext<{ dataset: Dataset }>()
  const labels = channelLabels(dataset.source)

  const daily = useQuery({ queryKey: ['daily-timeline', datasetId], queryFn: () => getDailyTimeline(datasetId!), enabled: !!datasetId })
  const hourly = useQuery({ queryKey: ['hourly-timeline', datasetId], queryFn: () => getHourlyTimeline(datasetId!), enabled: !!datasetId })
  const dow = useQuery({ queryKey: ['dow-timeline', datasetId], queryFn: () => getDayOfWeekTimeline(datasetId!), enabled: !!datasetId })
  const apps = useQuery({ queryKey: ['applications', datasetId], queryFn: () => getApplicationMetrics(datasetId!), enabled: !!datasetId })

  if (daily.isLoading) return <LoadingState label="Loading analytics…" />
  if (daily.error) return <ErrorState message="Could not load analytics." onRetry={() => daily.refetch()} />

  return (
    <div className="space-y-6">
      {daily.data && (
        <ChartCard title="Daily Volume & Delivery Outcomes">
          {(expanded) => <TimelineChart data={daily.data} height={expanded ? 500 : 280} />}
        </ChartCard>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {hourly.data && (
          <ChartCard title="Volume by Hour of Day">
            {(expanded) => (
              <RateBarChart
                data={hourly.data}
                xKey="hour"
                yKey="total_emails"
                label={labels.unitPlural}
                color="#334155"
                xFormatter={(h) => `${h}:00`}
                height={expanded ? 500 : 220}
              />
            )}
          </ChartCard>
        )}
        {dow.data && (
          <ChartCard title="Volume by Day of Week">
            {(expanded) => (
              <RateBarChart data={dow.data} xKey="day_of_week" yKey="total_emails" label={labels.unitPlural} color="#475569" height={expanded ? 500 : 220} />
            )}
          </ChartCard>
        )}
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
          Application / Workflow Breakdown
        </h2>
        <table className="table-base">
          <thead>
            <tr>
              <th>Category</th>
              <th>{labels.unitPlural}</th>
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
