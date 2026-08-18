// Centralised HTTP client for the FastAPI backend.
// 1:1 port of frontend/utils/api_client.py — same endpoints, same retry
// intent (axios + React Query's own retry/backoff replaces the manual
// retry loop the Streamlit version needed).

import axios from 'axios'
import type {
  ActualsResponse,
  AnomalyResponse,
  CompareModelsResponse,
  FeatureImportanceResponse,
  ForecastResponse,
  MetricsResponse,
  ModelsListResponse,
  RecommendationResponse,
  WhatIfResponse,
} from '@/types/api'

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Only sent when VITE_API_KEY is set (deployed demo instance). Local dev
// talks to a backend with no API_KEYS configured, where auth is a no-op —
// see backend/auth.py.
const API_KEY: string | undefined = import.meta.env.VITE_API_KEY

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
})

export async function checkHealth(): Promise<boolean> {
  try {
    await client.get('/health')
    return true
  } catch {
    return false
  }
}

export async function getModels(): Promise<ModelsListResponse> {
  const { data } = await client.get<ModelsListResponse>('/models')
  return data
}

export async function getMetrics(): Promise<MetricsResponse> {
  const { data } = await client.get<MetricsResponse>('/metrics')
  return data
}

export async function getActuals(category: string, days = 90): Promise<ActualsResponse> {
  const { data } = await client.get<ActualsResponse>(`/actuals/${category}`, { params: { days } })
  return data
}

export async function getFeatureImportance(category: string): Promise<FeatureImportanceResponse> {
  const { data } = await client.get<FeatureImportanceResponse>(`/feature-importance/${category}`)
  return data
}

export async function getForecast(category: string, model: string, horizon: number): Promise<ForecastResponse> {
  const { data } = await client.post<ForecastResponse>('/forecast', { category, model, horizon })
  return data
}

export async function compareModels(category: string): Promise<CompareModelsResponse> {
  const { data } = await client.post<CompareModelsResponse>('/compare-models', { category })
  return data
}

export async function detectAnomalies(category: string, model: string): Promise<AnomalyResponse> {
  const { data } = await client.post<AnomalyResponse>('/api/anomaly/detect', { category, model })
  return data
}

export async function runWhatIf(
  category: string,
  model: string,
  changePercent: number,
  disruptionStart?: string | null,
  disruptionEnd?: string | null,
): Promise<WhatIfResponse> {
  const payload: Record<string, unknown> = { category, model, change_percent: changePercent }
  if (disruptionStart) payload.disruption_start = disruptionStart
  if (disruptionEnd) payload.disruption_end = disruptionEnd
  const { data } = await client.post<WhatIfResponse>('/api/what-if', payload)
  return data
}

export async function getRecommendations(category: string, model: string): Promise<RecommendationResponse> {
  const { data } = await client.post<RecommendationResponse>('/api/recommendations', { category, model })
  return data
}
