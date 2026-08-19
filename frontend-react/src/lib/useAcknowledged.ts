import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { useAuth } from './AuthContext'

const STORAGE_KEY = 'pharmaforecast:acknowledged'

function readLocal(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

function writeLocal(set: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]))
  } catch {
    // localStorage unavailable (private browsing etc.) — degrade silently
  }
}

function splitKey(key: string): { category: string; signal: string } {
  const [category, ...rest] = key.split(':')
  return { category, signal: rest.join(':') }
}

/**
 * "Acknowledged" state for recommendation cards — turns the recommendations
 * list from a static report into something you actually act on. Key is
 * `${category}:${signal}`.
 *
 * Backed by Supabase (recommendation_acknowledgments, RLS-scoped to
 * auth.uid()) when signed in — real, server-side, multi-device state.
 * Falls back to localStorage when auth isn't configured or the user isn't
 * signed in, so the feature still works standalone.
 */
export function useAcknowledged() {
  const { user } = useAuth()
  const [acknowledged, setAcknowledged] = useState<Set<string>>(() => readLocal())
  const useRemote = !!supabase && !!user

  useEffect(() => {
    if (!useRemote) {
      setAcknowledged(readLocal())
      return
    }
    supabase!
      .from('recommendation_acknowledgments')
      .select('category, signal')
      .then(({ data, error }) => {
        if (error) return
        setAcknowledged(new Set((data ?? []).map((r) => `${r.category}:${r.signal}`)))
      })
  }, [useRemote, user?.id])

  useEffect(() => {
    if (!useRemote) writeLocal(acknowledged)
    // Remote writes happen per-toggle in toggle() below, not as a bulk sync.
  }, [acknowledged, useRemote])

  const toggle = useCallback(
    (key: string) => {
      const willAcknowledge = !acknowledged.has(key)
      setAcknowledged((prev) => {
        const next = new Set(prev)
        if (next.has(key)) next.delete(key)
        else next.add(key)
        return next
      })

      if (!useRemote) return
      const { category, signal } = splitKey(key)
      if (willAcknowledge) {
        supabase!.from('recommendation_acknowledgments').insert({ user_id: user!.id, category, signal }).then()
      } else {
        supabase!.from('recommendation_acknowledgments').delete().eq('user_id', user!.id).eq('category', category).eq('signal', signal).then()
      }
    },
    [acknowledged, useRemote, user],
  )

  return { acknowledged, toggle }
}
