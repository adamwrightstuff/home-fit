'use client'

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ScoreResponse } from '@/types/api'
import { useAuth } from '@/contexts/AuthContext'
import { deleteSavedScore, getSavedScore, updateSavedScore, type SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { getScore, getScoreWithProgress, recomputeComposites } from '@/lib/api'
import type { PillarPriorities, SearchOptions } from '@/components/SearchOptions'
import type { PillarKey } from '@/lib/pillars'
import type { RunPillarScoreOptions } from '@/components/ScoreDisplay'
import { DEFAULT_PRIORITIES, PREMIUM_CODE_KEY } from '@/components/SearchOptions'
import ScoreDisplay from '@/components/ScoreDisplay'
import InteractiveMap from '@/components/InteractiveMap'
import HomeFitInfo from '@/components/HomeFitInfo'
import LongevityInfo from '@/components/LongevityInfo'
import StatusSignalInfo from '@/components/StatusSignalInfo'
import HappinessInfo from '@/components/HappinessInfo'
import { longevityIndexFromLivabilityPillars, HOMEFIT_COPY, STATUS_SIGNAL_ONLY_PILLARS } from '@/lib/pillars'

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
  const [statusSignalRefreshLoading, setStatusSignalRefreshLoading] = useState(false)
  const [recomputeLoading, setRecomputeLoading] = useState(false)
  const [rescoringPillarKey, setRescoringPillarKey] = useState<PillarKey | null>(null)
  const [savingPreferences, setSavingPreferences] = useState(false)
  const [removeLoading, setRemoveLoading] = useState(false)
  const [searchOptions, setSearchOptions] = useState<SearchOptions | null>(null)
  const [premiumCodeInput, setPremiumCodeInput] = useState('')
  const [savedPremiumCode, setSavedPremiumCode] = useState('')

  useEffect(() => {
    try {
      const v = typeof window !== 'undefined' ? window.sessionStorage?.getItem(PREMIUM_CODE_KEY) ?? '' : ''
      setSavedPremiumCode(v)
      setPremiumCodeInput(v)
    } catch {
      setSavedPremiumCode('')
    }
  }, [])

  useEffect(() => {
    if (!id || !user) {
      setLoading(false)
      return
    }
    getSavedScore(id)
      .then((r) => {
        setRow(r)
        const rowPriorities = prioritiesFromRow(r)
        setPriorities(rowPriorities)
        const payload = r.score_payload as ScoreResponse | undefined
        const saved = (payload?.metadata as any)?.saved_search_options
        let storedPremium = ''
        try {
          storedPremium = typeof window !== 'undefined' ? window.sessionStorage?.getItem(PREMIUM_CODE_KEY) ?? '' : ''
        } catch {
          storedPremium = ''
        }
        const initialSearchOptions: SearchOptions = {
          priorities: rowPriorities,
          include_chains: Boolean(saved?.include_chains),
          // Match SearchOptions: do not show "schools on" without a code in this browser.
          enable_schools: Boolean(saved?.enable_schools) && Boolean(storedPremium),
          job_categories: Array.isArray(saved?.job_categories) ? saved.job_categories : [],
          natural_beauty_preference: Array.isArray(saved?.natural_beauty_preference)
            ? saved.natural_beauty_preference
            : null,
          built_character_preference:
            typeof saved?.built_character_preference === 'string' ? saved.built_character_preference : null,
          built_density_preference:
            typeof saved?.built_density_preference === 'string' ? saved.built_density_preference : null,
          diversity_preference: Array.isArray(saved?.diversity_preference) ? saved.diversity_preference : null,
        }
        setSearchOptions(initialSearchOptions)
        setJobCategories(initialSearchOptions.job_categories ?? [])
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id, user])

  const rawPayload = row?.score_payload as ScoreResponse | undefined
  const displayData = useMemo(() => {
    if (!rawPayload || !priorities) return null
    const rew = reweightScoreResponseFromPriorities(rawPayload, priorities)
    const li = longevityIndexFromLivabilityPillars(
      rew.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
    )
    if (li != null) return { ...rew, longevity_index: li }
    return rew
  }, [rawPayload, priorities])

  const handleScoreAgain = useCallback(async () => {
    if (!row || !priorities) return
    if (
      !window.confirm(
        'Refresh all pillar data for this place?\n\nThis will overwrite your existing pillar scores and longevity index with freshly pulled data and cannot be undone.'
      )
    ) {
      return
    }
    setScoreAgainError(null)
    setScoreAgainLoading(true)
    try {
      const coords = rawPayload?.coordinates ?? row.coordinates
      const lat = typeof coords?.lat === 'number' && Number.isFinite(coords.lat) ? coords.lat : undefined
      const lon = typeof coords?.lon === 'number' && Number.isFinite(coords.lon) ? coords.lon : undefined
      const newResponse = await getScore({
        location: row.input,
        priorities: JSON.stringify(priorities),
        job_categories: jobCategories.length > 0 ? jobCategories.join(',') : undefined,
        include_chains: searchOptions?.include_chains ?? true,
        enable_schools: searchOptions?.enable_schools ?? false,
        natural_beauty_preference: searchOptions?.natural_beauty_preference?.length
          ? JSON.stringify(searchOptions.natural_beauty_preference)
          : undefined,
        built_character_preference: searchOptions?.built_character_preference ?? undefined,
        built_density_preference: searchOptions?.built_density_preference ?? undefined,
        diversity_preference: searchOptions?.diversity_preference?.length
          ? JSON.stringify(searchOptions.diversity_preference)
          : undefined,
        ...(lat != null && lon != null ? { lat, lon } : {}),
      })
      const payloadWithConfig: ScoreResponse = {
        ...newResponse,
        // Allow custom metadata field for saved search options.
        metadata: {
          ...(newResponse.metadata ?? {}),
          saved_search_options: searchOptions,
        } as any,
      }
      await updateSavedScore(row.id, { scorePayload: payloadWithConfig, priorities })
      setRow((prev) =>
        prev
          ? {
              ...prev,
              score_payload: payloadWithConfig,
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
  }, [row, priorities, jobCategories, searchOptions, rawPayload])

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
          diversity_preference:
            options.diversity_preference?.length ? JSON.stringify(options.diversity_preference) : undefined,
          include_chains: options.include_chains ?? true,
          enable_schools: options.enable_schools ?? false,
        },
        () => {}
      )
      const current = rawPayload as ScoreResponse
      const mergedBase: ScoreResponse = {
        ...current,
        livability_pillars: {
          ...current.livability_pillars,
          [pillarKey]: (response.livability_pillars as unknown as Record<string, unknown>)[pillarKey],
        } as ScoreResponse['livability_pillars'],
        place_summary: response.place_summary ?? current.place_summary,
      }
      const merged: ScoreResponse = {
        ...mergedBase,
        // Allow custom metadata field for saved search options.
        metadata: {
          ...(mergedBase.metadata ?? {}),
          saved_search_options: searchOptions,
        } as any,
      }
      if (typeof (response as { happiness_index?: number }).happiness_index === 'number') {
        merged.happiness_index = (response as { happiness_index: number }).happiness_index
      }
      if ((response as { happiness_index_breakdown?: Record<string, unknown> }).happiness_index_breakdown != null) {
        merged.happiness_index_breakdown = (response as { happiness_index_breakdown: Record<string, unknown> }).happiness_index_breakdown
      }
      let toSave = reweightScoreResponseFromPriorities(merged, options.priorities)
      {
        const li = longevityIndexFromLivabilityPillars(
          toSave.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
        )
        if (li != null) toSave = { ...toSave, longevity_index: li }
      }
      await updateSavedScore(row.id, { scorePayload: toSave, priorities: options.priorities })
      setRow((prev) =>
        prev
          ? {
              ...prev,
              score_payload: toSave,
              priorities: options.priorities,
              updated_at: new Date().toISOString(),
            }
          : null
      )
      setPriorities(options.priorities)
    },
    [row, rawPayload, searchOptions]
  )

  const handleRefreshStatusSignal = useCallback(async () => {
    if (!row) throw new Error('Saved place not loaded.')
    const location = typeof row.input === 'string' ? row.input.trim() : ''
    if (!location) throw new Error('No address for this place.')
    const coords = rawPayload?.coordinates ?? row.coordinates
    const lat = typeof coords?.lat === 'number' && Number.isFinite(coords.lat) ? coords.lat : undefined
    const lon = typeof coords?.lon === 'number' && Number.isFinite(coords.lon) ? coords.lon : undefined
    setStatusSignalRefreshLoading(true)
    try {
      const statusPillarKeys = STATUS_SIGNAL_ONLY_PILLARS.split(',')
      const prioritiesForFour: Record<string, string> = {}
      statusPillarKeys.forEach((k) => {
        prioritiesForFour[k] = (priorities && (priorities as unknown as Record<string, string>)[k]) ?? 'Medium'
      })
      const response = await getScoreWithProgress(
        {
          location,
          only: STATUS_SIGNAL_ONLY_PILLARS,
          priorities: JSON.stringify(prioritiesForFour),
          ...(lat != null && lon != null ? { lat, lon } : {}),
          ...(jobCategories.length > 0 ? { job_categories: jobCategories.join(',') } : {}),
          ...(searchOptions?.natural_beauty_preference?.length
            ? { natural_beauty_preference: JSON.stringify(searchOptions.natural_beauty_preference) }
            : {}),
          ...(searchOptions?.built_character_preference
            ? { built_character_preference: searchOptions.built_character_preference }
            : {}),
          ...(searchOptions?.built_density_preference
            ? { built_density_preference: searchOptions.built_density_preference }
            : {}),
          ...(searchOptions?.diversity_preference?.length
            ? { diversity_preference: JSON.stringify(searchOptions.diversity_preference) }
            : {}),
          include_chains: searchOptions?.include_chains ?? true,
          enable_schools: searchOptions?.enable_schools ?? false,
        },
        () => {}
      )
      const current = rawPayload as ScoreResponse
      const statusKeys = STATUS_SIGNAL_ONLY_PILLARS.split(',')
      const incoming = response.livability_pillars as unknown as Record<string, unknown>
      const mergedPillars = { ...(current.livability_pillars ?? {}), ...Object.fromEntries(statusKeys.map((k) => [k, incoming[k]]).filter(([, v]) => v != null)) }
      const mergedBase: ScoreResponse = {
        ...current,
        livability_pillars: mergedPillars as ScoreResponse['livability_pillars'],
        place_summary: response.place_summary ?? current.place_summary,
        status_signal: typeof (response as { status_signal?: number }).status_signal === 'number' ? (response as { status_signal: number }).status_signal : current.status_signal,
        happiness_index: typeof (response as { happiness_index?: number }).happiness_index === 'number' ? (response as { happiness_index: number }).happiness_index : current.happiness_index,
        happiness_index_breakdown: (response as { happiness_index_breakdown?: Record<string, unknown> }).happiness_index_breakdown ?? current.happiness_index_breakdown,
      }
      const merged: ScoreResponse = {
        ...mergedBase,
        metadata: { ...(mergedBase.metadata ?? {}), saved_search_options: searchOptions } as any,
      }
      {
        const li = longevityIndexFromLivabilityPillars(
          merged.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
        )
        if (li != null) merged.longevity_index = li
      }
      await updateSavedScore(row.id, { scorePayload: merged, priorities })
      setRow((prev) => (prev ? { ...prev, score_payload: merged, updated_at: new Date().toISOString() } : null))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Refresh failed.'
      throw new Error(msg)
    } finally {
      setStatusSignalRefreshLoading(false)
    }
  }, [row, rawPayload, priorities, jobCategories, searchOptions])

  const handleRecomputeComposites = useCallback(async () => {
    if (!row || !rawPayload) return
    const pillars = rawPayload.livability_pillars
    if (!pillars || Object.keys(pillars).length === 0) {
      setError('No pillar data to recompute indices from.')
      return
    }
    setRecomputeLoading(true)
    setError(null)
    try {
      const resp = await recomputeComposites({
        livability_pillars: pillars,
        location_info: rawPayload.location_info,
        coordinates: rawPayload.coordinates,
        token_allocation: rawPayload.token_allocation,
      })
      const current = rawPayload as ScoreResponse
      const merged: ScoreResponse = {
        ...current,
        longevity_index: resp.longevity_index ?? current.longevity_index,
        longevity_index_contributions: resp.longevity_index_contributions ?? (current as any).longevity_index_contributions,
        status_signal: resp.status_signal ?? current.status_signal,
        status_signal_breakdown: resp.status_signal_breakdown ?? (current as any).status_signal_breakdown,
        happiness_index: resp.happiness_index ?? current.happiness_index,
        happiness_index_breakdown: resp.happiness_index_breakdown ?? current.happiness_index_breakdown,
        metadata: { ...(current.metadata ?? {}), saved_search_options: searchOptions ?? undefined } as any,
      }
      await updateSavedScore(row.id, { scorePayload: merged, priorities: priorities ?? undefined })
      setRow((prev) => (prev ? { ...prev, score_payload: merged, updated_at: new Date().toISOString() } : null))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh indices.')
    } finally {
      setRecomputeLoading(false)
    }
  }, [row, rawPayload, priorities, searchOptions])

  const handleRescorePillar = useCallback(
    async (pillarKey: PillarKey) => {
      if (!row || !priorities) return
      setRescoringPillarKey(pillarKey)
      try {
        await handleRunPillarScore(pillarKey, {
          priorities,
          job_categories: jobCategories.length > 0 ? jobCategories : undefined,
          natural_beauty_preference: searchOptions?.natural_beauty_preference ?? null,
          built_character_preference: searchOptions?.built_character_preference ?? undefined,
          built_density_preference: searchOptions?.built_density_preference ?? undefined,
          include_chains: searchOptions?.include_chains ?? false,
          enable_schools: searchOptions?.enable_schools ?? false,
        })
      } finally {
        setRescoringPillarKey(null)
      }
    },
    [row, priorities, jobCategories, handleRunPillarScore, searchOptions]
  )

  const handleSave = useCallback(async () => {
    if (!row || !priorities) return
    setSavingPreferences(true)
    try {
      const payload = row.score_payload as ScoreResponse
      const mergedPayload: ScoreResponse = {
        ...payload,
        metadata: {
          ...(payload.metadata ?? {}),
          saved_search_options: searchOptions ?? undefined,
        } as ScoreResponse['metadata'],
      }
      await updateSavedScore(row.id, { priorities, scorePayload: mergedPayload })
      setRow((prev) => (prev ? { ...prev, priorities, score_payload: mergedPayload } : null))
    } finally {
      setSavingPreferences(false)
    }
  }, [row, priorities, searchOptions])

  const handleRemoveSaved = useCallback(async () => {
    if (!row || removeLoading) return
    if (!window.confirm('Remove this place from your saved list? This cannot be undone.')) return
    setRemoveLoading(true)
    try {
      await deleteSavedScore(row.id)
      router.push('/saved')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove place.')
    } finally {
      setRemoveLoading(false)
    }
  }, [row, removeLoading, router])

  const schoolsPremiumSection: ReactNode = useMemo(() => {
    if (!searchOptions) return null
    const premiumCodeSynced =
      savedPremiumCode !== '' && premiumCodeInput.trim() === savedPremiumCode
    return (
      <div>
        <div className="hf-label" style={{ marginBottom: '0.35rem' }}>
          School scoring (Premium)
        </div>
        <p className="hf-muted" style={{ fontSize: '0.88rem', marginBottom: '0.75rem', lineHeight: 1.45 }}>
          Code is saved in this browser (same as home search). Turn on Include school scoring, then use the page{' '}
          <strong>Save</strong> button to store preferences on this place. Use <strong>Rescore this pillar</strong> below or{' '}
          <strong>Refresh data</strong> for a full rerun.
        </p>
        <label className="hf-muted" style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.35rem' }}>
          Premium code
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.65rem' }}>
          <input
            type="text"
            value={premiumCodeInput}
            onChange={(e) => setPremiumCodeInput(e.target.value)}
            placeholder="Enter code"
            className="hf-input"
            autoComplete="off"
            style={{ flex: 1, minWidth: 160 }}
          />
          {premiumCodeSynced ? (
            <span
              className="hf-premium-btn"
              style={{ opacity: 0.9, cursor: 'default', pointerEvents: 'none' }}
              aria-live="polite"
            >
              Saved
            </span>
          ) : (
            <button
              type="button"
              onClick={() => {
                const v = premiumCodeInput.trim()
                setSavedPremiumCode(v)
                try {
                  if (v) window.sessionStorage?.setItem(PREMIUM_CODE_KEY, v)
                  else window.sessionStorage?.removeItem(PREMIUM_CODE_KEY)
                } catch {
                  /* ignore */
                }
                if (!v) {
                  setSearchOptions((prev) => (prev ? { ...prev, enable_schools: false } : null))
                }
              }}
              className="hf-premium-btn"
            >
              Save code
            </button>
          )}
          {savedPremiumCode ? (
            <button
              type="button"
              onClick={() => {
                setPremiumCodeInput('')
                setSavedPremiumCode('')
                try {
                  window.sessionStorage?.removeItem(PREMIUM_CODE_KEY)
                } catch {
                  /* ignore */
                }
                setSearchOptions((prev) => (prev ? { ...prev, enable_schools: false } : null))
              }}
              className="hf-premium-btn hf-premium-btn--outline"
            >
              Clear
            </button>
          ) : null}
        </div>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.9rem',
            cursor: savedPremiumCode ? 'pointer' : 'not-allowed',
          }}
        >
          <input
            type="checkbox"
            checked={searchOptions.enable_schools}
            disabled={!savedPremiumCode}
            onChange={(e) => {
              if (!savedPremiumCode) return
              setSearchOptions({ ...searchOptions, enable_schools: e.target.checked })
            }}
          />
          <span style={{ color: 'var(--hf-text-primary)' }}>Include school scoring</span>
        </label>
        {!savedPremiumCode ? (
          <p className="hf-muted" style={{ fontSize: '0.82rem', marginTop: '0.5rem', marginBottom: 0 }}>
            Save a Premium code above to enable school scoring for this session.
          </p>
        ) : null}
      </div>
    )
  }, [searchOptions, premiumCodeInput, savedPremiumCode])

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

  const locationLabel =
    (typeof row.input === 'string' && row.input.trim()) ||
    [row.location_info?.city, row.location_info?.state, row.location_info?.zip]
      .filter(Boolean)
      .join(', ') ||
    'Unknown location'
  const coordinates = rawPayload?.coordinates ?? row.coordinates
  const totalScore = displayData.total_score
  const longevityIndex = typeof displayData.longevity_index === 'number' ? displayData.longevity_index : null
  const happinessIndex = typeof displayData.happiness_index === 'number' ? displayData.happiness_index : null
  const { location_info } = displayData

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        <div className="hf-card" style={{ marginTop: '1.5rem', paddingBottom: '1.5rem' }}>
          {/* Header row: location block (View Results style) + Saved actions */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            <div
              style={{
                minWidth: 0,
                flex: '1 1 260px',
                padding: '1rem 1.25rem',
                background: 'var(--hf-bg-subtle)',
                borderRadius: 12,
                border: '1px solid var(--hf-border)',
              }}
            >
              <div className="hf-label" style={{ marginBottom: '0.25rem' }}>
                Score summary for
              </div>
              <div style={{ fontSize: 'clamp(1.35rem, 4vw, 1.8rem)', fontWeight: 800, color: 'var(--hf-text-primary)' }}>
                {locationLabel}
              </div>
              <div className="hf-muted" style={{ marginTop: '0.5rem', fontSize: '0.95rem' }}>
                Location: {location_info?.city}, {location_info?.state} {location_info?.zip}
              </div>
              <div className="hf-muted" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
                Coordinates: {coordinates.lat.toFixed(6)}, {coordinates.lon.toFixed(6)}
              </div>
            </div>

            <nav
              className="hf-saved-detail-nav"
              aria-label="Actions"
              style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}
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
                style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', minHeight: 44 }}
              >
                {savingPreferences ? 'Saving…' : 'Save'}
              </button>
              <button
                type="button"
                onClick={handleRemoveSaved}
                disabled={removeLoading}
                className="hf-btn-link"
                style={{ fontSize: '0.95rem', padding: '0.5rem 0.75rem', color: 'var(--hf-danger)' }}
              >
                {removeLoading ? 'Removing…' : 'Remove from saved'}
              </button>
              {scoreAgainError && (
                <span className="hf-muted" style={{ color: 'var(--hf-danger)', fontSize: '0.9rem' }}>
                  {scoreAgainError}
                </span>
              )}
            </nav>
          </div>

          {/* Map */}
          <div
            style={{
              width: '100%',
              height: '280px',
              borderRadius: 12,
              overflow: 'hidden',
              marginBottom: '1.5rem',
              background: 'var(--hf-bg-subtle)',
            }}
          >
            <InteractiveMap
              location={locationLabel}
              coordinates={coordinates}
              completed_pillars={Object.keys(displayData.livability_pillars ?? {})}
            />
          </div>

          {/* HomeFit on top, Longevity & Status Signal below (same layout as PlaceView) */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              marginBottom: 0,
              padding: '1rem 0.75rem',
            }}
          >
            <div
              style={{
                fontSize: '2.25rem',
                fontWeight: 800,
                color: totalScore != null ? 'var(--c-purple-600)' : 'var(--hf-text-secondary)',
                lineHeight: 1.1,
              }}
            >
              {totalScore != null ? totalScore.toFixed(1) : '—'}
            </div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                fontSize: '0.875rem',
                fontWeight: 600,
                color: 'var(--hf-text-secondary)',
                marginTop: '0.25rem',
              }}
            >
              HomeFit Score
              <HomeFitInfo />
            </div>
            <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem', textAlign: 'center', maxWidth: 320 }}>
              {HOMEFIT_COPY.subtitle}
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexWrap: 'wrap',
                gap: '1.25rem',
                marginTop: '1rem',
                fontSize: '0.8rem',
                color: 'var(--hf-text-secondary)',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="hf-muted">Longevity Index</span>
                <span style={{ fontWeight: 600, color: longevityIndex != null ? 'var(--c-teal-600)' : 'var(--hf-text-secondary)' }}>
                  {longevityIndex != null ? longevityIndex.toFixed(1) : '—'}
                </span>
                <LongevityInfo />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="hf-muted">Status Signal</span>
                <span
                  style={{
                    fontWeight: 600,
                    color:
                      typeof displayData.status_signal === 'number' ? 'var(--c-coral-600)' : 'var(--hf-text-secondary)',
                  }}
                >
                  {typeof displayData.status_signal === 'number' ? Math.max(0, Math.min(100, displayData.status_signal)).toFixed(1) : '—'}
                </span>
                <StatusSignalInfo
                  onRefresh={handleRefreshStatusSignal}
                  refreshing={statusSignalRefreshLoading}
                  breakdown={displayData.status_signal_breakdown ?? null}
                  compositeScore={typeof displayData.status_signal === 'number' ? displayData.status_signal : null}
                />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <span className="hf-muted">Happiness Index</span>
                <span style={{ fontWeight: 600, color: happinessIndex != null ? 'var(--c-blue-600)' : 'var(--hf-text-secondary)' }}>
                  {happinessIndex != null ? Math.max(0, Math.min(100, happinessIndex)).toFixed(1) : '—'}
                </span>
                <HappinessInfo />
              </span>
              <button
                type="button"
                onClick={() => handleRecomputeComposites()}
                disabled={recomputeLoading}
                className="hf-btn-link"
                style={{ marginLeft: '0.5rem', fontSize: '0.75rem', opacity: recomputeLoading ? 0.6 : 1 }}
                aria-label="Refresh indices"
              >
                {recomputeLoading ? 'Refreshing…' : 'Refresh indices'}
              </button>
            </div>
          </div>
        </div>

        <ScoreDisplay
          hideSummaryCard
          data={displayData}
          priorities={priorities ?? DEFAULT_PRIORITIES}
          onPrioritiesChange={(next) => setPriorities(next)}
          placeSummary={displayData.place_summary ?? null}
          searchOptions={searchOptions}
          onSearchOptionsChange={(next) => {
            setSearchOptions(next)
            setJobCategories(next.job_categories ?? [])
          }}
          onRunPillarScore={handleRunPillarScore}
          onRescorePillar={handleRescorePillar}
          rescoringPillarKey={rescoringPillarKey}
          schoolsPremiumSection={schoolsPremiumSection}
        />
      </div>
    </main>
  )
}
