'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import Link from 'next/link'
import InteractiveMap from './InteractiveMap'
import LongevityInfo from './LongevityInfo'
import HomeFitInfo from './HomeFitInfo'
import StatusSignalInfo from './StatusSignalInfo'
import ExportScoresModal from './ExportScoresModal'
import { buildExportRow } from '@/lib/exportScores'
import { PILLAR_META, PILLAR_ORDER, getScoreBadgeClass, getScoreBandLabel, getScoreBandColor, getScoreBandBackground, getPillarFailureType, isLongevityPillar, LONGEVITY_COPY, HOMEFIT_COPY, computeLongevityIndex, STATUS_SIGNAL_ONLY_PILLARS, type PillarKey } from '@/lib/pillars'
import { totalFromPartialPillarScores, getPillarWeightsAndContributions, getPillarWeightsFromPriorities } from '@/lib/reweight'
import { getScoreWithProgress } from '@/lib/api'
import type { GeocodeResult } from '@/types/api'
import type { ScoreResponse } from '@/types/api'
import type { SearchOptions } from './SearchOptions'
import type { PillarPriorities } from './SearchOptions'
import { JOB_CATEGORY_OPTIONS } from './SearchOptions'
import { useAuth } from '@/contexts/AuthContext'

/** Natural Beauty inner-weight preference (multi-select, max 2; "Any" is exclusive). */
const NATURAL_BEAUTY_PREFERENCE_CHIPS: Array<{ value: string | null; label: string }> = [
  { value: null, label: 'Any' },
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean' },
  { value: 'lakes_rivers', label: 'Lakes & rivers' },
  { value: 'canopy', label: 'Greenery' },
]

/** Built Beauty character preference (single select). */
const BUILT_CHARACTER_CHIPS: Array<{ value: 'historic' | 'contemporary' | 'no_preference'; label: string }> = [
  { value: 'historic', label: 'Historic character' },
  { value: 'contemporary', label: 'Contemporary design' },
  { value: 'no_preference', label: 'No preference' },
]

/** Built Beauty density preference (single select). */
const BUILT_DENSITY_CHIPS: Array<{ value: 'spread_out_residential' | 'walkable_residential' | 'dense_urban_living'; label: string }> = [
  { value: 'spread_out_residential', label: 'Spread out residential' },
  { value: 'walkable_residential', label: 'Walkable residential' },
  { value: 'dense_urban_living', label: 'Downtown living' },
]

type Importance = 'Low' | 'Medium' | 'High'

/** Prefer neighborhood-style label: strip trailing zip so we show "Gowanus, Brooklyn" not "New York, NY 11217". */
function formatPlaceLabel(place: GeocodeResult & { location: string }): string {
  const name = place.display_name || place.location
  const withoutZip = name.replace(/,?\s*\d{5}(-\d{4})?$/, '').trim()
  if (withoutZip) return withoutZip
  return `${place.city}, ${place.state}`
}

const PREMIUM_CODE_KEY = 'homefit_premium_code'

export interface PlaceViewProps {
  place: GeocodeResult & { location: string }
  searchOptions: SearchOptions
  onSearchOptionsChange?: (options: SearchOptions) => void
  onError: (message: string) => void
  onBack: () => void
  onTakeQuiz?: () => void
  /** When true, select all pillars and sync priorities from searchOptions (e.g. after quiz apply). */
  justAppliedQuizPriorities?: boolean
  /** Called after syncing pillar selection from quiz priorities. */
  onAppliedQuizPrioritiesConsumed?: () => void
  /** When provided and user has results, show Save / Sign in to save. */
  onSave?: (payload: ScoreResponse, priorities: PillarPriorities) => Promise<{ id?: string; error?: string }>
  /** When user has scores and clicks "View results", call with current payload and priorities to show Results screen. */
  onShowResults?: (payload: ScoreResponse, priorities: PillarPriorities) => void
  /** When coming back from Results (Edit pillars), optional initial state from the last payload. */
  initialPayload?: ScoreResponse | null
  /** Priorities to use when initialPayload is provided (pillar selection and importance). */
  initialPriorities?: PillarPriorities | null
  isSignedIn?: boolean
  isAuthConfigured?: boolean
  savedScoreId?: string | null
}

export default function PlaceView({ place, searchOptions, onSearchOptionsChange, onError, onBack, onTakeQuiz, justAppliedQuizPriorities, onAppliedQuizPrioritiesConsumed, onSave, onShowResults, initialPayload, initialPriorities, isSignedIn, isAuthConfigured = true, savedScoreId }: PlaceViewProps) {
  const { openAuthModal } = useAuth()
  const [selectedPillars, setSelectedPillars] = useState<Set<string>>(() => {
    if (initialPayload?.livability_pillars && initialPriorities) {
      const pillars = Object.keys(initialPayload.livability_pillars) as (keyof typeof initialPayload.livability_pillars)[]
      const pri = initialPriorities as unknown as Record<string, string>
      return new Set(pillars.filter((k) => pri[k] && pri[k] !== 'None'))
    }
    return new Set()
  })
  const [selectedPriorities, setSelectedPriorities] = useState<Record<string, Importance>>(() => {
    if (initialPriorities) {
      const out: Record<string, Importance> = {}
      const pri = initialPriorities as unknown as Record<string, string>
      for (const k of PILLAR_ORDER) {
        const v = pri[k]
        if (v === 'Low' || v === 'Medium' || v === 'High') out[k] = v
      }
      return out
    }
    return {}
  })
  const [pillarScores, setPillarScores] = useState<Record<string, {
    score: number
    failed?: boolean
    confidence?: number
    status?: 'success' | 'fallback' | 'failed'
    data_quality?: { quality_tier?: string }
  }>>(() => {
    if (initialPayload?.livability_pillars) {
      const out: Record<string, { score: number; failed?: boolean; confidence?: number; status?: 'success' | 'fallback' | 'failed'; data_quality?: { quality_tier?: string } }> = {}
      const pillars = initialPayload.livability_pillars as unknown as Record<string, { score?: number; weight?: number; contribution?: number; confidence?: number; data_quality?: { quality_tier?: string }; status?: string; error?: string }>
      for (const k of Object.keys(pillars)) {
        const p = pillars[k]
        if (!p || typeof p.score !== 'number') continue
        const failed = p.error != null
        out[k] = {
          score: p.score,
          failed,
          confidence: p.confidence ?? 0,
          status: (p.status as 'success' | 'fallback' | 'failed') ?? (failed ? 'failed' : 'success'),
          data_quality: p.data_quality,
        }
      }
      return out
    }
    return {}
  })
  const [fullPillarData, setFullPillarData] = useState<Record<string, Record<string, unknown>>>(() => {
    if (initialPayload?.livability_pillars) {
      const pillars = initialPayload.livability_pillars as unknown as Record<string, Record<string, unknown>>
      const out: Record<string, Record<string, unknown>> = {}
      for (const k of Object.keys(pillars)) {
        if (pillars[k] && typeof pillars[k] === 'object') out[k] = { ...pillars[k] }
      }
      return out
    }
    return {}
  })
  const [placeSummary, setPlaceSummary] = useState<string | null>(() => initialPayload?.place_summary ?? null)
  const longevityIndex = useMemo(() => computeLongevityIndex(pillarScores), [pillarScores])
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [scoreProgress, setScoreProgress] = useState<Record<string, { score: number }>>({})
  const [pillarsInProgress, setPillarsInProgress] = useState<string[]>([])
  const [premiumCodeInput, setPremiumCodeInput] = useState('')
  const [savedPremiumCode, setSavedPremiumCode] = useState('')
  /** Number of pillar names revealed in the scoring overlay (0..N over ~5s). */
  const [overlayRevealedCount, setOverlayRevealedCount] = useState(0)
  const [exportModalOpen, setExportModalOpen] = useState(false)
  /** Status Signal (post-pillars); set from initialPayload or after running the four pillars. */
  const [statusSignal, setStatusSignal] = useState<number | null>(() => initialPayload?.status_signal ?? null)
  const [statusSignalRefreshLoading, setStatusSignalRefreshLoading] = useState(false)
  /** Pillar key that recently failed a rerun; show "Still unable to retrieve data" briefly. */
  const [rerunFailedPillar, setRerunFailedPillar] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => {
    try {
      const v = window.sessionStorage?.getItem(PREMIUM_CODE_KEY) ?? ''
      setPremiumCodeInput(v)
      setSavedPremiumCode(v)
    } catch (_) {}
  }, [])

  // When quiz results were just applied: select all pillars and sync priorities from searchOptions.
  useEffect(() => {
    if (!justAppliedQuizPriorities || !searchOptions?.priorities) return
    const priorities = searchOptions.priorities
    setSelectedPillars(new Set(PILLAR_ORDER))
    const importance: Record<string, Importance> = {}
    for (const key of PILLAR_ORDER) {
      const p = priorities[key as keyof typeof priorities]
      importance[key] = p === 'High' || p === 'Low' ? p : 'Medium'
    }
    setSelectedPriorities(importance)
    onAppliedQuizPrioritiesConsumed?.()
  }, [justAppliedQuizPriorities, searchOptions?.priorities, onAppliedQuizPrioritiesConsumed])

  const togglePillar = useCallback((key: string) => {
    setSelectedPillars((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
        setSelectedPriorities((p) => {
          const q = { ...p }
          delete q[key]
          return q
        })
      } else {
        next.add(key)
        setSelectedPriorities((p) => ({ ...p, [key]: 'Medium' }))
      }
      return next
    })
  }, [])

  const setPillarImportance = useCallback((key: string, level: Importance) => {
    setSelectedPriorities((prev) => ({ ...prev, [key]: level }))
  }, [])

  // Re-run a single pillar with given options (e.g. after Scenery/Character/Density change, or Rerun after failure). Updates that pillar's score and total.
  const runSinglePillar = useCallback(
    async (pillarKey: string, options: SearchOptions) => {
      setRerunFailedPillar(null)
      setLoading(true)
      setProgress(5)
      setScoreProgress({})
      setPillarsInProgress([pillarKey])
      const prioritiesForRequest: PillarPriorities = {
        active_outdoors: 'None',
        built_beauty: 'None',
        natural_beauty: 'None',
        neighborhood_amenities: 'None',
        air_travel_access: 'None',
        public_transit_access: 'None',
        healthcare_access: 'None',
        economic_security: 'None',
        quality_education: 'None',
        housing_value: 'None',
        climate_risk: 'None',
        social_fabric: 'None',
      }
      selectedPillars.forEach((k) => {
        prioritiesForRequest[k as keyof PillarPriorities] = selectedPriorities[k] ?? 'Medium'
      })
      try {
        const resp = await getScoreWithProgress(
          {
            location: place.location,
            only: pillarKey,
            priorities: JSON.stringify(prioritiesForRequest),
            job_categories: options.job_categories?.join(','),
            include_chains: options.include_chains,
            enable_schools: options.enable_schools,
            natural_beauty_preference:
              options.natural_beauty_preference?.length
                ? JSON.stringify(options.natural_beauty_preference)
                : undefined,
            built_character_preference: options.built_character_preference ?? undefined,
            built_density_preference: options.built_density_preference ?? undefined,
          },
          (partial) => {
            setScoreProgress((prev) => ({ ...prev, ...partial }))
            setProgress(Math.min(98, 5 + 90))
          }
        )
        const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number; error?: string; confidence?: number; data_quality?: { fallback_used?: boolean; quality_tier?: string }; status?: string }>) || {}
        const data = pillars[pillarKey]
        if (data != null) {
          const failed = Boolean(data.error) || (data.data_quality?.fallback_used === true && (data.confidence ?? 100) === 0)
          const status = data.status ?? (failed ? 'failed' : 'success')
          if (failed) {
            setPillarScores((prev) => ({ ...prev, [pillarKey]: { score: 0, failed: true, confidence: 0, status: status as 'failed', data_quality: data.data_quality } }))
          } else if (typeof data.score === 'number') {
            setPillarScores((prev) => ({ ...prev, [pillarKey]: { score: data.score!, confidence: data.confidence ?? 0, status: status as 'success' | 'fallback', data_quality: data.data_quality } }))
          }
          const fullPillar = (resp.livability_pillars as unknown as Record<string, unknown>)[pillarKey]
          if (fullPillar && typeof fullPillar === 'object') {
            setFullPillarData((prev) => ({ ...prev, [pillarKey]: { ...(fullPillar as Record<string, unknown>) } }))
          }
        }
        const summary = (resp as { place_summary?: string }).place_summary
        if (summary != null) setPlaceSummary(summary)
        setProgress(100)
      } catch (e) {
        setRerunFailedPillar(pillarKey)
        setTimeout(() => setRerunFailedPillar(null), 5000)
        onError(e instanceof Error ? e.message : 'Failed to update score.')
      } finally {
        setLoading(false)
        setProgress(0)
        setScoreProgress({})
        setPillarsInProgress([])
      }
    },
    [place.location, selectedPillars, selectedPriorities, onError]
  )

  const handleRefreshStatusSignal = useCallback(async () => {
    const location = place?.location?.trim()
    if (!location) {
      throw new Error('No address to refresh. Search for a place first.')
    }
    setStatusSignalRefreshLoading(true)
    try {
      // Explicit priorities for the four Status Signal pillars so backend has valid allocation
      const fourPillarKeys = ['housing_value', 'social_fabric', 'economic_security', 'neighborhood_amenities'] as const
      const prioritiesForRequest: Record<string, string> = {}
      fourPillarKeys.forEach((k) => {
        prioritiesForRequest[k] = selectedPriorities[k] ?? 'Medium'
      })
      const resp = await getScoreWithProgress(
        {
          location,
          only: STATUS_SIGNAL_ONLY_PILLARS,
          priorities: JSON.stringify(prioritiesForRequest),
          ...(searchOptions.job_categories?.length ? { job_categories: searchOptions.job_categories.join(',') } : {}),
          ...(searchOptions.include_chains !== undefined ? { include_chains: searchOptions.include_chains } : {}),
          ...(searchOptions.enable_schools !== undefined ? { enable_schools: searchOptions.enable_schools } : {}),
          ...(searchOptions.natural_beauty_preference?.length
            ? { natural_beauty_preference: JSON.stringify(searchOptions.natural_beauty_preference) }
            : {}),
          ...(searchOptions.built_character_preference
            ? { built_character_preference: searchOptions.built_character_preference }
            : {}),
          ...(searchOptions.built_density_preference
            ? { built_density_preference: searchOptions.built_density_preference }
            : {}),
        },
        () => {}
      )
      const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number; error?: string; confidence?: number; data_quality?: { fallback_used?: boolean; quality_tier?: string }; status?: string }>) || {}
      const fourKeys = ['housing_value', 'social_fabric', 'economic_security', 'neighborhood_amenities'] as const
      setPillarScores((prev) => {
        const next = { ...prev }
        for (const key of fourKeys) {
          const data = pillars[key]
          if (data == null) continue
          const failed = Boolean(data.error) || (data.data_quality?.fallback_used === true && (data.confidence ?? 100) === 0)
          const status = data.status ?? (failed ? 'failed' : 'success')
          if (failed) {
            next[key] = { score: 0, failed: true, confidence: 0, status: status as 'failed', data_quality: data.data_quality }
          } else if (typeof data.score === 'number') {
            next[key] = { score: data.score, confidence: data.confidence ?? 0, status: status as 'success' | 'fallback', data_quality: data.data_quality }
          }
        }
        return next
      })
      setFullPillarData((prev) => {
        const next = { ...prev }
        const full = resp.livability_pillars as unknown as Record<string, unknown>
        for (const key of fourKeys) {
          if (full[key] && typeof full[key] === 'object') next[key] = { ...(full[key] as Record<string, unknown>) }
        }
        return next
      })
      if (typeof (resp as { status_signal?: number }).status_signal === 'number') {
        setStatusSignal((resp as { status_signal: number }).status_signal)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to refresh Status Signal.'
      onError(msg)
      throw new Error(msg)
    } finally {
      setStatusSignalRefreshLoading(false)
    }
  }, [place.location, selectedPriorities, searchOptions, onError])

  // When user changes Scenery / Character / Density, update parent options and re-run only that pillar so its score updates.
  const handleSearchOptionsChange = useCallback(
    (newOptions: SearchOptions) => {
      const prev = searchOptions
      onSearchOptionsChange?.(newOptions)

      const naturalChanged = prev.natural_beauty_preference !== newOptions.natural_beauty_preference
      const builtChanged =
        prev.built_character_preference !== newOptions.built_character_preference ||
        prev.built_density_preference !== newOptions.built_density_preference

      if (naturalChanged && pillarScores.natural_beauty && selectedPillars.has('natural_beauty')) {
        runSinglePillar('natural_beauty', newOptions)
      }
      if (builtChanged && pillarScores.built_beauty && selectedPillars.has('built_beauty')) {
        runSinglePillar('built_beauty', newOptions)
      }
    },
    [onSearchOptionsChange, searchOptions, pillarScores, selectedPillars, runSinglePillar]
  )

  // Merge page-level priorities with local so total updates whether user changes Importance here or in SearchOptions.
  const effectivePriorities = useMemo(
    () => ({ ...searchOptions.priorities, ...selectedPriorities }),
    [searchOptions.priorities, selectedPriorities]
  )

  // For total and weight display: only pillars that have scores get weight; others are None.
  // Otherwise with 1 pillar run you'd get 1/12 of the weight (e.g. 8.6 instead of 96).
  const prioritiesForScoredOnly = useMemo(() => {
    const out: Record<string, 'None' | 'Low' | 'Medium' | 'High'> = {}
    for (const k of PILLAR_ORDER) {
      const entry = pillarScores[k]
      const hasScore = entry && typeof entry.score === 'number' && !entry.failed
      out[k] = hasScore ? (selectedPriorities[k] ?? 'Medium') : 'None'
    }
    return out
  }, [pillarScores, selectedPriorities])

  // Derive total from pillar scores. Only run pillars count so 1 pillar => total = that score.
  const totalScore = useMemo(() => {
    if (Object.keys(pillarScores).length === 0) return null
    return totalFromPartialPillarScores(pillarScores, prioritiesForScoredOnly) ?? null
  }, [pillarScores, prioritiesForScoredOnly])

  // Per-pillar weight % and contribution. Only scored pillars get weight.
  const pillarWeightsAndContributions = useMemo(() => {
    if (Object.keys(pillarScores).length === 0) return {}
    return getPillarWeightsAndContributions(pillarScores, prioritiesForScoredOnly)
  }, [pillarScores, prioritiesForScoredOnly])

  /** Build ScoreResponse payload for save (only when has results). Uses full pillar data when available so Show details has breakdown/summary. */
  const savePayload = useMemo((): ScoreResponse | null => {
    if (Object.keys(pillarScores).length === 0 || totalScore == null) return null
    const tokenAllocation = getPillarWeightsFromPriorities(prioritiesForScoredOnly)
    const livability_pillars: Record<string, unknown> = {}
    for (const k of Object.keys(pillarScores)) {
      const entry = pillarScores[k]
      if (!entry || entry.failed) continue
      const wc = pillarWeightsAndContributions[k]
      const weight = wc ? wc.weight : 0
      const contribution = wc ? wc.contribution : 0
      const importanceLevel = selectedPriorities[k] === 'Low' || selectedPriorities[k] === 'Medium' || selectedPriorities[k] === 'High' ? selectedPriorities[k] : 'None'
      const full = fullPillarData[k]
      livability_pillars[k] = full
        ? {
            ...full,
            score: entry.score,
            weight,
            contribution,
            confidence: entry.confidence ?? 0,
            data_quality: entry.data_quality ?? full.data_quality ?? {},
            status: entry.status ?? full.status ?? 'success',
            importance_level: importanceLevel,
          }
        : {
            score: entry.score,
            weight,
            contribution,
            confidence: entry.confidence ?? 0,
            data_quality: entry.data_quality ?? {},
            status: entry.status ?? 'success',
            importance_level: importanceLevel,
          }
    }
    const location_info = { city: place.city, state: place.state, zip: place.zip_code ?? '' }
    return {
      input: place.location,
      coordinates: { lat: place.lat, lon: place.lon },
      location_info,
      livability_pillars: livability_pillars as unknown as ScoreResponse['livability_pillars'],
      place_summary: placeSummary ?? undefined,
      total_score: totalScore,
      longevity_index: longevityIndex ?? undefined,
      status_signal: statusSignal ?? undefined,
      token_allocation: tokenAllocation as Record<string, number>,
      allocation_type: 'priority_based',
      overall_confidence: { average_confidence: 80, pillars_using_fallback: 0, fallback_percentage: 0, quality_tier_distribution: {}, overall_quality: 'good' },
      data_quality_summary: { data_sources_used: [], area_classification: {}, total_pillars: Object.keys(pillarScores).length, data_completeness: 'partial' },
      metadata: { version: '', architecture: '', note: '', test_mode: false },
    }
  }, [place, pillarScores, totalScore, longevityIndex, statusSignal, placeSummary, selectedPriorities, pillarWeightsAndContributions, prioritiesForScoredOnly, fullPillarData])

  /** Priorities object for save (all pillars, selected use current importance). */
  const savePriorities = useMemo((): PillarPriorities => {
    const p: Record<string, 'None' | 'Low' | 'Medium' | 'High'> = {}
    for (const k of PILLAR_ORDER) {
      p[k] = (selectedPriorities[k] as 'Low' | 'Medium' | 'High') ?? 'None'
    }
    return p as unknown as PillarPriorities
  }, [selectedPriorities])

  const handleSave = useCallback(async () => {
    if (!onSave || !savePayload) return
    setSaveError(null)
    setSaving(true)
    try {
      const result = await onSave(savePayload, savePriorities)
      if (result.error) setSaveError(result.error)
    } finally {
      setSaving(false)
    }
  }, [onSave, savePayload, savePriorities])

  // When user changes prioritization for pillars that already have scores, total is recomputed above (no effect needed).
  // Removed previous useEffect that set totalScore; total is now derived so it always reflects current priorities.

  // Scoring overlay: reveal pillar names one by one over ~5s when loading
  const overlayPillarList = pillarsInProgress.length > 0
    ? PILLAR_ORDER.filter((k) => pillarsInProgress.includes(k))
    : PILLAR_ORDER.filter((k) => selectedPillars.has(k))
  useEffect(() => {
    if (!loading || overlayPillarList.length === 0) {
      setOverlayRevealedCount(0)
      return
    }
    const N = overlayPillarList.length
    const intervalMs = N > 0 ? Math.max(80, 5000 / N) : 5000
    let count = 0
    const id = setInterval(() => {
      count += 1
      setOverlayRevealedCount((prev) => Math.min(prev + 1, N))
      if (count >= N) clearInterval(id)
    }, intervalMs)
    return () => clearInterval(id)
  }, [loading, overlayPillarList.length])

  const runScore = useCallback(async () => {
    const selected = Array.from(selectedPillars)
    if (selected.length === 0) return

    // Only run pillars that don't have a valid score yet (or had a failed run). Once a pillar has a valid score,
    // changing its priority or preferences does not re-run it; we just recompute the total from existing scores and current weights.
    const toRun = selected.filter((k) => {
      const entry = pillarScores[k]
      return !entry || entry.failed
    })

    // If all selected pillars already have scores, total is derived from priorities (no API call).
    if (toRun.length === 0) {
      return
    }

    setLoading(true)
    setProgress(5)
    setScoreProgress({})
    setPillarsInProgress(toRun)
    try {
      const prioritiesForRequest: PillarPriorities = {
        active_outdoors: 'None',
        built_beauty: 'None',
        natural_beauty: 'None',
        neighborhood_amenities: 'None',
        air_travel_access: 'None',
        public_transit_access: 'None',
        healthcare_access: 'None',
        economic_security: 'None',
        quality_education: 'None',
        housing_value: 'None',
        climate_risk: 'None',
        social_fabric: 'None',
      }
      selected.forEach((k) => {
        prioritiesForRequest[k as keyof PillarPriorities] = selectedPriorities[k] ?? 'Medium'
      })
      const resp = await getScoreWithProgress(
        {
          location: place.location,
          only: toRun.join(','),
          priorities: JSON.stringify(prioritiesForRequest),
          job_categories: searchOptions.job_categories?.join(','),
          include_chains: searchOptions.include_chains,
          enable_schools: searchOptions.enable_schools,
          natural_beauty_preference:
            searchOptions.natural_beauty_preference?.length ?
              JSON.stringify(searchOptions.natural_beauty_preference) :
              undefined,
          built_character_preference: searchOptions.built_character_preference ?? undefined,
          built_density_preference: searchOptions.built_density_preference ?? undefined,
        },
        (partial) => {
          setScoreProgress((prev) => ({ ...prev, ...partial }))
          const completed = Object.keys(partial).length
          const total = toRun.length
          const pct = total > 0 ? Math.min(98, 5 + (completed / total) * 90) : 5
          setProgress(pct)
        }
      )
      const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number; error?: string; confidence?: number; data_quality?: { fallback_used?: boolean; quality_tier?: string }; status?: string }>) || {}
      const mergedScores = { ...pillarScores }
      toRun.forEach((k) => {
        const data = pillars[k]
        if (data == null) return
        const failed = Boolean(data.error) || (data.data_quality?.fallback_used === true && (data.confidence ?? 100) === 0)
        const status = data.status ?? (failed ? 'failed' : 'success')
        if (failed) {
          mergedScores[k] = { score: 0, failed: true, confidence: 0, status: status as 'failed', data_quality: data.data_quality }
        } else if (typeof data.score === 'number') {
          mergedScores[k] = { score: data.score, confidence: data.confidence ?? 0, status: status as 'success' | 'fallback', data_quality: data.data_quality }
        }
      })
      setPillarScores(mergedScores)
      const fullPillars = resp.livability_pillars as unknown as Record<string, Record<string, unknown>>
      if (fullPillars && typeof fullPillars === 'object') {
        setFullPillarData((prev) => {
          const next = { ...prev }
          toRun.forEach((k) => {
            const fp = fullPillars[k]
            if (fp && typeof fp === 'object') next[k] = { ...fp }
          })
          return next
        })
      }
      const summary = (resp as { place_summary?: string }).place_summary
      setPlaceSummary(summary ?? null)
      if (typeof (resp as { status_signal?: number }).status_signal === 'number') {
        setStatusSignal((resp as { status_signal: number }).status_signal)
      }
      setProgress(100)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Failed to run score.')
    } finally {
      setLoading(false)
      setProgress(0)
      setScoreProgress({})
      setPillarsInProgress([])
    }
  }, [place.location, searchOptions, selectedPillars, selectedPriorities, pillarScores, onError])

  // Net-new pillars: configured but not yet scored (or failed). Run Score (N) uses this count; when 0, show "View results".
  const netNewPillars = useMemo(() => {
    return Array.from(selectedPillars).filter((k) => {
      const entry = pillarScores[k]
      return !entry || entry.failed
    })
  }, [selectedPillars, pillarScores])
  const netNewCount = netNewPillars.length

  const hasResults = Object.keys(pillarScores).length > 0
  const locationLabel = formatPlaceLabel(place)
  const exportRow = useMemo(
    () =>
      buildExportRow({
        locationName: locationLabel,
        lat: place.lat,
        lon: place.lon,
        homefitScore: totalScore,
        longevityScore: longevityIndex,
        pillarScores,
        selectedPriorities,
      }),
    [locationLabel, place.lat, place.lon, totalScore, longevityIndex, pillarScores, selectedPriorities]
  )

  return (
    <div className="hf-card" style={{ marginTop: '1.5rem', paddingBottom: '12rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <div className="hf-label" style={{ marginBottom: '0.25rem' }}>Location</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
            {locationLabel}
          </div>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Select pillars and set importance, then Run Score.
          </div>
        </div>
        <button type="button" onClick={onBack} className="hf-btn-link">
          Search another place
        </button>
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
          coordinates={{ lat: place.lat, lon: place.lon }}
          completed_pillars={Object.keys(pillarScores)}
        />
      </div>

      {/* Score Summary — HomeFit Score on top, Longevity & Status Signal below in smaller font */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          marginBottom: '1.5rem',
          padding: '1rem 0.75rem',
        }}
      >
        <div
          style={{
            fontSize: '2.25rem',
            fontWeight: 800,
            color: totalScore != null ? 'var(--hf-homefit-green)' : 'var(--hf-text-secondary)',
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
            color: 'var(--hf-text-primary)',
            marginTop: '0.25rem',
          }}
        >
          HomeFit Score
          <HomeFitInfo />
        </div>
        <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem', textAlign: 'center', maxWidth: 320 }}>
          {HOMEFIT_COPY.subtitle}
        </div>

        {/* Longevity Index & Status Signal — below, smaller font */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '1.25rem',
            marginTop: '1rem',
            fontSize: '0.8rem',
            color: 'var(--hf-text-secondary)',
          }}
          data-longevity-index
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span className="hf-muted">Longevity Index</span>
            <span style={{ fontWeight: 600, color: longevityIndex != null ? 'var(--hf-longevity-purple)' : 'var(--hf-text-secondary)' }}>
              {longevityIndex != null ? longevityIndex.toFixed(1) : '—'}
            </span>
            <LongevityInfo />
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span className="hf-muted">Status Signal</span>
            <span style={{ fontWeight: 600, color: statusSignal != null ? 'var(--hf-text-secondary)' : 'var(--hf-text-secondary)' }}>
              {statusSignal != null ? Math.max(0, Math.min(100, statusSignal)).toFixed(1) : '—'}
            </span>
            <StatusSignalInfo onRefresh={handleRefreshStatusSignal} refreshing={statusSignalRefreshLoading} />
          </span>
        </div>
      </div>

      {/* Export scores — only when we have results */}
      {hasResults && (
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
          <button
            type="button"
            onClick={() => setExportModalOpen(true)}
            className="hf-btn-link"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontSize: '0.9rem',
              fontWeight: 600,
            }}
            aria-label="Export scores"
          >
            <span aria-hidden>📤</span>
            Export scores
          </button>
        </div>
      )}

      <ExportScoresModal
        isOpen={exportModalOpen}
        onClose={() => setExportModalOpen(false)}
        locationName={locationLabel}
        csvHeaderLine={exportRow.csvHeaderLine}
        csvDataLine={exportRow.csvDataLine}
        copyBlock={exportRow.copyBlock}
      />

      {/* Place summary from pillar data (when present) */}
      {hasResults && placeSummary && (
        <div
          className="hf-panel"
          style={{
            marginBottom: '1.5rem',
            padding: '1rem 1.25rem',
          }}
        >
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>Summary</div>
          <p
            style={{
              margin: 0,
              fontSize: '0.95rem',
              lineHeight: 1.5,
              color: 'var(--hf-text-primary)',
            }}
          >
            {placeSummary}
          </p>
        </div>
      )}

      {/* Quiz CTA: collapsed at top of pillar grid */}
      {onTakeQuiz && (
        <div className="hf-panel" style={{ marginBottom: '1rem' }}>
          <button
            type="button"
            onClick={onTakeQuiz}
            className="hf-btn-link"
            style={{ width: '100%', textAlign: 'center', padding: '0.75rem' }}
          >
            Not sure what matters to you? Take the quiz
          </button>
        </div>
      )}

      {/* Pillar list: tap to select, importance only when selected */}
      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {PILLAR_ORDER.map((key) => {
          const selected = selectedPillars.has(key)
          const score = pillarScores[key]
          const importance = selectedPriorities[key] ?? 'Medium'
          const meta = PILLAR_META[key]
          return (
            <div
              key={key}
              role="button"
              tabIndex={0}
              onClick={() => togglePillar(key)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePillar(key) } }}
              className="hf-panel"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                padding: '1rem 1.25rem',
                border: `2px solid ${selected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                borderRadius: 12,
                cursor: 'pointer',
                background: selected ? 'var(--hf-bg-subtle)' : undefined,
              }}
            >
              <div className="hf-pillar-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0, flex: '1 1 0' }}>
                  <span style={{ fontSize: '1.75rem' }}>{meta.icon}</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>{meta.name}</span>
                      {isLongevityPillar(key) && (
                        <span
                          className="hf-muted"
                          title={LONGEVITY_COPY.tooltip}
                          style={{
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            padding: '0.2rem 0.45rem',
                            borderRadius: 6,
                            background: 'var(--hf-bg-subtle)',
                            border: '1px solid var(--hf-border)',
                          }}
                        >
                          Longevity
                        </span>
                      )}
                      {score != null && (() => {
                        const ft = getPillarFailureType({ status: score.status, error: score.failed ? 'PillarExecutionFailed' : undefined, data_quality: score.data_quality })
                        const incomplete = ft === 'incomplete'
                        const fallback = ft === 'fallback'
                        const failed = ft === 'execution_error'
                        const showRerun = fallback || failed
                        const rerunDisabled = loading || pillarsInProgress.length > 0
                        return (
                          <>
                            {incomplete && (
                              <span
                                title="Score is based on incomplete data for this location and may not be fully accurate."
                                style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.2rem 0.4rem', borderRadius: 6, background: '#C8B84A', color: 'rgba(0,0,0,0.75)' }}
                              >
                                Limited data
                              </span>
                            )}
                            {fallback && (
                              <span
                                title="Real data wasn't available — this score is estimated."
                                style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.2rem 0.4rem', borderRadius: 6, background: '#C8B84A', color: 'rgba(0,0,0,0.75)' }}
                              >
                                Estimated score
                              </span>
                            )}
                            {failed && (
                              <span
                                title="We weren't able to retrieve data for this pillar."
                                className="hf-muted"
                                style={{ fontSize: '0.7rem', fontWeight: 600, padding: '0.2rem 0.4rem', borderRadius: 6, background: 'var(--hf-bg-subtle)', border: '1px solid var(--hf-border)' }}
                              >
                                Data unavailable
                              </span>
                            )}
                            {showRerun && (
                              <>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    runSinglePillar(key, searchOptions)
                                  }}
                                  disabled={rerunDisabled}
                                  aria-label="Rerun this pillar"
                                  className="hf-btn-primary"
                                  style={{
                                    padding: '0.5rem 0.75rem',
                                    minHeight: 44,
                                    minWidth: 44,
                                    borderRadius: 8,
                                    fontSize: '0.85rem',
                                    fontWeight: 600,
                                    cursor: rerunDisabled ? 'not-allowed' : 'pointer',
                                    opacity: rerunDisabled ? 0.6 : 1,
                                  }}
                                >
                                  Rerun
                                </button>
                                {rerunFailedPillar === key && (
                                  <span className="hf-muted" style={{ fontSize: '0.8rem' }}>
                                    Still unable to retrieve data
                                  </span>
                                )}
                              </>
                            )}
                          </>
                        )
                      })()}
                    </div>
                    <div className="hf-muted" style={{ fontSize: '0.85rem' }}>{meta.description}</div>
                  </div>
                </div>
                <div className="hf-pillar-row-right">
                  {!selected && score == null && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        togglePillar(key)
                      }}
                      onKeyDown={(e) => e.stopPropagation()}
                      className="hf-btn-primary"
                      style={{
                        padding: '0.4rem 0.85rem',
                        borderRadius: 8,
                        fontSize: '0.9rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Add
                    </button>
                  )}
                  {score != null && (() => {
                    const failureType = getPillarFailureType({
                      status: score.status,
                      error: score.failed ? 'PillarExecutionFailed' : undefined,
                      data_quality: score.data_quality,
                    })
                    const showRerun = (failureType === 'fallback' || failureType === 'execution_error')
                    const rerunDisabled = loading || pillarsInProgress.length > 0
                    const isRerunning = pillarsInProgress.includes(key)
                    const isFailed = failureType === 'execution_error'
                    const isFallback = failureType === 'fallback'
                    const isIncomplete = failureType === 'incomplete'
                    if (isRerunning) {
                      return (
                        <span className="hf-muted" style={{ fontSize: '0.85rem' }}>
                          Updating…
                        </span>
                      )
                    }
                    return (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'baseline',
                            gap: '0.25rem',
                            fontWeight: 800,
                            fontSize: '1rem',
                            padding: '0.3rem 0.55rem',
                            borderRadius: 8,
                            background: isFailed ? 'var(--hf-bg-subtle)' : getScoreBandBackground(score.score),
                            border: `1px solid ${isFailed ? 'var(--hf-border)' : getScoreBandColor(score.score)}`,
                            color: isFailed ? 'var(--hf-text-secondary)' : getScoreBandColor(score.score),
                          }}
                        >
                          {isFailed ? (
                            '?'
                          ) : (
                            <>
                              {isFallback && <span style={{ opacity: 0.9 }}>~</span>}
                              <span style={{ color: isFailed ? undefined : 'var(--hf-text-primary)' }}>{score.score.toFixed(0)}</span>
                              <span style={{ fontSize: '0.8rem', fontWeight: 600, opacity: 0.95 }}>· {getScoreBandLabel(score.score)}</span>
                            </>
                          )}
                        </span>
                      </span>
                    )
                  })()}
                  {score != null && !score.failed && pillarWeightsAndContributions[key] && (
                    <div className="hf-muted hf-pillar-weight-line" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                      {pillarWeightsAndContributions[key].weight.toFixed(1)}% · {pillarWeightsAndContributions[key].contribution.toFixed(1)} to total
                    </div>
                  )}
                  {score == null && selected && (
                    <span className="hf-muted" style={{ fontSize: '0.85rem' }}>Selected</span>
                  )}
                </div>
              </div>
              {selected && (
                <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.25rem' }}>Importance:</span>
                    {(['Low', 'Medium', 'High'] as const).map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setPillarImportance(key, level)
                        }}
                        style={{
                          padding: '0.35rem 0.65rem',
                          borderRadius: 8,
                          fontSize: '0.85rem',
                          fontWeight: importance === level ? 700 : 400,
                          background: importance === level ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                          color: importance === level ? 'white' : 'var(--hf-text-secondary)',
                          border: '1px solid var(--hf-border)',
                          cursor: 'pointer',
                        }}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                  {key === 'natural_beauty' && onSearchOptionsChange && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.25rem' }}>Scenery:</span>
                      <span className="hf-muted" style={{ fontSize: '0.75rem', marginRight: '0.35rem' }}>(up to 2)</span>
                      {NATURAL_BEAUTY_PREFERENCE_CHIPS.map(({ value, label }) => {
                        const pref = searchOptions.natural_beauty_preference ?? []
                        const isAny = value === null
                        const hasAny = !pref.length || (pref.length === 1 && pref[0] === 'no_preference')
                        const chipSelected = isAny
                          ? hasAny
                          : pref.includes(value as string)
                        const atMax = !isAny && pref.length >= 2 && !pref.includes(value as string)
                        const handleClick = () => {
                          if (isAny) {
                            handleSearchOptionsChange({ ...searchOptions, natural_beauty_preference: null })
                            return
                          }
                          const current = pref.filter((v) => v !== 'no_preference')
                          if (current.includes(value as string)) {
                            const next = current.filter((v) => v !== value)
                            handleSearchOptionsChange({
                              ...searchOptions,
                              natural_beauty_preference: next.length ? next : null,
                            })
                          } else if (current.length >= 2) {
                            handleSearchOptionsChange({
                              ...searchOptions,
                              natural_beauty_preference: [current[1], value as string],
                            })
                          } else {
                            handleSearchOptionsChange({
                              ...searchOptions,
                              natural_beauty_preference: [...current, value as string],
                            })
                          }
                        }
                        return (
                          <button
                            key={label}
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleClick()
                            }}
                            disabled={atMax}
                            style={{
                              padding: '0.35rem 0.65rem',
                              borderRadius: 8,
                              fontSize: '0.85rem',
                              fontWeight: chipSelected ? 600 : 400,
                              background: chipSelected ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                              color: chipSelected ? 'white' : atMax ? 'var(--hf-text-tertiary)' : 'var(--hf-text-secondary)',
                              border: `1px solid ${chipSelected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                              cursor: atMax ? 'not-allowed' : 'pointer',
                              opacity: atMax ? 0.7 : 1,
                            }}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </div>
                  )}
                  {key === 'economic_security' && onSearchOptionsChange && (
                    <div style={{ borderTop: '1px solid var(--hf-border)', paddingTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <span className="hf-muted" style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>Economic Opportunity Focus (optional)</span>
                      <p className="hf-muted" style={{ fontSize: '0.8rem', margin: 0 }}>
                        Select job categories you care about. Scoring may take a bit longer when categories are selected.
                      </p>
                      <div style={{ display: 'grid', gap: '0.5rem' }}>
                        {JOB_CATEGORY_OPTIONS.map((opt) => {
                          const current = Array.isArray(searchOptions.job_categories) ? searchOptions.job_categories : []
                          const checked = current.includes(opt.key)
                          return (
                            <label key={opt.key} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer' }} onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={loading}
                                onChange={(e) => {
                                  const next = e.target.checked
                                    ? Array.from(new Set([...current, opt.key]))
                                    : current.filter((k) => k !== opt.key)
                                  handleSearchOptionsChange({ ...searchOptions, job_categories: next })
                                }}
                                style={{ marginTop: '0.2rem' }}
                              />
                              <span style={{ flex: 1 }}>
                                <span style={{ fontWeight: 600, color: 'var(--hf-text-primary)', fontSize: '0.9rem' }}>{opt.label}</span>
                                <span className="hf-muted" style={{ display: 'block', fontSize: '0.8rem' }}>{opt.description}</span>
                              </span>
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  )}
                  {key === 'built_beauty' && (
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.25rem' }}>Character:</span>
                        {BUILT_CHARACTER_CHIPS.map(({ value, label }) => {
                          const selected = searchOptions.built_character_preference === value
                          return (
                            <button
                              key={value}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleSearchOptionsChange({
                                  ...searchOptions,
                                  built_character_preference: selected ? null : value,
                                })
                              }}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: 8,
                                fontSize: '0.85rem',
                                fontWeight: selected ? 600 : 400,
                                background: selected ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                color: selected ? 'white' : 'var(--hf-text-secondary)',
                                border: `1px solid ${selected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                cursor: 'pointer',
                              }}
                            >
                              {label}
                            </button>
                          )
                        })}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.25rem' }}>Density:</span>
                        {BUILT_DENSITY_CHIPS.map(({ value, label }) => {
                          const selected = searchOptions.built_density_preference === value
                          return (
                            <button
                              key={value}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleSearchOptionsChange({
                                  ...searchOptions,
                                  built_density_preference: selected ? null : value,
                                })
                              }}
                              style={{
                                padding: '0.35rem 0.65rem',
                                borderRadius: 8,
                                fontSize: '0.85rem',
                                fontWeight: selected ? 600 : 400,
                                background: selected ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                                color: selected ? 'white' : 'var(--hf-text-secondary)',
                                border: `1px solid ${selected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                                cursor: 'pointer',
                              }}
                            >
                              {label}
                            </button>
                          )
                        })}
                      </div>
                    </>
                  )}
                  {key === 'quality_education' && (
                    <div style={{ borderTop: '1px solid var(--hf-border)', paddingTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <label className="hf-muted" style={{ fontSize: '0.85rem' }}>Premium code (enables school scoring)</label>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <input
                          type="text"
                          value={premiumCodeInput}
                          onChange={(e) => setPremiumCodeInput(e.target.value)}
                          placeholder="Enter code"
                          className="hf-input"
                          disabled={loading}
                          style={{ flex: 1, minWidth: 140 }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const v = premiumCodeInput.trim()
                            setSavedPremiumCode(v)
                            try {
                              if (v) window.sessionStorage?.setItem(PREMIUM_CODE_KEY, v)
                              else window.sessionStorage?.removeItem(PREMIUM_CODE_KEY)
                            } catch (_) {}
                          }}
                          disabled={loading}
                          className="hf-premium-btn"
                        >
                          Save
                        </button>
                        {savedPremiumCode ? (
                          <button
                            type="button"
                            onClick={() => {
                              setPremiumCodeInput('')
                              setSavedPremiumCode('')
                              try { window.sessionStorage?.removeItem(PREMIUM_CODE_KEY) } catch (_) {}
                            }}
                            disabled={loading}
                            className="hf-premium-btn hf-premium-btn--outline"
                          >
                            Clear
                          </button>
                        ) : null}
                      </div>
                      {onSearchOptionsChange && (
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', cursor: 'pointer', marginTop: '0.25rem' }}>
                          <input
                            type="checkbox"
                            checked={searchOptions.enable_schools}
                            disabled={loading}
                            onChange={(e) => handleSearchOptionsChange({ ...searchOptions, enable_schools: e.target.checked })}
                          />
                          <span style={{ color: 'var(--hf-text-primary)' }}>Include school scoring</span>
                        </label>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Fixed bottom bar: pillar count, Run Score, and importance prompt */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          padding: '1rem 1.25rem',
          paddingLeft: 'max(1.25rem, env(safe-area-inset-left))',
          paddingRight: 'max(1.25rem, env(safe-area-inset-right))',
          paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
          background: 'var(--hf-card-bg)',
          borderTop: '1px solid var(--hf-border)',
          boxShadow: '0 -4px 20px rgba(0,0,0,0.06)',
        }}
      >
        {/* Save this place — show when we have results and save is available */}
        {hasResults && onSave && savePayload && (
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
            {isSignedIn ? (
              savedScoreId ? (
                <span className="hf-muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.95rem' }}>
                  ✓ Saved
                  <Link href="/saved" className="hf-auth-link" style={{ fontWeight: 600 }}>My places</Link>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="hf-btn-secondary"
                  style={{ padding: '0.6rem 1rem', borderRadius: 10, fontSize: '0.95rem' }}
                  data-testid="save-place"
                >
                  {saving ? 'Saving…' : 'Save this place'}
                </button>
              )
            ) : isAuthConfigured ? (
              <button
                type="button"
                onClick={() => openAuthModal('signin')}
                className="hf-btn-secondary"
                style={{ padding: '0.6rem 1rem', borderRadius: 10, fontSize: '0.95rem' }}
              >
                Sign in to save this place
              </button>
            ) : null}
            {saveError && <span className="hf-muted" style={{ fontSize: '0.85rem', color: 'var(--hf-danger)' }}>{saveError}</span>}
          </div>
        )}
        {selectedPillars.size > 0 && !loading && (
          <p className="hf-muted" style={{ fontSize: '0.85rem', marginBottom: '0.75rem', marginTop: 0 }}>
            {netNewCount === 0 ? (
              <>All {selectedPillars.size} pillar{selectedPillars.size === 1 ? '' : 's'} scored</>
            ) : (
              <>Run score for {netNewCount} new pillar{netNewCount === 1 ? '' : 's'}</>
            )}
          </p>
        )}
        {netNewCount > 0 ? (
          <button
            type="button"
            onClick={runScore}
            disabled={loading || pillarsInProgress.length > 0}
            className="hf-btn-primary"
            style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1.1rem' }}
            data-testid="run-score"
          >
            {loading ? 'Scoring…' : pillarsInProgress.length > 0 ? 'Rerunning…' : `Run Score (${netNewCount})`}
          </button>
        ) : hasResults && savePayload && onShowResults ? (
          <button
            type="button"
            onClick={() => onShowResults(savePayload, savePriorities)}
            className="hf-btn-primary"
            style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1.1rem' }}
          >
            View results
          </button>
        ) : (
          <button
            type="button"
            disabled
            className="hf-btn-primary"
            style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1.1rem', opacity: 0.6, cursor: 'not-allowed' }}
          >
            Run Score
          </button>
        )}
      </div>

      {/* Scoring overlay: dimmed, non-interactive; shows headline, subtitle, pillar names appearing over ~5s */}
      {loading && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="scoring-overlay-headline"
          aria-describedby="scoring-overlay-subtitle"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0,0,0,0.5)',
            padding: '1.5rem',
          }}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <div
            className="hf-panel"
            style={{
              maxWidth: 400,
              width: '100%',
              padding: '1.5rem 1.75rem',
              borderRadius: 12,
              background: 'var(--hf-card-bg)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2
              id="scoring-overlay-headline"
              style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}
            >
              Analyzing HomeFit
            </h2>
            <p
              id="scoring-overlay-subtitle"
              className="hf-muted"
              style={{ fontSize: '0.95rem', marginTop: '0.35rem', marginBottom: 0 }}
            >
              Scoring {overlayPillarList.length} pillar{overlayPillarList.length === 1 ? '' : 's'}…
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '1rem 0 0', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {overlayPillarList.slice(0, overlayRevealedCount).map((key) => {
                const meta = PILLAR_META[key]
                const isComplete = key in scoreProgress
                return (
                  <li key={key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: isComplete ? 'var(--hf-homefit-green, #4A9E6B)' : 'var(--hf-primary-1)',
                        flexShrink: 0,
                      }}
                      aria-hidden
                    />
                    <span style={{ fontSize: '0.95rem', color: 'var(--hf-text-primary)' }}>{meta.name}</span>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
