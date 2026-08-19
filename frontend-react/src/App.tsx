import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { Login } from '@/pages/Login'

// Route-level code splitting: each page (and the Plotly charts it pulls
// in) only downloads when the user actually navigates there, instead of
// all six pages' JS loading upfront on first paint.
const Dashboard = lazy(() => import('@/pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const ForecastExplorer = lazy(() => import('@/pages/ForecastExplorer').then((m) => ({ default: m.ForecastExplorer })))
const AnomalyDetection = lazy(() => import('@/pages/AnomalyDetection').then((m) => ({ default: m.AnomalyDetection })))
const WhatIfSimulator = lazy(() => import('@/pages/WhatIfSimulator').then((m) => ({ default: m.WhatIfSimulator })))
const Recommendations = lazy(() => import('@/pages/Recommendations').then((m) => ({ default: m.Recommendations })))
const ModelComparison = lazy(() => import('@/pages/ModelComparison').then((m) => ({ default: m.ModelComparison })))

function PageFallback() {
  return <div className="p-6 text-sm text-text-muted">Loading…</div>
}

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<Suspense fallback={<PageFallback />}><Dashboard /></Suspense>} />
          <Route path="forecast" element={<Suspense fallback={<PageFallback />}><ForecastExplorer /></Suspense>} />
          <Route path="anomalies" element={<Suspense fallback={<PageFallback />}><AnomalyDetection /></Suspense>} />
          <Route path="whatif" element={<Suspense fallback={<PageFallback />}><WhatIfSimulator /></Suspense>} />
          <Route path="recommendations" element={<Suspense fallback={<PageFallback />}><Recommendations /></Suspense>} />
          <Route path="models" element={<Suspense fallback={<PageFallback />}><ModelComparison /></Suspense>} />
        </Route>
      </Route>
    </Routes>
  )
}
