import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

/**
 * Public read-only endpoint for shared saved scores.
 * No authentication required — only rows with is_public=true are accessible.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = await createClient()
  if (!supabase) {
    return NextResponse.json({ error: 'Service unavailable' }, { status: 503 })
  }

  const { data, error } = await supabase
    .from('saved_scores')
    .select('id, input, coordinates, location_info, score_payload, priorities, created_at')
    .eq('id', id)
    .eq('is_public', true)
    .single()

  if (error || !data) {
    return NextResponse.json(
      { error: 'Not found or not publicly shared' },
      { status: 404 }
    )
  }

  return NextResponse.json(data)
}
