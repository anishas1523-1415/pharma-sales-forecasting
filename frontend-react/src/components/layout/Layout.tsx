import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { useHealth, useModels } from '@/lib/queries'
import { API_BASE_URL } from '@/lib/apiClient'
import { useAuth } from '@/lib/AuthContext'
import { supabase } from '@/lib/supabaseClient'
import { CommandPalette } from './CommandPalette'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '◆' },
  { to: '/forecast', label: 'Forecast Explorer', icon: '◇' },
  { to: '/anomalies', label: 'Anomaly Detection', icon: '▲' },
  { to: '/whatif', label: 'What-If Simulator', icon: '◈' },
  { to: '/recommendations', label: 'Recommendations', icon: '○' },
  { to: '/models', label: 'Model Comparison', icon: '▣' },
]

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent)

export function Layout() {
  const { data: isConnected } = useHealth()
  const { data: models } = useModels()
  const { user, signOut } = useAuth()
  const [showStatus, setShowStatus] = useState(false)
  const location = useLocation()
  const current = NAV_ITEMS.find((n) => (n.to === '/' ? location.pathname === '/' : location.pathname.startsWith(n.to)))

  return (
    <div className="flex min-h-screen">
      <CommandPalette />

      <aside className="flex w-60 shrink-0 flex-col border-r border-border px-4 py-6">
        <div className="mb-8 flex items-center gap-2.5 px-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <img src="/pharma_logo.svg" alt="" className="h-4 w-4" />
          </div>
          <div>
            <div className="font-display text-[0.92rem] font-semibold leading-none text-text">PharmaForecast</div>
            <div className="text-[0.65rem] text-text-faint">Analytics Platform</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                'flex items-center gap-2.5 rounded-lg px-3 py-2 text-[0.84rem] font-medium transition-colors ' +
                (isActive ? 'bg-accent/10 text-accent' : 'text-text-muted hover:bg-surface hover:text-text')
              }
            >
              <span className="text-xs opacity-70">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="relative mt-4 border-t border-border pt-3">
          <button
            onClick={() => setShowStatus((v) => !v)}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-text-muted transition-colors hover:bg-surface"
          >
            <span className={'h-1.5 w-1.5 rounded-full ' + (isConnected ? 'bg-positive' : 'bg-negative')} />
            {isConnected ? 'API Online' : 'API Offline'}
          </button>
          {showStatus && (
            <div className="absolute bottom-full left-0 mb-2 w-72 rounded-xl border border-border bg-surface-2 p-3 text-xs shadow-2xl">
              <div className="mb-1 text-text-faint">Backend URL</div>
              <div className="mb-2 truncate rounded bg-black/30 px-2 py-1 font-mono text-text">{API_BASE_URL}</div>
              <div className="mb-1 text-text-faint">Models Available</div>
              <div className="mb-2 text-text">{models?.models?.length ?? 0} / 5</div>
              <div className="mb-1 text-text-faint">Categories Loaded</div>
              <div className="text-text">{models?.categories?.length ?? 0} / 8</div>
              {supabase && user && (
                <>
                  <div className="mb-1 mt-2 border-t border-border pt-2 text-text-faint">Signed in as</div>
                  <div className="mb-2 truncate text-text">{user.email}</div>
                  <button
                    onClick={() => signOut()}
                    className="w-full rounded-md border border-border px-2 py-1 text-left text-negative transition-colors hover:border-negative/40 hover:bg-negative/10"
                  >
                    Sign out
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-8">
          <div className="flex items-center gap-2 text-xs text-text-faint">
            <span>{current?.icon}</span>
            <span className="text-text-muted">{current?.label ?? 'PharmaForecast'}</span>
          </div>
          <button
            onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-text-faint transition-colors hover:border-border-strong hover:text-text-muted"
          >
            <span>Jump to…</span>
            <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[0.65rem]">{isMac ? '⌘' : 'Ctrl'} K</kbd>
          </button>
        </header>

        <main className="min-w-0 flex-1 overflow-x-hidden px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
