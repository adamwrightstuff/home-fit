'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import SmartLoadingScreen from '@/components/SmartLoadingScreen'
import ScoreDisplay, { type RunPillarScoreOptions } from '@/components/ScoreDisplay'
import type { PillarPriorities, SearchOptions } from '@/components/SearchOptions'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { Metadata, ScoreResponse } from '@/types/api'
import type { PillarKey } from '@/lib/pillars'
import {
  PILLAR_ORDER,
  longevityIndexFromLivabilityPillars,
  HOMEFIT_COPY,
  STATUS_SIGNAL_ONLY_PILLARS,
} from '@/lib/pillars'
import { getScoreSinglePillar, getScoreWithProgress, recomputeComposites } from '@/lib/api'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { buildResultsCacheKey, buildResultsUrl, type ResultsRouteParams } from '@/lib/resultsShare'
import { readAndConsumeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import InteractiveMap from '@/components/InteractiveMap'
import HomeFitInfo from '@/components/HomeFitInfo'
import LongevityInfo from '@/components/LongevityInfo'
import StatusSignalInfo from '@/components/StatusSignalInfo'
import HappinessInfo from '@/components/HappinessInfo'
import { useAuth } from '@/contexts/AuthContext'
import { saveScore } from '@/lib/savedScores'

type RawSearchParams = Record<string, string | string[] | undefined>

type Normalized = Required<Pick<ResultsRouteParams, 'location' | 'prioritiesJson'>> &
  Omit<ResultsRouteParams, 'location' | 'prioritiesJson'> & {
    job_categories: string | null
    include_chains: boolean
    enable_schools: boolean
    natural_beauty_preference: string | null
    built_character_preference: string | null
    built_density_preference: string | null
  }

type CacheEntry = { ts: number; payload: ScoreResponse }

const CACHE_TTL_MS = 6 * 60 * 60 * 1000

function firstParam(v: string | string[] | undefined): string | null {
  if (typeof v === 'string') return v
  if (Array.isArray(v)) return v[0] ?? null
  return null
}

function normalizeSearchParams(sp: RawSearchParams): Normalized | null {
  const location = (firstParam(sp.location) || '').trim()
  if (!location) return null

  const prioritiesRaw = firstParam(sp.priorities)
  let prioritiesJson = ''
  try {
    if (prioritiesRaw) {
      const obj = JSON.parse(prioritiesRaw)
      prioritiesJson = JSON.stringify(obj)
    }
  } catch {
    // ignore; fall back to default priorities
  }
  if (!prioritiesJson) prioritiesJson = JSON.stringify(DEFAULT_PRIORITIES)

  const job_categories = firstParam(sp.job_categories)

  const include_chains = (() => {
    const raw = firstParam(sp.include_chains)
    if (raw == null) return false
    return raw === '1' || raw.toLowerCase() === 'true'
  })()

  const enable_schools = (() => {
    const raw = firstParam(sp.enable_schools)
    if (raw == null) return false
    return raw === '1' || raw.toLowerCase() === 'true'
  })()

  const natural_beauty_preference = firstParam(sp.natural_beauty_preference)
  const built_character_preference = firstParam(sp.built_character_preference)
  const built_density_preference = firstParam(sp.built_density_preference)

  return {
    location,
    prioritiesJson,
    job_categories: job_categories && job_categories.trim() ? job_categories.trim() : null,
    include_chains,
    enable_schools,
    natural_beauty_preference: natural_beauty_preference && natural_beauty_preference.trim() ? natural_beauty_preference : null,
    built_character_preference: built_character_preference && built_character_preference.trim() ? built_character_preference : null,
    built_density_preference: built_density_preference && built_density_preference.trim() ? built_density_preference : null,
  }
}

function safeParseCache(raw: string | null): CacheEntry | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed.ts !== 'number' || !parsed.payload) return null
    return parsed as CacheEntry
  } catch {
    return null
  }
}

function buildProgressivePayload(n: Normalized, partial: Record<string, { score: number }>): ScoreResponse {
  const pillars: Record<string, any> = {}
  for (const k of PILLAR_ORDER) {
    const s = partial[k]?.score
    pillars[k] = {
      score: typeof s === 'number' ? s : 0,
      weight: 0,
      contribution: 0,
      confidence: typeof s === 'number' ? 50 : 0,
      data_quality: { quality_tier: typeof s === 'number' ? 'fair' : 'loading' },
      status: typeof s === 'number' ? 'success' : 'success',
      breakdown: {},
      summary: {},
    }
  }
  return {
    input: n.location,
    coordinates: { lat: 0, lon: 0 },
    location_info: { city: '', state: '', zip: '' },
    livability_pillars: pillars as any,
    total_score: 0,
    token_allocation: {},
    allocation_type: 'priority_based',
    overall_confidence: {
      average_confidence: 0,
      pillars_using_fallback: 0,
      fallback_percentage: 0,
      quality_tier_distribution: {},
      overall_quality: 'good',
    },
    data_quality_summary: {
      data_sources_used: [],
      area_classification: {},
      total_pillars: PILLAR_ORDER.length,
      data_completeness: 'partial',
    },
    metadata: { version: '', architecture: '', note: '', test_mode: false },
  }
}

function persistCache(cacheKey: string | null, payload: ScoreResponse) {
  if (!cacheKey) return
  try {
    window.sessionStorage?.setItem(cacheKey, JSON.stringify({ ts: Date.now(), payload } satisfies CacheEntry))
  } catch {
    // ignore
  }
}

export default function ResultsClient({ initialSearchParams }: { initialSearchParams: RawSearchParams }) {
  const router = useRouter()
  const { user, isConfigured: isAuthConfigured, openAuthModal } = useAuth()
  const normalized = useMemo(() => normalizeSearchParams(initialSearchParams), [initialSearchParams])

  const [finalResponse, setFinalResponse] = useState<ScoreResponse | null>(null)
  const [savedScoreId, setSavedScoreId] = useState<string | null>(null)
  const [saveBusy, setSaveBusy] = useState(false)
  const [saveErr, setSaveErr] = useState<string | null>(null)
  const [partial, setPartial] = useState<Record<string, { score: number }>>({})
  const [error, setError] = useState<string | null>(null)
  const [showCachedNote, setShowCachedNote] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [runActive, setRunActive] = useState(false)
  const [gateVisible, setGateVisible] = useState(true)
  const [rescoringPillarKey, setRescoringPillarKey] = useState<PillarKey | null>(null)
  const [catalogSnapshot, setCatalogSnapshot] = useState(false)
  const [recomputeLoading, setRecomputeLoading] = useState(false)
  const [statusSignalRefreshLoading, setStatusSignalRefreshLoading] = useState(false)
  const runKeyRef = useRef(0)

  const searchOptions: SearchOptions | null = useMemo(() => {
    if (!normalized) return null
    return {
      priorities: JSON.parse(normalized.prioritiesJson) as PillarPriorities,
      include_chains: normalized.include_chains,
      enable_schools: normalized.enable_schools,
      job_categories: normalized.job_categories ? normalized.job_categories.split(',').map((s) => s.trim()).filter(Boolean) : [],
      natural_beauty_preference: (() => {
        if (!normalized.natural_beauty_preference) return null
        try {
          const raw = JSON.parse(normalized.natural_beauty_preference)
          return Array.isArray(raw) ? raw : null
        } catch {
          return null
        }
      })(),
      built_character_preference: normalized.built_character_preference as any,
      built_density_preference: normalized.built_density_preference as any,
    }
  }, [normalized])

  const cacheKey = useMemo(() => (normalized ? buildResultsCacheKey(normalized) : null), [normalized])

  const displayData = useMemo(() => {
    if (!finalResponse || !searchOptions) return null
    const rew = reweightScoreResponseFromPriorities(finalResponse, searchOptions.priorities)
    const li = longevityIndexFromLivabilityPillars(
      rew.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
    )
    if (li != null) return { ...rew, longevity_index: li }
    return rew
  }, [finalResponse, searchOptions])

  const progressivePayload = useMemo(() => {
    if (!normalized) return null
    if (finalResponse) return finalResponse
    return buildProgressivePayload(normalized, partial)
  }, [normalized, partial, finalResponse])

  const pillarLoadingKeys = useMemo(() => {
    const out = new Set<PillarKey>()
    for (const k of PILLAR_ORDER) {
      if (!(k in partial)) out.add(k)
    }
    return out
  }, [partial])

  useEffect(() => {
    const id = setTimeout(() => setGateVisible(false), 1200)
    return () => clearTimeout(id)
  }, [])

  useEffect(() => {
    if (!normalized || !cacheKey) return
    setError(null)
    setPartial({})
    setSavedScoreId(null)
    setSaveErr(null)
    setShowCachedNote(false)
    setCatalogSnapshot(false)
    setRunActive(false)
    setRefreshing(false)

    let hydrated: ScoreResponse | null = null
    try {
      hydrated = readAndConsumeCatalogResultsHydrate(cacheKey)
    } catch {
      hydrated = null
    }
    if (hydrated) {
      setFinalResponse(hydrated)
      setShowCachedNote(true)
      setCatalogSnapshot(true)
      persistCache(cacheKey, hydrated)
      return
    }

    let cached: CacheEntry | null = null
    try {
      cached = safeParseCache(window.sessionStorage?.getItem(cacheKey))
    } catch {
      cached = null
    }
    if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
      setFinalResponse(cached.payload)
      setShowCachedNote(true)
      return
    }

    setFinalResponse(null)
    setRefreshing(true)
    setRunActive(true)
    runKeyRef.current += 1
  }, [normalized, cacheKey])

  const handleRefresh = () => {
    if (!normalized) return
    setError(null)
    setFinalResponse(null)
    setPartial({})
    setCatalogSnapshot(false)
    setRefreshing(true)
    setRunActive(true)
    runKeyRef.current += 1
    setGateVisible(true)
    setTimeout(() => setGateVisible(false), 1200)
  }

  const handleSavePlace = useCallback(
    async (payload: ScoreResponse, priorities: PillarPriorities) => {
      if (!searchOptions) return { error: 'Missing search options' }
      try {
        const payloadWithConfig: ScoreResponse = {
          ...payload,
          metadata: {
            ...(payload.metadata ?? {}),
            saved_search_options: searchOptions,
          } as Metadata,
        }
        const { id } = await saveScore(payloadWithConfig, priorities)
        setSavedScoreId(id)
        return { id }
      } catch (e) {
        return { error: e instanceof Error ? e.message : 'Failed to save' }
      }
    },
    [searchOptions]
  )

  const runSaveFromResultsHeader = useCallback(async () => {
    if (!displayData || !searchOptions) return
    setSaveErr(null)
    setSaveBusy(true)
    try {
      const r = await handleSavePlace(displayData, searchOptions.priorities)
      if (r.error) setSaveErr(r.error)
    } finally {
      setSaveBusy(false)
    }
  }, [displayData, searchOptions, handleSavePlace])

  const handleSearchOptionsChange = useCallback(
    (next: SearchOptions) => {
      if (!normalized) return
      const updated: ResultsRouteParams = {
        location: normalized.location,
        prioritiesJson: JSON.stringify(next.priorities),
        job_categories: next.job_categories?.length ? next.job_categories.join(',') : null,
        include_chains: Boolean(next.include_chains),
        enable_schools: Boolean(next.enable_schools),
        natural_beauty_preference: next.natural_beauty_preference?.length ? JSON.stringify(next.natural_beauty_preference) : null,
        built_character_preference: next.built_character_preference ?? null,
        built_density_preference: next.built_density_preference ?? null,
      }
      router.replace(buildResultsUrl(updated))
    },
    [normalized, router]
  )

  const handleRescorePillar = useCallback(
    async (pillarKey: PillarKey) => {
      if (!normalized || !finalResponse || !searchOptions) return
      setRescoringPillarKey(pillarKey)
      try {
        const resp = await getScoreSinglePillar({
          location: normalized.location,
          pillar: pillarKey,
          priorities: normalized.prioritiesJson,
          job_categories: normalized.job_categories ?? undefined,
          include_chains: normalized.include_chains,
          enable_schools: normalized.enable_schools,
          natural_beauty_preference: normalized.natural_beauty_preference ?? undefined,
          built_character_preference: normalized.built_character_preference ?? undefined,
          built_density_preference: normalized.built_density_preference ?? undefined,
        })
        const livability_pillars = {
          ...finalResponse.livability_pillars,
          [pillarKey]: (resp.livability_pillars as any)[pillarKey],
        } as ScoreResponse['livability_pillars']

        const mergedBase: ScoreResponse = {
          ...finalResponse,
          livability_pillars,
          place_summary: resp.place_summary ?? finalResponse.place_summary,
          overall_confidence: resp.overall_confidence ?? finalResponse.overall_confidence,
          data_quality_summary: resp.data_quality_summary ?? finalResponse.data_quality_summary,
        }
        if (typeof (resp as { happiness_index?: number }).happiness_index === 'number') {
          mergedBase.happiness_index = (resp as { happiness_index: number }).happiness_index
        }
        if ((resp as { happiness_index_breakdown?: Record<string, unknown> }).happiness_index_breakdown != null) {
          mergedBase.happiness_index_breakdown = (resp as { happiness_index_breakdown: Record<string, unknown> }).happiness_index_breakdown
        }

        let next = reweightScoreResponseFromPriorities(mergedBase, searchOptions.priorities)
        const li = longevityIndexFromLivabilityPillars(
          next.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
        )
        if (li != null) next = { ...next, longevity_index: li }

        setFinalResponse(next)
        persistCache(cacheKey, next)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to rescore pillar')
      } finally {
        setRescoringPillarKey(null)
      }
    },
    [normalized, finalResponse, searchOptions, cacheKey]
  )

  const handleRunPillarScore = useCallback(
    async (pillarKey: PillarKey, options: RunPillarScoreOptions) => {
      if (!normalized || !finalResponse || !searchOptions) return
      const response = await getScoreWithProgress(
        {
          location: normalized.location,
          only: pillarKey,
          priorities: JSON.stringify(options.priorities),
          job_categories: options.job_categories?.length ? options.job_categories.join(',') : undefined,
          natural_beauty_preference: options.natural_beauty_preference?.length
            ? JSON.stringify(options.natural_beauty_preference)
            : undefined,
          built_character_preference: options.built_character_preference ?? undefined,
          built_density_preference: options.built_density_preference ?? undefined,
          include_chains: options.include_chains ?? true,
          enable_schools: options.enable_schools ?? false,
        },
        () => {}
      )
      const mergedBase: ScoreResponse = {
        ...finalResponse,
        livability_pillars: {
          ...finalResponse.livability_pillars,
          [pillarKey]: (response.livability_pillars as unknown as Record<string, unknown>)[pillarKey],
        } as ScoreResponse['livability_pillars'],
        place_summary: response.place_summary ?? finalResponse.place_summary,
      }
      if (typeof (response as { happiness_index?: number }).happiness_index === 'number') {
        mergedBase.happiness_index = (response as { happiness_index: number }).happiness_index
      }
      if ((response as { happiness_index_breakdown?: Record<string, unknown> }).happiness_index_breakdown != null) {
        mergedBase.happiness_index_breakdown = (response as { happiness_index_breakdown: Record<string, unknown> }).happiness_index_breakdown
      }
      let next = reweightScoreResponseFromPriorities(mergedBase, options.priorities)
      const li = longevityIndexFromLivabilityPillars(
        next.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
      )
      if (li != null) next = { ...next, longevity_index: li }
      setFinalResponse(next)
      // Persist under the post-navigation cache key *before* router.replace so the
      // normalized/cacheKey effect finds a hit and does not restart a full score run.
      const jobCat =
        options.job_categories && options.job_categories.length > 0
          ? options.job_categories.join(',')
          : normalized.job_categories
      const updated: ResultsRouteParams = {
        location: normalized.location,
        prioritiesJson: JSON.stringify(options.priorities),
        job_categories: jobCat && jobCat.trim() ? jobCat.trim() : null,
        include_chains: options.include_chains ?? searchOptions.include_chains,
        enable_schools: options.enable_schools ?? searchOptions.enable_schools,
        natural_beauty_preference:
          options.natural_beauty_preference && options.natural_beauty_preference.length > 0
            ? JSON.stringify(options.natural_beauty_preference)
            : normalized.natural_beauty_preference,
        built_character_preference: options.built_character_preference ?? normalized.built_character_preference,
        built_density_preference: options.built_density_preference ?? normalized.built_density_preference,
      }
      persistCache(buildResultsCacheKey(updated), next)
      router.replace(buildResultsUrl(updated))
    },
    [normalized, finalResponse, searchOptions, router]
  )

  const handleRefreshStatusSignal = useCallback(async () => {
    if (!normalized || !finalResponse || !searchOptions) throw new Error('Results not ready.')
    const coords = finalResponse.coordinates
    const lat = typeof coords?.lat === 'number' && Number.isFinite(coords.lat) ? coords.lat : undefined
    const lon = typeof coords?.lon === 'number' && Number.isFinite(coords.lon) ? coords.lon : undefined
    setStatusSignalRefreshLoading(true)
    try {
      const statusPillarKeys = STATUS_SIGNAL_ONLY_PILLARS.split(',')
      const prioritiesForFour: Record<string, string> = {}
      statusPillarKeys.forEach((k) => {
        prioritiesForFour[k] = (searchOptions.priorities as unknown as Record<string, string>)[k] ?? 'Medium'
      })
      const jc = searchOptions.job_categories ?? []
      const response = await getScoreWithProgress(
        {
          location: normalized.location,
          only: STATUS_SIGNAL_ONLY_PILLARS,
          priorities: JSON.stringify(prioritiesForFour),
          ...(lat != null && lon != null ? { lat, lon } : {}),
          ...(jc.length > 0 ? { job_categories: jc.join(',') } : {}),
          ...(searchOptions.natural_beauty_preference?.length
            ? { natural_beauty_preference: JSON.stringify(searchOptions.natural_beauty_preference) }
            : {}),
          ...(searchOptions.built_character_preference
            ? { built_character_preference: searchOptions.built_character_preference }
            : {}),
          ...(searchOptions.built_density_preference ? { built_density_preference: searchOptions.built_density_preference } : {}),
          include_chains: searchOptions.include_chains ?? true,
          enable_schools: searchOptions.enable_schools ?? false,
        },
        () => {}
      )
      const current = finalResponse
      const incoming = response.livability_pillars as unknown as Record<string, unknown>
      const mergedPillars = {
        ...(current.livability_pillars ?? {}),
        ...Object.fromEntries(statusPillarKeys.map((k) => [k, incoming[k]]).filter(([, v]) => v != null)),
      }
      const mergedBase: ScoreResponse = {
        ...current,
        livability_pillars: mergedPillars as ScoreResponse['livability_pillars'],
        place_summary: response.place_summary ?? current.place_summary,
        status_signal:
          typeof (response as { status_signal?: number }).status_signal === 'number'
            ? (response as { status_signal: number }).status_signal
            : current.status_signal,
        happiness_index:
          typeof (response as { happiness_index?: number }).happiness_index === 'number'
            ? (response as { happiness_index: number }).happiness_index
            : current.happiness_index,
        happiness_index_breakdown:
          (response as { happiness_index_breakdown?: Record<string, unknown> }).happiness_index_breakdown ??
          current.happiness_index_breakdown,
      }
      let merged = reweightScoreResponseFromPriorities(mergedBase, searchOptions.priorities)
      const li = longevityIndexFromLivabilityPillars(
        merged.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
      )
      if (li != null) merged = { ...merged, longevity_index: li }
      setFinalResponse(merged)
      persistCache(cacheKey, merged)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Refresh failed.'
      throw new Error(msg)
    } finally {
      setStatusSignalRefreshLoading(false)
    }
  }, [normalized, finalResponse, searchOptions, cacheKey])

  const handleRecomputeComposites = useCallback(async () => {
    if (!finalResponse || !searchOptions) return
    const pillars = finalResponse.livability_pillars
    if (!pillars || Object.keys(pillars).length === 0) {
      setError('No pillar data to recompute indices from.')
      return
    }
    setRecomputeLoading(true)
    setError(null)
    try {
      const resp = await recomputeComposites({
        livability_pillars: pillars,
        location_info: finalResponse.location_info,
        coordinates: finalResponse.coordinates,
        token_allocation: finalResponse.token_allocation,
      })
      const current = finalResponse
      const merged: ScoreResponse = {
        ...current,
        longevity_index: resp.longevity_index ?? current.longevity_index,
        longevity_index_contributions: resp.longevity_index_contributions ?? (current as any).longevity_index_contributions,
        status_signal: resp.status_signal ?? current.status_signal,
        status_signal_breakdown: resp.status_signal_breakdown ?? (current as any).status_signal_breakdown,
        happiness_index: resp.happiness_index ?? current.happiness_index,
        happiness_index_breakdown: resp.happiness_index_breakdown ?? current.happiness_index_breakdown,
      }
      const next = reweightScoreResponseFromPriorities(merged, searchOptions.priorities)
      const li = longevityIndexFromLivabilityPillars(
        next.livability_pillars as unknown as Record<string, { score?: number; status?: string; error?: string }>
      )
      const out = li != null ? { ...next, longevity_index: li } : next
      setFinalResponse(out)
      persistCache(cacheKey, out)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh indices.')
    } finally {
      setRecomputeLoading(false)
    }
  }, [finalResponse, searchOptions, cacheKey])

  if (!normalized) {
    return (
      <main className="hf-page">
        <div className="hf-container">
          <div className="hf-card">
            <div style={{ fontWeight: 800, fontSize: '1.2rem' }}>Missing required parameter</div>
            <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
              This link is missing a location. Go back and run a new search.
            </div>
            <div style={{ marginTop: '1rem' }}>
              <Link href="/" className="hf-btn-primary" style={{ padding: '0.8rem 1rem', borderRadius: 10 }}>
                Back to search
              </Link>
            </div>
          </div>
        </div>
      </main>
    )
  }

  const locationLabel =
    (typeof displayData?.input === 'string' && displayData.input.trim()) ||
    [displayData?.location_info?.city, displayData?.location_info?.state, displayData?.location_info?.zip]
      .filter(Boolean)
      .join(', ') ||
    normalized.location

  const coordinates = displayData?.coordinates
  const mapCoords =
    coordinates &&
    typeof coordinates.lat === 'number' &&
    typeof coordinates.lon === 'number' &&
    Number.isFinite(coordinates.lat) &&
    Number.isFinite(coordinates.lon) &&
    !(coordinates.lat === 0 && coordinates.lon === 0)
      ? coordinates
      : null

  const showSavedStyle = Boolean(finalResponse && displayData && searchOptions)

  return (
    <main className={showSavedStyle ? 'hf-page hf-page-no-hero' : 'hf-page'}>
      <div className="hf-container">
        {error && (
          <div className="hf-card" style={{ marginTop: '1rem' }}>
            <div className="hf-auth-error" role="alert">
              {error}
            </div>
          </div>
        )}

        {runActive ? (
          <div style={{ display: gateVisible && !finalResponse ? 'block' : 'none', marginTop: '1rem' }}>
            <SmartLoadingScreen
              key={`run-${runKeyRef.current}`}
              location={normalized.location}
              priorities={normalized.prioritiesJson}
              job_categories={normalized.job_categories ?? undefined}
              include_chains={normalized.include_chains}
              enable_schools={normalized.enable_schools}
              on_complete={(resp) => {
                setRefreshing(false)
                setRunActive(false)
                setCatalogSnapshot(false)
                setFinalResponse(resp)
                setPartial({})
                persistCache(cacheKey, resp)
              }}
              on_partial={(p) => {
                setPartial((prev) => ({ ...prev, ...p }))
              }}
              on_error={(err) => {
                setRefreshing(false)
                setRunActive(false)
                setError(err instanceof Error ? err.message : 'Failed to score')
              }}
            />
          </div>
        ) : null}

        {showSavedStyle ? (
          <div className="hf-card" style={{ marginTop: '1.5rem', paddingBottom: '1.5rem' }}>
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
                  Location: {displayData!.location_info?.city}, {displayData!.location_info?.state}{' '}
                  {displayData!.location_info?.zip}
                </div>
                <div className="hf-muted" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
                  Coordinates: {displayData!.coordinates.lat.toFixed(6)}, {displayData!.coordinates.lon.toFixed(6)}
                </div>
                {displayData!.metadata?.version && (
                  <div className="hf-muted" style={{ marginTop: '0.2rem', fontSize: '0.8rem', opacity: 0.9 }}>
                    API version: {displayData!.metadata.version}
                  </div>
                )}
              </div>

              <nav
                className="hf-saved-detail-nav"
                aria-label="Actions"
                style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}
              >
                <Link href="/" className="hf-btn-link" style={{ fontSize: '0.95rem' }}>
                  ← New search
                </Link>
                {catalogSnapshot && (
                  <span className="hf-muted" style={{ fontSize: '0.9rem' }}>
                    NYC metro catalog snapshot — refresh to recompute live
                  </span>
                )}
                {showCachedNote && !catalogSnapshot && (
                  <span className="hf-muted" style={{ fontSize: '0.9rem' }}>
                    Showing cached results
                  </span>
                )}
                {finalResponse && searchOptions ? (
                  user ? (
                    savedScoreId ? (
                      <span className="hf-muted" style={{ fontSize: '0.9rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        ✓ Saved
                        <Link href="/saved" className="hf-auth-link" style={{ fontWeight: 600 }}>
                          My places →
                        </Link>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={runSaveFromResultsHeader}
                        className="hf-btn-primary"
                        style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', minHeight: 44 }}
                        disabled={saveBusy}
                      >
                        {saveBusy ? 'Saving…' : 'Save this place'}
                      </button>
                    )
                  ) : isAuthConfigured ? (
                    <button
                      type="button"
                      onClick={() => openAuthModal('signin')}
                      className="hf-btn-primary"
                      style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', minHeight: 44 }}
                    >
                      Sign in to save
                    </button>
                  ) : null
                ) : null}
                {saveErr ? (
                  <span className="hf-muted" style={{ fontSize: '0.85rem', color: 'var(--hf-danger)' }}>
                    {saveErr}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={handleRefresh}
                  className="hf-btn-secondary"
                  style={{ padding: '0.85rem 1.25rem', borderRadius: 12, fontSize: '0.95rem', minHeight: 44 }}
                  disabled={refreshing}
                >
                  {refreshing ? 'Refreshing…' : 'Refresh data'}
                </button>
              </nav>
            </div>

            {mapCoords ? (
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
                  coordinates={mapCoords}
                  completed_pillars={Object.keys(displayData!.livability_pillars ?? {})}
                />
              </div>
            ) : null}

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
                  color: displayData!.total_score != null ? 'var(--c-purple-600)' : 'var(--hf-text-secondary)',
                  lineHeight: 1.1,
                }}
              >
                {displayData!.total_score != null ? displayData!.total_score.toFixed(1) : '—'}
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
                  <span
                    style={{
                      fontWeight: 600,
                      color:
                        typeof displayData!.longevity_index === 'number'
                          ? 'var(--c-teal-600)'
                          : 'var(--hf-text-secondary)',
                    }}
                  >
                    {typeof displayData!.longevity_index === 'number' ? displayData!.longevity_index.toFixed(1) : '—'}
                  </span>
                  <LongevityInfo />
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span className="hf-muted">Status Signal</span>
                  <span
                    style={{
                      fontWeight: 600,
                      color:
                        typeof displayData!.status_signal === 'number' ? 'var(--c-coral-600)' : 'var(--hf-text-secondary)',
                    }}
                  >
                    {typeof displayData!.status_signal === 'number'
                      ? Math.max(0, Math.min(100, displayData!.status_signal)).toFixed(1)
                      : '—'}
                  </span>
                  <StatusSignalInfo
                    onRefresh={handleRefreshStatusSignal}
                    refreshing={statusSignalRefreshLoading}
                    breakdown={displayData!.status_signal_breakdown ?? null}
                    compositeScore={typeof displayData!.status_signal === 'number' ? displayData!.status_signal : null}
                  />
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span className="hf-muted">Happiness Index</span>
                  <span
                    style={{
                      fontWeight: 600,
                      color:
                        typeof displayData!.happiness_index === 'number'
                          ? 'var(--c-blue-600)'
                          : 'var(--hf-text-secondary)',
                    }}
                  >
                    {typeof displayData!.happiness_index === 'number'
                      ? Math.max(0, Math.min(100, displayData!.happiness_index)).toFixed(1)
                      : '—'}
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
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <Link href="/" className="hf-btn-link">
              ← New search
            </Link>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              {catalogSnapshot && (
                <span className="hf-muted" style={{ fontSize: '0.9rem' }}>
                  NYC metro catalog snapshot — refresh to recompute live
                </span>
              )}
              {showCachedNote && !catalogSnapshot && (
                <span className="hf-muted" style={{ fontSize: '0.9rem' }}>
                  Showing cached results
                </span>
              )}
              <button
                type="button"
                onClick={handleRefresh}
                className="hf-btn-secondary"
                style={{ padding: '0.55rem 0.9rem', borderRadius: 10, minHeight: 44 }}
                disabled={refreshing}
              >
                {refreshing ? 'Refreshing…' : 'Refresh data'}
              </button>
            </div>
          </div>
        )}

        <div style={{ marginTop: showSavedStyle ? '0' : '1rem' }}>
          {progressivePayload && searchOptions ? (
            <ScoreDisplay
              data={showSavedStyle && displayData ? displayData : progressivePayload}
              priorities={searchOptions.priorities}
              searchOptions={searchOptions}
              onSearchOptionsChange={handleSearchOptionsChange}
              onRunPillarScore={finalResponse ? handleRunPillarScore : undefined}
              onRescorePillar={finalResponse ? handleRescorePillar : undefined}
              rescoringPillarKey={rescoringPillarKey}
              loading={!finalResponse}
              pillarLoadingKeys={!finalResponse ? pillarLoadingKeys : undefined}
              hideSummaryCard={Boolean(showSavedStyle)}
              placeSummary={displayData?.place_summary ?? null}
            />
          ) : null}
        </div>
      </div>
    </main>
  )
}
