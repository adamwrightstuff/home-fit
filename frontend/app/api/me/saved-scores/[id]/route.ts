import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
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
    .eq('id', id)
    .eq('user_id', user.id)
    .single()

  if (error || !data) {
    return NextResponse.json({ error: error?.message ?? 'Not found' }, { status: error?.code === 'PGRST116' ? 404 : 500 })
  }
  return NextResponse.json(data)
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = await createClient()
  if (!supabase) {
    return NextResponse.json({ error: 'Auth not configured' }, { status: 503 })
  }
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  let body: { scorePayload?: unknown; priorities?: unknown }
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  const updates: Record<string, unknown> = {}
  if (body.scorePayload != null && typeof body.scorePayload === 'object') {
    const p = body.scorePayload as Record<string, unknown>
    updates.score_payload = p
    if (typeof p.input === 'string') updates.input = p.input
    if (p.coordinates != null) updates.coordinates = p.coordinates
    if (p.location_info != null) updates.location_info = p.location_info
  }
  if (body.priorities != null && typeof body.priorities === 'object') {
    updates.priorities = body.priorities
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: 'Provide scorePayload and/or priorities' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('saved_scores')
    .update(updates)
    .eq('id', id)
    .eq('user_id', user.id)
    .select('id, input, updated_at')
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  return NextResponse.json(data)
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = await createClient()
  if (!supabase) {
    return NextResponse.json({ error: 'Auth not configured' }, { status: 503 })
  }
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { error } = await supabase
    .from('saved_scores')
    .delete()
    .eq('id', id)
    .eq('user_id', user.id)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  return new NextResponse(null, { status: 204 })
}
