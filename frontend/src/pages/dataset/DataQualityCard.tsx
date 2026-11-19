import { useParams, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDatasetQuality } from '@/services/datasets'
import { formatNumber } from '@/utils/format'
import { NotAvailable } from '@/components/Feedback'
import { channelLabels } from '@/utils/channel'
import type { Dataset } from '@/types/api'

export function DataQualityCard() {
  const { datasetId } = useParams()
  const { dataset } = useOutletContext<{ dataset: Dataset }>()
  const labels = channelLabels(dataset.source)
  const { data } = useQuery({
    queryKey: ['quality', datasetId],
    queryFn: () => getDatasetQuality(datasetId!),
    enabled: !!datasetId,
  })

  if (!data || data.rows === 0) return null

  const hasIssues = data.invalid_rows > 0 || data.duplicate_rows > 0 || data.malformed_emails > 0
  const malformedLabel = labels.hasInfrastructure ? 'Malformed emails' : 'Malformed phone numbers'

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Data Quality</h2>
        <span className="text-xs text-slate-400">
          {formatNumber(data.valid_rows)} valid {labels.unitLower} from {formatNumber(data.rows)} rows
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <QualityStat label="Invalid rows" value={data.invalid_rows} warn={data.invalid_rows > 0} />
        <QualityStat label="Duplicates" value={data.duplicate_rows} warn={data.duplicate_rows > 0} />
        <QualityStat label={malformedLabel} value={data.malformed_emails} warn={data.malformed_emails > 0} />
        <QualityStat label="Missing timestamps" value={data.missing_timestamps} warn={data.missing_timestamps > 0} />
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
        <span>
          Open tracking: {data.missing_open_data ? <NotAvailable /> : 'Available'}
        </span>
        <span>
          Click tracking: {data.missing_click_data ? <NotAvailable /> : 'Available'}
        </span>
      </div>
      {hasIssues && data.issue_samples.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-400">
            View sample issues ({data.issue_samples.length})
          </summary>
          <div className="mt-2 max-h-48 overflow-auto rounded border border-slate-100">
            <table className="table-base">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Field</th>
                  <th>Issue</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {data.issue_samples.map((issue, i) => (
                  <tr key={i}>
                    <td>{issue.row_index}</td>
                    <td>{issue.field}</td>
                    <td>{issue.issue.replace(/_/g, ' ')}</td>
                    <td className="text-slate-400">{issue.raw_value ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}

function QualityStat({ label, value, warn }: { label: string; value: number; warn: boolean }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className={`text-lg font-semibold ${warn ? 'text-amber-600' : 'text-slate-800'}`}>{formatNumber(value)}</p>
    </div>
  )
}
