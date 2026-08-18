// React Query hooks — staleTimes match the original st.cache_data(ttl=...)
// values in frontend/utils/api_client.py: health 30s, models 3600s,
// metrics 1800s, forecast/anomaly/whatif/recommendations 300s.

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import * as api from './apiClient'
import type {
  ActualsResponse,
  AnomalyResponse,
  CompareModelsResponse,
  ForecastResponse,
  MetricsResponse,
  ModelsListResponse,
  RecommendationResponse,
  WhatIfResponse,
} from '@/types/api'

export function useHealth(): UseQueryResult<boolean> {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.checkHealth,
    staleTime: 30_000,
    refetchInterval: 30_000,
    retry: false,
  })
}

export function useModels(): UseQueryResult<ModelsListResponse> {
  return useQuery({
    queryKey: ['models'],
    queryFn: api.getModels,
    staleTime: 3_600_000,
  })
}

export function useMetrics(): UseQueryResult<MetricsResponse> {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    staleTime: 1_800_000,
  })
}

export function useActuals(category: string, days = 90, enabled = true): UseQueryResult<ActualsResponse> {
  return useQuery({
    queryKey: ['actuals', category, days],
    queryFn: () => api.getActuals(category, days),
    staleTime: 1_800_000,
    enabled,
  })
}

export function useForecast(category: string, model: string, horizon: number, enabled = true): UseQueryResult<ForecastResponse> {
  return useQuery({
    queryKey: ['forecast', category, model, horizon],
    queryFn: () => api.getForecast(category, model, horizon),
    staleTime: 300_000,
    enabled,
  })
}

export function useCompareModels(category: string, enabled = true): UseQueryResult<CompareModelsResponse> {
  return useQuery({
    queryKey: ['compare-models', category],
    queryFn: () => api.compareModels(category),
    staleTime: 300_000,
    enabled,
  })
}

export function useAnomalies(category: string, model: string, enabled = true): UseQueryResult<AnomalyResponse> {
  return useQuery({
    queryKey: ['anomalies', category, model],
    queryFn: () => api.detectAnomalies(category, model),
    staleTime: 300_000,
    enabled,
  })
}

export function useWhatIf(
  category: string,
  model: string,
  changePercent: number,
  disruptionStart: string | null,
  disruptionEnd: string | null,
  enabled = true,
): UseQueryResult<WhatIfResponse> {
  return useQuery({
    queryKey: ['whatif', category, model, changePercent, disruptionStart, disruptionEnd],
    queryFn: () => api.runWhatIf(category, model, changePercent, disruptionStart, disruptionEnd),
    staleTime: 300_000,
    enabled,
  })
}

export function useRecommendations(category: string, model: string, enabled = true): UseQueryResult<RecommendationResponse> {
  return useQuery({
    queryKey: ['recommendations', category, model],
    queryFn: () => api.getRecommendations(category, model),
    staleTime: 300_000,
    enabled,
  })
}
