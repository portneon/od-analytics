import { useParams, useNavigate, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDomainProfile } from '@/services/analytics'
import { StatTile, rateTone } from '@/components/StatTile'
import { StatusBadge } from '@/components/Badges'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { formatDateTime, formatNumber, formatPercent } from '@/utils/format'
import { channelLabels } from '@/utils/channel'
import type { Dataset } from '@/types/api'

export function DomainDetailPage() {
  const { datasetId, domainId } = useParams()
  const navigate = useNavigate()
  const { dataset } = useOutletContext<{ dataset: Dataset }>()
  const labels = channelLabels(dataset.source)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['domain-profile', datasetId, domainId],
    queryFn: () => getDomainProfile(datasetId!, domainId!),
    enabled: !!datasetId && !!domainId,
  })

  if (isLoading) return <LoadingState label={`Loading ${labels.domainLabel.toLowerCase()}…`} />
  if (error || !data) return <ErrorState message={`Could not load ${labels.domainLabel.toLowerCase()} profile.`} onRetry={() => refetch()} />

  const m = data.metrics

  return (
    <div className="space-y-6">
      <button className="text-sm text-slate-500 hover:text-slate-700" onClick={() => navigate(-1)}>
        ← Back
      </button>
      <h1 className="text-lg font-semibold text-slate-900">{data.domain}</h1>

      {m && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label={`Total ${labels.unitPlural}`} value={formatNumber(m.total_emails)} />
          <StatTile label="Unique Recipients" value={formatNumber(m.unique_recipients)} />
          <StatTile label="Delivery Rate" value={formatPercent(m.delivery_rate)} tone={rateTone(m.delivery_rate, 'delivery')} />
          <StatTile label="Failure Rate" value={formatPercent(m.failure_rate)} tone={rateTone(m.failure_rate, 'failure')} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Message Categories</h2>
          {data.category_breakdown.length === 0 ? (
            <EmptyState title="No categorized messages" />
          ) : (
            <table className="table-base">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Count</th>
                  <th>Share</th>
                </tr>
              </thead>
              <tbody>
                {data.category_breakdown.map((c) => (
                  <tr key={c.category}>
                    <td className="font-medium text-slate-700">{c.category}</td>
                    <td>{formatNumber(c.count)}</td>
                    <td className="text-slate-400">{c.percent}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card overflow-hidden">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Top Recipients</h2>
          {data.top_recipients.length === 0 ? (
            <EmptyState title="No recipients found" />
          ) : (
            <table className="table-base">
              <thead>
                <tr>
                  <th>{labels.contact}</th>
                  <th>Total</th>
                  <th>Failure Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.top_recipients.map((r) => (
                  <tr key={r.id} className="cursor-pointer" onClick={() => navigate(`../../recipients/${r.id}`, { relative: 'path' })}>
                    <td className="font-medium text-slate-700">{r.name}</td>
                    <td>{formatNumber(r.total_emails)}</td>
                    <td className={r.failure_rate > 0 ? 'text-red-600' : 'text-slate-400'}>{r.failure_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">{labels.eventsHeading}</h2>
        {data.timeline.length === 0 ? (
          <EmptyState title={`No ${labels.unitLower} found`} />
        ) : (
          <div className="max-h-[480px] overflow-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Recipient</th>
                  <th>Category</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.timeline.map((e) => (
                  <tr key={e.id}>
                    <td>{formatDateTime(e.event_time)}</td>
                    <td className="text-slate-700">{e.recipient_email ?? '—'}</td>
                    <td className="text-slate-500">{e.subject ?? '—'}</td>
                    <td>
                      <StatusBadge status={e.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
