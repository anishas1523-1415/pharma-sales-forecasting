// Port of frontend/pages/3_🚨_Anomaly_Detection.py

import { useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { ControlBar, Select } from '@/components/ui/Controls'
import { useHealth, useAnomalies } from '@/lib/queries'
import { CATEGORIES, VALIDATION_MODELS, MODEL_LABELS } from '@/lib/constants'
import { fmtNum, severityColor } from '@/lib/format'
import { anomalyChart, severityDonut } from '@/lib/charts'
import type { Category, ModelType } from '@/types/api'

const SEVERITY_OPTIONS = [
  { key: 'normal', label: '🟢 Normal (<10%)' },
  { key: 'moderate', label: '🟡 Moderate (10–25%)' },
  { key: 'medium', label: '🟠 Medium (25–50%)' },
  { key: 'high', label: '🔴 High (>50%)' },
]

export function AnomalyDetection() {
  const { data: isConnected } = useHealth()
  const [category, setCategory] = useState<Category>('M01AB')
  const [model, setModel] = useState<ModelType>('arima')
  const [severityFilter, setSeverityFilter] = useState<string[]>(['moderate', 'medium', 'high'])

  const { data, isLoading } = useAnomalies(category, model, !!isConnected)

  if (!isConnected) {
    return (
      <div>
        <PageHeader title="🚨 Anomaly Detection" subtitle="Identify demand deviations — compare ML forecast vs actual historical sales" connected={false} />
        <OfflineBanner />
      </div>
    )
  }

  const results = data?.results ?? []
  const high = results.filter((r) => r.severity === 'high').length
  const medium = results.filter((r) => r.severity === 'medium').length

  const filtered = severityFilter.length
    ? results.filter((r) => {
        const allowedSev = new Set<string>(severityFilter.filter((s) => s === 'medium' || s === 'high'))
        const allowedStat = new Set<string>(severityFilter.filter((s) => s === 'normal' || s === 'moderate'))
        return allowedSev.has(r.severity) || allowedStat.has(r.status)
      })
    : results

  const { data: chartData, layout } = anomalyChart(results, category, model)
  const { data: donutData, layout: donutLayout } = severityDonut(results)

  return (
    <div>
      <PageHeader title="🚨 Anomaly Detection" subtitle="Identify demand deviations — compare ML forecast vs actual historical sales" connected />

      <ControlBar>
        <Select label="Drug Category" value={category} onChange={(v) => setCategory(v as Category)}
          options={CATEGORIES.map((c) => ({ value: c, label: c }))} />
        <Select label="Model" value={model} onChange={(v) => setModel(v as ModelType)}
          options={VALIDATION_MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
        <div className="flex flex-wrap gap-1.5">
          <span className="mb-1 block w-full text-xs text-text-muted">Filter by Severity</span>
          {SEVERITY_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSeverityFilter((cur) => cur.includes(opt.key) ? cur.filter((k) => k !== opt.key) : [...cur, opt.key])}
              className={
                'rounded-full border px-3 py-1 text-xs font-semibold ' +
                (severityFilter.includes(opt.key) ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted')
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </ControlBar>

      {isLoading ? (
        <div className="rounded-xl border border-border bg-surface/60 p-6 text-sm text-text-muted">Detecting anomalies…</div>
      ) : !data ? (
        <div className="rounded-xl border border-negative/30 bg-negative/10 p-4 text-sm text-negative">❌ Could not retrieve anomaly data.</div>
      ) : (
        <>
          <SectionTitle icon="📊" title="Anomaly Summary" />
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard icon="📅" label="Days Compared" value={String(data.total_days)} accent="#7C6FF0" />
            <KpiCard icon="🚨" label="Total Anomalies" value={String(data.anomaly_count)} accent={data.anomaly_count > 0 ? '#F0596B' : '#3ECF8E'} />
            <KpiCard icon="🔴" label="High Severity" value={String(high)} accent={high > 0 ? '#F0596B' : '#3ECF8E'} />
            <KpiCard icon="🟡" label="Medium Severity" value={String(medium)} accent={medium > 0 ? '#F0B429' : '#3ECF8E'} />
          </div>

          {results.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">
              No overlapping date range found between forecast and actual sales data.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
                <div className="lg:col-span-3">
                  <SectionTitle icon="📉" title="Forecast vs Actuals with Anomaly Markers" />
                  <PlotlyChart data={chartData} layout={layout} height={430} />
                </div>
                <div>
                  <SectionTitle icon="🍩" title="Severity Split" />
                  <PlotlyChart data={donutData} layout={donutLayout} height={430} />
                </div>
              </div>

              <SectionTitle icon="📋" title="Detailed Results Table" />
              {filtered.length === 0 ? (
                <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">No results match the selected severity filters.</div>
              ) : (
                <div className="max-h-[450px] overflow-y-auto rounded-xl border border-border">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-surface text-text-muted">
                      <tr>
                        <th className="px-3 py-2">Date</th>
                        <th className="px-3 py-2 text-right">Actual Sales</th>
                        <th className="px-3 py-2 text-right">Forecast Sales</th>
                        <th className="px-3 py-2 text-right">Deviation %</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Severity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r) => (
                        <tr key={r.date} className="border-t border-border">
                          <td className="px-3 py-2">{r.date}</td>
                          <td className="px-3 py-2 text-right font-mono">{fmtNum(r.actual_sales, 2)}</td>
                          <td className="px-3 py-2 text-right font-mono">{fmtNum(r.forecast_sales, 2)}</td>
                          <td className="px-3 py-2 text-right font-mono">{r.deviation_percent.toFixed(2)}%</td>
                          <td className="px-3 py-2" style={{ color: severityColor(r.status) }}>{r.status}</td>
                          <td className="px-3 py-2 font-bold" style={{ color: severityColor(r.severity) }}>{r.severity}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
