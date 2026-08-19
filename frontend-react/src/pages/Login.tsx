import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/lib/AuthContext'

export function Login() {
  const { user, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={redirectTo} replace />
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setInfo(null)
    setBusy(true)
    const { error } = mode === 'signin' ? await signIn(email, password) : await signUp(email, password)
    setBusy(false)
    if (error) {
      setError(error)
    } else if (mode === 'signup') {
      setInfo('Account created — check your email to confirm, then sign in.')
      setMode('signin')
    } else {
      navigate('/', { replace: true })
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <img src="/pharma_logo.svg" alt="" className="h-5 w-5" />
          </div>
          <div>
            <div className="font-display text-lg font-semibold text-text">PharmaForecast</div>
            <div className="text-xs text-text-faint">Sign in to your analytics workspace</div>
          </div>
        </div>

        <form onSubmit={submit} className="rounded-2xl border border-border bg-surface p-6 shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_12px_24px_-12px_rgba(0,0,0,0.5)]">
          <div className="mb-4 flex gap-1 rounded-lg bg-surface-2 p-1">
            <button
              type="button"
              onClick={() => { setMode('signin'); setError(null); setInfo(null) }}
              className={'flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ' + (mode === 'signin' ? 'bg-accent/15 text-accent' : 'text-text-faint hover:text-text-muted')}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setMode('signup'); setError(null); setInfo(null) }}
              className={'flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ' + (mode === 'signup' ? 'bg-accent/15 text-accent' : 'text-text-faint hover:text-text-muted')}
            >
              Create account
            </button>
          </div>

          <label className="mb-3 flex flex-col gap-1.5 text-xs text-text-muted">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text outline-none focus:border-border-strong"
              placeholder="you@example.com"
            />
          </label>

          <label className="mb-4 flex flex-col gap-1.5 text-xs text-text-muted">
            Password
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text outline-none focus:border-border-strong"
              placeholder="••••••••"
            />
          </label>

          {error && <div className="mb-3 rounded-lg border border-negative/25 bg-negative/[0.06] px-3 py-2 text-xs text-negative">{error}</div>}
          {info && <div className="mb-3 rounded-lg border border-positive/25 bg-positive/[0.06] px-3 py-2 text-xs text-positive">{info}</div>}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-accent/15 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/25 disabled:opacity-50"
          >
            {busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
