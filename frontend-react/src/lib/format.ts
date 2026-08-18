// Ported from frontend/utils/formatting.py — colors recalibrated to the
// muted premium palette (see index.css @theme) instead of the original
// neon set.

export function fmtNum(val: number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) return 'N/A'
  return val.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function fmtPct(val: number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) return 'N/A'
  return `${val.toFixed(decimals)}%`
}

export function fmtTrend(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—'
  const arrow = val >= 0 ? '▲' : '▼'
  return `${arrow} ${Math.abs(val).toFixed(2)}%`
}

export function mapeColor(mape: number | null | undefined): string {
  if (mape === null || mape === undefined) return '#98989F'
  if (mape <= 20) return '#3ECF8E'
  if (mape <= 30) return '#F0B429'
  return '#E8836C'
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#F0596B',
  medium: '#E8836C',
  low: '#3ECF8E',
  normal: '#6EA8D8',
  moderate: '#F0B429',
  anomaly: '#E8836C',
}
export function severityColor(severity: string): string {
  return SEVERITY_COLORS[severity?.toLowerCase()] ?? '#98989F'
}

const PRIORITY_COLORS: Record<string, string> = {
  HIGH: '#F0596B',
  MEDIUM: '#F0B429',
  LOW: '#3ECF8E',
}
export function priorityColor(priority: string): string {
  return PRIORITY_COLORS[priority?.toUpperCase()] ?? '#98989F'
}
