import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export const dataMode = import.meta.env.VITE_DATA_MODE ?? 'demo'
// Keep API calls same-origin by default. In development Vite proxies `/api`
// to the local FastAPI service; in a hosted deployment the reverse proxy can
// route the same path without exposing a browser-local address.
export const apiUrl = import.meta.env.VITE_API_URL ?? ''

let client: SupabaseClient | null = null

export function getSupabase(): SupabaseClient | null {
  if (dataMode !== 'supabase') return null
  const url = import.meta.env.VITE_SUPABASE_URL
  const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
  if (!url || !key) return null
  client ??= createClient(url, key)
  return client
}

export async function accessToken(): Promise<string | null> {
  const supabase = getSupabase()
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
