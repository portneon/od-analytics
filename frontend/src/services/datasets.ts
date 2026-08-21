import { apiClient, apiGet } from './api'
import type { ApiSuccess, Dataset, DataQualityReport } from '@/types/api'

export function listDatasets() {
  return apiGet<Dataset[]>('/datasets')
}

export function getDataset(id: string) {
  return apiGet<Dataset>(`/datasets/${id}`)
}

export function getDatasetStatus(id: string) {
  return apiGet<{ dataset_id: string; status: Dataset['status']; row_count: number | null }>(`/datasets/${id}/status`)
}

export function getDatasetQuality(id: string) {
  return apiGet<DataQualityReport>(`/datasets/${id}/quality`)
}

export async function deleteDataset(id: string) {
  const res = await apiClient.delete<ApiSuccess<{ dataset_id: string; deleted: boolean }>>(`/datasets/${id}`)
  if (!res.data.success) throw new Error('Delete failed')
  return res.data.data
}

export async function uploadDataset(file: File, name: string, onProgress?: (pct: number) => void) {
  const form = new FormData()
  form.append('file', file)
  if (name) form.append('name', name)
  const res = await apiClient.post<ApiSuccess<{ dataset_id: string; job_id: string; status: string; task_id: string }>>(
    '/datasets/upload',
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100))
      },
    },
  )
  if (!res.data.success) throw new Error('Upload failed')
  return res.data.data
}

export async function uploadDatasets(files: File[], onProgress?: (pct: number) => void) {
  if (files.length === 0) throw new Error('No files provided')
  if (files.length === 1) {
    return uploadDataset(files[0], files[0].name.replace(/\.csv$/i, ''), onProgress)
  }
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const res = await apiClient.post<ApiSuccess<{ dataset_id?: string; datasets?: { dataset_id: string }[]; count?: number }>>(
    '/datasets/upload',
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100))
      },
    },
  )
  if (!res.data.success) throw new Error('Upload failed')
  return res.data.data
}

export async function generateReport(datasetId: string, format: 'pdf' | 'csv'): Promise<Blob> {
  const res = await apiClient.post(`/datasets/${datasetId}/reports`, undefined, {
    params: { format },
    responseType: 'blob',
  })
  return res.data as Blob
}
