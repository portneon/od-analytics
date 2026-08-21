import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getInfrastructure } from '@/services/analytics'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { formatNumber, formatPercent } from '@/utils/format'

const COMPONENT_TYPES = [
  { value: 'remote_mta', label: 'Remote MTA' },
  { value: 'relay_server', label: 'Relay Server' },
  { value: 'remote_ip', label: 'Remote IP' },
]

export function InfrastructureTab() {
  const { datasetId } = useParams()
  const [componentType, setComponentType] = useState('remote_mta')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['infrastructure', datasetId, componentType],
    queryFn: () => getInfrastructure(datasetId!, componentType),
    enabled: !!datasetId,
  })

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-700">Infrastructure Components</h2>
        <select className="input w-auto text-xs" value={componentType} onChange={(e) => setComponentType(e.target.value)}>
          {COMPONENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>
      {isLoading && <LoadingState />}
      {error && <ErrorState message="Could not load infrastructure metrics." onRetry={() => refetch()} />}
      {data && data.length === 0 && <EmptyState title="No data" description="No infrastructure activity for this component type." />}
      {data && data.length > 0 && (
        <table className="table-base">
          <thead>
            <tr>
              <th>Component</th>
              <th>Emails</th>
              <th>Unique Recipients</th>
              <th>Delivery Rate</th>
              <th>Bounce Rate</th>
              <th>Failure Rate</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.component_value}>
                <td className="font-medium text-slate-700">{row.component_value}</td>
                <td>{formatNumber(row.total_emails)}</td>
                <td>{formatNumber(row.unique_recipients)}</td>
                <td>{formatPercent(row.delivery_rate)}</td>
                <td>{formatPercent(row.bounce_rate)}</td>
                <td>{formatPercent(row.failure_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
