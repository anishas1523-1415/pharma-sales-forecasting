import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/lib/AuthContext'
import { supabase } from '@/lib/supabaseClient'

export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  // Auth not configured (no Supabase env vars) — don't lock the app out,
  // just skip the gate. Keeps local dev/CI working without requiring
  // every contributor to have Supabase credentials.
  if (!supabase) return <Outlet />

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-text-faint">Loading…</div>
  }

  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return <Outlet />
}
