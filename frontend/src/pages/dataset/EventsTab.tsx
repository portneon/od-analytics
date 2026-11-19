import { useState } from 'react'
import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listEvents, getEvent } from '@/services/analytics'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { Pagination } from '@/components/Pagination'
import { StatusBadge } from '@/components/Badges'
import { formatDateTime } from '@/utils/format'
import { channelLabels } from '@/utils/channel'
import type { Dataset } from '@/types/api'

const STATUS_OPTIONS = ['', 'SUCCESS', 'HARD_BOUNCE', 'SOFT_BOUNCE', 'FAILED', 'DEFERRED', 'UNKNOWN']

export function EventsTab() {
  const { datasetId } = useParams()
  const { dataset } = useOutletContext<{ dataset: Dataset }>()
  const labels = channelLabels(dataset.source)
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['events', datasetId, page, status],
    queryFn: () => listEvents(datasetId!, { page, page_size: 25, status: status || undefined }),
    enabled: !!datasetId,
  })

  return (
    <div className="space-y-4">
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-700">{labels.eventsHeading}</h2>
          <select
            className="input w-auto text-xs"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s || 'All statuses'}
              </option>
            ))}
          </select>
        </div>

        {isLoading && <LoadingState label="Loading events…" />}
        {error && <ErrorState message="Could not load events." onRetry={() => refetch()} />}
        {data && data.items.length === 0 && <EmptyState title="No events match these filters" />}

        {data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Sender</th>
                  <th>Recipient</th>
                  <th>Status</th>
                  <th>Bounce Category</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id} className="cursor-pointer" onClick={() => setSelectedEventId(e.id)}>
                    <td>{formatDateTime(e.event_time)}</td>
                    <td className="text-slate-500">{e.sender_email ?? '—'}</td>
                    <td className="text-slate-700">{e.recipient_email ?? '—'}</td>
                    <td>
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="text-slate-400">{e.bounce_category !== 'NONE' ? e.bounce_category : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination meta={data.meta} onPageChange={setPage} />}
      </div>

      {selectedEventId && (
        <EventDetailPanel datasetId={datasetId!} eventId={selectedEventId} isWhatsapp={!labels.hasInfrastructure} onClose={() => setSelectedEventId(null)} />
      )}
    </div>
  )
}

function EventDetailPanel({
  datasetId,
  eventId,
  isWhatsapp,
  onClose,
}: {
  datasetId: string
  eventId: string
  isWhatsapp: boolean
  onClose: () => void
}) {
  const { data, isLoading } = useQuery({ queryKey: ['event', datasetId, eventId], queryFn: () => getEvent(datasetId, eventId) })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-lg bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Event Detail</h3>
          <button className="text-slate-400 hover:text-slate-600" onClick={onClose}>
            ✕
          </button>
        </div>
        {isLoading && <LoadingState />}
        {data && (
          <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
            {(
              [
                ['Timestamp', formatDateTime(data.event_time)],
                ['Sender', data.sender_email ?? '—'],
                ['Recipient', data.recipient_email ?? '—'],
                ['Status', data.status],
                !isWhatsapp && ['Bounce Type', data.bounce_type],
                !isWhatsapp && ['SMTP Code', data.bounce_code ?? '—'],
                !isWhatsapp && ['Bounce Category', data.bounce_category],
                ['Bounce Reason', data.bounce_reason ?? '—'],
                !isWhatsapp && ['Remote IP', data.remote_ip ?? '—'],
                !isWhatsapp && ['Remote MTA', data.remote_mta ?? '—'],
                !isWhatsapp && ['Relay Server', data.relay_server ?? '—'],
                ['Mail Reference', data.mail_reference ?? '—'],
                ['Processing Time', data.processing_time ? `${data.processing_time} ms` : '—'],
                ['Retry', data.is_retry ? `Yes (${data.retry_count})` : 'No'],
                ['Duplicate', data.is_duplicate ? 'Yes' : 'No'],
              ].filter(Boolean) as [string, string][]
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
                <dd className="text-slate-800">{value}</dd>
              </div>
            ))}
            {data.raw_record && (
              <div className="col-span-full">
                <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Raw Record</dt>
                <dd>
                  <pre className="overflow-x-auto rounded bg-slate-50 p-3 text-xs text-slate-600">{JSON.stringify(data.raw_record, null, 2)}</pre>
                </dd>
              </div>
            )}
          </dl>
        )}
      </div>
    </div>
  )
}
