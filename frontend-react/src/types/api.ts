// Mirrors backend/schemas/*.py exactly — keep in sync with the Python models.

export type Category = 'M01AB' | 'M01AE' | 'N02BA' | 'N02BE' | 'N05B' | 'N05C' | 'R03' | 'R06'
export type ModelType = 'prophet' | 'arima' | 'sarima' | 'lightgbm' | 'lstm'

export interface ForecastPoint {
  date: string
  prediction: number
  lower?: number
  upper?: number
}

export interface ForecastResponse {
  category: string
  model: string
  horizon: number
  forecast: ForecastPoint[]
}

export interface ModelMetricEntry {
  MAE: number
  RMSE: number
  MAPE?: number
  'MAPE_%'?: number
  [key: string]: unknown
}

export interface CategoryMetrics {
  prophet: ModelMetricEntry
  arima: ModelMetricEntry
  sarima: ModelMetricEntry
  lightgbm: ModelMetricEntry
  lstm: ModelMetricEntry
  best_model: string
}

export type MetricsResponse = Record<string, CategoryMetrics>

export interface CompareModelsResponse {
  category: string
  models: Record<string, ModelMetricEntry>
  best_model: string | null
}

export interface ModelsListResponse {
  models: string[]
  categories: string[]
}

export interface AnomalyResult {
  date: string
  actual_sales: number
  forecast_sales: number
  deviation_percent: number
  status: 'normal' | 'moderate' | 'anomaly'
  severity: 'low' | 'medium' | 'high'
}

export interface AnomalyResponse {
  category: string
  model: string
  total_days: number
  anomaly_count: number
  results: AnomalyResult[]
}

export interface WhatIfPoint {
  date: string
  baseline_sales: number
  adjusted_sales: number
  difference: number
  change_percent: number
}

export interface WhatIfResponse {
  category: string
  model: string
  change_percent: number
  total_baseline: number
  total_adjusted: number
  total_difference: number
  disruption_days: number
  results: WhatIfPoint[]
}

export interface Recommendation {
  signal: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  recommendation: string
  rationale: string
}

export interface ActualsResponse {
  category: string
  results: { date: string; actual_sales: number }[]
}

export interface FeatureImportanceItem {
  feature: string
  importance: number
  importance_pct: number
}

export interface FeatureImportanceResponse {
  category: string
  features: FeatureImportanceItem[]
}

export interface RecommendationResponse {
  category: string
  model: string
  forecast_trend_pct: number
  model_mape: number | null
  model_mae: number | null
  anomaly_count: number
  recommendations: Recommendation[]
}

export interface ChatResponse {
  reply: string
  provider: 'gemini' | 'groq'
}
