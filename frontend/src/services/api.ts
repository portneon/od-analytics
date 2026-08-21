import axios from 'axios'
import { useAuthStore } from '@/store/authStore'
import type { ApiError, ApiSuccess } from '@/types/api'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
})

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  },
)

export class ApiRequestError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

export async function apiGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const res = await apiClient.get<ApiSuccess<T> | ApiError>(url, { params })
  return unwrap(res.data)
}

export async function apiGetWithMeta<T>(url: string, params?: Record<string, unknown>): Promise<{ data: T; meta: Record<string, unknown> }> {
  const res = await apiClient.get<ApiSuccess<T> | ApiError>(url, { params })
  if (!res.data.success) throw new ApiRequestError(res.data.error.code, res.data.error.message)
  return { data: res.data.data, meta: res.data.meta }
}

export async function apiPost<T>(url: string, body?: unknown, config?: Record<string, unknown>): Promise<T> {
  const res = await apiClient.post<ApiSuccess<T> | ApiError>(url, body, config)
  return unwrap(res.data)
}

function unwrap<T>(payload: ApiSuccess<T> | ApiError): T {
  if (!payload.success) throw new ApiRequestError(payload.error.code, payload.error.message)
  return payload.data
}
