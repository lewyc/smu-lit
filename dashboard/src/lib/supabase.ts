import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export const dataMode = import.meta.env.VITE_DATA_MODE ?? 'demo'
export const apiUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

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
