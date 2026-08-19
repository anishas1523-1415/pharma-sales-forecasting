// Port of frontend/pages/1_🏠_Home.py

import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { RecCard } from '@/components/ui/RecCard'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { PlotlyChart } from '@/components/ui/PlotlyChart'
import { useDashboardSummary, useHealth, useModels } from '@/lib/queries'
import { CAT_NAMES, MODEL_COLORS, SIGNAL_ICONS } from '@/lib/constants'
import { fmtTrend } from '@/lib/format'
import { applyDark } from '@/lib/charts'
import type { Data } from 'plotly.js'

export function Dashboard() {
  const { data: isConnected } = useHealth()
  const { data: modelsData } = useModels()
  // Forecast + anomaly + recommendation data for all 8 categories in one
  // request — see backend/services/dashboard_service.py. Used to be 24
  // separate requests (forecast/anomaly/recommendations × 8 categories),
  // which queued up behind the browser's per-host connection limit and
  // were the real cause of this page's slow initial paint.
  const { data: summary, isFetched } = useDashboardSummary(!!isConnected)
  const categories = summary?.categories ?? []

  // ── KPIs ──────────────────────────────────────────────────────────
  const maes = categories.map((c) => c.model_mae).filter((v): v is number => v !== null && v !== undefined)
  const avgMae = maes.length ? maes.reduce((a, b) => a + b, 0) / maes.length : null

  // ── Overview chart ───────────────────────────────────────────────
  const overviewData: Data[] = categories
    .map((c) => ({
      x: c.forecast.map((p) => p.date),
      y: c.forecast.map((p) => p.prediction),
      name: c.category,
      type: 'scatter',
      mode: 'lines',
      line: { width: 2, color: MODEL_COLORS[c.best_model] },
      hovertemplate: `<b>${c.category}</b><br>Date: %{x}<br>Sales: %{y:,.2f}<extra></extra>`,
    } as Data))
    .filter((t) => (t as { x: unknown[] }).x.length > 0)

  // ── Anomaly summary ──────────────────────────────────────────────
  const totalAnomalies = categories.reduce((sum, c) => sum + c.anomaly_count, 0)
  const highSev = categories.reduce((sum, c) => sum + c.high_severity_count, 0)

  // ── Top recommendations ──────────────────────────────────────────
  const highRecs: { category: string; signal: string; priority: string; recommendation: string; rationale: string }[] = []
  for (const c of categories) {
    for (const r of c.recommendations) {
      if (r.priority === 'HIGH') highRecs.push({ ...r, category: c.category })
    }
  }

  // ── Headline insight — the first thing a reader sees, synthesized from
  // the same recommendation/anomaly data as the sections below, not a
  // separate analysis. Replaces a generic KPI-tiles opening with an
  // actual read on portfolio state.
  const demandSpikes = highRecs.filter((r) => r.signal === 'DEMAND_SPIKE')
  const restockAlerts = highRecs.filter((r) => r.signal === 'RESTOCK_ALERT')
  const headline = demandSpikes.length
    ? `${demandSpikes.length} categor${demandSpikes.length > 1 ? 'ies show' : 'y shows'} a high-severity demand spike`
    : restockAlerts.length
      ? `${restockAlerts.length} categor${restockAlerts.length > 1 ? 'ies are' : 'y is'} trending up and may need restocking`
      : highRecs.length
        ? `${highRecs.length} high-priority signal${highRecs.length > 1 ? 's' : ''} flagged across the portfolio`
        : 'No high-priority signals — portfolio looks stable'
  const leadCategory = (demandSpikes[0] ?? restockAlerts[0] ?? highRecs[0])?.category

  return (
    <div>
      <PageHeader
        title="💊 PharmaForecast Analytics"
        subtitle="Pharmaceutical Sales Intelligence Platform · 8 Drug Categories · 5 ML Models"
        connected={!!isConnected}
      />
      {!isConnected && <OfflineBanner />}

      {isConnected && (
        <div className={'mb-6 rounded-2xl border p-6 ' + (highRecs.length ? 'border-negative/25 bg-negative/[0.04]' : 'border-positive/25 bg-positive/[0.04]')}>
          {!isFetched ? (
            <div className="h-16 animate-pulse rounded-lg bg-surface-2" />
          ) : (
            <>
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-faint">
                <span>{highRecs.length ? '⚠' : '✓'}</span> Today's read
              </div>
              <div className="font-display text-xl font-semibold leading-snug text-text">{headline}</div>
              {leadCategory && (
                <div className="mt-2 text-sm text-text-muted">
                  Most urgent:{' '}
                  <a href={`/forecast?category=${leadCategory}`} className="font-medium text-accent hover:underline">
                    {leadCategory} — {CAT_NAMES[leadCategory as keyof typeof CAT_NAMES]}
                  </a>
                  {highRecs.length > 1 && ` · ${highRecs.length - 1} more below`}
                </div>
              )}
            </>
          )}
        </div>
      )}

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
        {categories.map((c) => {
          const color = MODEL_COLORS[c.best_model] ?? '#7C6FF0'
          const pts = c.forecast
          let trend: number | null = null
          if (pts.length >= 2) {
            const first = pts[0].prediction
            const last = pts[pts.length - 1].prediction
            trend = first !== 0 ? ((last - first) / first) * 100 : 0
          }
          return (
            <div key={c.category} className="rounded-2xl border border-border bg-surface p-4 transition-colors hover:border-border-strong">
              <div className="flex items-center justify-between">
                <span className="font-mono text-base font-semibold text-text">{c.category}</span>
                <span className={'text-xs font-medium ' + ((trend ?? 0) >= 0 ? 'text-positive' : 'text-negative')}>{fmtTrend(trend)}</span>
              </div>
              <div className="mt-1 text-xs text-text-faint">{CAT_NAMES[c.category as keyof typeof CAT_NAMES]}</div>
              <div className="mt-3">
                <span
                  className="rounded-md px-2 py-0.5 text-[0.68rem] font-medium"
                  style={{ color, background: `${color}14` }}
                >
                  {c.best_model.toUpperCase()}
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
                    {categories.map((c) => (
                      <tr key={c.category} className="border-t border-border">
                        <td className="px-3 py-2 font-mono">{c.category}</td>
                        <td className="px-3 py-2">{c.total_days}</td>
                        <td className="px-3 py-2">{c.anomaly_count}</td>
                        <td className={'px-3 py-2 ' + (c.high_severity_count > 0 ? 'font-bold text-negative' : '')}>{c.high_severity_count}</td>
                        <td className="px-3 py-2 text-text-muted">{c.validation_model.toUpperCase()}</td>
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
