// Port of frontend/pages/5_💡_Recommendations.py

import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { PageHeader } from '@/components/ui/PageHeader'
import { KpiCard } from '@/components/ui/KpiCard'
import { SectionTitle } from '@/components/ui/SectionTitle'
import { RecCard } from '@/components/ui/RecCard'
import { OfflineBanner } from '@/components/ui/OfflineBanner'
import { ControlBar, Select } from '@/components/ui/Controls'
import { useHealth, useRecommendations } from '@/lib/queries'
import { getRecommendations } from '@/lib/apiClient'
import { useAcknowledged } from '@/lib/useAcknowledged'
import { CATEGORIES, CAT_NAMES, VALIDATION_MODELS, MODEL_LABELS, SIGNAL_DESCRIPTIONS, SIGNAL_ICONS } from '@/lib/constants'
import { fmtPct, fmtNum, priorityColor } from '@/lib/format'
import type { Category, ModelType } from '@/types/api'

type ViewMode = 'single' | 'all'

export function Recommendations() {
  const { data: isConnected } = useHealth()
  const [viewMode, setViewMode] = useState<ViewMode>('single')
  const [category, setCategory] = useState<Category>('M01AB')
  const [model, setModel] = useState<ModelType>('arima')
  const [priorityFilter, setPriorityFilter] = useState<string[]>(['HIGH', 'MEDIUM', 'LOW'])
  const { acknowledged, toggle } = useAcknowledged()

  const { data } = useRecommendations(category, model, !!isConnected && viewMode === 'single')

  const allQueries = useQueries({
    queries: CATEGORIES.map((cat) => ({
      queryKey: ['recommendations', cat, 'arima'],
      queryFn: () => getRecommendations(cat, 'arima'),
      enabled: !!isConnected && viewMode === 'all',
      staleTime: 300_000,
    })),
  })

  if (!isConnected) {
    return (
      <div>
        <PageHeader title="💡 Recommendations Engine" subtitle="Intelligent supply chain signals — prioritised actions for 8 drug categories" connected={false} />
        <OfflineBanner />
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="💡 Recommendations Engine" subtitle="Intelligent supply chain signals — prioritised actions for 8 drug categories" connected />

      <ControlBar>
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('single')}
            className={'rounded-lg border px-3 py-2 text-xs font-semibold ' + (viewMode === 'single' ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted')}
          >🎯 Single Category</button>
          <button
            onClick={() => setViewMode('all')}
            className={'rounded-lg border px-3 py-2 text-xs font-semibold ' + (viewMode === 'all' ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted')}
          >📊 All Categories Overview</button>
        </div>
        {viewMode === 'single' && (
          <>
            <Select label="Drug Category" value={category} onChange={(v) => setCategory(v as Category)}
              options={CATEGORIES.map((c) => ({ value: c, label: `${c} — ${CAT_NAMES[c]}` }))} />
            <Select label="Model" value={model} onChange={(v) => setModel(v as ModelType)}
              options={VALIDATION_MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
            <div className="flex flex-wrap gap-1.5">
              {(['HIGH', 'MEDIUM', 'LOW'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter((cur) => cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p])}
                  className={
                    'rounded-full border px-3 py-1 text-xs font-semibold ' +
                    (priorityFilter.includes(p) ? 'border-accent bg-accent/10 text-accent' : 'border-border bg-surface text-text-muted')
                  }
                >
                  {p === 'HIGH' ? '🔴 High' : p === 'MEDIUM' ? '🟡 Medium' : '🟢 Low'}
                </button>
              ))}
            </div>
          </>
        )}
      </ControlBar>

      {viewMode === 'all' ? (
        <>
          <SectionTitle icon="📊" title="All Categories — Signal Overview" />
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface text-text-muted">
                <tr><th className="px-3 py-2">Category</th><th className="px-3 py-2">Name</th><th className="px-3 py-2">Top Signal</th><th className="px-3 py-2">Priority</th><th className="px-3 py-2 text-right">Trend %</th><th className="px-3 py-2 text-right">MAE</th><th className="px-3 py-2 text-right">Anomalies</th></tr>
              </thead>
              <tbody>
                {CATEGORIES.map((cat, i) => {
                  const d = allQueries[i]?.data
                  const top = d?.recommendations?.[0]
                  return (
                    <tr key={cat} className="border-t border-border">
                      <td className="px-3 py-2 font-mono">{cat}</td>
                      <td className="px-3 py-2 text-text-muted">{CAT_NAMES[cat]}</td>
                      <td className="px-3 py-2" style={{ color: top ? (top.signal.includes('RESTOCK') ? '#3ECF8E' : top.signal.includes('SPIKE') ? '#F0596B' : '#F0B429') : undefined }}>{top?.signal ?? '—'}</td>
                      <td className="px-3 py-2 font-bold" style={{ color: top ? priorityColor(top.priority) : undefined }}>{top?.priority ?? '—'}</td>
                      <td className="px-3 py-2 text-right font-mono">{d ? fmtPct(d.forecast_trend_pct) : 'N/A'}</td>
                      <td className="px-3 py-2 text-right font-mono">{d?.model_mae !== undefined && d?.model_mae !== null ? fmtNum(d.model_mae, 2) : 'N/A'}</td>
                      <td className="px-3 py-2 text-right">{d ? d.anomaly_count : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : !data ? (
        <div className="rounded-xl border border-negative/30 bg-negative/10 p-4 text-sm text-negative">❌ Could not load recommendations.</div>
      ) : (
        <>
          <SectionTitle icon="📊" title="Category Context" />
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <KpiCard icon="📈" label="Forecast Trend" value={fmtPct(data.forecast_trend_pct)} accent={data.forecast_trend_pct >= 0 ? '#3ECF8E' : '#F0596B'} />
            <KpiCard icon="🎯" label="Model MAE" value={data.model_mae !== null ? fmtNum(data.model_mae, 2) : fmtPct(data.model_mape)} accent="#3ECF8E" />
            <KpiCard icon="🚨" label="Anomaly Count" value={String(data.anomaly_count)} accent={data.anomaly_count > 0 ? '#F0596B' : '#3ECF8E'} />
          </div>

          {(() => {
            const recs = data.recommendations.filter((r) => priorityFilter.includes(r.priority))
            if (recs.length === 0) {
              return <div className="rounded-xl border border-border bg-surface/60 p-4 text-sm text-text-muted">No recommendations match the selected priority filter.</div>
            }
            const keyed = recs.map((r) => ({ ...r, key: `${category}:${r.signal}` }))
            const active = keyed.filter((r) => !acknowledged.has(r.key))
            const done = keyed.filter((r) => acknowledged.has(r.key))
            return (
              <>
                <SectionTitle icon="💡" title={`Recommendations (${active.length} active${done.length ? `, ${done.length} acknowledged` : ''})`} />
                {active.length === 0 ? (
                  <div className="rounded-xl border border-positive/25 bg-positive/[0.04] p-4 text-sm text-positive">✓ All caught up for {category}.</div>
                ) : (
                  active.map((r) => (
                    <RecCard
                      key={r.key}
                      signal={r.signal}
                      priority={r.priority}
                      text={r.recommendation}
                      rationale={r.rationale}
                      icon={SIGNAL_ICONS[r.signal] ?? '📊'}
                      onToggleAcknowledge={() => toggle(r.key)}
                    />
                  ))
                )}
                {done.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-text-faint">{done.length} acknowledged</summary>
                    <div className="mt-2">
                      {done.map((r) => (
                        <RecCard
                          key={r.key}
                          signal={r.signal}
                          priority={r.priority}
                          text={r.recommendation}
                          rationale={r.rationale}
                          icon={SIGNAL_ICONS[r.signal] ?? '📊'}
                          acknowledged
                          onToggleAcknowledge={() => toggle(r.key)}
                        />
                      ))}
                    </div>
                  </details>
                )}
              </>
            )
          })()}

          <details className="mt-4 rounded-xl border border-border bg-surface/60 p-4">
            <summary className="cursor-pointer text-sm font-semibold text-text">📖 Signal Reference Guide</summary>
            <table className="mt-3 w-full text-left text-sm">
              <tbody>
                {Object.entries(SIGNAL_DESCRIPTIONS).map(([signal, desc]) => (
                  <tr key={signal} className="border-t border-border">
                    <td className="px-3 py-2 font-mono text-text-muted">{signal}</td>
                    <td className="px-3 py-2 text-text-muted">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </div>
  )
}
