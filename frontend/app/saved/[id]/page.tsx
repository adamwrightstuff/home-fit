'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ScoreResponse } from '@/types/api'
import { useAuth } from '@/contexts/AuthContext'
import { getSavedScore, updateSavedScore, type SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { getScore } from '@/lib/api'
import type { PillarPriorities } from '@/components/SearchOptions'
import SearchOptionsComponent, { DEFAULT_PRIORITIES, type SearchOptions } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'

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
    // If saved value is None or missing, keep default (Medium) so the UI doesn't show "None" for everything.
    if (out[k] === 'None') out[k] = 'Medium'
  }
  return out as unknown as PillarPriorities
}

export default function SavedDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = typeof params.id === 'string' ? params.id : null
  const { user, loading: authLoading } = useAuth()
  const [row, setRow] = useState<SavedScoreRow | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [priorities, setPriorities] = useState<PillarPriorities | null>(null)
  const [scoreAgainLoading, setScoreAgainLoading] = useState(false)
  const [scoreAgainError, setScoreAgainError] = useState<string | null>(null)
  const [savingPreferences, setSavingPreferences] = useState(false)

  useEffect(() => {
    if (!id || !user) {
      setLoading(false)
      return
    }
    getSavedScore(id)
      .then((r) => {
        setRow(r)
        setPriorities(prioritiesFromRow(r))
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id, user])

  const searchOptions: SearchOptions = useMemo(
    () => ({
      priorities: priorities ?? DEFAULT_PRIORITIES,
      include_chains: true,
      enable_schools: false,
      job_categories: [],
      natural_beauty_preference: null,
      built_character_preference: null,
      built_density_preference: null,
    }),
    [priorities]
  )

  const handleSearchOptionsChange = useCallback((options: SearchOptions) => {
    setPriorities(options.priorities)
  }, [])

  const rawPayload = row?.score_payload as ScoreResponse | undefined
  // Depend on serialized priorities so any change in priority values triggers reweight (avoids stale display).
  const prioritiesSignature = priorities ? JSON.stringify(priorities) : ''
  const displayData = useMemo(() => {
    if (!rawPayload || !priorities) return null
    return reweightScoreResponseFromPriorities(rawPayload, priorities)
  }, [rawPayload, prioritiesSignature, priorities])

  const handleScoreAgain = useCallback(async () => {
    if (!row || !priorities) return
    setScoreAgainError(null)
    setScoreAgainLoading(true)
    try {
      const newResponse = await getScore({
        location: row.input,
        priorities: JSON.stringify(priorities),
      })
      await updateSavedScore(row.id, { scorePayload: newResponse, priorities })
      setRow((prev) =>
        prev
          ? {
              ...prev,
              score_payload: newResponse,
              priorities,
              updated_at: new Date().toISOString(),
            }
          : null
      )
    } catch (e) {
      setScoreAgainError(e instanceof Error ? e.message : 'Failed to re-run score')
    } finally {
      setScoreAgainLoading(false)
    }
  }, [row, priorities])

  const handleSavePreferences = useCallback(async () => {
    if (!row || !priorities) return
    setSavingPreferences(true)
    try {
      await updateSavedScore(row.id, { priorities })
      setRow((prev) => (prev ? { ...prev, priorities } : null))
    } finally {
      setSavingPreferences(false)
    }
  }, [row, priorities])

  if (!authLoading && !user) {
    router.replace('/saved')
    return null
  }

  if (!id) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <p className="hf-muted">Invalid saved place.</p>
          <Link href="/saved" className="hf-btn-link" style={{ marginTop: '0.5rem', display: 'inline-block' }}>
            ← My places
          </Link>
        </div>
      </main>
    )
  }

  if (loading) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <p className="hf-muted">Loading…</p>
        </div>
      </main>
    )
  }

  if (error || !row) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <p className="hf-auth-error" role="alert">{error ?? 'Not found'}</p>
          <Link href="/saved" className="hf-btn-link" style={{ marginTop: '0.5rem', display: 'inline-block' }}>
            ← My places
          </Link>
        </div>
      </main>
    )
  }

  if (!displayData) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <p className="hf-muted">Unable to display score.</p>
          <Link href="/saved" className="hf-btn-link" style={{ marginTop: '0.5rem', display: 'inline-block' }}>
            ← My places
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="hf-page">
      <div className="hf-container">
        <div style={{ marginBottom: '1rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
          <Link href="/saved" className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
            ← My places
          </Link>
          <button
            type="button"
            onClick={handleScoreAgain}
            disabled={scoreAgainLoading}
            className="hf-btn-secondary"
            style={{ padding: '0.5rem 1rem', borderRadius: 8, fontSize: '0.95rem' }}
          >
            {scoreAgainLoading ? 'Scoring…' : 'Score again'}
          </button>
          <button
            type="button"
            onClick={handleSavePreferences}
            disabled={savingPreferences || !row}
            className="hf-btn-secondary"
            style={{ padding: '0.5rem 1rem', borderRadius: 8, fontSize: '0.95rem' }}
          >
            {savingPreferences ? 'Saving…' : 'Save preferences'}
          </button>
          {scoreAgainError && (
            <span className="hf-muted" style={{ color: 'var(--hf-danger)', fontSize: '0.9rem' }}>{scoreAgainError}</span>
          )}
        </div>

        <div className="hf-card" style={{ marginBottom: '1.5rem' }}>
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>Adjust weights</div>
          <p className="hf-muted" style={{ marginBottom: '0.75rem', fontSize: '0.95rem' }}>
            Changing priorities updates the total score below instantly (no new API run). Use &quot;Score again&quot; to fetch fresh data for this place.
          </p>
          <SearchOptionsComponent
            options={searchOptions}
            onChange={handleSearchOptionsChange}
            skipSessionRestore
          />
        </div>

        <ScoreDisplay data={displayData} />
      </div>
    </main>
  )
}
