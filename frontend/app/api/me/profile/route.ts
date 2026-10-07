import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { sanitizeProfile } from '@/lib/userProfile'

export async function GET() {
  const supabase = await createClient()
  if (!supabase) return NextResponse.json({ profile: null })
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ profile: null })
  const { data } = await supabase
    .from('user_preferences')
    .select('profile')
    .eq('user_id', user.id)
    .maybeSingle()
  return NextResponse.json({ profile: data?.profile ?? null })
}

/** Merges the validated keys in the body into the stored profile (absent keys are left alone). */
export async function PUT(req: Request) {
  const supabase = await createClient()
  if (!supabase) return NextResponse.json({ ok: false }, { status: 503 })
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ ok: false }, { status: 401 })

  let body: unknown
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'Invalid JSON' }, { status: 400 })
  }
  const patch = sanitizeProfile(body)

  const { data: existing } = await supabase
    .from('user_preferences')
    .select('profile')
    .eq('user_id', user.id)
    .maybeSingle()
  const merged = { ...sanitizeProfile(existing?.profile), ...patch }

  const { error } = await supabase
    .from('user_preferences')
    .upsert({ user_id: user.id, profile: merged }, { onConflict: 'user_id' })
  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
