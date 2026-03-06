import { createClient as createSupabaseClient, type SupabaseClient } from '@supabase/supabase-js'

let _client: SupabaseClient | null = null

export function createClient(): SupabaseClient | null {
  if (_client) return _client
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return null
  _client = createSupabaseClient(url, key)
  return _client
}
