export function OfflineBanner() {
  return (
    <div className="mb-4 rounded-xl border border-negative/25 bg-negative/[0.06] px-4 py-3 text-sm text-negative">
      Backend offline — start the API with{' '}
      <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-xs">uvicorn main:app --reload</code>
      {import.meta.env.DEV && (
        <>
          {' '}or check that <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-xs">VITE_API_BASE_URL</code> points at it.
        </>
      )}
    </div>
  )
}
