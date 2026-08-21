import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getRecipientProfile } from '@/services/analytics'
import { StatTile, rateTone } from '@/components/StatTile'
import { RiskBadge, StatusBadge } from '@/components/Badges'
import { LoadingState, ErrorState } from '@/components/Feedback'
import { formatDateTime, formatPercent } from '@/utils/format'

export function RecipientDetailPage() {
  const { datasetId, recipientId } = useParams()
  const navigate = useNavigate()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['recipient-profile', datasetId, recipientId],
    queryFn: () => getRecipientProfile(datasetId!, recipientId!),
    enabled: !!datasetId && !!recipientId,
  })

  if (isLoading) return <LoadingState label="Loading recipient…" />
  if (error || !data) return <ErrorState message="Could not load recipient profile." onRetry={() => refetch()} />

  const m = data.metrics

  return (
    <div className="space-y-6">
      <button className="text-sm text-slate-500 hover:text-slate-700" onClick={() => navigate(-1)}>
        ← Back
      </button>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">{data.email}</h1>
          <p className="text-sm text-slate-400">{data.domain}</p>
        </div>
        {m && <RiskBadge level={m.risk_level} />}
      </div>

      {m && (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="Total Emails" value={m.total_emails} />
            <StatTile label="Delivery Rate" value={formatPercent(m.delivery_rate)} tone={rateTone(m.delivery_rate, 'delivery')} />
            <StatTile label="Bounce Rate" value={formatPercent(m.bounce_rate)} tone={rateTone(m.bounce_rate, 'bounce')} />
            <StatTile label="Risk Score" value={`${m.risk_score} / 100`} tone={rateTone(m.risk_score, 'bounce')} />
          </div>

          <div className="card p-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-700">Why this risk score</h2>
            {m.risk_reasons.length === 0 ? (
              <p className="text-sm text-slate-400">No specific risk factors identified.</p>
            ) : (
              <ul className="list-inside list-disc space-y-1 text-sm text-slate-600">
                {m.risk_reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      <div className="card overflow-hidden">
        <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">Event Timeline</h2>
        <table className="table-base">
          <thead>
            <tr>
              <th>Date</th>
              <th>Status</th>
              <th>Bounce Category</th>
            </tr>
          </thead>
          <tbody>
            {data.timeline.map((e) => (
              <tr key={e.id}>
                <td>{formatDateTime(e.event_time)}</td>
                <td>
                  <StatusBadge status={e.status} />
                </td>
                <td className="text-slate-500">{e.bounce_category && e.bounce_category !== 'NONE' ? e.bounce_category : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
