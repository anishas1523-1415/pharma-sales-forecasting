import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { CATEGORIES, CAT_NAMES } from '@/lib/constants'

const PAGES = [
  { to: '/', label: 'Dashboard', icon: '◆' },
  { to: '/forecast', label: 'Forecast Explorer', icon: '◇' },
  { to: '/anomalies', label: 'Anomaly Detection', icon: '▲' },
  { to: '/whatif', label: 'What-If Simulator', icon: '◈' },
  { to: '/recommendations', label: 'Recommendations', icon: '○' },
  { to: '/models', label: 'Model Comparison', icon: '▣' },
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const go = (to: string) => {
    navigate(to)
    setOpen(false)
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-border-strong bg-surface-2 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="Command palette" className="flex flex-col">
          <Command.Input
            autoFocus
            placeholder="Jump to a page or category…"
            className="w-full border-b border-border bg-transparent px-4 py-3.5 text-sm text-text outline-none placeholder:text-text-faint"
          />
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-text-faint">No matches.</Command.Empty>

            <Command.Group heading="Pages" className="px-2 pb-1 pt-2 text-[0.68rem] font-medium uppercase tracking-wider text-text-faint">
              {PAGES.map((p) => (
                <Command.Item
                  key={p.to}
                  value={p.label}
                  onSelect={() => go(p.to)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text data-[selected=true]:bg-accent/10 data-[selected=true]:text-accent"
                >
                  <span className="text-xs opacity-70">{p.icon}</span>
                  {p.label}
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Categories — jump to Forecast Explorer" className="px-2 pb-1 pt-3 text-[0.68rem] font-medium uppercase tracking-wider text-text-faint">
              {CATEGORIES.map((cat) => (
                <Command.Item
                  key={cat}
                  value={`${cat} ${CAT_NAMES[cat]}`}
                  onSelect={() => go(`/forecast?category=${cat}`)}
                  className="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text data-[selected=true]:bg-accent/10 data-[selected=true]:text-accent"
                >
                  <span className="font-mono text-xs text-text-muted">{cat}</span>
                  <span className="text-text-muted">{CAT_NAMES[cat]}</span>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  )
}
