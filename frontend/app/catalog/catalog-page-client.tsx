'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useRouter, useSearchParams } from 'next/navigation'
import { LayoutGrid, List, SlidersHorizontal, X } from 'lucide-react'
import CatalogMapView from '@/components/catalog/CatalogMapView'
import CatalogBottomSheet, { findPlaceByKey, type CatalogSheetSnap } from '@/components/catalog/CatalogBottomSheet'
import CatalogDetailPanel from '@/components/catalog/CatalogDetailPanel'
import CatalogWeightPanel from '@/components/catalog/CatalogWeightPanel'
import PillarTwinDrawer from '@/components/catalog/PillarTwinDrawer'
import TwinFinderPanel from '@/components/catalog/TwinFinderPanel'
import TwinCandidateDetailContent from '@/components/catalog/TwinCandidateDetailContent'
import CatalogListView from '@/components/catalog/CatalogListView'
import HeroBand from '@/components/catalog/HeroBand'
import FilterSheet from '@/components/catalog/FilterSheet'
import IndexInfoButton from '@/components/catalog/IndexInfoButton'
import CompareTray from '@/components/catalog/CompareTray'
import { DEFAULT_PRIORITIES, type PillarPriorities, type PriorityLevel } from '@/components/SearchOptions'
import {
  buildCatalogFeatureCollection,
  buildTwinMatchFeatureCollection,
} from '@/lib/catalogMapGeo'
import { catalogRampKey } from '@/lib/catalogIndexColors'
import { catalogTabActiveStyle } from '@/lib/indexColorSystem'
import {
  catalogRowKey,
  inferCatalogMetro,
  type CatalogMapIndexMode,
  type CatalogMapPlace,
  type CatalogMapPlaceWithMetro,
} from '@/lib/catalogMapTypes'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import { buildResultsCacheKey, buildResultsUrl } from '@/lib/resultsShare'
import { reweightScoreResponseFromPriorities, applyUserIncomeToScore, passesHousingValueDealbreaker, passesAirTravelDealbreaker, passesQualityEducationDealbreaker, passesCommunitySafetyDealbreaker, passesNeighborhoodAmenitiesDealbreaker, passesPublicTransitDealbreaker, passesHealthcareAccessDealbreaker, passesActiveOutdoorsDealbreaker, passesClimateRiskDealbreaker, passesSocialFabricDealbreaker } from '@/lib/reweight'
import type { V9Breakdown } from '@/lib/nbPreference'
import { PILLAR_ORDER, type PillarKey, HOMEFIT_COPY, LONGEVITY_COPY, HAPPINESS_INDEX_COPY, STATUS_SIGNAL_COPY } from '@/lib/pillars'
import { rankTwinMatches, defaultTwinPillarSet, type TwinMatchResult } from '@/lib/twinSimilarity'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import PlaceValuesGame from '@/components/PlaceValuesGame'

const INDEXES: { id: CatalogMapIndexMode; label: string; tooltip: string }[] = [
  { id: 'homefit', label: 'Trovamo', tooltip: HOMEFIT_COPY.tooltip },
  { id: 'longevity', label: 'Longevity', tooltip: LONGEVITY_COPY.tooltip },
  { id: 'happiness', label: 'Happiness', tooltip: HAPPINESS_INDEX_COPY.tooltip },
  { id: 'status', label: 'Archetype', tooltip: STATUS_SIGNAL_COPY.tooltip },
]

type CatalogMode = 'explorer' | 'twin'

function sortPlaces(
  places: CatalogMapPlace[],
  sortKey: CatalogMapIndexMode | 'name',
  dir: 'asc' | 'desc',
  priorities: PillarPriorities
): CatalogMapPlace[] {
  const mult = dir === 'desc' ? -1 : 1
  const out = [...places]
  out.sort((a, b) => {
    if (sortKey === 'name') {
      return mult * a.catalog.name.localeCompare(b.catalog.name)
    }
    const get = (p: CatalogMapPlace) => {
      if (sortKey === 'homefit') return reweightScoreResponseFromPriorities(p.score, priorities).total_score
      if (sortKey === 'longevity') return p.score.longevity_index ?? NaN
      if (sortKey === 'happiness') return p.score.happiness_index ?? NaN
      return p.score.status_signal ?? NaN
    }
    const va = get(a)
    const vb = get(b)
    if (!Number.isFinite(va) && !Number.isFinite(vb)) return 0
    if (!Number.isFinite(va)) return 1
    if (!Number.isFinite(vb)) return -1
    return mult * (va - vb)
  })
  return out
}

export default function CatalogPageClient({
  initialMetroFilter = 'all',
}: {
  initialMetroFilter?: 'all' | 'nyc' | 'la'
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [places, setPlaces] = useState<CatalogMapPlaceWithMetro[]>([])
  const [loadMessage, setLoadMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [catalogMode, setCatalogMode] = useState<CatalogMode>('explorer')
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map')
  const [indexMode, setIndexMode] = useState<CatalogMapIndexMode>('homefit')
  const [priorities, setPriorities] = useState<PillarPriorities>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        const merged = { ...DEFAULT_PRIORITIES }
        const valid: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']
        for (const k of [...PILLAR_ORDER, 'natural_beauty'] as PillarKey[]) {
          if (valid.includes(parsed[k])) merged[k] = parsed[k]
        }
        return merged
      }
    } catch { /* ignore */ }
    return { ...DEFAULT_PRIORITIES }
  })
  const [filterPoliticalLean, setFilterPoliticalLean] = useState<'all' | 'progressive' | 'conservative'>('all')
  const [filterNbTypes, setFilterNbTypes] = useState<string[]>([])
  const [filterDiversity, setFilterDiversity] = useState<'all' | 'high' | 'mixed' | 'low'>('all')
  /** Deal-breaker pillars (housing_value MVP). Independent of importance weight — see CatalogWeightPanel. */
  const [dealbreakers, setDealbreakers] = useState<Partial<Record<PillarKey, boolean>>>({})
  const toggleDealbreaker = useCallback((key: PillarKey) => {
    setDealbreakers((prev) => ({ ...prev, [key]: !prev[key] }))
  }, [])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [snap, setSnap] = useState<CatalogSheetSnap>('peek')
  const [weightOpen, setWeightOpen] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  const [twinPillarOpen, setTwinPillarOpen] = useState(false)
  const [layoutVersion, setLayoutVersion] = useState(0)
  const [twinQueryKey, setTwinQueryKey] = useState<string | null>(null)
  const [twinSearchText, setTwinSearchText] = useState('')
  const [twinCrossMetro, setTwinCrossMetro] = useState(true)
  const [twinSameBand, setTwinSameBand] = useState(false)
  const [twinPillars, setTwinPillars] = useState<Set<PillarKey>>(() => defaultTwinPillarSet())
  const [filterText, setFilterText] = useState('')
  const [filterMetro, setFilterMetro] = useState<'all' | 'nyc' | 'la'>(initialMetroFilter)
  const [filterAreaTypes, setFilterAreaTypes] = useState<string[]>([])
  const [filterArchetype, setFilterArchetype] = useState<string>('all')
  const [filterTrajectory, setFilterTrajectory] = useState<'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'>('all')
  /** When true, list sorts by name; map coloring still follows `indexMode`. */
  const [sortByName, setSortByName] = useState(false)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [householdIncome, setHouseholdIncome] = useState<number | null>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return typeof parsed.household_income === 'number' && parsed.household_income > 0
          ? parsed.household_income
          : null
      }
    } catch { /* ignore */ }
    return null
  })
  const [incomeInputValue, setIncomeInputValue] = useState<string>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return typeof parsed.household_income === 'number' && parsed.household_income > 0
          ? String(parsed.household_income)
          : ''
      }
    } catch { /* ignore */ }
    return ''
  })
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [filterSheetOpen, setFilterSheetOpen] = useState(false)
  const [hoverInfo, setHoverInfo] = useState<{ key: string; x: number; y: number } | null>(null)

  const handleCompareToggle = useCallback((key: string) => {
    setCompareIds((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key)
      if (prev.length >= 2) return prev
      return [...prev, key]
    })
  }, [])

  const handleIncomeBlur = useCallback((val: string, current: number | null) => {
    const v = val === '' ? null : parseInt(val.replace(/,/g, ''), 10)
    const next = Number.isFinite(v) && (v as number) >= 10000 ? (v as number) : null
    if (next !== current) setHouseholdIncome(next)
    setIncomeInputValue(next ? String(next) : '')
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, household_income: next }))
    } catch { /* ignore */ }
  }, [])

  const handleIncomeClear = useCallback(() => {
    setHouseholdIncome(null)
    setIncomeInputValue('')
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, household_income: null }))
    } catch { /* ignore */ }
  }, [])

  const setIndexModeAndListSort = useCallback((mode: CatalogMapIndexMode) => {
    setIndexMode(mode)
    setSortByName(false)
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    setLoading(true)
    setLoadMessage(null)
    setPlaces([])
    ;(async () => {
      try {
        const r = await fetch('/api/catalog-map?metro=all', { signal: ac.signal })
        if (ac.signal.aborted) return
        const j = (await r.json()) as {
          places?: CatalogMapPlaceWithMetro[]
          source?: string
          detail?: string
          error?: string
        }
        if (ac.signal.aborted) return
        if (!r.ok) {
          setPlaces([])
          setLoadMessage(j.error ?? `Catalog request failed (${r.status}).`)
          return
        }
        setPlaces(Array.isArray(j.places) ? (j.places as CatalogMapPlaceWithMetro[]) : [])
        if (j.detail && (!j.places || j.places.length === 0)) setLoadMessage(j.detail)
        else if (j.source === 'missing') setLoadMessage(j.detail ?? 'Catalog data not found on server.')
      } catch (e) {
        if (ac.signal.aborted) return
        setLoadMessage(e instanceof Error ? e.message : 'Failed to load catalog.')
      } finally {
        if (!ac.signal.aborted) setLoading(false)
      }
    })()
    return () => ac.abort()
  }, [])

  // Load preferences from Supabase on sign-in; save debounced on change when signed in.
  useEffect(() => {
    if (!user) return
    fetch('/api/me/preferences')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        const opts = data?.explorer_options
        if (!opts) return
        const valid: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']
        if (opts.priorities) {
          const merged = { ...DEFAULT_PRIORITIES }
          for (const k of [...PILLAR_ORDER, 'natural_beauty'] as PillarKey[]) {
            if (valid.includes(opts.priorities[k])) merged[k] = opts.priorities[k]
          }
          setPriorities(merged)
        }
        if (opts.dealbreakers && typeof opts.dealbreakers === 'object') setDealbreakers(opts.dealbreakers)
        if (typeof opts.household_income === 'number' && opts.household_income > 0) {
          setHouseholdIncome(opts.household_income)
          setIncomeInputValue(String(opts.household_income))
        }
      })
      .catch(() => { /* silently ignore — sessionStorage fallback already applied */ })
  }, [user])

  useEffect(() => {
    if (!user) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      fetch('/api/me/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priorities, dealbreakers, household_income: householdIncome }),
      }).catch(() => {})
    }, 1500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [user, priorities, dealbreakers, householdIncome])

  useEffect(() => {
    const key = searchParams.get('key')
    const mode = searchParams.get('mode')
    if (key) {
      setCatalogMode('twin')
      setTwinQueryKey(key)
      setTwinSearchText('')
      setViewMode('list')
    }
    if (mode === 'twin') {
      setCatalogMode('twin')
      setViewMode('list')
    }
  }, [searchParams])

  useEffect(() => {
    if (twinQueryKey) {
      setSelectedKey(twinQueryKey)
      setSnap('peek')
    }
  }, [twinQueryKey])

  const archetypes = useMemo(() => {
    const ORDER = [
      // Current DFG bands
      'Elite', 'Affluent', 'Middle Class', 'Working Class', 'Struggling',
      // Legacy band names — kept so filters still work on old catalog data
      'Wealthy', 'Well-Off', 'Modest', 'Up-and-Coming', 'Immigrant Community',
      'Established', 'Upper Middle Class', 'Transitional',
    ]
    const s = new Set<string>()
    for (const p of places) {
      const a = p.score.status_signal_breakdown?.archetype
      if (a) s.add(a)
    }
    return Array.from(s).sort((a, b) => {
      const ia = ORDER.indexOf(a)
      const ib = ORDER.indexOf(b)
      if (ia !== -1 && ib !== -1) return ia - ib
      if (ia !== -1) return -1
      if (ib !== -1) return 1
      return a.localeCompare(b)
    })
  }, [places])

  const adjustedPlaces = useMemo(() => {
    const withIncome = householdIncome
      ? places.map((p) => ({ ...p, score: applyUserIncomeToScore(p.score, householdIncome) }))
      : places

    // Synthesize natural_beauty from neighborhood_beauty sub-score.
    // Zero out neighborhood_beauty so it doesn't double-count.
    return withIncome.map((p) => {
      const nb = (p.score.livability_pillars as any)?.neighborhood_beauty
      if (!nb) return p
      const storedNaturalScore = Number(nb.natural_beauty_score ?? nb.breakdown?.natural_beauty_score ?? 0)
      return {
        ...p,
        score: {
          ...p.score,
          livability_pillars: {
            ...p.score.livability_pillars,
            neighborhood_beauty: { ...nb, score: 0, weight: 0, contribution: 0 },
            natural_beauty: { score: storedNaturalScore, status: 'success', weight: 0, contribution: 0 },
          },
        },
      }
    })
  }, [places, householdIncome])

  const filteredPlaces = useMemo(() => {
    const t = filterText.trim().toLowerCase()
    let list = adjustedPlaces.filter((p) => {
      if (filterMetro !== 'all' && inferCatalogMetro(p) !== filterMetro) return false
      if (filterAreaTypes.length > 0) {
        const at = p.score.data_quality_summary?.area_classification?.area_type ?? ''
        if (!filterAreaTypes.includes(at)) return false
      }
      if (filterArchetype !== 'all') {
        const ar = p.score.status_signal_breakdown?.archetype
        if (ar !== filterArchetype) return false
      }
      if (filterTrajectory !== 'all') {
        const tr = p.score.status_signal_breakdown?.trajectory
        if (tr !== filterTrajectory) return false
      }
      if (filterPoliticalLean !== 'all') {
        const lean = (p.score.livability_pillars as any)?.political_lean?.breakdown?.lean_2024
        if (typeof lean !== 'number') return false
        if (filterPoliticalLean === 'progressive' && lean <= 0) return false
        if (filterPoliticalLean === 'conservative' && lean >= 0) return false
      }
      if (filterNbTypes.length > 0) {
        const nb = (p.score.livability_pillars as any)?.neighborhood_beauty
        const v9 = nb?.details?.natural_beauty?.v9_breakdown as V9Breakdown | undefined
        const passes = filterNbTypes.every((t) => {
          if (t === 'mountains') return (v9?.topo_score ?? 0) >= 35
          if (t === 'ocean') return (v9?.water_score ?? 0) >= 55
          if (t === 'lakes_rivers') return (v9?.water_score ?? 0) >= 40
          if (t === 'canopy') return (v9?.canopy_score ?? 0) >= 50 || (v9?.gvi_score ?? 0) >= 50
          return true
        })
        if (!passes) return false
      }
      if (filterDiversity !== 'all') {
        const divScore = (p.score.livability_pillars as any)?.diversity?.score
        if (typeof divScore !== 'number') return false
        if (filterDiversity === 'high' && divScore < 65) return false
        if (filterDiversity === 'mixed' && (divScore < 40 || divScore >= 65)) return false
        if (filterDiversity === 'low' && divScore >= 40) return false
      }
      if (!t) return true
      const name = (p.catalog.name || '').toLowerCase()
      const county = (p.catalog.county_borough || '').toLowerCase()
      const st = (p.catalog.state_abbr || '').toLowerCase()
      return name.includes(t) || county.includes(t) || st.includes(t)
    })
    const sortKey: CatalogMapIndexMode | 'name' = sortByName ? 'name' : indexMode
    return sortPlaces(list, sortKey, sortDir, priorities)
  }, [
    adjustedPlaces,
    filterText,
    filterMetro,
    filterAreaTypes,
    filterArchetype,
    filterTrajectory,
    filterPoliticalLean,
    filterNbTypes,
    filterDiversity,
    indexMode,
    sortByName,
    sortDir,
    priorities,
  ])

  /**
   * Deal-breaker gates: excludes places that fail any active dealbreaker, independent of
   * importance weight. Never silently empties the list — if nothing survives, fall back to
   * the unfiltered set rather than showing a blank screen. Add a pillar by adding an entry
   * here and to DEALBREAKER_PILLARS in CatalogWeightPanel.
   */
  const DEALBREAKER_CHECKS: Partial<Record<PillarKey, (p: CatalogMapPlace) => boolean>> = {
    housing_value: (p) => {
      const hv = (p.score.livability_pillars as any)?.housing_value
      const medianHomeValue = Number(hv?.summary?.median_home_value ?? 0) || null
      return passesHousingValueDealbreaker(medianHomeValue, householdIncome)
    },
    air_travel_access: (p) => {
      const ata = (p.score.livability_pillars as any)?.air_travel_access
      const nb = (p.score.livability_pillars as any)?.neighborhood_beauty
      const nearestAirportKm = Number(ata?.summary?.nearest_airport_km ?? 0) || null
      const effectiveAreaType = nb?.breakdown?.effective_area_type ?? nb?.details?.effective_area_type ?? null
      return passesAirTravelDealbreaker(nearestAirportKm, effectiveAreaType)
    },
    quality_education: (p) => {
      const qe = (p.score.livability_pillars as any)?.quality_education
      const score = typeof qe?.score === 'number' ? qe.score : null
      return passesQualityEducationDealbreaker(score)
    },
    community_safety: (p) => {
      const cs = (p.score.livability_pillars as any)?.community_safety
      const score = typeof cs?.score === 'number' ? cs.score : null
      return passesCommunitySafetyDealbreaker(score)
    },
    neighborhood_amenities: (p) => {
      const na = (p.score.livability_pillars as any)?.neighborhood_amenities
      const nb = (p.score.livability_pillars as any)?.neighborhood_beauty
      const businessesWithinWalk = na?.breakdown?.home_walkability?.businesses_within_walk
      const effectiveAreaType = nb?.breakdown?.effective_area_type ?? nb?.details?.effective_area_type ?? null
      return passesNeighborhoodAmenitiesDealbreaker(
        typeof businessesWithinWalk === 'number' ? businessesWithinWalk : null,
        effectiveAreaType
      )
    },
    public_transit_access: (p) => {
      const pt = (p.score.livability_pillars as any)?.public_transit_access
      const meanCommuteMinutes = pt?.summary?.mean_commute_minutes
      return passesPublicTransitDealbreaker(typeof meanCommuteMinutes === 'number' ? meanCommuteMinutes : null)
    },
    healthcare_access: (p) => {
      const score = (p.score.livability_pillars as any)?.healthcare_access?.score
      return passesHealthcareAccessDealbreaker(typeof score === 'number' ? score : null)
    },
    active_outdoors: (p) => {
      const score = (p.score.livability_pillars as any)?.active_outdoors?.score
      return passesActiveOutdoorsDealbreaker(typeof score === 'number' ? score : null)
    },
    climate_risk: (p) => {
      const score = (p.score.livability_pillars as any)?.climate_risk?.score
      return passesClimateRiskDealbreaker(typeof score === 'number' ? score : null)
    },
    social_fabric: (p) => {
      const score = (p.score.livability_pillars as any)?.social_fabric?.score
      return passesSocialFabricDealbreaker(typeof score === 'number' ? score : null)
    },
  }
  const activeDealbreakerKeys = (Object.keys(dealbreakers) as PillarKey[]).filter((k) => dealbreakers[k] && DEALBREAKER_CHECKS[k])
  const dealbreakerActive = activeDealbreakerKeys.length > 0
  const { gatedPlaces, dealbreakerExcludedCount, dealbreakerZeroSurvivors } = useMemo(() => {
    if (activeDealbreakerKeys.length === 0) {
      return { gatedPlaces: filteredPlaces, dealbreakerExcludedCount: 0, dealbreakerZeroSurvivors: false }
    }
    const survivors = filteredPlaces.filter((p) => activeDealbreakerKeys.every((k) => DEALBREAKER_CHECKS[k]!(p)))
    if (survivors.length === 0) {
      return { gatedPlaces: filteredPlaces, dealbreakerExcludedCount: 0, dealbreakerZeroSurvivors: true }
    }
    return {
      gatedPlaces: survivors,
      dealbreakerExcludedCount: filteredPlaces.length - survivors.length,
      dealbreakerZeroSurvivors: false,
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredPlaces, activeDealbreakerKeys.join(','), householdIncome])

  const queryPlace = twinQueryKey ? findPlaceByKey(adjustedPlaces, twinQueryKey) : null

  const twinCandidatePlaces = useMemo(() => {
    if (catalogMode !== 'twin' || !queryPlace || !twinQueryKey) return []
    const qm = inferCatalogMetro(queryPlace)
    return adjustedPlaces.filter((p) => {
      const id = catalogRowKey(p.catalog)
      if (id === twinQueryKey) return false
      const m = inferCatalogMetro(p)
      if (twinCrossMetro) return m !== qm
      return m === qm
    })
  }, [catalogMode, queryPlace, adjustedPlaces, twinQueryKey, twinCrossMetro])

  const twinPillarList = useMemo(() => PILLAR_ORDER.filter((k) => twinPillars.has(k)), [twinPillars])

  const twinRanked: TwinMatchResult[] = useMemo(() => {
    if (catalogMode !== 'twin' || !twinQueryKey || !queryPlace || twinPillarList.length < 2) return []
    return rankTwinMatches(
      queryPlace,
      twinCandidatePlaces,
      twinPillarList,
      (pl) => catalogRowKey(pl.catalog),
      12,
      twinSameBand
    )
  }, [catalogMode, twinQueryKey, queryPlace, twinCandidatePlaces, twinPillarList, twinSameBand])

  const mapPlacesNoTwinQuery = useMemo(() => {
    if (catalogMode !== 'twin') return gatedPlaces
    if (!twinQueryKey) return []
    return gatedPlaces
  }, [catalogMode, twinQueryKey, gatedPlaces])

  const explorerGeo = useMemo(
    () => buildCatalogFeatureCollection(mapPlacesNoTwinQuery, indexMode, priorities),
    [mapPlacesNoTwinQuery, indexMode, priorities]
  )

  const twinGeo = useMemo(() => {
    if (catalogMode !== 'twin' || !queryPlace) {
      return buildCatalogFeatureCollection([], indexMode, priorities)
    }
    const topKey = twinRanked[0]?.key ?? null
    return buildTwinMatchFeatureCollection(twinRanked, topKey)
  }, [catalogMode, queryPlace, twinRanked, indexMode, priorities])

  const mapData = catalogMode === 'twin' && twinQueryKey ? twinGeo : explorerGeo

  const mapRegion = useMemo(() => {
    if (catalogMode === 'twin' && queryPlace && twinQueryKey) {
      const qm = inferCatalogMetro(queryPlace)
      if (twinCrossMetro) return qm === 'nyc' ? 'la' : 'nyc'
      return qm
    }
    if (filterMetro === 'all') return 'both'
    return filterMetro
  }, [catalogMode, queryPlace, twinQueryKey, twinCrossMetro, filterMetro])

  const twinLineGeoJson = useMemo(() => {
    if (catalogMode !== 'twin' || !queryPlace || twinRanked.length === 0) return null
    const top = twinRanked[0]!
    const coordinates: [number, number][] = [
      [queryPlace.catalog.lon, queryPlace.catalog.lat],
      [top.place.catalog.lon, top.place.catalog.lat],
    ]
    return {
      type: 'FeatureCollection' as const,
      features: [
        {
          type: 'Feature' as const,
          properties: {},
          geometry: {
            type: 'LineString' as const,
            coordinates,
          },
        },
      ],
    }
  }, [catalogMode, queryPlace, twinRanked])

  const fitKey = `${catalogMode}-${twinQueryKey ?? 'nq'}-${filterMetro}-${twinCrossMetro}-${twinPillarList.join(',')}-${mapData.features.length}`

  const selectedPlace = useMemo(() => findPlaceByKey(gatedPlaces, selectedKey), [gatedPlaces, selectedKey])

  const selectedTwinMatch = useMemo(() => {
    if (!selectedKey || !twinQueryKey || selectedKey === twinQueryKey) return null
    return twinRanked.find((r) => r.key === selectedKey) ?? null
  }, [selectedKey, twinQueryKey, twinRanked])

  const twinControlsLocked = catalogMode === 'twin' && !twinQueryKey

  const onSelectKey = useCallback(
    (key: string | null) => {
      setSelectedKey(key)
      if (key) setSnap('peek')
      if (!key) return
      if (catalogMode === 'twin' && !twinQueryKey) {
        setTwinQueryKey(key)
        setTwinSearchText('')
        router.replace(`/catalog?mode=twin&key=${encodeURIComponent(key)}`, { scroll: false })
      }
    },
    [catalogMode, twinQueryKey, router]
  )

  useEffect(() => {
    setLayoutVersion((v) => v + 1)
  }, [snap])

  useEffect(() => {
    if (indexMode !== 'homefit') setWeightOpen(false)
  }, [indexMode])

  const handleFullBreakdown = useCallback(
    (place: CatalogMapPlace) => {
      const prioritiesJson = JSON.stringify(priorities)
      const routeParams = {
        location: place.catalog.search_query,
        prioritiesJson,
        job_categories: null as string | null,
        include_chains: false,
        enable_schools: false,
        natural_beauty_preference: null as string | null,
        built_character_preference: null as string | null,
        built_density_preference: null as string | null,
        political_preference: null,
      }
      const cacheKey = buildResultsCacheKey(routeParams)
      writeCatalogResultsHydrate({ v: 1, cacheKey, score: place.score })
      router.push(buildResultsUrl(routeParams))
    },
    [priorities, router]
  )

  const clearSelection = useCallback(() => {
    setSelectedKey(null)
    setSnap('peek')
  }, [])

  const clearTwinQuery = useCallback(() => {
    setTwinQueryKey(null)
    setTwinSearchText('')
    setSelectedKey(null)
    router.replace('/catalog', { scroll: false })
  }, [router])

  const onTwinRow = useCallback(
    (key: string) => {
      setCatalogMode('twin')
      setTwinQueryKey(key)
      setTwinSearchText('')
      setViewMode('list')
      setSelectedKey(key)
      setSnap('peek')
      router.replace(`/catalog?mode=twin&key=${encodeURIComponent(key)}`, { scroll: false })
    },
    [router]
  )

  const onTwinSelectFromSearch = useCallback(
    (key: string) => {
      setTwinQueryKey(key)
      setTwinSearchText('')
      setSelectedKey(key)
      setSnap('peek')
      router.replace(`/catalog?mode=twin&key=${encodeURIComponent(key)}`, { scroll: false })
    },
    [router]
  )

  if (showQuiz) {
    return (
      <PlaceValuesGame
        onApplyPriorities={(quizPriorities) => {
          setPriorities(quizPriorities)
          setShowQuiz(false)
        }}
        onBack={() => setShowQuiz(false)}
      />
    )
  }

  return (
    <div className="hf-viewport hf-catalog-root flex min-h-0 flex-col">
      <div className="hidden md:block"><HeroBand /></div>
      <header className="z-30 shrink-0 border-b border-[var(--hf-border)] bg-white/95 backdrop-blur">
        {/* ── Desktop single-row toolbar ── */}
        <div className="hidden md:flex md:items-center md:gap-2 md:px-4 md:py-2 md:flex-wrap">
          {/* Mode tabs */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              className={`rounded-full px-3 py-1 text-xs font-bold ${catalogMode === 'explorer' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
              style={catalogMode === 'explorer' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
              onClick={() => { setCatalogMode('explorer'); setTwinQueryKey(null); setTwinSearchText(''); router.replace('/catalog', { scroll: false }) }}
            >Explorer</button>
            <button
              type="button"
              className={`rounded-full px-3 py-1 text-xs font-bold ${catalogMode === 'twin' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
              style={catalogMode === 'twin' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
              onClick={() => { setCatalogMode('twin'); setViewMode('list') }}
            >Twin finder</button>
          </div>

          <div className="h-4 w-px bg-[var(--hf-border)] shrink-0" />

          {/* Search / Twin input */}
          {catalogMode === 'explorer' ? (
            <input
              type="search"
              placeholder="Filter neighborhoods…"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="w-44 rounded-lg border border-[var(--hf-border)] px-2 py-1 text-xs shrink-0"
            />
          ) : (
            <div className="relative flex items-center shrink-0">
              <input
                type="search"
                placeholder="Search a neighborhood to find its twin…"
                value={twinQueryKey && queryPlace ? queryPlace.catalog.name : twinSearchText}
                onChange={(e) => { if (twinQueryKey) return; setTwinSearchText(e.target.value) }}
                readOnly={!!twinQueryKey}
                className="w-56 rounded-lg border border-[var(--hf-border)] py-1 pl-2 pr-7 text-xs"
              />
              {twinQueryKey && (
                <button type="button" className="absolute right-1 rounded p-0.5 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]" onClick={clearTwinQuery} aria-label="Clear neighborhood">
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          )}

          {catalogMode === 'explorer' && (
            <>
              <div className="h-4 w-px bg-[var(--hf-border)] shrink-0" />
              {/* Metro */}
              <div className="flex items-center gap-1 shrink-0">
                {(['all', 'nyc', 'la'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-bold ${filterMetro === m ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
                    style={filterMetro === m ? { background: 'var(--hf-primary-1)' } : {}}
                    onClick={() => setFilterMetro(m)}
                  >{m === 'all' ? 'All metros' : m.toUpperCase()}</button>
                ))}
              </div>

              <div className="h-4 w-px bg-[var(--hf-border)] shrink-0" />
              {/* Index tabs */}
              <div className="flex items-center gap-1 shrink-0">
                {INDEXES.map((x) => {
                  const active = indexMode === x.id && !sortByName
                  const activeStyle = catalogTabActiveStyle(catalogRampKey(x.id))
                  return (
                    <div key={x.id} className="flex items-center gap-0.5">
                      <button
                        type="button"
                        aria-pressed={active}
                        title={x.tooltip}
                        className="rounded-full px-2.5 py-1 text-xs font-bold"
                        style={active ? { ...activeStyle, border: 'none' } : { background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }}
                        onClick={() => setIndexModeAndListSort(x.id)}
                      >{x.label}</button>
                      <IndexInfoButton indexId={x.id} />
                    </div>
                  )
                })}
                <button
                  type="button"
                  aria-pressed={sortByName}
                  className={`text-[0.65rem] font-semibold ${sortByName ? 'text-[var(--hf-primary-1)] underline' : 'text-[var(--hf-text-secondary)]'}`}
                  onClick={() => setSortByName(true)}
                >A–Z</button>
                <button
                  type="button"
                  className="text-[0.65rem] font-semibold text-[var(--hf-primary-1)]"
                  onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
                >{sortDir === 'desc' ? 'Desc' : 'Asc'}</button>
              </div>
            </>
          )}

          {catalogMode === 'twin' && (
            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-bold disabled:opacity-40 ${twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinCrossMetro(true)}
              >Cross-metro</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-bold disabled:opacity-40 ${!twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinCrossMetro(false)}
              >Same metro</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-bold disabled:opacity-40 ${twinSameBand ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinSameBand((v) => !v)}
              >Same class</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className="flex items-center gap-1 rounded-lg border border-[var(--hf-border)] px-2 py-0.5 text-[0.65rem] font-bold disabled:opacity-40"
                onClick={() => !twinControlsLocked && setTwinPillarOpen(true)}
              >
                <SlidersHorizontal className="h-3 w-3" />
                Pillars ({twinPillarList.length})
              </button>
            </div>
          )}

          {/* Right-side controls */}
          <div className="ml-auto flex items-center gap-1.5 shrink-0">
            {catalogMode === 'explorer' && (
              <>
                <button
                  type="button"
                  className="flex items-center gap-1 rounded-lg border border-[var(--hf-border)] px-2.5 py-1 text-xs font-semibold text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]"
                  onClick={() => setFilterSheetOpen(true)}
                >
                  <span>⚙</span>
                  Filters
                  {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetype !== 'all' ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean !== 'all' ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterDiversity !== 'all' ? 1 : 0) > 0 && (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full text-[0.6rem] font-bold text-white" style={{ background: 'var(--hf-primary-1)' }}>
                      {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetype !== 'all' ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean !== 'all' ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterDiversity !== 'all' ? 1 : 0)}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  title={indexMode !== 'homefit' ? 'Weights apply to Trovamo score only' : undefined}
                  className="rounded-lg border border-[var(--hf-border-strong)] px-2.5 py-1 text-xs font-bold text-[var(--hf-text-primary)] hover:bg-[var(--hf-hover-bg)]"
                  style={{ opacity: indexMode !== 'homefit' ? 0.4 : 1, pointerEvents: indexMode !== 'homefit' ? 'none' : 'auto' }}
                  onClick={() => setWeightOpen(true)}
                >Adjust weights</button>
              </>
            )}
            <div className="h-4 w-px bg-[var(--hf-border)]" />
            <button type="button" className={`rounded-lg p-1.5 ${viewMode === 'map' ? 'bg-[var(--hf-hover-bg)]' : ''}`} onClick={() => setViewMode('map')} title="Map">
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button type="button" className={`rounded-lg p-1.5 ${viewMode === 'list' ? 'bg-[var(--hf-hover-bg)]' : ''}`} onClick={() => setViewMode('list')} title="List">
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* ── Mobile header: single compact row ── */}
        <div className="md:hidden flex items-center gap-1.5 px-3 py-2 min-h-[48px]">
          {/* Mode tabs */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              className={`rounded-full px-3 py-1.5 text-xs font-bold ${catalogMode === 'explorer' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
              style={catalogMode === 'explorer' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
              onClick={() => { setCatalogMode('explorer'); setTwinQueryKey(null); setTwinSearchText(''); router.replace('/catalog', { scroll: false }) }}
            >Explorer</button>
            <button
              type="button"
              className={`rounded-full px-3 py-1.5 text-xs font-bold ${catalogMode === 'twin' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
              style={catalogMode === 'twin' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
              onClick={() => { setCatalogMode('twin'); setViewMode('list') }}
            >Twin</button>
          </div>

          {catalogMode === 'explorer' && (
            <div className="flex items-center gap-0.5 shrink-0">
              {(['all', 'nyc', 'la'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`rounded-full px-2 py-1 text-[0.65rem] font-bold ${filterMetro === m ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
                  style={filterMetro === m ? { background: 'var(--hf-primary-1)' } : {}}
                  onClick={() => setFilterMetro(m)}
                >{m === 'all' ? 'All' : m.toUpperCase()}</button>
              ))}
            </div>
          )}

          <div className="ml-auto flex items-center gap-0.5 shrink-0">
            {/* Filters */}
            <button
              type="button"
              className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]"
              onClick={() => setFilterSheetOpen(true)}
              aria-label="Filters"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetype !== 'all' ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean !== 'all' ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterDiversity !== 'all' ? 1 : 0) > 0 && (
                <span className="flex h-4 w-4 items-center justify-center rounded-full text-[0.6rem] font-bold text-white" style={{ background: 'var(--hf-primary-1)' }}>
                  {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetype !== 'all' ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean !== 'all' ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterDiversity !== 'all' ? 1 : 0)}
                </span>
              )}
            </button>
            {/* View toggle */}
            <button type="button" className={`rounded-lg p-1.5 ${viewMode === 'map' ? 'bg-[var(--hf-hover-bg)]' : ''}`} onClick={() => setViewMode('map')} title="Map">
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button type="button" className={`rounded-lg p-1.5 ${viewMode === 'list' ? 'bg-[var(--hf-hover-bg)]' : ''}`} onClick={() => setViewMode('list')} title="List">
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Twin mode second row: search + controls */}
        {catalogMode === 'twin' && (
          <div className="md:hidden flex flex-col gap-1.5 border-t border-[var(--hf-border)] px-3 py-2">
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-1 text-[0.7rem] font-bold disabled:opacity-40 ${twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinCrossMetro(true)}
              >Cross-metro</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-1 text-[0.7rem] font-bold disabled:opacity-40 ${!twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinCrossMetro(false)}
              >Same metro</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-1 text-[0.7rem] font-bold disabled:opacity-40 ${twinSameBand ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'}`}
                onClick={() => setTwinSameBand((v) => !v)}
              >Same class</button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className="ml-auto flex items-center gap-1 rounded-lg border border-[var(--hf-border)] px-2 py-1 text-[0.7rem] font-bold disabled:opacity-40"
                onClick={() => !twinControlsLocked && setTwinPillarOpen(true)}
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Pillars ({twinPillarList.length})
              </button>
            </div>
            <div className="relative">
              <input
                type="search"
                placeholder="Search a neighborhood to find its twin…"
                value={twinQueryKey && queryPlace ? queryPlace.catalog.name : twinSearchText}
                onChange={(e) => { if (twinQueryKey) return; setTwinSearchText(e.target.value) }}
                readOnly={!!twinQueryKey}
                className="w-full rounded-lg border border-[var(--hf-border)] py-2 pl-3 pr-9 text-sm"
              />
              {twinQueryKey && (
                <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--hf-text-secondary)]" onClick={clearTwinQuery} aria-label="Clear">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        )}
      </header>

      {viewMode === 'map' && (
        <div className="relative flex min-h-0 flex-1 flex-col">
          <CatalogMapView
            key={`${mapRegion}-${catalogMode}`}
            data={mapData}
            selectedKey={selectedKey}
            onSelectKey={onSelectKey}
            layoutVersion={layoutVersion}
            indexMode={indexMode}
            region={mapRegion}
            mapVariant={catalogMode === 'twin' && twinQueryKey ? 'twin' : 'explorer'}
            twinLineGeoJson={catalogMode === 'twin' && twinQueryKey && twinLineGeoJson ? twinLineGeoJson : null}
            fitKey={fitKey}
            onHover={catalogMode === 'explorer' ? setHoverInfo : undefined}
          />
          {/* Mobile floating score + sort strip */}
          {catalogMode === 'explorer' && (
            <div className="md:hidden absolute top-2 left-0 right-0 z-10 pointer-events-none">
              {/* Right-edge fade hint */}
              <div className="absolute right-0 top-0 bottom-0 w-10 z-10 pointer-events-none" style={{ background: 'linear-gradient(to right, transparent, rgba(255,255,255,0.7))' }} />
              <div
                className="flex gap-1.5 overflow-x-auto px-3 pb-1 pointer-events-auto"
                style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}
              >
                {INDEXES.map((x) => {
                  const active = indexMode === x.id && !sortByName
                  const activeStyle = catalogTabActiveStyle(catalogRampKey(x.id))
                  return (
                    <button
                      key={x.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setIndexModeAndListSort(x.id)}
                      className="shrink-0 rounded-full px-3 py-1.5 text-xs font-bold shadow-sm"
                      style={active
                        ? { ...activeStyle, border: 'none' }
                        : { background: 'rgba(255,255,255,0.92)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)', backdropFilter: 'blur(4px)' }
                      }
                    >{x.label}</button>
                  )
                })}
                <button
                  type="button"
                  aria-pressed={sortByName}
                  onClick={() => setSortByName(true)}
                  className="shrink-0 rounded-full px-3 py-1.5 text-xs font-bold shadow-sm"
                  style={sortByName
                    ? { background: 'var(--hf-primary-1)', color: '#fff', border: 'none' }
                    : { background: 'rgba(255,255,255,0.92)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)', backdropFilter: 'blur(4px)' }
                  }
                >A–Z</button>
                {indexMode === 'homefit' && !sortByName && (
                  <button
                    type="button"
                    onClick={() => setWeightOpen(true)}
                    className="shrink-0 rounded-full px-3 py-1.5 text-xs font-bold shadow-sm"
                    style={{ background: 'rgba(255,255,255,0.92)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)', backdropFilter: 'blur(4px)' }}
                  >⚖ Weights</button>
                )}
              </div>
            </div>
          )}

          {hoverInfo && catalogMode === 'explorer' && (() => {
            const hoverPlace = findPlaceByKey(gatedPlaces, hoverInfo.key)
            if (!hoverPlace) return null
            const rw = reweightScoreResponseFromPriorities(hoverPlace.score, priorities)
            const hf = rw.total_score
            const lon = hoverPlace.score.longevity_index ?? null
            const hap = hoverPlace.score.happiness_index ?? null
            const archetype = hoverPlace.score.status_signal_breakdown?.archetype ?? null
            return (
              <div
                style={{
                  position: 'absolute',
                  left: hoverInfo.x,
                  top: hoverInfo.y,
                  transform: 'translate(-50%, calc(-100% - 12px))',
                  pointerEvents: 'none',
                  zIndex: 20,
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 10,
                  padding: '8px 12px',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                  minWidth: 160,
                  maxWidth: 220,
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 13, color: '#1a1a2e', marginBottom: 2 }}>
                  {hoverPlace.catalog.name}
                </div>
                <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                  {hoverPlace.catalog.county_borough} · {hoverPlace.catalog.state_abbr}
                </div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#1a1a2e', marginBottom: 2 }}>
                  Score {Number.isFinite(hf) ? hf.toFixed(0) : '—'}
                </div>
                <div style={{ fontSize: 11, color: '#6b7280', display: 'flex', gap: 8, marginBottom: archetype ? 4 : 0 }}>
                  <span>Lon {lon != null && Number.isFinite(lon) ? lon.toFixed(0) : '—'}</span>
                  <span>Hap {hap != null && Number.isFinite(hap) ? hap.toFixed(0) : '—'}</span>
                </div>
                {archetype && (
                  <div style={{ fontSize: 11, background: '#f3f4f6', borderRadius: 4, padding: '2px 6px', display: 'inline-block', color: '#374151' }}>
                    {archetype}
                  </div>
                )}
              </div>
            )
          })()}
          {catalogMode === 'twin' && twinQueryKey && queryPlace && selectedTwinMatch && (
            <div className="max-h-[min(50vh,28rem)] shrink-0 overflow-y-auto border-t border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] px-3 py-3">
              <TwinCandidateDetailContent
                query={queryPlace}
                twin={selectedTwinMatch.place}
                matchPct={selectedTwinMatch.matchPct}
                matchingPillars={twinPillarList}
                priorities={priorities}
              />
            </div>
          )}
          {/* Desktop detail panel — slides in from right on selection */}
          {catalogMode === 'explorer' && (
            <div className="hidden md:block">
              <CatalogDetailPanel
                place={selectedPlace}
                indexMode={indexMode}
                onIndexModeChange={setIndexModeAndListSort}
                priorities={priorities}
                onClose={clearSelection}
                onFullBreakdown={handleFullBreakdown}
              />
            </div>
          )}
        </div>
      )}

      {viewMode === 'list' && catalogMode === 'explorer' && dealbreakerActive && (
        <div className="border-b border-[var(--hf-border)] bg-[var(--hf-hover-bg)] px-4 py-2 text-xs text-[var(--hf-text-secondary)]">
          {dealbreakerZeroSurvivors
            ? 'No places clear all your must-haves — showing closest matches anyway'
            : dealbreakerExcludedCount > 0
              ? `${gatedPlaces.length} match all your must-haves · ${dealbreakerExcludedCount} excluded`
              : `All ${gatedPlaces.length} shown clear your must-haves`}
        </div>
      )}

      {viewMode === 'list' && catalogMode === 'explorer' && (
        <CatalogListView
          places={gatedPlaces}
          priorities={priorities}
          onTwinRow={onTwinRow}
          compareIds={compareIds}
          onCompareToggle={handleCompareToggle}
        />
      )}

      {viewMode === 'list' && catalogMode === 'twin' && (
        <TwinFinderPanel
          places={places}
          twinSearchText={twinSearchText}
          twinQueryKey={twinQueryKey}
          queryPlace={queryPlace}
          twinRanked={twinRanked}
          priorities={priorities}
          selectedPillars={twinPillarList}
          selectedTwinKey={
            selectedKey && twinQueryKey && selectedKey !== twinQueryKey ? selectedKey : null
          }
          onSelectTwinResult={(key) => {
            if (key === null && twinQueryKey) setSelectedKey(twinQueryKey)
            else setSelectedKey(key)
          }}
          onSelectQuery={onTwinSelectFromSearch}
        />
      )}

      {catalogMode === 'explorer' && viewMode === 'map' && (
        <div className="md:hidden">
        <CatalogBottomSheet
          place={selectedPlace}
          indexMode={indexMode}
          onIndexModeChange={setIndexModeAndListSort}
          priorities={priorities}
          snap={snap}
          onSnapChange={setSnap}
          onClose={clearSelection}
          onFullBreakdown={handleFullBreakdown}
        />
        </div>
      )}

      {catalogMode === 'twin' && twinQueryKey && queryPlace && (
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            zIndex: 20,
            height: 44,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 16px',
            paddingBottom: 'max(0px, env(safe-area-inset-bottom))',
            background: 'var(--hf-card-bg)',
            borderTop: '1px solid var(--hf-border)',
            boxShadow: '0 -2px 8px rgba(0,0,0,0.06)',
          }}
        >
          <span style={{ fontSize: '0.8rem', color: 'var(--hf-text-secondary)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <span style={{ color: 'var(--hf-text-tertiary)' }}>Matching to: </span>
            <span style={{ fontWeight: 600, color: 'var(--hf-text-primary)' }}>{queryPlace.catalog.name}</span>
            {(() => {
              const rw = reweightScoreResponseFromPriorities(queryPlace.score, priorities)
              const hf = rw.total_score
              return Number.isFinite(hf) ? (
                <span style={{ color: 'var(--hf-text-secondary)' }}> · Trovamo {hf.toFixed(1)}</span>
              ) : null
            })()}
          </span>
          <button
            type="button"
            onClick={clearTwinQuery}
            style={{
              marginLeft: 12,
              flexShrink: 0,
              fontSize: '0.8rem',
              fontWeight: 600,
              color: 'var(--hf-primary-1)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0 4px',
            }}
          >
            Change
          </button>
        </div>
      )}

      <CatalogWeightPanel
        open={weightOpen && indexMode === 'homefit'}
        onClose={() => setWeightOpen(false)}
        priorities={priorities}
        onChange={setPriorities}

        onTakeQuiz={() => { setWeightOpen(false); setShowQuiz(true) }}
        householdIncome={householdIncome}
        incomeInputValue={incomeInputValue}
        onIncomeInputChange={setIncomeInputValue}
        onIncomeBlur={() => handleIncomeBlur(incomeInputValue, householdIncome)}
        onIncomeClear={handleIncomeClear}
        dealbreakers={dealbreakers}
        onDealbreakerToggle={toggleDealbreaker}
      />

      <PillarTwinDrawer
        open={twinPillarOpen}
        onClose={() => setTwinPillarOpen(false)}
        selected={twinPillars}
        onChange={setTwinPillars}
        disabled={twinControlsLocked}
      />

      <CompareTray
        compareIds={compareIds}
        places={gatedPlaces}
        onRemove={(key) => setCompareIds((prev) => prev.filter((k) => k !== key))}
        onClear={() => setCompareIds([])}
      />

      <FilterSheet
        open={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        filterMetro={filterMetro}
        onFilterMetroChange={setFilterMetro}
        filterAreaTypes={filterAreaTypes}
        onFilterAreaTypesChange={setFilterAreaTypes}
        filterArchetype={filterArchetype}
        onFilterArchetypeChange={setFilterArchetype}
        archetypes={archetypes}
        filterTrajectory={filterTrajectory}
        onFilterTrajectoryChange={setFilterTrajectory}
        filterPoliticalLean={filterPoliticalLean}
        onFilterPoliticalLeanChange={setFilterPoliticalLean}
        filterNbTypes={filterNbTypes}
        onFilterNbTypesChange={setFilterNbTypes}
        filterDiversity={filterDiversity}
        onFilterDiversityChange={setFilterDiversity}
        resultCount={filteredPlaces.length}
      />

      {loading && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.85)' }}
        >
          <p className="text-sm font-semibold text-[var(--hf-text-primary)]">Loading catalog…</p>
        </div>
      )}
      {!loading && loadMessage && places.length === 0 && (
        <div className="fixed bottom-28 left-4 right-4 z-40 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          {loadMessage}
        </div>
      )}
    </div>
  )
}
