// Port of frontend/pages/1_🏠_Home.py

import { useQueries } from '@tanstack/react-query'
import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { RecCard } from '@/components/ui/RecCard'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { useHealth, useMetrics, useModels } from '@/lib/queries'
import { getForecast, detectAnomalies, getRecommendations } from '@/lib/apiClient'
import { bestModelFor, bestValidationModelFor } from '@/lib/modelSelection'
import { CATEGORIES, CAT_NAMES, MODEL_COLORS, SIGNAL_ICONS } from '@/lib/constants'
import { fmtTrend } from '@/lib/format'
import { applyDark } from '@/lib/charts'
import type { Data } from 'plotly.js'

const HORIZON = 30

export function Dashboard() {
  const { data: isConnected } = useHealth()
  const { data: metrics } = useMetrics()
  const { data: modelsData } = useModels()

  const forecastQueries = useQueries({
    queries: CATEGORIES.map((cat) => {
      const model = bestModelFor(metrics, cat)
      return {
        queryKey: ['forecast', cat, model, HORIZON],
        queryFn: () => getForecast(cat, model, HORIZON),
        enabled: !!isConnected && !!metrics,
        staleTime: 300_000,
      }
    }),
  })

  const anomalyQueries = useQueries({
    queries: CATEGORIES.map((cat) => {
      const model = bestValidationModelFor(metrics, cat)
      return {
        queryKey: ['anomalies', cat, model],
        queryFn: () => detectAnomalies(cat, model),
        enabled: !!isConnected && !!metrics,
        staleTime: 300_000,
      }
    }),
  })

  const recQueries = useQueries({
    queries: CATEGORIES.map((cat) => {
      const model = bestValidationModelFor(metrics, cat)
      return {
        queryKey: ['recommendations', cat, model],
        queryFn: () => getRecommendations(cat, model),
        enabled: !!isConnected && !!metrics,
        staleTime: 300_000,
      }
    }),
  })

  // ── KPIs ──────────────────────────────────────────────────────────
  const allMaes: number[] = []
  if (metrics) {
    for (const cat of CATEGORIES) {
      const catData = metrics[cat]
      if (!catData) continue
      for (const [key, m] of Object.entries(catData)) {
        if (key === 'best_model' || typeof m !== 'object' || m === null) continue
        const mae = (m as { MAE?: number }).MAE
        if (mae !== undefined) allMaes.push(mae)
      }
    }
  }
  const avgMae = allMaes.length ? allMaes.reduce((a, b) => a + b, 0) / allMaes.length : null

  // ── Overview chart ───────────────────────────────────────────────
  const overviewData: Data[] = CATEGORIES.map((cat, i) => {
    const model = bestModelFor(metrics, cat)
    const fc = forecastQueries[i].data
    const pts = fc?.forecast ?? []
    return {
      x: pts.map((p) => p.date),
      y: pts.map((p) => p.prediction),
      name: cat,
      type: 'scatter',
      mode: 'lines',
      line: { width: 2, color: MODEL_COLORS[model] },
      hovertemplate: `<b>${cat}</b><br>Date: %{x}<br>Sales: %{y:,.2f}<extra></extra>`,
    } as Data
  }).filter((t) => (t as { x: unknown[] }).x.length > 0)

  // ── Anomaly summary ──────────────────────────────────────────────
  let totalAnomalies = 0
  let highSev = 0
  const anomalyRows: { cat: string; totalDays: number; anomalies: number; high: number; model: string }[] = []
  CATEGORIES.forEach((cat, i) => {
    const data = anomalyQueries[i].data
    if (!data) return
    const high = data.results.filter((r) => r.severity === 'high').length
    totalAnomalies += data.anomaly_count
    highSev += high
    anomalyRows.push({ cat, totalDays: data.total_days, anomalies: data.anomaly_count, high, model: bestValidationModelFor(metrics, cat).toUpperCase() })
  })

  // ── Top recommendations ──────────────────────────────────────────
  const highRecs: { category: string; signal: string; priority: string; recommendation: string; rationale: string }[] = []
  CATEGORIES.forEach((cat, i) => {
    const data = recQueries[i].data
    if (!data) return
    for (const r of data.recommendations) {
      if (r.priority === 'HIGH') highRecs.push({ ...r, category: cat })
    }
  })

  return (
    <div>
      <PageHeader
        title="💊 PharmaForecast Analytics"
        subtitle="Pharmaceutical Sales Intelligence Platform · 8 Drug Categories · 5 ML Models"
        connected={!!isConnected}
      />
      {!isConnected && <OfflineBanner />}

      <SectionTitle icon="📊" title="Executive Overview" />
      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard icon="🏥" label="Drug Categories" value="8" accent="#7C6FF0" />
        <KpiCard icon="🤖" label="Active Models" value={String(modelsData?.models?.length ?? 5)} accent="#3ECF8E" />
        <KpiCard icon="🎯" label="Avg. MAE (All)" value={avgMae !== null ? avgMae.toFixed(2) : 'N/A'} accent="#F0B429" />
      </div>

      <SectionTitle icon="📈" title="30-Day Forecast Trends (Best Model per Category)" />
      {isConnected ? (
        <PlotlyChart data={overviewData} layout={applyDark({})} height={420} />
      ) : (
        <div className="rounded-xl border border-border bg-surface/60 p-6 text-sm text-text-muted">
          Connect to backend to view live forecast trends.
        </div>
      )}

      <SectionTitle icon="📦" title="Category Overview" />
      <p className="mb-3 text-xs text-text-muted">Best model selected automatically per category based on lowest MAE.</p>
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {CATEGORIES.map((cat, i) => {
          const model = bestModelFor(metrics, cat)
          const color = MODEL_COLORS[model] ?? '#7C6FF0'
          const pts = forecastQueries[i].data?.forecast ?? []
          let trend: number | null = null
          if (pts.length >= 2) {
            const first = pts[0].prediction
            const last = pts[pts.length - 1].prediction
            trend = first !== 0 ? ((last - first) / first) * 100 : 0
          }
          return (
            <div key={cat} className="rounded-2xl border border-border bg-surface p-4 transition-colors hover:border-border-strong">
              <div className="flex items-center justify-between">
                <span className="font-mono text-base font-semibold text-text">{cat}</span>
                <span className={'text-xs font-medium ' + ((trend ?? 0) >= 0 ? 'text-positive' : 'text-negative')}>{fmtTrend(trend)}</span>
              </div>
              <div className="mt-1 text-xs text-text-faint">{CAT_NAMES[cat]}</div>
              <div className="mt-3">
                <span
                  className="rounded-md px-2 py-0.5 text-[0.68rem] font-medium"
                  style={{ color, background: `${color}14` }}
                >
                  {model.toUpperCase()}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <SectionTitle icon="🚨" title="Anomaly Summary (Across All Categories)" />
          {!isConnected ? (
            <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">Backend offline — anomaly data unavailable.</div>
          ) : (
            <>
              <div className="mb-3 grid grid-cols-2 gap-3">
                <KpiCard icon="🚨" label="Total Anomalies Detected" value={String(totalAnomalies)} accent="#E8836C" />
                <KpiCard icon="🔴" label="High Severity Events" value={String(highSev)} accent="#F0596B" />
              </div>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface text-text-muted">
                    <tr>
                      <th className="px-3 py-2">Category</th>
                      <th className="px-3 py-2">Total Days</th>
                      <th className="px-3 py-2">Anomalies</th>
                      <th className="px-3 py-2">High Severity</th>
                      <th className="px-3 py-2">Model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {anomalyRows.map((r) => (
                      <tr key={r.cat} className="border-t border-border">
                        <td className="px-3 py-2 font-mono">{r.cat}</td>
                        <td className="px-3 py-2">{r.totalDays}</td>
                        <td className="px-3 py-2">{r.anomalies}</td>
                        <td className={'px-3 py-2 ' + (r.high > 0 ? 'font-bold text-negative' : '')}>{r.high}</td>
                        <td className="px-3 py-2 text-text-muted">{r.model}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        <div className="lg:col-span-2">
          <SectionTitle icon="💡" title="Top Priority Recommendations" />
          {!isConnected ? (
            <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">Backend offline — recommendations unavailable.</div>
          ) : highRecs.length === 0 ? (
            <div className="rounded-xl border border-positive/30 bg-positive/10 p-4 text-sm text-positive">✅ No high-priority alerts across all categories.</div>
          ) : (
            highRecs.slice(0, 6).map((r, i) => (
              <RecCard
                key={i}
                signal={`${r.category} — ${r.signal}`}
                priority={r.priority}
                text={r.recommendation}
                rationale={r.rationale}
                icon={SIGNAL_ICONS[r.signal] ?? '📊'}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}
