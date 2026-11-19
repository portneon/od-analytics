import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useDataset } from '@/hooks/useDataset'
import { deleteDataset } from '@/services/datasets'
import { DatasetStatusBadge } from '@/components/Badges'
import { LoadingState, ErrorState } from '@/components/Feedback'
import { formatDate, formatNumber } from '@/utils/format'
import { channelLabels } from '@/utils/channel'

const TABS = [
  { to: '', label: 'Overview', end: true },
  { to: 'analytics', label: 'Analytics' },
  { to: 'recipients', label: 'Recipients' },
  { to: 'domains', label: 'Domains', requires: 'hasDomains' as const },
  { to: 'subjects', label: 'Subjects' },
  { to: 'senders', label: 'Senders' },
  { to: 'bounces', label: 'Bounces', requires: 'hasBounceClassification' as const },
  { to: 'infrastructure', label: 'Infrastructure', requires: 'hasInfrastructure' as const },
  { to: 'anomalies', label: 'Anomalies' },
  { to: 'events', label: 'Events' },
  { to: 'ask', label: 'AI Analyst' },
  { to: 'reports', label: 'Reports' },
]

export function DatasetLayout() {
  const { datasetId } = useParams()
  const { data: dataset, isLoading, error, refetch } = useDataset(datasetId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => deleteDataset(datasetId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      navigate('/datasets', { replace: true })
    },
  })

  function handleDelete() {
    if (window.confirm(`Delete "${dataset?.name}"? This permanently removes all its data and cannot be undone.`)) {
      deleteMutation.mutate()
    }
  }

  if (isLoading) return <LoadingState label="Loading dataset…" />
  if (error || !dataset) return <ErrorState message="Could not load this dataset." onRetry={() => refetch()} />

  const isProcessing = dataset.status === 'UPLOADING' || dataset.status === 'QUEUED' || dataset.status === 'PROCESSING'
  const labels = channelLabels(dataset.source)
  const tabs = TABS.filter((tab) => !tab.requires || labels[tab.requires])

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-slate-900">{dataset.name}</h1>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{labels.badge}</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              {dataset.file_name} · {formatDate(dataset.date_start)} – {formatDate(dataset.date_end)} · {formatNumber(dataset.row_count)} rows
            </p>
          </div>
          <div className="flex items-center gap-3">
            <DatasetStatusBadge status={dataset.status} />
            <button
              className="btn-secondary text-xs text-red-600 hover:bg-red-50"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete dataset'}
            </button>
          </div>
        </div>
        {deleteMutation.isError && (
          <p className="mt-2 text-xs text-red-600">
            Delete failed: {(deleteMutation.error as Error)?.message ?? 'Unknown error'}
          </p>
        )}
        <nav className="mt-4 flex gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <div className="flex-1 overflow-auto p-6">
        {isProcessing ? (
          <div className="card p-8 text-center">
            <p className="text-sm font-medium text-slate-700">Processing {formatNumber(dataset.row_count)} events…</p>
            <p className="mt-1 text-xs text-slate-400">This page will update automatically once processing completes.</p>
          </div>
        ) : (
          <Outlet context={{ dataset }} />
        )}
      </div>
    </div>
  )
}
