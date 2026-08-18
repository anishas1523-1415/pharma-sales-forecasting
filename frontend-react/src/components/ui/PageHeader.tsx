interface Props {
  title: string
  subtitle?: string
  connected: boolean
}

export function PageHeader({ title, subtitle, connected }: Props) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4 border-b border-border pb-5">
      <div>
        <h1 className="font-display m-0 text-[1.7rem] font-semibold tracking-tight text-text">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-text-muted">{subtitle}</p>}
      </div>
      <div
        className={
          'flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ' +
          (connected ? 'border-border text-positive' : 'border-border text-negative')
        }
      >
        <span className={'h-1.5 w-1.5 rounded-full ' + (connected ? 'bg-positive' : 'bg-negative')} />
        {connected ? 'Live' : 'Offline'}
      </div>
    </div>
  )
}
