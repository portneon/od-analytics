import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteDataset, listDatasets, uploadDatasets } from '@/services/datasets'
import { DatasetStatusBadge } from '@/components/Badges'
import { LoadingState, ErrorState, EmptyState } from '@/components/Feedback'
import { formatDate, formatNumber } from '@/utils/format'

export function DatasetsPage() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets, refetchInterval: 5000 })
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [uploadCount, setUploadCount] = useState<number>(0)

  const uploadMutation = useMutation({
    mutationFn: ({ files }: { files: File[] }) => uploadDatasets(files, setUploadProgress),
    onSuccess: (result: any) => {
      setUploadProgress(null)
      queryClient.invalidateQueries({ queryKey: ['datasets'] })
      if (result && result.dataset_id) {
        navigate(`/datasets/${result.dataset_id}`)
      }
    },
    onError: () => setUploadProgress(null),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteDataset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datasets'] }),
  })

  function handleDelete(e: React.MouseEvent, id: string, name: string) {
    e.stopPropagation()
    if (window.confirm(`Delete "${name}"? This permanently removes all its data and cannot be undone.`)) {
      deleteMutation.mutate(id)
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files ? Array.from(e.target.files) : []
    if (files.length === 0) return
    setUploadCount(files.length)
    uploadMutation.mutate({ files })
    e.target.value = ''
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Datasets</h1>
          <p className="text-sm text-slate-400">Upload one or multiple Zoho Mail export CSVs to generate executive analytics.</p>
        </div>
        <div>
          <input ref={fileInputRef} type="file" accept=".csv" multiple className="hidden" onChange={handleFileChange} />
          <button className="btn-primary" onClick={() => fileInputRef.current?.click()} disabled={uploadMutation.isPending}>
            {uploadMutation.isPending ? `Uploading ${uploadCount} file${uploadCount > 1 ? 's' : ''}… ${uploadProgress ?? 0}%` : 'Upload CSV(s)'}
          </button>
        </div>
      </div>

      {uploadMutation.isError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Upload failed: {(uploadMutation.error as Error)?.message ?? 'Unknown error'}
        </div>
      )}

      {deleteMutation.isError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Delete failed: {(deleteMutation.error as Error)?.message ?? 'Unknown error'}
        </div>
      )}

      {isLoading && <LoadingState label="Loading datasets…" />}
      {error && <ErrorState message="Could not load datasets." onRetry={() => refetch()} />}
      {data && data.length === 0 && (
        <EmptyState
          title="No datasets yet"
          description="Upload your first Zoho Mail CSV export to see delivery analytics, bounce analysis, and executive insights."
        />
      )}

      {data && data.length > 0 && (
        <div className="card overflow-hidden">
          <table className="table-base">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Period</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.id} className="cursor-pointer" onClick={() => navigate(`/datasets/${d.id}`)}>
                  <td className="font-medium text-slate-800">{d.name}</td>
                  <td>
                    <DatasetStatusBadge status={d.status} />
                  </td>
                  <td>{formatNumber(d.row_count)}</td>
                  <td>
                    {formatDate(d.date_start)} – {formatDate(d.date_end)}
                  </td>
                  <td className="text-slate-400">{formatDate(d.created_at)}</td>
                  <td>
                    <button
                      className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50"
                      onClick={(e) => handleDelete(e, d.id, d.name)}
                      disabled={deleteMutation.isPending && deleteMutation.variables === d.id}
                    >
                      {deleteMutation.isPending && deleteMutation.variables === d.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
