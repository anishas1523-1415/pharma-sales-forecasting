// Plotly chart factories. Same trace types as the original Streamlit charts
// (line+fill, heatmap, donut, vrect/vline shading) but restyled to the
// muted premium palette — quiet gridlines, no neon fills.

import type { Data, Layout, Shape, Annotations } from 'plotly.js'
import { MODEL_COLORS } from './constants'
import type { AnomalyResult, ForecastPoint, WhatIfPoint, MetricsResponse } from '@/types/api'
import { CATEGORIES } from './constants'

export const DARK_LAYOUT: Partial<Layout> = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Switzer, sans-serif', color: '#F4F4F5' },
  xaxis: { gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.1)', showgrid: true },
  yaxis: { gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.1)', showgrid: true },
  legend: { bgcolor: 'rgba(0,0,0,0)', bordercolor: 'rgba(255,255,255,0.08)', borderwidth: 1 },
  margin: { l: 10, r: 10, t: 40, b: 10 },
  hovermode: 'x unified',
  hoverlabel: { bgcolor: '#1B1B20', bordercolor: 'rgba(255,255,255,0.1)', font: { color: '#F4F4F5' } },
}

export function hexToRgba(hex: string, alpha = 0.1): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

export function applyDark(layout: Partial<Layout> = {}, title?: string): Partial<Layout> {
  return {
    ...DARK_LAYOUT,
    ...layout,
    ...(title ? { title: { text: title, font: { size: 15, color: '#F4F4F5' }, x: 0 } } : {}),
  }
}

export function forecastChart(
  forecast: ForecastPoint[],
  historical: { date: string; actual_sales: number }[] | null,
  category: string,
  model: string,
  showHistory: boolean,
): { data: Data[]; layout: Partial<Layout> } {
  const data: Data[] = []

  if (showHistory && historical && historical.length > 0) {
    data.push({
      x: historical.map((h) => h.date),
      y: historical.map((h) => h.actual_sales),
      name: 'Historical',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#6EA8D8', width: 2 },
      opacity: 0.8,
    })
  }

  const color = MODEL_COLORS[model.toLowerCase()] ?? '#7C6FF0'

  // Confidence band (only present for prophet/arima/sarima)
  const hasBounds = forecast.some((p) => p.lower !== undefined && p.upper !== undefined)
  if (hasBounds) {
    data.push({
      x: forecast.map((p) => p.date),
      y: forecast.map((p) => p.upper ?? p.prediction),
      name: 'Upper bound',
      type: 'scatter',
      mode: 'lines',
      line: { width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    })
    data.push({
      x: forecast.map((p) => p.date),
      y: forecast.map((p) => p.lower ?? p.prediction),
      name: 'Confidence Interval',
      type: 'scatter',
      mode: 'lines',
      line: { width: 0 },
      fill: 'tonexty',
      fillcolor: hexToRgba(color, 0.15),
      hoverinfo: 'skip',
    })
  }

  data.push({
    x: forecast.map((p) => p.date),
    y: forecast.map((p) => p.prediction),
    name: `${model.toUpperCase()} Forecast`,
    type: 'scatter',
    mode: 'lines',
    line: { color, width: 2.5 },
    fill: 'tozeroy',
    fillcolor: hexToRgba(color, 0.1),
  })

  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []
  if (showHistory && historical && historical.length > 0) {
    const sepDate = historical[historical.length - 1].date
    shapes.push({
      type: 'line',
      x0: sepDate, x1: sepDate, y0: 0, y1: 1, yref: 'paper',
      line: { dash: 'dash', color: 'rgba(176,181,192,0.5)' },
    })
    annotations.push({ x: sepDate, y: 1, yref: 'paper', text: 'Forecast →', showarrow: false, font: { color: '#98989F' } })
  }

  return { data, layout: applyDark({ shapes, annotations }, `${category} — ${model.toUpperCase()} Forecast`) }
}

export function multiModelForecastChart(
  forecastsByModel: Record<string, ForecastPoint[]>,
  historical: { date: string; actual_sales: number }[] | null,
  category: string,
): { data: Data[]; layout: Partial<Layout> } {
  const data: Data[] = []

  if (historical && historical.length > 0) {
    data.push({
      x: historical.map((h) => h.date),
      y: historical.map((h) => h.actual_sales),
      name: 'Actual',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#6EA8D8', width: 2, dash: 'dot' },
      opacity: 0.7,
    })
  }

  for (const [model, points] of Object.entries(forecastsByModel)) {
    if (!points || points.length === 0) continue
    const color = MODEL_COLORS[model.toLowerCase()] ?? '#98989F'
    data.push({
      x: points.map((p) => p.date),
      y: points.map((p) => p.prediction),
      name: model.toUpperCase(),
      type: 'scatter',
      mode: 'lines',
      line: { color, width: 2 },
    })
  }

  return { data, layout: applyDark({}, `${category} — All Models Comparison`) }
}

const SEVERITY_MARKERS: Record<string, { color: string; symbol: string; size: number }> = {
  low: { color: '#3ECF8E', symbol: 'circle', size: 8 },
  medium: { color: '#F0B429', symbol: 'circle', size: 10 },
  high: { color: '#F0596B', symbol: 'circle-open', size: 14 },
}

export function anomalyChart(results: AnomalyResult[], category: string, model: string): { data: Data[]; layout: Partial<Layout> } {
  if (!results || results.length === 0) {
    return { data: [], layout: applyDark({}, 'No overlapping data for anomaly detection') }
  }

  const data: Data[] = [
    {
      x: results.map((r) => r.date),
      y: results.map((r) => r.actual_sales),
      name: 'Actual Sales',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#6EA8D8', width: 2 },
    },
    {
      x: results.map((r) => r.date),
      y: results.map((r) => r.forecast_sales),
      name: 'Forecast',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#E8836C', width: 2, dash: 'dot' },
    },
  ]

  for (const [sev, marker] of Object.entries(SEVERITY_MARKERS)) {
    const sub = results.filter((r) => r.severity === sev)
    if (sub.length === 0) continue
    data.push({
      x: sub.map((r) => r.date),
      y: sub.map((r) => r.actual_sales),
      name: `${sev[0].toUpperCase()}${sev.slice(1)} Deviation`,
      type: 'scatter',
      mode: 'markers',
      marker: { color: marker.color, size: marker.size, symbol: marker.symbol, line: { color: marker.color, width: 2 } },
    })
  }

  return { data, layout: applyDark({}, `${category} — ${model.toUpperCase()} Anomaly Detection`) }
}

export function whatIfChart(results: WhatIfPoint[], disruptionDays: number): { data: Data[]; layout: Partial<Layout> } {
  if (!results || results.length === 0) {
    return { data: [], layout: applyDark({}, 'No data available') }
  }

  const data: Data[] = [
    {
      x: results.map((r) => r.date),
      y: results.map((r) => r.baseline_sales),
      name: 'Baseline Forecast',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#6EA8D8', width: 2.5 },
    },
    {
      x: results.map((r) => r.date),
      y: results.map((r) => r.adjusted_sales),
      name: 'Adjusted Forecast',
      type: 'scatter',
      mode: 'lines',
      line: { color: '#3ECF8E', width: 2.5 },
      fill: 'tonexty',
      fillcolor: 'rgba(62,207,142,0.06)',
    },
  ]

  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []

  if (disruptionDays > 0) {
    const disrupted = results.filter((r) => r.adjusted_sales === 0)
    if (disrupted.length > 0) {
      const x0 = disrupted[0].date
      const x1 = disrupted[disrupted.length - 1].date
      shapes.push({
        type: 'rect', x0, x1, y0: 0, y1: 1, yref: 'paper',
        fillcolor: 'rgba(240,89,107,0.18)', line: { width: 1, color: 'rgba(240,89,107,0.6)' }, layer: 'below',
      })
      annotations.push({
        x: x0, y: 1, yref: 'paper', xanchor: 'left',
        text: `🚨 Supply Disruption (${disruptionDays}d)`, showarrow: false,
        font: { color: '#F0596B', size: 12, family: 'Switzer, sans-serif' },
      })
      data.push({
        x: disrupted.map((r) => r.date),
        y: disrupted.map((r) => r.adjusted_sales),
        name: 'Stockout (0 units)',
        type: 'scatter',
        mode: 'markers',
        marker: { color: '#F0596B', size: 8, symbol: 'x' },
      })
    }
  }

  return { data, layout: applyDark({ shapes, annotations }, 'What-If Scenario — Baseline vs Adjusted') }
}

export function maeHeatmap(metrics: MetricsResponse): { data: Data[]; layout: Partial<Layout> } {
  const models = ['prophet', 'arima', 'sarima', 'lightgbm', 'lstm']
  const z = CATEGORIES.map((cat) => models.map((m) => {
    const v = metrics[cat]?.[m as keyof (typeof metrics)[string]] as { MAE?: number } | undefined
    return v?.MAE ?? null
  }))

  const data: Data[] = [{
    z,
    x: models.map((m) => m.toUpperCase()),
    y: [...CATEGORIES],
    type: 'heatmap',
    colorscale: [
      [0.0, '#3ECF8E'],
      [0.35, '#F0B429'],
      [0.7, '#E8836C'],
      [1.0, '#F0596B'],
    ],
    text: z.map((row) => row.map((v) => (v !== null ? v.toFixed(2) : 'N/A'))) as unknown as string[],
    texttemplate: '%{text}',
    hovertemplate: '<b>%{y}</b> · <b>%{x}</b><br>MAE: %{z:.2f}<extra></extra>',
    showscale: true,
    colorbar: { title: { text: 'MAE (units)', font: { color: '#F4F4F5' } }, tickfont: { color: '#F4F4F5' } },
  }]

  return { data, layout: applyDark({ margin: { l: 70, r: 10, t: 40, b: 10 } }, 'MAE Heatmap — All Categories × Models') }
}

export function modelBarChart(metrics: MetricsResponse): { data: Data[]; layout: Partial<Layout> } {
  const models = ['prophet', 'arima', 'sarima', 'lightgbm', 'lstm']
  const avgMaes = models.map((m) => {
    const vals = CATEGORIES
      .map((cat) => (metrics[cat]?.[m as keyof (typeof metrics)[string]] as { MAE?: number } | undefined)?.MAE)
      .filter((v): v is number => v !== undefined)
    return vals.length ? Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100 : 0
  })

  const data: Data[] = [{
    x: models.map((m) => m.toUpperCase()),
    y: avgMaes,
    type: 'bar',
    marker: { color: models.map((m) => MODEL_COLORS[m] ?? '#98989F'), line: { color: 'rgba(255,255,255,0.1)', width: 1 } },
    text: avgMaes.map((v) => v.toFixed(2)),
    textposition: 'outside',
    textfont: { color: '#F4F4F5' },
    hovertemplate: '<b>%{x}</b><br>Avg MAE: %{y:.2f}<extra></extra>',
  }]

  return { data, layout: applyDark({ yaxis: { ...DARK_LAYOUT.yaxis, title: { text: 'Average MAE (units)' } } }, 'Average MAE by Model (All 8 Categories)') }
}

export function severityDonut(results: AnomalyResult[]): { data: Data[]; layout: Partial<Layout> } {
  const counts = { normal: 0, moderate: 0, 'anomaly-medium': 0, 'anomaly-high': 0 }
  for (const r of results) {
    if (r.status === 'normal') counts.normal++
    else if (r.status === 'moderate') counts.moderate++
    else if (r.status === 'anomaly' && r.severity === 'medium') counts['anomaly-medium']++
    else if (r.status === 'anomaly' && r.severity === 'high') counts['anomaly-high']++
  }

  const labels = Object.keys(counts)
  const values = Object.values(counts)
  const colors = ['#3ECF8E', '#F0B429', '#E8836C', '#F0596B']

  const data: Data[] = [{
    labels, values,
    type: 'pie',
    hole: 0.55,
    marker: { colors, line: { color: 'rgba(15,20,25,0.8)', width: 2 } },
    textinfo: 'label+percent',
    textfont: { color: '#F4F4F5', size: 11 },
    hovertemplate: '<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
  }]

  return { data, layout: applyDark({ showlegend: false }, 'Severity Distribution') }
}
