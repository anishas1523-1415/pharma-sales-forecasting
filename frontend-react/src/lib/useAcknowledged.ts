import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'pharmaforecast:acknowledged'

function read(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

function write(set: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]))
  } catch {
    // localStorage unavailable (private browsing etc.) — degrade silently
  }
}

/** Client-side "acknowledged" state for recommendation cards, persisted
 * across sessions. Key is `${category}:${signal}` — turns the
 * recommendations list from a static report into something you actually
 * act on, without needing a backend user-state model for this. */
export function useAcknowledged() {
  const [acknowledged, setAcknowledged] = useState<Set<string>>(() => read())

  useEffect(() => write(acknowledged), [acknowledged])

  const toggle = useCallback((key: string) => {
    setAcknowledged((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  return { acknowledged, toggle }
}
