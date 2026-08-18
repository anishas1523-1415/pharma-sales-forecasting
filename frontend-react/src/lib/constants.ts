import type { Category, ModelType } from '@/types/api'

export const CATEGORIES: Category[] = ['M01AB', 'M01AE', 'N02BA', 'N02BE', 'N05B', 'N05C', 'R03', 'R06']

export const CAT_NAMES: Record<Category, string> = {
  M01AB: 'Anti-inflammatory (NSAID)',
  M01AE: 'Propionic Acid Derivatives',
  N02BA: 'Aspirin & Salicylates',
  N02BE: 'Paracetamol & Anilides',
  N05B: 'Anxiolytics',
  N05C: 'Hypnotics / Sedatives',
  R03: 'Bronchodilators',
  R06: 'Antihistamines',
}

export const ALL_MODELS: ModelType[] = ['prophet', 'arima', 'sarima', 'lightgbm', 'lstm']

// ARIMA/SARIMA are the only models whose forecast CSVs retain a held-out
// test window (actual y alongside yhat) overlapping real historical dates.
// Prophet/LightGBM/LSTM forecast pure future dates with zero overlap
// against actuals, so anomaly matching and demand-spike detection return
// nothing for them. This restriction mirrors the original Streamlit app's
// (already-correct) behavior — see frontend/pages/3_..._Anomaly_Detection.py
// and 5_..._Recommendations.py, both hardcode MODELS = ["arima", "sarima"].
export const VALIDATION_MODELS: ModelType[] = ['arima', 'sarima']

export const MODEL_COLORS: Record<string, string> = {
  prophet: '#7C6FF0',
  arima: '#E8B86C',
  sarima: '#52C4A0',
  lightgbm: '#E8836C',
  lstm: '#6EA8D8',
}

export const MODEL_LABELS: Record<string, string> = {
  prophet: 'PROPHET',
  arima: 'ARIMA',
  sarima: 'SARIMA',
  lightgbm: 'LIGHTGBM',
  lstm: 'LSTM',
}

export const SIGNAL_DESCRIPTIONS: Record<string, string> = {
  RESTOCK_ALERT: 'Forecast shows growing demand — consider restocking inventory proactively.',
  OVERSTOCK_RISK: 'Forecast shows declining demand — reduce procurement to avoid overstock.',
  HIGH_UNCERTAINTY: 'Model MAPE is above 30% — treat forecast with additional caution.',
  STABLE_SUPPLY: 'No significant demand signals — supply chain appears balanced.',
  DEMAND_SPIKE: 'High-severity anomalies detected — investigate demand drivers urgently.',
}

export const SIGNAL_ICONS: Record<string, string> = {
  RESTOCK_ALERT: '📦',
  OVERSTOCK_RISK: '⚠️',
  HIGH_UNCERTAINTY: '🔮',
  STABLE_SUPPLY: '✅',
  DEMAND_SPIKE: '🚨',
}
