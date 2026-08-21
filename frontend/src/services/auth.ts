import { apiPost } from './api'
import type { User } from '@/types/api'

interface AuthResponse {
  access_token: string
  token_type: string
  user: User
  tenant?: { id: string; name: string; slug: string }
}

export function login(email: string, password: string) {
  return apiPost<AuthResponse>('/auth/login', { email, password })
}

export function register(payload: { tenant_name: string; name: string; email: string; password: string }) {
  return apiPost<AuthResponse>('/auth/register', payload)
}
