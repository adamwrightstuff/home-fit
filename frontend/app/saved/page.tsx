'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
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
      pillarsForRank = (reweighted.livability_pillars as unknown as Record<string, { score?: number }>) ?? pillars
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

/** Prefer saved search input (e.g. "Carroll Gardens Brooklyn"); fall back to city, state zip. */
function placeDisplayName(row: SavedScoreRow): string {
  const input = typeof row.input === 'string' ? row.input.trim() : ''
  if (input) return input
  const loc = row.location_info as { city?: string; state?: string; zip?: string }
  const fallback = [loc.city ?? '', loc.state ?? '', loc.zip ?? ''].filter(Boolean).join(', ')
  return fallback || 'Unknown location'
}

export default function SavedPage() {
  const { user, loading: authLoading } = useAuth()
  const [list, setList] = useState<SavedScoreRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [compareMode, setCompareMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const router = useRouter()

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

  const toggleSelected = (id: string, hasScore: boolean) => {
    if (!compareMode || !hasScore) return
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 2) return [prev[1], id]
      return [...prev, id]
    })
  }

  const handleStartCompare = () => {
    if (selectedIds.length !== 2) return
    const [a, b] = selectedIds
    router.push(`/saved/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
  }

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <Link href="/" className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
              ← Back to search
            </Link>
            <h1 className="hf-section-title" style={{ marginBottom: '0.25rem', marginTop: '0.75rem' }}>My saved places</h1>
            <p className="hf-muted" style={{ marginBottom: 0 }}>
              {compareMode
                ? 'Select two scored places to compare side by side.'
                : 'Tap a place to view scores and adjust weights, or compare two places.'}
            </p>
          </div>
          {list.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setCompareMode((prev) => !prev)
                setSelectedIds([])
              }}
              className={compareMode ? 'hf-btn-secondary' : 'hf-btn-primary'}
              style={{ minHeight: 40, padding: '0.5rem 1rem', borderRadius: 999, fontSize: '0.9rem' }}
            >
              {compareMode ? 'Done comparing' : 'Compare places'}
            </button>
          )}
        </div>

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
              const { total, top2, bottom1 } = summaryFromPayload(row.score_payload, row)
              const hasScore = row.score_payload != null
              const selected = selectedIds.includes(row.id)
              return (
                <div
                  key={row.id}
                  className="hf-card-sm"
                  style={{
                    textDecoration: 'none',
                    color: 'inherit',
                    position: 'relative',
                    borderWidth: compareMode && selected ? 2 : undefined,
                    borderColor: compareMode && selected ? 'var(--hf-primary-1)' : undefined,
                    cursor: compareMode ? (hasScore ? 'pointer' : 'default') : 'pointer',
                  }}
                  onClick={() => {
                    if (compareMode) {
                      toggleSelected(row.id, hasScore)
                    } else {
                      router.push(`/saved/${row.id}`)
                    }
                  }}
                >
                  {compareMode && (
                    <div style={{ position: 'absolute', top: 10, right: 10 }}>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={!hasScore}
                        onChange={() => toggleSelected(row.id, hasScore)}
                        aria-label={hasScore ? 'Select place for compare' : 'Run a score first to compare'}
                      />
                    </div>
                  )}
                  <div style={{ fontWeight: 700, fontSize: '1.15rem', paddingRight: compareMode ? '1.5rem' : 0 }}>
                    {placeDisplayName(row)}
                  </div>
                  <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className="hf-score-badge hf-score-badge--blue">{total.toFixed(1)}</span>
                    <span className="hf-muted" style={{ fontSize: '0.9rem' }}>{formatDate(row.updated_at)}</span>
                  </div>
                  <div className="hf-muted" style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
                    Strongest: {top2}. Weakest: {bottom1}.
                  </div>
                  {!hasScore && (
                    <div className="hf-muted" style={{ marginTop: '0.25rem', fontSize: '0.85rem' }}>
                      Run a score first to compare this place.
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {compareMode && list.length > 0 && (
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 10,
            padding: '0.85rem 1.25rem',
            paddingLeft: 'max(1.25rem, env(safe-area-inset-left))',
            paddingRight: 'max(1.25rem, env(safe-area-inset-right))',
            paddingBottom: 'max(0.85rem, env(safe-area-inset-bottom))',
            background: 'var(--hf-card-bg)',
            borderTop: '1px solid var(--hf-border)',
            boxShadow: '0 -6px 18px rgba(0,0,0,0.06)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
              {selectedIds.length === 0 && 'Select 2 places to compare.'}
              {selectedIds.length === 1 && 'Select 1 more place to compare.'}
              {selectedIds.length === 2 && 'Ready to compare these 2 places.'}
              {selectedIds.length > 2 && 'Only the last two selected places will be compared.'}
            </div>
            <button
              type="button"
              onClick={handleStartCompare}
              disabled={selectedIds.length !== 2}
              className="hf-btn-primary"
              style={{ minWidth: 180, minHeight: 44, opacity: selectedIds.length === 2 ? 1 : 0.6 }}
            >
              {selectedIds.length === 2 ? 'Compare' : 'Select 2 places to compare'}
            </button>
          </div>
        </div>
      )}
    </main>
  )
}
