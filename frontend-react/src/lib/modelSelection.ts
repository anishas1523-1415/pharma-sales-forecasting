import type { MetricsResponse } from '@/types/api'
import { ALL_MODELS, VALIDATION_MODELS } from './constants'

function lowestMae(metrics: MetricsResponse | undefined, category: string, candidates: readonly string[]): string {
  const catData = metrics?.[category] as unknown as Record<string, unknown> | undefined
  if (!catData) return candidates[0]
  let best = candidates[0]
  let bestMae = Infinity
  for (const m of candidates) {
    const mae = catData[m]
    if (mae && typeof mae === 'object' && 'MAE' in mae) {
      const v = Number((mae as { MAE: number }).MAE)
      if (v < bestMae) {
        bestMae = v
        best = m
      }
    }
  }
  return best
}

/** True best-performing model per category (any of the 5) — for forecast display. */
export function bestModelFor(metrics: MetricsResponse | undefined, category: string): string {
  const catData = metrics?.[category]
  if (catData?.best_model) return catData.best_model
  return lowestMae(metrics, category, ALL_MODELS)
}

/**
 * Best model restricted to {arima, sarima} — the only two with a held-out
 * test window (real y overlap with actuals). Anomaly detection and the
 * recommendation engine's demand-spike signal need this: Prophet/LightGBM/
 * LSTM forecast pure future dates, so anomaly matching against them always
 * returns 0 days. Using bestModelFor() here (as the original Streamlit
 * Home page did) silently zeroes out the anomaly/demand-spike summary for
 * every category whose overall best model isn't arima/sarima.
 */
export function bestValidationModelFor(metrics: MetricsResponse | undefined, category: string): string {
  return lowestMae(metrics, category, VALIDATION_MODELS)
}
