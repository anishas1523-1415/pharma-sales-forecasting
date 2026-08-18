// Port of frontend/pages/2_📈_Forecast_Explorer.py

import { useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { ControlBar, Select, Slider, Checkbox } from '@/components/ui/Controls'
import { useHealth, useMetrics, useForecast, useActuals } from '@/lib/queries'
import { ALL_MODELS, CATEGORIES, CAT_NAMES, MODEL_LABELS } from '@/lib/constants'
import { fmtNum } from '@/lib/format'
import { forecastChart } from '@/lib/charts'
import type { Category, ModelType } from '@/types/api'

export function ForecastExplorer() {
  const { data: isConnected } = useHealth()
  const { data: metrics } = useMetrics()
  const [category, setCategory] = useState<Category>('M01AB')
  const [model, setModel] = useState<ModelType>('prophet')
  const [horizon, setHorizon] = useState(30)
  const [showHistory, setShowHistory] = useState(true)

  const { data: forecastData, isLoading } = useForecast(category, model, horizon, !!isConnected)
  // Recent actual sales leading into the forecast — deliberately NOT
  // sourced from anomaly detection, whose "actuals" for ARIMA/SARIMA are
  // a held-out validation window from over a year before the forecast
  // start (see backend/routes/actuals.py for why that broke this chart).
  const { data: actualsData } = useActuals(category, 60, !!isConnected && showHistory)

  if (!isConnected) {
    return (
      <div>
        <PageHeader title="📈 Forecast Explorer" subtitle="Deep-dive into individual category forecasts" connected={false} />
        <OfflineBanner />
      </div>
    )
  }

  const mae = metrics?.[category]?.[model]?.MAE ?? null
  const rmse = metrics?.[category]?.[model]?.RMSE ?? null
  const preds = forecastData?.forecast?.map((p) => p.prediction) ?? []
  const historical = showHistory && actualsData?.results?.length ? actualsData.results : null

  const stdDev = preds.length
    ? Math.sqrt(preds.reduce((s, v) => s + (v - preds.reduce((a, b) => a + b, 0) / preds.length) ** 2, 0) / preds.length)
    : 0

  let trendPct: number | null = null
  if (preds.length >= 2) {
    const mid = Math.floor(preds.length / 2)
    const firstHalf = preds.slice(0, mid).reduce((a, b) => a + b, 0) / mid
    const secondHalf = preds.slice(mid).reduce((a, b) => a + b, 0) / (preds.length - mid)
    trendPct = firstHalf ? ((secondHalf - firstHalf) / firstHalf) * 100 : 0
  }

  const { data: chartData, layout } = forecastChart(forecastData?.forecast ?? [], historical, category, model, showHistory)

  return (
    <div>
      <PageHeader title="📈 Forecast Explorer" subtitle="Deep-dive into individual category forecasts · Adjust horizon · Compare against actuals" connected />

      <ControlBar>
        <Select label="Drug Category" value={category} onChange={(v) => setCategory(v as Category)}
          options={CATEGORIES.map((c) => ({ value: c, label: `${c} — ${CAT_NAMES[c]}` }))} />
        <Select label="Forecasting Model" value={model} onChange={(v) => setModel(v as ModelType)}
          options={ALL_MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
        <div className="w-56">
          <Slider label="Forecast Horizon (days)" value={horizon} onChange={setHorizon} min={7} max={30} />
        </div>
        <Checkbox label="Show Historical Overlay" checked={showHistory} onChange={setShowHistory} />
      </ControlBar>

      {isLoading ? (
        <div className="rounded-xl border border-border bg-surface/60 p-6 text-sm text-text-muted">Loading forecast…</div>
      ) : !forecastData ? (
        <div className="rounded-xl border border-negative/30 bg-negative/10 p-4 text-sm text-negative">❌ Could not load forecast data.</div>
      ) : (
        <>
          <SectionTitle icon="📊" title="Forecast Summary" />
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard icon="📅" label="Forecast Days" value={String(preds.length)} accent="#7C6FF0" />
            <KpiCard icon="📦" label="Total Forecast Sales" value={fmtNum(preds.reduce((a, b) => a + b, 0), 0)} accent="#3ECF8E" />
            <KpiCard icon="📈" label="Avg Daily Forecast" value={fmtNum(preds.length ? preds.reduce((a, b) => a + b, 0) / preds.length : 0, 2)} accent="#F0B429" />
            <KpiCard icon="🎯" label="Model MAE" value={mae !== null ? fmtNum(mae, 2) : 'N/A'} accent="#3ECF8E" />
          </div>

          <SectionTitle icon="📉" title="Forecast Chart" />
          <PlotlyChart data={chartData} layout={layout} height={460} />

          <SectionTitle icon="🔢" title="Statistical Summary" />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="w-full text-left text-sm">
                <tbody>
                  {[
                    ['Min Forecast', fmtNum(Math.min(...preds), 2)],
                    ['Max Forecast', fmtNum(Math.max(...preds), 2)],
                    ['Std Dev', fmtNum(stdDev, 2)],
                    ['MAE', mae !== null ? fmtNum(mae, 2) : 'N/A'],
                    ['RMSE', rmse !== null ? fmtNum(rmse, 2) : 'N/A'],
                  ].map(([k, v]) => (
                    <tr key={k} className="border-t border-border first:border-t-0">
                      <td className="px-3 py-2 text-text-muted">{k}</td>
                      <td className="px-3 py-2 text-right font-mono text-text">{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="max-h-64 overflow-y-auto rounded-xl border border-border lg:col-span-2">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-surface text-text-muted">
                  <tr><th className="px-3 py-2">Date</th><th className="px-3 py-2 text-right">Forecast (units)</th></tr>
                </thead>
                <tbody>
                  {forecastData.forecast.map((p) => (
                    <tr key={p.date} className="border-t border-border">
                      <td className="px-3 py-2">{p.date}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtNum(p.prediction, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {trendPct !== null && (
            <div className="mt-4 flex items-center gap-4 rounded-xl border border-border bg-surface/90 px-6 py-4">
              <span className="text-3xl">{trendPct >= 0 ? '📈' : '📉'}</span>
              <div>
                <div className="text-xs font-medium uppercase text-text-muted">Forecast Trend (First Half vs Second Half)</div>
                <div className={'font-mono text-2xl font-bold ' + (trendPct >= 0 ? 'text-positive' : 'text-negative')}>
                  {trendPct >= 0 ? '+' : ''}{trendPct.toFixed(2)}%
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
