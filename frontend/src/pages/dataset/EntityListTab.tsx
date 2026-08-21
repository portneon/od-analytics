import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listEntities } from '@/services/analytics'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { Pagination } from '@/components/Pagination'
import { RiskBadge } from '@/components/Badges'
import { formatDate, formatNumber, formatPercent } from '@/utils/format'

const SORT_OPTIONS = [
  { value: 'total_emails', label: 'Volume' },
  { value: 'bounce_rate', label: 'Bounce rate' },
  { value: 'failure_rate', label: 'Failure rate' },
  { value: 'delivery_rate', label: 'Delivery rate' },
]

interface Props {
  kind: 'domains' | 'recipients' | 'subjects' | 'senders'
  nameLabel: string
  clickable?: boolean
}

export function EntityListTab({ kind, nameLabel, clickable = true }: Props) {
  const { datasetId } = useParams()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('total_emails')

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['entities', kind, datasetId, page, sortBy],
    queryFn: () => listEntities(datasetId!, kind, { page, page_size: 25, sort_by: sortBy }),
    enabled: !!datasetId,
  })

  if (isLoading) return <LoadingState label={`Loading ${kind}…`} />
  if (error) return <ErrorState message={`Could not load ${kind}.`} onRetry={() => refetch()} />
  if (!data || data.items.length === 0) return <EmptyState title={`No ${kind} found`} description="No activity for this dataset yet." />

  const hasRisk = kind === 'recipients'

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-700">{nameLabel}</h2>
        <select className="input w-auto text-xs" value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1) }}>
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              Sort by {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>{nameLabel.replace(/s$/, '')}</th>
              <th>Total</th>
              <th>Delivery Rate</th>
              <th>Bounce Rate</th>
              <th>Failure Rate</th>
              {hasRisk && <th>Risk</th>}
              {hasRisk && <th>Last Seen</th>}
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr
                key={item.id}
                className={clickable ? 'cursor-pointer' : ''}
                onClick={clickable ? () => navigate(`../${kind}/${item.id}`, { relative: 'path' }) : undefined}
              >
                <td className="font-medium text-slate-700">{item.name}</td>
                <td>{formatNumber(item.total_emails)}</td>
                <td>{formatPercent(item.delivery_rate)}</td>
                <td>{formatPercent(item.bounce_rate)}</td>
                <td>{formatPercent(item.failure_rate)}</td>
                {hasRisk && <td>{item.risk_level ? <RiskBadge level={item.risk_level} /> : '—'}</td>}
                {hasRisk && <td className="text-slate-400">{formatDate(item.last_seen)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination meta={data.meta} onPageChange={setPage} />
    </div>
  )
}
