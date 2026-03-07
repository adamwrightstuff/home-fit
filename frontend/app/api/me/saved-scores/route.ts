import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET() {
  const supabase = await createClient()
  if (!supabase) {
    return NextResponse.json({ error: 'Auth not configured' }, { status: 503 })
  }
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { data, error } = await supabase
    .from('saved_scores')
    .select('id, input, coordinates, location_info, score_payload, priorities, created_at, updated_at')
    .eq('user_id', user.id)
    .order('updated_at', { ascending: false })

  if (error) {
    console.error('saved_scores list error:', error)
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  return NextResponse.json(data ?? [])
}

export async function POST(req: NextRequest) {
  const supabase = await createClient()
  if (!supabase) {
    return NextResponse.json({ error: 'Auth not configured' }, { status: 503 })
  }
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  let body: { scorePayload: unknown; priorities: unknown }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }
  const { scorePayload, priorities } = body
  if (!scorePayload || typeof scorePayload !== 'object' || !priorities || typeof priorities !== 'object') {
    return NextResponse.json({ error: 'Missing scorePayload or priorities' }, { status: 400 })
  }

  const payload = scorePayload as Record<string, unknown>
  const input = typeof payload.input === 'string' ? payload.input : ''
  const coordinates = payload.coordinates && typeof payload.coordinates === 'object' ? payload.coordinates : {}
  const location_info = payload.location_info && typeof payload.location_info === 'object' ? payload.location_info : {}
  if (!input) {
    return NextResponse.json({ error: 'scorePayload.input required' }, { status: 400 })
  }

  const row = {
    user_id: user.id,
    input,
    coordinates,
    location_info,
    score_payload: payload,
    priorities: priorities as Record<string, unknown>,
  }

  const { data, error } = await supabase
    .from('saved_scores')
    .upsert(row, { onConflict: 'user_id,input', ignoreDuplicates: false })
    .select('id, input, updated_at')
    .single()

  if (error) {
    console.error('saved_scores insert/upsert error:', error)
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  return NextResponse.json(data)
}
