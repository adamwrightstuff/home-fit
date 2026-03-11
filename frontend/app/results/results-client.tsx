'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import SmartLoadingScreen from '@/components/SmartLoadingScreen'
import ScoreDisplay from '@/components/ScoreDisplay'
import type { PillarPriorities, SearchOptions } from '@/components/SearchOptions'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { ScoreResponse } from '@/types/api'
import type { PillarKey } from '@/lib/pillars'
import { PILLAR_ORDER } from '@/lib/pillars'
import { getScoreSinglePillar } from '@/lib/api'
import { buildResultsCacheKey, buildResultsUrl, type ResultsRouteParams } from '@/lib/resultsShare'

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
  // Minimal payload to let ScoreDisplay render pillar cards while scoring.
  // Total score stays skeletoned until final response arrives.
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

export default function ResultsClient({ initialSearchParams }: { initialSearchParams: RawSearchParams }) {
  const router = useRouter()
  const normalized = useMemo(() => normalizeSearchParams(initialSearchParams), [initialSearchParams])

  const [finalResponse, setFinalResponse] = useState<ScoreResponse | null>(null)
  const [partial, setPartial] = useState<Record<string, { score: number }>>({})
  const [error, setError] = useState<string | null>(null)
  const [showCachedNote, setShowCachedNote] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [runActive, setRunActive] = useState(false)
  const [gateVisible, setGateVisible] = useState(true)
  const [rescoringPillarKey, setRescoringPillarKey] = useState<PillarKey | null>(null)
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

  // Initial gate: show SmartLoadingScreen for 1.2s minimum
  useEffect(() => {
    const id = setTimeout(() => setGateVisible(false), 1200)
    return () => clearTimeout(id)
  }, [])

  // Cache-first: load from sessionStorage; only auto-run when no cache exists
  useEffect(() => {
    if (!normalized || !cacheKey) return
    setError(null)
    setPartial({})
    setShowCachedNote(false)
    setRunActive(false)
    setRefreshing(false)

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

    // No cache: run automatically
    setFinalResponse(null)
    setRefreshing(true)
    setRunActive(true)
    runKeyRef.current += 1
    // SmartLoadingScreen will run and call on_complete
  }, [normalized, cacheKey])

  const handleRefresh = () => {
    if (!normalized) return
    setError(null)
    setFinalResponse(null)
    setPartial({})
    setRefreshing(true)
    setRunActive(true)
    runKeyRef.current += 1
    setGateVisible(true)
    setTimeout(() => setGateVisible(false), 1200)
  }

  const handleSearchOptionsChange = (next: SearchOptions) => {
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
    const url = buildResultsUrl(updated)
    router.replace(url)
  }

  const handleRescorePillar = async (pillarKey: PillarKey) => {
    if (!normalized || !finalResponse) return
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
      const merged: ScoreResponse = {
        ...finalResponse,
        livability_pillars: {
          ...finalResponse.livability_pillars,
          [pillarKey]: (resp.livability_pillars as any)[pillarKey],
        } as any,
        place_summary: resp.place_summary ?? finalResponse.place_summary,
        total_score: resp.total_score ?? finalResponse.total_score,
        overall_confidence: resp.overall_confidence ?? finalResponse.overall_confidence,
        data_quality_summary: resp.data_quality_summary ?? finalResponse.data_quality_summary,
        token_allocation: resp.token_allocation ?? finalResponse.token_allocation,
      }
      setFinalResponse(merged)
      if (cacheKey) {
        try {
          window.sessionStorage?.setItem(cacheKey, JSON.stringify({ ts: Date.now(), payload: merged } satisfies CacheEntry))
        } catch {
          // ignore cache failures
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rescore pillar')
    } finally {
      setRescoringPillarKey(null)
    }
  }

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

  return (
    <main className="hf-page">
      <div className="hf-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <Link href="/" className="hf-btn-link">
            ← New search
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            {showCachedNote && (
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

        {error && (
          <div className="hf-card" style={{ marginTop: '1rem' }}>
            <div className="hf-auth-error" role="alert">
              {error}
            </div>
          </div>
        )}

        {/* Loading gate: keep SmartLoadingScreen mounted so it can run scoring, but hide after ~1.2s */}
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
                setFinalResponse(resp)
                setPartial({})
                if (cacheKey) {
                  try {
                    window.sessionStorage?.setItem(cacheKey, JSON.stringify({ ts: Date.now(), payload: resp } satisfies CacheEntry))
                  } catch {
                    // ignore
                  }
                }
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

        {/* Progressive results: show ScoreDisplay after the initial gate */}
        <div style={{ marginTop: '1rem' }}>
          {progressivePayload && searchOptions ? (
            <ScoreDisplay
              data={progressivePayload}
              priorities={searchOptions.priorities}
              searchOptions={searchOptions}
              onSearchOptionsChange={handleSearchOptionsChange}
              onRescorePillar={finalResponse ? handleRescorePillar : undefined}
              rescoringPillarKey={rescoringPillarKey}
              loading={!finalResponse}
              pillarLoadingKeys={!finalResponse ? pillarLoadingKeys : undefined}
            />
          ) : null}
        </div>
      </div>
    </main>
  )
}

