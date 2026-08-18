interface Props {
  icon: string
  label: string
  value: string
  delta?: string
  accent?: string
}

export function KpiCard({ icon, label, value, delta, accent = '#7C6FF0' }: Props) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_12px_24px_-12px_rgba(0,0,0,0.5)] transition-colors hover:border-border-strong">
      <div
        className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg text-base"
        style={{ background: `${accent}1A`, color: accent }}
      >
        {icon}
      </div>
      <div className="text-[0.72rem] font-medium uppercase tracking-wider text-text-faint">{label}</div>
      <div className="font-display mt-1 text-[1.85rem] font-semibold leading-tight text-text">{value}</div>
      {delta && <div className="mt-1 text-[0.78rem]">{delta}</div>}
    </div>
  )
}
