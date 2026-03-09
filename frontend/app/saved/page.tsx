'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import { listSavedScores, type SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { PILLAR_META, PILLAR_ORDER, type PillarKey } from '@/lib/pillars'
import type { PillarPriorities } from '@/components/SearchOptions'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'

function prioritiesFromRow(row: SavedScoreRow): PillarPriorities {
  const p = row.priorities as Record<string, string> | null | undefined
  if (!p || typeof p !== 'object') return { ...DEFAULT_PRIORITIES }
  const levels = ['None', 'Low', 'Medium', 'High'] as const
  const out: Record<string, (typeof levels)[number]> = { ...DEFAULT_PRIORITIES }
  for (const k of Object.keys(out)) {
    const v = String(p[k] ?? '').trim()
    if (levels.includes(v as (typeof levels)[number])) {
      out[k] = v as (typeof levels)[number]
    }
  }
  return out as unknown as PillarPriorities
}

function summaryFromPayload(score_payload: unknown, row?: SavedScoreRow | null): { total: number; top2: string; bottom1: string } {
  const p = score_payload as Record<string, unknown>
  const pillars = (p?.livability_pillars as Record<string, { score?: number }>) ?? {}
  let total = Number(p?.total_score ?? 0)
  let pillarsForRank = pillars

  // Use same reweight as detail page so list and detail show the same score
  if (row && p && typeof p === 'object' && p !== null) {
    try {
      const priorities = prioritiesFromRow(row)
      const reweighted = reweightScoreResponseFromPriorities(score_payload as import('@/types/api').ScoreResponse, priorities)
      total = reweighted.total_score
      pillarsForRank = (reweighted.livability_pillars as Record<string, { score?: number }>) ?? pillars
    } catch {
      // keep raw total and pillars
    }
  }

  const ranked = PILLAR_ORDER.filter((k) => pillarsForRank[k]?.score != null)
    .map((k) => ({ key: k, score: Number(pillarsForRank[k]?.score ?? 0) }))
    .sort((a, b) => b.score - a.score)
  const top2 = ranked.slice(0, 2).map((r) => `${PILLAR_META[r.key].name} (${r.score.toFixed(0)})`).join(', ')
  const bottom1 = ranked.length ? `${PILLAR_META[ranked[ranked.length - 1].key].name} (${ranked[ranked.length - 1].score.toFixed(0)})` : '—'
  return { total, top2, bottom1 }
}

function formatDate(s: string): string {
  try {
    const d = new Date(s)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 86400000) return 'Today'
    if (diff < 172800000) return 'Yesterday'
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} days ago`
    return d.toLocaleDateString()
  } catch {
    return ''
  }
}

export default function SavedPage() {
  const { user, loading: authLoading } = useAuth()
  const [list, setList] = useState<SavedScoreRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    listSavedScores()
      .then(setList)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [user])

  if (!authLoading && !user) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <div className="hf-card">
            <h2 className="hf-section-title">My saved places</h2>
            <p className="hf-muted">Sign in to see and manage your saved scores.</p>
            <Link href="/" className="hf-btn-primary" style={{ marginTop: '1rem', display: 'inline-block' }}>
              Go home
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        <div style={{ marginBottom: '1.5rem' }}>
          <Link href="/" className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
            ← Back to search
          </Link>
        </div>
        <h1 className="hf-section-title" style={{ marginBottom: '0.5rem' }}>My saved places</h1>
        <p className="hf-muted" style={{ marginBottom: '1.5rem' }}>
          Tap a place to view scores and adjust weights. You can re-run the score and save again to update.
        </p>

        {loading && <p className="hf-muted">Loading…</p>}
        {error && <p className="hf-auth-error" role="alert">{error}</p>}

        {!loading && !error && list.length === 0 && (
          <div className="hf-card">
            <p className="hf-muted">No saved places yet. Score a location and click &quot;Save this place&quot; to add it here.</p>
            <Link href="/" className="hf-btn-primary" style={{ marginTop: '1rem', display: 'inline-block' }}>
              Search a place
            </Link>
          </div>
        )}

        {!loading && !error && list.length > 0 && (
          <div className="hf-grid-2" style={{ gap: '1rem' }}>
            {list.map((row) => {
              const loc = row.location_info as { city?: string; state?: string; zip?: string }
              const { total, top2, bottom1 } = summaryFromPayload(row.score_payload, row)
              return (
                <Link
                  key={row.id}
                  href={`/saved/${row.id}`}
                  className="hf-card-sm"
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div style={{ fontWeight: 700, fontSize: '1.15rem' }}>
                    {loc.city ?? ''}, {loc.state ?? ''} {loc.zip ?? ''}
                  </div>
                  <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className="hf-score-badge hf-score-badge--blue">{total.toFixed(1)}</span>
                    <span className="hf-muted" style={{ fontSize: '0.9rem' }}>{formatDate(row.updated_at)}</span>
                  </div>
                  <div className="hf-muted" style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                    Strongest: {top2}. Weakest: {bottom1}.
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </main>
  )
}
