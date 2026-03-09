'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ScoreResponse } from '@/types/api'
import { useAuth } from '@/contexts/AuthContext'
import { getSavedScore, updateSavedScore, type SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { getScore, getScoreWithProgress } from '@/lib/api'
import type { PillarPriorities } from '@/components/SearchOptions'
import type { PillarKey } from '@/lib/pillars'
import type { RunPillarScoreOptions } from '@/components/ScoreDisplay'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
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
  const [jobCategories, setJobCategories] = useState<string[]>([])
  const [scoreAgainLoading, setScoreAgainLoading] = useState(false)
  const [scoreAgainError, setScoreAgainError] = useState<string | null>(null)
  const [rescoringPillarKey, setRescoringPillarKey] = useState<PillarKey | null>(null)
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

  const rawPayload = row?.score_payload as ScoreResponse | undefined
  // Depend on serialized priorities so any change in priority values triggers reweight (avoids stale display).
  const prioritiesSignature = priorities ? JSON.stringify(priorities) : ''
  const displayData = useMemo(() => {
    if (!rawPayload || !priorities) return null
    return reweightScoreResponseFromPriorities(rawPayload, priorities)
  }, [rawPayload, prioritiesSignature, priorities])

  const handleScoreAgain = useCallback(async () => {
    if (!row || !priorities) return
    if (!window.confirm('Refresh all pillar data? This may take a moment')) return
    setScoreAgainError(null)
    setScoreAgainLoading(true)
    try {
      const newResponse = await getScore({
        location: row.input,
        priorities: JSON.stringify(priorities),
        job_categories: jobCategories.length > 0 ? jobCategories.join(',') : undefined,
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
  }, [row, priorities, jobCategories])

  const handleRescorePillar = useCallback(
    async (pillarKey: PillarKey) => {
      if (!row || !priorities) return
      setRescoringPillarKey(pillarKey)
      try {
        await handleRunPillarScore(pillarKey, {
          priorities,
          job_categories: jobCategories.length > 0 ? jobCategories : undefined,
          natural_beauty_preference: null,
          built_character_preference: undefined,
          built_density_preference: undefined,
          include_chains: true,
          enable_schools: false,
        })
      } finally {
        setRescoringPillarKey(null)
      }
    },
    [row, priorities, jobCategories, handleRunPillarScore]
  )

  const handleSave = useCallback(async () => {
    if (!row || !priorities) return
    setSavingPreferences(true)
    try {
      await updateSavedScore(row.id, { priorities })
      setRow((prev) => (prev ? { ...prev, priorities } : null))
    } finally {
      setSavingPreferences(false)
    }
  }, [row, priorities])

  const handleRunPillarScore = useCallback(
    async (pillarKey: PillarKey, options: RunPillarScoreOptions) => {
      if (!row) return
      const response = await getScoreWithProgress(
        {
          location: row.input,
          only: pillarKey,
          priorities: JSON.stringify(options.priorities),
          job_categories: options.job_categories?.length ? options.job_categories.join(',') : undefined,
          natural_beauty_preference: options.natural_beauty_preference?.length ? JSON.stringify(options.natural_beauty_preference) : undefined,
          built_character_preference: options.built_character_preference ?? undefined,
          built_density_preference: options.built_density_preference ?? undefined,
          include_chains: options.include_chains ?? true,
          enable_schools: options.enable_schools ?? false,
        },
        () => {}
      )
      const current = rawPayload as ScoreResponse
      const merged: ScoreResponse = {
        ...current,
        livability_pillars: {
          ...current.livability_pillars,
          [pillarKey]: (response.livability_pillars as unknown as Record<string, unknown>)[pillarKey],
        } as ScoreResponse['livability_pillars'],
        place_summary: response.place_summary ?? current.place_summary,
      }
      await updateSavedScore(row.id, { scorePayload: merged, priorities: options.priorities })
      setRow((prev) =>
        prev
          ? {
              ...prev,
              score_payload: merged,
              priorities: options.priorities,
              updated_at: new Date().toISOString(),
            }
          : null
      )
      setPriorities(options.priorities)
    },
    [row, rawPayload]
  )

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
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        <nav
          className="hf-saved-detail-nav"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '0.75rem',
            marginBottom: '1rem',
          }}
          aria-label="Actions"
        >
          <Link href="/saved" className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
            ← My places
          </Link>
          <button
            type="button"
            onClick={handleScoreAgain}
            disabled={scoreAgainLoading}
            className="hf-btn-link"
            style={{ fontSize: '0.95rem', padding: '0.5rem 0.75rem' }}
          >
            {scoreAgainLoading ? 'Refreshing…' : 'Refresh data'}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={savingPreferences || !row}
            className="hf-btn-secondary"
            style={{ padding: '0.5rem 1rem', borderRadius: 8, fontSize: '0.95rem', minHeight: 44 }}
          >
            {savingPreferences ? 'Saving…' : 'Save'}
          </button>
          {scoreAgainError && (
            <span className="hf-muted" style={{ color: 'var(--hf-danger)', fontSize: '0.9rem' }}>{scoreAgainError}</span>
          )}
        </nav>

        <ScoreDisplay
          data={displayData}
          priorities={priorities ?? DEFAULT_PRIORITIES}
          onPrioritiesChange={(next) => setPriorities(next)}
          placeSummary={displayData.place_summary ?? null}
          onRunPillarScore={handleRunPillarScore}
          onRescorePillar={handleRescorePillar}
          rescoringPillarKey={rescoringPillarKey}
        />
      </div>
    </main>
  )
}
