import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET() {
  const supabase = await createClient()
  if (!supabase) return NextResponse.json({ explorer_options: null })
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ explorer_options: null })
  const { data } = await supabase
    .from('user_preferences')
    .select('explorer_options')
    .eq('user_id', user.id)
    .single()
  return NextResponse.json({ explorer_options: data?.explorer_options ?? null })
}

export async function PUT(req: Request) {
  const supabase = await createClient()
  if (!supabase) return NextResponse.json({ ok: false }, { status: 503 })
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ ok: false }, { status: 401 })
  const body = await req.json()
  const { error } = await supabase
    .from('user_preferences')
    .upsert({ user_id: user.id, explorer_options: body }, { onConflict: 'user_id' })
  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
