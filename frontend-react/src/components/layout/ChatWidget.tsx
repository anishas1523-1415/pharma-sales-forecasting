import { useEffect, useRef, useState } from 'react'
import { sendChatMessage } from '@/lib/apiClient'
import { useHealth } from '@/lib/queries'

interface Message {
  role: 'user' | 'assistant'
  text: string
}

const SUGGESTIONS = [
  'Which category has sold the most overall?',
  'When was the biggest sales spike?',
  'Which category needs restocking most urgently?',
  'How accurate are the models?',
]

export function ChatWidget() {
  const { data: isConnected } = useHealth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: "Hi — I'm the PharmaForecast assistant. Ask me anything about the sales data, forecasts, or just say hello." },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    setMessages((prev) => [...prev, { role: 'user', text: trimmed }])
    setInput('')
    setBusy(true)
    setError(null)
    try {
      const { reply } = await sendChatMessage(trimmed)
      setMessages((prev) => [...prev, { role: 'assistant', text: reply }])
    } catch {
      setError("Couldn't reach the assistant — try again in a moment.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[520px] w-[380px] flex-col overflow-hidden rounded-2xl border border-border-strong bg-surface-2 shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 text-accent">
                <img src="/pharma_logo.svg" alt="" className="h-3.5 w-3.5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-text">Ask PharmaForecast</div>
                <div className="flex items-center gap-1 text-[0.68rem] text-text-faint">
                  <span className={'h-1.5 w-1.5 rounded-full ' + (isConnected ? 'bg-positive' : 'bg-negative')} />
                  {isConnected ? 'Live data' : 'Backend offline'}
                </div>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-text-faint transition-colors hover:bg-surface hover:text-text"
              aria-label="Close chat"
            >
              ✕
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.map((m, i) => (
              <div key={i} className={'flex ' + (m.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div
                  className={
                    'max-w-[85%] rounded-xl px-3 py-2 text-[0.83rem] leading-relaxed ' +
                    (m.role === 'user' ? 'bg-accent/15 text-text' : 'bg-surface text-text-muted')
                  }
                >
                  {m.text}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-xl bg-surface px-3 py-2 text-[0.83rem] text-text-faint">Thinking…</div>
              </div>
            )}
            {error && (
              <div className="rounded-lg border border-negative/25 bg-negative/[0.06] px-3 py-2 text-xs text-negative">{error}</div>
            )}

            {messages.length === 1 && (
              <div className="flex flex-wrap gap-1.5 pt-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-full border border-border px-2.5 py-1 text-[0.72rem] text-text-muted transition-colors hover:border-border-strong hover:text-text"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              send(input)
            }}
            className="flex items-center gap-2 border-t border-border p-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              disabled={busy}
              className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-border-strong disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-lg bg-accent/15 px-3 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/25 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-canvas shadow-2xl transition-transform hover:scale-105"
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          <span className="text-xl">✕</span>
        ) : (
          <span className="text-xl">💬</span>
        )}
      </button>
    </>
  )
}
