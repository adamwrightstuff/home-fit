'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import InteractiveMap from './InteractiveMap'
import LongevityInfo from './LongevityInfo'
import HomeFitInfo from './HomeFitInfo'
import ExportScoresModal from './ExportScoresModal'
import { buildExportRow } from '@/lib/exportScores'
import { PILLAR_META, getScoreBadgeClass, getScoreBandLabel, getScoreBandColor, isLongevityPillar, LONGEVITY_COPY, HOMEFIT_COPY, computeLongevityIndex, type PillarKey } from '@/lib/pillars'
import { totalFromPartialPillarScores, getPillarWeightsAndContributions } from '@/lib/reweight'
import { getScoreWithProgress } from '@/lib/api'
import type { GeocodeResult } from '@/types/api'
import type { SearchOptions } from './SearchOptions'
import type { PillarPriorities } from './SearchOptions'

const PILLAR_ORDER: PillarKey[] = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'economic_security',
  'quality_education',
  'housing_value',
  'climate_risk',
  'social_fabric',
]

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
}

export default function PlaceView({ place, searchOptions, onSearchOptionsChange, onError, onBack, onTakeQuiz, justAppliedQuizPriorities, onAppliedQuizPrioritiesConsumed }: PlaceViewProps) {
  const [selectedPillars, setSelectedPillars] = useState<Set<string>>(new Set())
  const [selectedPriorities, setSelectedPriorities] = useState<Record<string, Importance>>({})
  const [pillarScores, setPillarScores] = useState<Record<string, { score: number }>>({})
  const longevityIndex = useMemo(() => computeLongevityIndex(pillarScores), [pillarScores])
  const [placeSummary, setPlaceSummary] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [scoreProgress, setScoreProgress] = useState<Record<string, { score: number }>>({})
  const [pillarsInProgress, setPillarsInProgress] = useState<string[]>([])
  const [premiumCodeInput, setPremiumCodeInput] = useState('')
  const [savedPremiumCode, setSavedPremiumCode] = useState('')
  /** Number of pillar names revealed in the scoring overlay (0..N over ~5s). */
  const [overlayRevealedCount, setOverlayRevealedCount] = useState(0)
  const [exportModalOpen, setExportModalOpen] = useState(false)
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

  // Re-run a single pillar with given options (e.g. after Scenery/Character/Density change). Updates that pillar's score and total.
  const runSinglePillar = useCallback(
    async (pillarKey: 'natural_beauty' | 'built_beauty', options: SearchOptions) => {
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
        const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number }>) || {}
        const data = pillars[pillarKey]
        if (data != null && typeof data.score === 'number') {
          setPillarScores((prev) => ({ ...prev, [pillarKey]: { score: data.score } }))
        }
        const summary = (resp as { place_summary?: string }).place_summary
        if (summary != null) setPlaceSummary(summary)
        setProgress(100)
      } catch (e) {
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

  // Derive total from pillar scores and effective priorities so changing priority updates total immediately (no API call).
  const totalScore = useMemo(() => {
    const partialScores = Object.fromEntries(
      Object.entries(pillarScores).map(([k, v]) => [k, v.score])
    )
    if (Object.keys(partialScores).length === 0) return null
    return totalFromPartialPillarScores(partialScores, effectivePriorities) ?? null
  }, [pillarScores, effectivePriorities])

  // Per-pillar weight % and contribution from current priorities (recalculation without API — updates when Importance changes).
  const pillarWeightsAndContributions = useMemo(() => {
    const partialScores = Object.fromEntries(
      Object.entries(pillarScores).map(([k, v]) => [k, v.score])
    )
    if (Object.keys(partialScores).length === 0) return {}
    return getPillarWeightsAndContributions(partialScores, effectivePriorities)
  }, [pillarScores, effectivePriorities])

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

    // Only run pillars that don't have a score yet. Once a pillar has been run for this location,
    // changing its priority or preferences does not re-run it; we just recompute the total from
    // existing scores and current weights (see useEffect below).
    const toRun = selected.filter((k) => !(k in pillarScores))

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
      const pillars = (resp.livability_pillars as unknown as Record<string, { score?: number }>) || {}
      const mergedScores = { ...pillarScores }
      toRun.forEach((k) => {
        const data = pillars[k]
        if (data != null && typeof data.score === 'number') mergedScores[k] = { score: data.score }
      })
      setPillarScores(mergedScores)
      const summary = (resp as { place_summary?: string }).place_summary
      setPlaceSummary(summary ?? null)
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

      {/* Score Summary — single row, two scores, no tiles */}
      <div
        style={{
          display: 'flex',
          alignItems: 'stretch',
          marginBottom: '1.5rem',
          gap: 0,
        }}
      >
        {/* HomeFit Score — left half */}
        <div
          style={{
            flex: '1 1 50%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
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
          <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem', textAlign: 'center', maxWidth: 260 }}>
            {HOMEFIT_COPY.subtitle}
          </div>
        </div>

        {/* Divider */}
        <div
          style={{
            width: 1,
            minHeight: 60,
            background: 'var(--hf-border)',
            flexShrink: 0,
          }}
        />

        {/* Longevity Index — right half */}
        <div
          style={{
            flex: '1 1 50%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem 0.75rem',
          }}
          data-longevity-index
        >
          <div
            style={{
              fontSize: '2.25rem',
              fontWeight: 800,
              color: longevityIndex != null ? 'var(--hf-longevity-purple)' : 'var(--hf-text-secondary)',
              lineHeight: 1.1,
            }}
          >
            {longevityIndex != null ? longevityIndex.toFixed(1) : '—'}
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
            Longevity Index
            <LongevityInfo />
          </div>
          <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem', textAlign: 'center', maxWidth: 260 }}>
            {LONGEVITY_COPY.short}
          </div>
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minWidth: 0 }}>
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
                    </div>
                    <div className="hf-muted" style={{ fontSize: '0.85rem' }}>{meta.description}</div>
                  </div>
                </div>
                <div style={{ flexShrink: 0 }}>
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
                  {score != null && (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span className={getScoreBadgeClass(score.score)} style={{ padding: '0.35rem 0.75rem', borderRadius: 8 }}>
                        {score.score.toFixed(0)}
                      </span>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: getScoreBandColor(score.score) }}>
                        {getScoreBandLabel(score.score)}
                      </span>
                    </span>
                  )}
                  {score != null && pillarWeightsAndContributions[key] && (
                    <div className="hf-muted" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                      Weight {pillarWeightsAndContributions[key].weight.toFixed(1)}% → contributes {pillarWeightsAndContributions[key].contribution.toFixed(1)} to total
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
        {selectedPillars.size > 0 && !loading && (
          <p className="hf-muted" style={{ fontSize: '0.85rem', marginBottom: '0.75rem', marginTop: 0 }}>
            Set importance to customize your score
          </p>
        )}
        <button
          type="button"
          onClick={runScore}
          disabled={selectedPillars.size === 0 || loading}
          className="hf-btn-primary"
          style={{ width: '100%', padding: '1rem 1.5rem', fontSize: '1.1rem' }}
        >
          {loading ? 'Scoring…' : selectedPillars.size > 0 ? `Run Score (${selectedPillars.size})` : 'Run Score'}
        </button>
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
