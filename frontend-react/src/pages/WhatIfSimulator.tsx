// Port of frontend/pages/4_🔬_WhatIf_Simulator.py
//
// The date-range defaults for the disruption window are computed from the
// already-fetched forecast response, not by reaching into the backend's
// Python module the way the Streamlit page did (`from backend.data_loader
// import load_forecast`) — that only worked because Streamlit and FastAPI
// shared one process. A browser-based React app can't do that; it only
// has what the API returns.

import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { ControlBar, Select, Slider, Checkbox } from '@/components/ui/Controls'
import { useHealth, useForecast, useWhatIf } from '@/lib/queries'
import { ALL_MODELS, CATEGORIES, CAT_NAMES, MODEL_LABELS } from '@/lib/constants'
import { fmtNum } from '@/lib/format'
import { whatIfChart } from '@/lib/charts'
import type { Category, ModelType } from '@/types/api'

export function WhatIfSimulator() {
  const { data: isConnected } = useHealth()
  const [category, setCategory] = useState<Category>('M01AB')
  const [model, setModel] = useState<ModelType>('prophet')
  const [changePct, setChangePct] = useState(20)
  const [useDisruption, setUseDisruption] = useState(false)
  const [disruptionStart, setDisruptionStart] = useState('')
  const [disruptionEnd, setDisruptionEnd] = useState('')

  // Pull the baseline forecast just to derive the date range for the
  // disruption picker's min/max/defaults.
  const { data: baselineForecast } = useForecast(category, model, 30, !!isConnected)

  useEffect(() => {
    const dates = baselineForecast?.forecast?.map((p) => p.date) ?? []
    if (dates.length >= 12) {
      setDisruptionStart(dates[3])
      setDisruptionEnd(dates[11])
    } else if (dates.length >= 2) {
      setDisruptionStart(dates[0])
      setDisruptionEnd(dates[dates.length - 1])
    }
    // Reset whenever the underlying forecast changes (new category/model).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, model, baselineForecast?.forecast?.length])

  const { data, isLoading } = useWhatIf(
    category, model, changePct,
    useDisruption ? disruptionStart : null,
    useDisruption ? disruptionEnd : null,
    !!isConnected,
  )

  if (!isConnected) {
    return (
      <div>
        <PageHeader title="🔬 What-If Simulator" subtitle="Model demand scenarios — apply % shifts and supply disruptions to any forecast" connected={false} />
        <OfflineBanner />
      </div>
    )
  }

  const dateOptions = baselineForecast?.forecast?.map((p) => p.date) ?? []
  const baseline = data?.total_baseline ?? 0
  const adjusted = data?.total_adjusted ?? 0
  const difference = data?.total_difference ?? 0
  const disruptionDays = data?.disruption_days ?? 0
  const pctDiff = baseline ? (difference / baseline) * 100 : 0
  const direction = pctDiff >= 0 ? 'increase' : 'decrease'
  const color = pctDiff >= 0 ? 'text-positive' : 'text-negative'

  const { data: chartData, layout } = data ? whatIfChart(data.results, disruptionDays) : { data: [], layout: {} }

  return (
    <div>
      <PageHeader title="🔬 What-If Simulator" subtitle="Model demand scenarios — apply % shifts and supply disruptions to any forecast" connected />

      <ControlBar>
        <Select label="Drug Category" value={category} onChange={(v) => setCategory(v as Category)}
          options={CATEGORIES.map((c) => ({ value: c, label: `${c} — ${CAT_NAMES[c]}` }))} />
        <Select label="Model" value={model} onChange={(v) => setModel(v as ModelType)}
          options={ALL_MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
        <div className="w-64">
          <Slider label="Demand Change %" value={changePct} onChange={setChangePct} min={-80} max={200} step={5} suffix="%" />
        </div>
        <Checkbox label="Enable Supply Disruption" checked={useDisruption} onChange={setUseDisruption} />
        {useDisruption && (
          <>
            <Select label="Disruption Start" value={disruptionStart} onChange={setDisruptionStart}
              options={dateOptions.map((d) => ({ value: d, label: d }))} />
            <Select label="Disruption End" value={disruptionEnd} onChange={setDisruptionEnd}
              options={dateOptions.map((d) => ({ value: d, label: d }))} />
          </>
        )}
      </ControlBar>

      {isLoading || !data ? (
        <div className="rounded-xl border border-border bg-surface/60 p-6 text-sm text-text-muted">
          {isLoading ? 'Running simulation…' : '❌ Simulation failed. Ensure the forecast CSV exists for this category/model combination.'}
        </div>
      ) : (
        <>
          <div className="mb-4 rounded-2xl border border-border bg-surface px-6 py-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-text-faint">
                Business Impact Summary — {category} · {model.toUpperCase()}
              </span>
              {useDisruption && disruptionDays > 0 && (
                <span className="rounded-md border border-negative/40 bg-negative/[0.18] px-3 py-1 text-xs font-bold text-negative">
                  🚨 Disruption: {disruptionStart} → {disruptionEnd}
                </span>
              )}
            </div>
            <div className="text-lg font-bold leading-relaxed text-text">
              A <span className={color}>{changePct >= 0 ? '+' : ''}{changePct}%</span> demand shift results in a{' '}
              <span className={color}>{Math.abs(pctDiff).toFixed(1)}% {direction}</span> in total forecasted sales
              ({fmtNum(baseline, 0)} → {fmtNum(adjusted, 0)} units)
              {disruptionDays > 0 ? (
                <> with <span className="font-bold text-negative">{disruptionDays} disruption days zeroed out</span>.</>
              ) : '.'}
            </div>
          </div>

          <SectionTitle icon="📊" title="Simulation Results" />
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard icon="📊" label="Baseline Total" value={fmtNum(baseline, 0)} accent="#6EA8D8" />
            <KpiCard icon="🎯" label="Adjusted Total" value={fmtNum(adjusted, 0)} accent={adjusted >= baseline ? '#3ECF8E' : '#F0596B'} />
            <KpiCard icon="∆" label="Net Impact" value={`${difference >= 0 ? '+' : ''}${fmtNum(difference, 0)}`} accent={difference >= 0 ? '#3ECF8E' : '#F0596B'} />
            <KpiCard icon="⚡" label="Disruption Days" value={String(disruptionDays)} accent={disruptionDays > 0 ? '#E8836C' : '#98989F'} />
          </div>

          <SectionTitle icon="📉" title="Baseline vs Adjusted Forecast" />
          <PlotlyChart data={chartData} layout={layout} height={460} />

          <SectionTitle icon="📋" title="Day-by-Day Breakdown" />
          <div className="max-h-[350px] overflow-y-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-surface text-text-muted">
                <tr><th className="px-3 py-2">Date</th><th className="px-3 py-2 text-right">Baseline</th><th className="px-3 py-2 text-right">Adjusted</th><th className="px-3 py-2 text-right">Δ</th><th className="px-3 py-2 text-right">Δ %</th></tr>
              </thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={r.date} className="border-t border-border">
                    <td className="px-3 py-2">{r.date}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmtNum(r.baseline_sales, 2)}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmtNum(r.adjusted_sales, 2)}</td>
                    <td className="px-3 py-2 text-right font-mono">{r.difference >= 0 ? '+' : ''}{fmtNum(r.difference, 2)}</td>
                    <td className="px-3 py-2 text-right font-mono">{r.change_percent >= 0 ? '+' : ''}{r.change_percent.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
