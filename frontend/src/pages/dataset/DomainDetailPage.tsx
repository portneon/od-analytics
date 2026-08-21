import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDomainProfile } from '@/services/analytics'
import { StatTile, rateTone } from '@/components/StatTile'
import { LoadingState, ErrorState } from '@/components/Feedback'
import { formatPercent } from '@/utils/format'

export function DomainDetailPage() {
  const { datasetId, domainId } = useParams()
  const navigate = useNavigate()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['domain-profile', datasetId, domainId],
    queryFn: () => getDomainProfile(datasetId!, domainId!),
    enabled: !!datasetId && !!domainId,
  })

  if (isLoading) return <LoadingState label="Loading domain…" />
  if (error || !data) return <ErrorState message="Could not load domain profile." onRetry={() => refetch()} />

  const m = data.metrics

  return (
    <div className="space-y-6">
      <button className="text-sm text-slate-500 hover:text-slate-700" onClick={() => navigate(-1)}>
        ← Back
      </button>
      <h1 className="text-lg font-semibold text-slate-900">{data.domain}</h1>

      {m && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label="Total Emails" value={m.total_emails} />
          <StatTile label="Unique Recipients" value={m.unique_recipients} />
          <StatTile label="Delivery Rate" value={formatPercent(m.delivery_rate)} tone={rateTone(m.delivery_rate, 'delivery')} />
          <StatTile label="Bounce Rate" value={formatPercent(m.bounce_rate)} tone={rateTone(m.bounce_rate, 'bounce')} />
        </div>
      )}
    </div>
  )
}
