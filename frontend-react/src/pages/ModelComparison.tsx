// Port of frontend/pages/6_🤖_Model_Comparison.py

import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { PageHeader } from '@/components/ui/PageHeader'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { ControlBar, Select, Slider } from '@/components/ui/Controls'
import { useHealth, useMetrics, useCompareModels, useFeatureImportance } from '@/lib/queries'
import { getForecast } from '@/lib/apiClient'
import { ALL_MODELS, CATEGORIES, MODEL_COLORS, MODEL_LABELS } from '@/lib/constants'
import { fmtNum, fmtPct } from '@/lib/format'
import { maeHeatmap, modelBarChart, multiModelForecastChart, applyDark } from '@/lib/charts'
import type { Category, ModelType } from '@/types/api'

type View = 'heatmap' | 'category' | 'overlay'

export function ModelComparison() {
  const { data: isConnected } = useHealth()
  const { data: metrics } = useMetrics()
  const [view, setView] = useState<View>('heatmap')
  const [category, setCategory] = useState<Category>('M01AB')
  const [horizon, setHorizon] = useState(30)
  const [selectedModels, setSelectedModels] = useState<ModelType[]>([...ALL_MODELS])

  const { data: cmpData } = useCompareModels(category, view === 'category')
  const { data: importanceData } = useFeatureImportance(category, view === 'category')

  const overlayQueries = useQueries({
    queries: selectedModels.map((m) => ({
      queryKey: ['forecast', category, m, horizon],
      queryFn: () => getForecast(category, m, horizon),
      enabled: view === 'overlay',
      staleTime: 300_000,
    })),
  })

  if (!isConnected) {
    return (
      <div>
        <PageHeader title="🤖 Model Comparison" subtitle="Evaluate & compare MAPE, RMSE across Prophet · ARIMA · SARIMA · LightGBM · LSTM" connected={false} />
        <OfflineBanner />
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="🤖 Model Comparison" subtitle="Evaluate & compare MAPE, RMSE across Prophet · ARIMA · SARIMA · LightGBM · LSTM" connected />

      <ControlBar>
        <div className="flex gap-2">
          {(['heatmap', 'category', 'overlay'] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={
                'rounded-lg border px-3 py-2 text-xs font-semibold ' +
                (view === v ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted hover:text-text')
              }
            >
              {v === 'heatmap' ? '🌡️ Global Heatmap' : v === 'category' ? '🔍 Category Deep-Dive' : '📈 Overlay Chart'}
            </button>
          ))}
        </div>
        {(view === 'category' || view === 'overlay') && (
          <Select label="Drug Category" value={category} onChange={(v) => setCategory(v as Category)}
            options={CATEGORIES.map((c) => ({ value: c, label: c }))} />
        )}
        {view === 'overlay' && (
          <div className="w-56">
            <Slider label="Forecast Horizon (days)" value={horizon} onChange={setHorizon} min={7} max={30} />
          </div>
        )}
      </ControlBar>

      {view === 'heatmap' && metrics && (
        <>
          <SectionTitle icon="🌡️" title="MAE Heatmap — All Categories × Models" />
          <PlotlyChart {...maeHeatmap(metrics)} height={500} />

          <SectionTitle icon="📊" title="Average MAE by Model (All 8 Categories)" />
          <PlotlyChart {...modelBarChart(metrics)} height={380} />

          <SectionTitle icon="⭐" title="Best Model per Category (Lowest MAE)" />
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface text-text-muted"><tr><th className="px-3 py-2">Category</th><th className="px-3 py-2">Best Model</th><th className="px-3 py-2 text-right">MAE (units)</th></tr></thead>
              <tbody>
                {CATEGORIES.map((cat) => {
                  const catData = metrics[cat]
                  let best = 'prophet'
                  let bestMae = Infinity
                  for (const m of ALL_MODELS) {
                    const v = catData?.[m]?.MAE
                    if (v !== undefined && v < bestMae) { bestMae = v; best = m }
                  }
                  return (
                    <tr key={cat} className="border-t border-border">
                      <td className="px-3 py-2 font-mono">{cat}</td>
                      <td className="px-3 py-2 font-bold" style={{ color: MODEL_COLORS[best] }}>{best.toUpperCase()}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtNum(bestMae, 2)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {view === 'category' && (
        !cmpData ? (
          <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">⚠️ No comparison data for this category.</div>
        ) : (
          <>
            <SectionTitle icon="🔍" title={`Model Performance — ${category}`} />
            {(() => {
              let best = 'prophet'
              let bestMae = Infinity
              for (const [m, d] of Object.entries(cmpData.models)) {
                const mae = (d as { MAE?: number }).MAE
                if (mae !== undefined && mae < bestMae) { bestMae = mae; best = m }
              }
              const rows = Object.entries(cmpData.models).map(([m, d]) => {
                const data = d as { MAE?: number; RMSE?: number; MAPE?: number; 'MAPE_%'?: number }
                return { model: m, mae: data.MAE, rmse: data.RMSE, mape: data.MAPE ?? data['MAPE_%'] }
              })
              return (
                <>
                  <div className="mb-3 text-sm text-text-muted">
                    Best Model (Lowest MAE):{' '}
                    <span className="rounded-md border px-2 py-0.5 text-xs font-bold" style={{ color: MODEL_COLORS[best], borderColor: `${MODEL_COLORS[best]}55`, background: `${MODEL_COLORS[best]}22` }}>
                      ⭐ {best.toUpperCase()}
                    </span>
                  </div>
                  <div className="mb-4 overflow-hidden rounded-xl border border-border">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-surface text-text-muted"><tr><th className="px-3 py-2">Model</th><th className="px-3 py-2 text-right">MAE</th><th className="px-3 py-2 text-right">RMSE</th><th className="px-3 py-2 text-right">MAPE %</th><th className="px-3 py-2">Status</th></tr></thead>
                      <tbody>
                        {rows.map((r) => (
                          <tr key={r.model} className="border-t border-border">
                            <td className="px-3 py-2 font-bold" style={{ color: MODEL_COLORS[r.model] }}>{r.model.toUpperCase()}</td>
                            <td className="px-3 py-2 text-right font-mono">{r.mae !== undefined ? fmtNum(r.mae, 2) : 'N/A'}</td>
                            <td className="px-3 py-2 text-right font-mono">{r.rmse !== undefined ? fmtNum(r.rmse, 2) : 'N/A'}</td>
                            <td className="px-3 py-2 text-right font-mono">{r.mape !== undefined ? fmtPct(r.mape) : 'N/A'}</td>
                            <td className="px-3 py-2">{r.model === best ? '⭐ Best' : ''}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <PlotlyChart
                    data={[{
                      x: rows.map((r) => r.model.toUpperCase()),
                      y: rows.map((r) => r.mae ?? 0),
                      type: 'bar',
                      marker: { color: rows.map((r) => MODEL_COLORS[r.model]), line: { color: 'rgba(255,255,255,0.1)', width: 1 } },
                      text: rows.map((r) => fmtNum(r.mae, 2)),
                      textposition: 'outside',
                    }]}
                    layout={applyDark({ yaxis: { title: { text: 'MAE (units)' } } }, `${category} — Model MAE Comparison`)}
                    height={350}
                  />

                  {importanceData && importanceData.features.length > 0 && (
                    <>
                      <SectionTitle icon="🔬" title="What drives the LightGBM forecast" />
                      <p className="mb-3 text-xs text-text-muted">
                        Top features by split-gain importance from the trained model — which lagged/rolling sales
                        values and calendar signals it actually relies on for {category}.
                      </p>
                      <PlotlyChart
                        data={[{
                          x: [...importanceData.features].reverse().map((f) => f.importance_pct),
                          y: [...importanceData.features].reverse().map((f) => f.feature),
                          type: 'bar',
                          orientation: 'h',
                          marker: { color: MODEL_COLORS.lightgbm },
                          text: [...importanceData.features].reverse().map((f) => `${f.importance_pct}%`),
                          textposition: 'outside',
                        }]}
                        layout={applyDark({ margin: { l: 120, r: 30, t: 10, b: 30 }, xaxis: { title: { text: '% of total importance' } } })}
                        height={320}
                      />
                    </>
                  )}
                </>
              )
            })()}
          </>
        )
      )}

      {view === 'overlay' && (
        <>
          <SectionTitle icon="📈" title={`All-Model Forecast Overlay — ${category}`} />
          <div className="mb-4 flex flex-wrap gap-2">
            {ALL_MODELS.map((m) => (
              <button
                key={m}
                onClick={() => setSelectedModels((cur) => cur.includes(m) ? cur.filter((x) => x !== m) : [...cur, m])}
                className={
                  'rounded-full border px-3 py-1 text-xs font-semibold ' +
                  (selectedModels.includes(m) ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted')
                }
              >
                {MODEL_LABELS[m]}
              </button>
            ))}
          </div>
          {(() => {
            const forecasts: Record<string, { date: string; prediction: number }[]> = {}
            selectedModels.forEach((m, i) => {
              const pts = overlayQueries[i]?.data?.forecast
              if (pts?.length) forecasts[m] = pts
            })
            if (Object.keys(forecasts).length === 0) {
              return <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">No forecast data available for the selected models.</div>
            }
            const { data, layout } = multiModelForecastChart(forecasts, null, category)
            return (
              <>
                <PlotlyChart data={data} layout={layout} height={480} />
                <SectionTitle icon="📋" title="Model Totals Comparison" />
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-surface text-text-muted"><tr><th className="px-3 py-2">Model</th><th className="px-3 py-2 text-right">Total Forecast</th><th className="px-3 py-2 text-right">Avg Daily</th><th className="px-3 py-2 text-right">Min</th><th className="px-3 py-2 text-right">Max</th></tr></thead>
                    <tbody>
                      {Object.entries(forecasts).map(([m, pts]) => {
                        const preds = pts.map((p) => p.prediction)
                        const total = preds.reduce((a, b) => a + b, 0)
                        return (
                          <tr key={m} className="border-t border-border">
                            <td className="px-3 py-2 font-bold" style={{ color: MODEL_COLORS[m] }}>{m.toUpperCase()}</td>
                            <td className="px-3 py-2 text-right font-mono">{fmtNum(total, 0)}</td>
                            <td className="px-3 py-2 text-right font-mono">{fmtNum(total / preds.length, 2)}</td>
                            <td className="px-3 py-2 text-right font-mono">{fmtNum(Math.min(...preds), 2)}</td>
                            <td className="px-3 py-2 text-right font-mono">{fmtNum(Math.max(...preds), 2)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )
          })()}
        </>
      )}
    </div>
  )
}
