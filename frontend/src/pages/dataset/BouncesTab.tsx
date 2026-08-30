import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getBounceReasons } from '@/services/analytics'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { RateBarChart } from '@/charts/RateBarChart'
import { ChartCard } from '@/components/ChartCard'
import { formatNumber, formatPercent } from '@/utils/format'

export function BouncesTab() {
  const { datasetId } = useParams()
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['bounces', datasetId],
    queryFn: () => getBounceReasons(datasetId!),
    enabled: !!datasetId,
  })

  if (isLoading) return <LoadingState label="Loading bounce reasons…" />
  if (error) return <ErrorState message="Could not load bounce reasons." onRetry={() => refetch()} />
  if (!data || data.length === 0) return <EmptyState title="No bounces recorded" description="This dataset has no bounce events." />

  return (
    <div className="space-y-6">
      <ChartCard title="Bounce Volume by Reason">
        {(expanded) => (
          <RateBarChart data={data} xKey="business_label" yKey="count" label="Bounces" color="#dc2626" height={expanded ? 500 : 220} />
        )}
      </ChartCard>

      <div className="card overflow-hidden">
        <table className="table-base">
          <thead>
            <tr>
              <th>Reason</th>
              <th>Technical (SMTP)</th>
              <th>Type</th>
              <th>Count</th>
              <th>% of Bounces</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i}>
                <td className="font-medium text-slate-700">{row.business_label}</td>
                <td className="text-slate-400">
                  {row.bounce_code || row.bounce_category}
                </td>
                <td>{row.bounce_type}</td>
                <td>{formatNumber(row.count)}</td>
                <td>{formatPercent(row.percent_of_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
