type Level = 'high' | 'medium' | 'low' | 'accent'

const LEVEL_STYLES: Record<Level, string> = {
  high: 'bg-negative/10 text-negative border-negative/25',
  medium: 'bg-warning/10 text-warning border-warning/25',
  low: 'bg-positive/10 text-positive border-positive/25',
  accent: 'bg-accent/10 text-accent border-accent/25',
}

export function Badge({ text, level = 'accent' }: { text: string; level?: Level }) {
  return (
    <span className={`inline-block rounded-md border px-2 py-0.5 text-[0.68rem] font-medium uppercase tracking-wide ${LEVEL_STYLES[level]}`}>
      {text}
    </span>
  )
}
