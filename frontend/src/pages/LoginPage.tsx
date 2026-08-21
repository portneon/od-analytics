import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '@/services/auth'
import { useAuthStore } from '@/store/authStore'
import { ApiRequestError } from '@/services/api'

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const setSession = useAuthStore((s) => s.setSession)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result =
        mode === 'login' ? await login(email, password) : await register({ tenant_name: tenantName, name, email, password })
      setSession(result.access_token, result.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-slate-900">Email Intelligence Platform</h1>
          <p className="mt-1 text-sm text-slate-400">Executive email analytics</p>
        </div>
        <div className="card p-6">
          <div className="mb-4 flex gap-1 rounded-md bg-slate-100 p-1 text-sm">
            <button
              className={`flex-1 rounded px-2 py-1.5 font-medium ${mode === 'login' ? 'bg-white shadow-sm' : 'text-slate-500'}`}
              onClick={() => setMode('login')}
              type="button"
            >
              Sign in
            </button>
            <button
              className={`flex-1 rounded px-2 py-1.5 font-medium ${mode === 'register' ? 'bg-white shadow-sm' : 'text-slate-500'}`}
              onClick={() => setMode('register')}
              type="button"
            >
              Create organization
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === 'register' && (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Organization name</label>
                  <input className="input" required value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600">Your name</label>
                  <input className="input" required value={name} onChange={(e) => setName(e.target.value)} />
                </div>
              </>
            )}
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Email</label>
              <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Password</label>
              <input className="input" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button className="btn-primary w-full" disabled={loading} type="submit">
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create organization & sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
