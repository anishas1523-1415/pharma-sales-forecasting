import type { ReactNode } from 'react'

interface SelectProps {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}

export function Select({ label, value, onChange, options }: SelectProps) {
  return (
    <label className="flex flex-col gap-1.5 text-xs text-text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-sm text-text outline-none transition-colors focus:border-border-strong"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  )
}

interface SliderProps {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  suffix?: string
}

export function Slider({ label, value, onChange, min, max, step = 1, suffix = '' }: SliderProps) {
  return (
    <label className="flex flex-col gap-1.5 text-xs text-text-muted">
      <span className="flex items-center justify-between">
        <span>{label}</span>
        <span className="rounded-md bg-surface-2 px-2 py-0.5 font-mono text-[0.72rem] text-text">{value}{suffix}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full cursor-pointer"
      />
    </label>
  )
}

interface CheckboxProps {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}

export function Checkbox({ label, checked, onChange }: CheckboxProps) {
  return (
    <label className="flex items-center gap-2 text-xs text-text-muted">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-border-strong accent-[#7C6FF0]"
      />
      {label}
    </label>
  )
}

export function ControlBar({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end gap-5 rounded-xl border border-border bg-surface/60 p-4">
      {children}
    </div>
  )
}
