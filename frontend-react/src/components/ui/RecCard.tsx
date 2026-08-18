import { Badge } from './Badge'

interface Props {
  signal: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW' | string
  text: string
  rationale: string
  icon?: string
  acknowledged?: boolean
  onToggleAcknowledge?: () => void
}

const ICON_COLOR: Record<string, string> = {
  high: '#F0596B',
  medium: '#F0B429',
  low: '#3ECF8E',
}

export function RecCard({ signal, priority, text, rationale, icon = '📊', acknowledged, onToggleAcknowledge }: Props) {
  const lvl = priority.toLowerCase() as 'high' | 'medium' | 'low'
  const isKnownLevel = (['high', 'medium', 'low'] as const).includes(lvl)

  return (
    <div className={'mb-3 rounded-2xl border border-border bg-surface p-5 transition-colors hover:border-border-strong ' + (acknowledged ? 'opacity-50' : '')}>
      <div className="mb-2 flex items-center gap-2.5">
        <span
          className="flex h-8 w-8 items-center justify-center rounded-lg text-sm"
          style={{ background: `${isKnownLevel ? ICON_COLOR[lvl] : '#7C6FF0'}1A` }}
        >
          {icon}
        </span>
        <span className={'text-sm font-semibold text-text' + (acknowledged ? ' line-through' : '')}>{signal}</span>
        <span className="ml-auto flex items-center gap-2">
          <Badge text={priority} level={isKnownLevel ? lvl : 'accent'} />
          {onToggleAcknowledge && (
            <button
              onClick={onToggleAcknowledge}
              title={acknowledged ? 'Mark as unread' : 'Acknowledge'}
              className={
                'flex h-6 w-6 items-center justify-center rounded-md border text-xs transition-colors ' +
                (acknowledged ? 'border-positive/40 bg-positive/10 text-positive' : 'border-border text-text-faint hover:border-border-strong hover:text-text')
              }
            >
              ✓
            </button>
          )}
        </span>
      </div>
      <div className="text-[0.86rem] leading-relaxed text-text-muted">{text}</div>
      <div className="mt-2 text-[0.76rem] text-text-faint">{rationale}</div>
    </div>
  )
}
