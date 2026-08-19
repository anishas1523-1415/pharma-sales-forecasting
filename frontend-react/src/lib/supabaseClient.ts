import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// The anon key is meant to be public — every table it can reach is gated
// by Row Level Security (see the recommendation_acknowledgments migration),
// not by keeping this key secret. Auth itself (session cookies/tokens) is
// what actually protects a user's data.
export const supabase = url && anonKey ? createClient(url, anonKey) : null
