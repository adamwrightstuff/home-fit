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
  isPillarIndexMode,
  PILLAR_INDEX_MODES,
  type CatalogMapIndexMode,
  type CatalogMapPlace,
  type CatalogMapPlaceWithMetro,
} from '@/lib/catalogMapTypes'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import { buildResultsCacheKey, buildResultsUrl } from '@/lib/resultsShare'
import { reweightScoreResponseFromPriorities, applyUserIncomeToScore, passesHousingValueDealbreaker, passesAirTravelDealbreaker, passesQualityEducationDealbreaker, passesCommunitySafetyDealbreaker, passesNeighborhoodAmenitiesDealbreaker, passesHealthcareAccessDealbreaker, passesActiveOutdoorsDealbreaker, passesClimateRiskDealbreaker, passesSocialFabricDealbreaker } from '@/lib/reweight'
import { type WaterfrontSubPreference } from '@/lib/aoPreference'
import { applyExplorerScoreAdjustments, writeCompareContext } from '@/lib/explorerScoreAdjust'
import { scoreClimateMatch, hasClimatePreferences, type ClimatePreferences } from '@/lib/climatePreferences'
import { PILLAR_ORDER, PILLAR_META, type PillarKey, HOMEFIT_COPY, LONGEVITY_COPY, HAPPINESS_INDEX_COPY, STATUS_SIGNAL_COPY } from '@/lib/pillars'
import { rankTwinMatches, defaultTwinPillarSet, type TwinMatchResult } from '@/lib/twinSimilarity'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import QuizModal, { type QuizPayload } from '@/components/QuizModal'

const INDEXES: { id: 'homefit' | 'longevity' | 'happiness' | 'status'; label: string; tooltip: string }[] = [
  { id: 'homefit', label: 'HomeFit', tooltip: HOMEFIT_COPY.tooltip },
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
      if (isPillarIndexMode(sortKey)) return (p.score.livability_pillars as any)?.[sortKey]?.score ?? NaN
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
  initialMetroFilter?: 'all' | 'nyc' | 'la' | 'sf' | 'seattle'
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hasRestoredRef = useRef(false)
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
        const source = parsed.priorities ?? parsed
        for (const k of [...PILLAR_ORDER, 'natural_beauty'] as PillarKey[]) {
          if (valid.includes(source[k])) merged[k] = source[k]
        }
        return merged
      }
    } catch { /* ignore */ }
    return { ...DEFAULT_PRIORITIES }
  })
  const [filterPoliticalLean, setFilterPoliticalLean] = useState<string[]>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return Array.isArray(f?.filterPoliticalLean) ? f.filterPoliticalLean : []
    } catch { return [] }
  })
  const [filterNbTypes, setFilterNbTypes] = useState<string[]>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return Array.isArray(f?.filterNbTypes) ? f.filterNbTypes : []
    } catch { return [] }
  })
  const [filterAoTypes, setFilterAoTypes] = useState<string[]>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return Array.isArray(f?.filterAoTypes) ? f.filterAoTypes : []
    } catch { return [] }
  })
  const [filterWaterfrontSubPref, setFilterWaterfrontSubPref] = useState<WaterfrontSubPreference | null>(null)
  const [filterHousingType, setFilterHousingType] = useState<string[]>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return Array.isArray(f?.filterHousingType) ? f.filterHousingType : []
    } catch { return [] }
  })
  const [filterTenure, setFilterTenure] = useState<string[]>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return Array.isArray(f?.filterTenure) ? f.filterTenure : []
    } catch { return [] }
  })
  const [filterSchoolType, setFilterSchoolType] = useState<'any' | 'public_only' | 'charter'>('any')
  const [filterLocalScene, setFilterLocalScene] = useState<'all' | 'Some' | 'High'>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      const v = f?.filterLocalScene
      return v === 'Some' || v === 'High' ? v : 'all'
    } catch { return 'all' }
  })
  const [filterCommuteMax, setFilterCommuteMax] = useState<'all' | '15' | '30' | '45' | '60'>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      const v = f?.filterCommuteMax
      return v === '15' || v === '30' || v === '45' || v === '60' ? v : 'all'
    } catch { return 'all' }
  })
  const [climatePrefs, setClimatePrefs] = useState<ClimatePreferences>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      return f?.climatePrefs && typeof f.climatePrefs === 'object' ? f.climatePrefs : {}
    } catch { return {} }
  })
/** Deal-breaker pillars (housing_value MVP). Independent of importance weight — see CatalogWeightPanel. */
  const [dealbreakers, setDealbreakers] = useState<Partial<Record<PillarKey, boolean>>>(() => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')
      return parsed?.dealbreakers && typeof parsed.dealbreakers === 'object' ? parsed.dealbreakers : {}
    } catch { return {} }
  })
  const toggleDealbreaker = useCallback((key: PillarKey) => {
    setDealbreakers((prev) => ({ ...prev, [key]: !prev[key] }))
  }, [])
  const [showExcluded, setShowExcluded] = useState(false)
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
  const [filterMetro, setFilterMetro] = useState<'all' | 'nyc' | 'la' | 'sf' | 'seattle'>(initialMetroFilter)
  const [filterAreaTypes, setFilterAreaTypes] = useState<string[]>([])
  const [filterArchetypes, setFilterArchetypes] = useState<string[]>([])
  const [filterTrajectory, setFilterTrajectory] = useState<'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'>(() => {
    try {
      const f = JSON.parse(sessionStorage.getItem('homefit_search_options') ?? '{}')?.filters
      const v = f?.filterTrajectory
      return v === 'Arrived' || v === 'Up-and-Coming' || v === 'Stable' || v === 'Cooling' || v === 'Declining' ? v : 'all'
    } catch { return 'all' }
  })
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

  const [currentHomeMonthlyCost, setCurrentHomeMonthlyCost] = useState<number | null>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return typeof parsed.current_home_monthly_cost === 'number' && parsed.current_home_monthly_cost > 0
          ? parsed.current_home_monthly_cost : null
      }
    } catch { /* ignore */ }
    return null
  })
  const [currentHomeMonthlyCostInput, setCurrentHomeMonthlyCostInput] = useState<string>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return typeof parsed.current_home_monthly_cost === 'number' && parsed.current_home_monthly_cost > 0
          ? String(parsed.current_home_monthly_cost) : ''
      }
    } catch { /* ignore */ }
    return ''
  })
  const [currentHomeMatch, setCurrentHomeMatch] = useState<string>(() => {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const parsed = JSON.parse(stored)
        return typeof parsed.current_home_match === 'string' ? parsed.current_home_match : ''
      }
    } catch { /* ignore */ }
    return ''
  })

  const handleCurrentHomeMonthlyCostBlur = useCallback((val: string) => {
    const v = val === '' ? null : parseInt(val.replace(/,/g, ''), 10)
    const next = Number.isFinite(v) && (v as number) >= 100 ? (v as number) : null
    setCurrentHomeMonthlyCost(next)
    setCurrentHomeMonthlyCostInput(next ? String(next) : '')
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, current_home_monthly_cost: next }))
    } catch { /* ignore */ }
  }, [])

  const handleCurrentHomeMonthlyCostClear = useCallback(() => {
    setCurrentHomeMonthlyCost(null)
    setCurrentHomeMonthlyCostInput('')
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, current_home_monthly_cost: null }))
    } catch { /* ignore */ }
  }, [])

  const handleCurrentHomeSelect = useCallback((name: string) => {
    setCurrentHomeMatch(name)
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, current_home_match: name }))
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
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      if (stored) {
        const opts = JSON.parse(stored)
        if (opts.quiz_override) {
          delete opts.quiz_override
          sessionStorage.setItem('homefit_search_options', JSON.stringify(opts))
          hasRestoredRef.current = true
          return
        }
      }
    } catch { /* ignore */ }
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
        const f = opts.filters
        if (f && typeof f === 'object') {
          if (Array.isArray(f.filterAreaTypes)) setFilterAreaTypes(f.filterAreaTypes)
          if (Array.isArray(f.filterArchetypes)) setFilterArchetypes(f.filterArchetypes)
          if (typeof f.filterTrajectory === 'string') setFilterTrajectory(f.filterTrajectory)
          if (Array.isArray(f.filterPoliticalLean)) setFilterPoliticalLean(f.filterPoliticalLean)
          if (Array.isArray(f.filterNbTypes)) setFilterNbTypes(f.filterNbTypes)
          if (Array.isArray(f.filterAoTypes)) setFilterAoTypes(f.filterAoTypes)
          if (typeof f.filterWaterfrontSubPref === 'string') setFilterWaterfrontSubPref(f.filterWaterfrontSubPref as WaterfrontSubPreference)
          if (Array.isArray(f.filterHousingType)) setFilterHousingType(f.filterHousingType)
          if (Array.isArray(f.filterTenure)) setFilterTenure(f.filterTenure)
          if (typeof f.filterSchoolType === 'string') setFilterSchoolType(f.filterSchoolType)
          if (typeof f.filterLocalScene === 'string') setFilterLocalScene(f.filterLocalScene)
          if (typeof f.filterCommuteMax === 'string') setFilterCommuteMax(f.filterCommuteMax)
          if (f.climatePrefs && typeof f.climatePrefs === 'object') setClimatePrefs(f.climatePrefs)
        }
        hasRestoredRef.current = true
      })
      .catch(() => { hasRestoredRef.current = true /* silently ignore — sessionStorage fallback already applied */ })
  }, [user])

  useEffect(() => {
    if (!user || !hasRestoredRef.current) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      fetch('/api/me/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          priorities,
          dealbreakers,
          household_income: householdIncome,
          filters: {
            filterAreaTypes,
            filterArchetypes,
            filterTrajectory,
            filterPoliticalLean,
            filterNbTypes,
            filterAoTypes,
            filterWaterfrontSubPref,
            filterHousingType,
            filterTenure,
            filterSchoolType,
            filterLocalScene,
            filterCommuteMax,
            climatePrefs,
          },
        }),
      }).catch(() => {})
    }, 1500)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [user, priorities, dealbreakers, householdIncome, filterAreaTypes, filterArchetypes, filterTrajectory, filterPoliticalLean, filterNbTypes, filterAoTypes, filterWaterfrontSubPref, filterHousingType, filterTenure, filterSchoolType, filterLocalScene, filterCommuteMax, climatePrefs])

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

  const currentHomePlaceOptions = useMemo(() =>
    places.map((p) => ({
      name: p.catalog?.name ?? '',
      sub: [p.catalog?.county_borough, p.catalog?.state_abbr].filter(Boolean).join(', '),
    })).filter(o => o.name),
  [places])

  const adjustedPlaces = useMemo(() => {
    const withIncome = householdIncome
      ? places.map((p) => {
          const isCurrentHome = currentHomeMatch && p.catalog?.name === currentHomeMatch
          const monthlyCostOverride = isCurrentHome ? currentHomeMonthlyCost : null
          return { ...p, score: applyUserIncomeToScore(p.score, householdIncome, monthlyCostOverride) }
        })
      : places

    const f = { filterSchoolType, filterNbTypes, filterAoTypes, filterWaterfrontSubPref }
    return withIncome.map((p) => ({ ...p, score: applyExplorerScoreAdjustments(p.score, f) }))
  }, [places, householdIncome, filterSchoolType, filterNbTypes, filterAoTypes, filterWaterfrontSubPref, currentHomeMonthlyCost, currentHomeMatch])

  // Hand the current weights + score-affecting filters to Compare ("Your HomeFit" mode).
  useEffect(() => {
    writeCompareContext({
      priorities,
      filters: { filterSchoolType, filterNbTypes, filterAoTypes, filterWaterfrontSubPref },
    })
  }, [priorities, filterSchoolType, filterNbTypes, filterAoTypes, filterWaterfrontSubPref])

  const effectivePriorities = useMemo(
    () => priorities,
    [priorities],
  )

  const filteredPlaces = useMemo(() => {
    const t = filterText.trim().toLowerCase()
    let list = adjustedPlaces.filter((p) => {
      if (filterMetro !== 'all' && inferCatalogMetro(p) !== filterMetro) return false
      if (filterAreaTypes.length > 0) {
        const at = p.score.data_quality_summary?.area_classification?.area_type
        if (at && !filterAreaTypes.includes(at)) return false
      }
      if (filterArchetypes.length > 0) {
        const ar = p.score.status_signal_breakdown?.archetype
        if (ar && !filterArchetypes.includes(ar)) return false
      }
      if (filterTrajectory !== 'all') {
        const tr = p.score.status_signal_breakdown?.trajectory
        if (tr && tr !== filterTrajectory) return false
      }
      if (filterPoliticalLean.length > 0 && filterPoliticalLean.length < 5) {
        const lean = (p.score.livability_pillars as any)?.political_lean?.breakdown?.lean_2024
        if (typeof lean !== 'number') return true
        const matchesAny = filterPoliticalLean.some(pref => {
          if (pref === 'strong_d') return lean >= 0.5
          if (pref === 'lean_d') return lean >= 0.15 && lean < 0.5
          if (pref === 'moderate') return lean >= -0.15 && lean < 0.15
          if (pref === 'lean_r') return lean >= -0.5 && lean < -0.15
          if (pref === 'strong_r') return lean < -0.5
          return false
        })
        if (!matchesAny) return false
      }
      if (filterLocalScene === 'Some' && p.score.local_scene_bucket === 'Low') return false
      if (filterLocalScene === 'High' && p.score.local_scene_bucket && p.score.local_scene_bucket !== 'High') return false
      if (filterCommuteMax !== 'all') {
        const cbd = p.cbd_transit_minutes
        if (typeof cbd === 'number' && cbd > Number(filterCommuteMax)) return false
      }
      if (filterHousingType.length > 0 && filterHousingType.length < 3) {
        const hs = (p.score as any).housing_stock
        const pctLow = typeof hs?.pct_low_density === 'number' ? hs.pct_low_density : null
        if (pctLow !== null) {
          const passesAny = filterHousingType.some((t) => {
            if (t === 'sf_townhouse') return pctLow >= 0.25
            if (t === 'small_multifamily') return pctLow >= 0.1 && pctLow < 0.7
            if (t === 'apartment') return pctLow < 0.3
            return false
          })
          if (!passesAny) return false
        }
      }
      if (filterTenure.length > 0 && filterTenure.length < 3) {
        const renterPct = (p.score as any)?.livability_pillars?.housing_value?.summary?.renter_pct
        if (typeof renterPct === 'number') {
          const passesAny = filterTenure.some((t) => {
            if (t === 'renter') return renterPct >= 0.6
            if (t === 'balanced') return renterPct >= 0.3 && renterPct < 0.6
            if (t === 'homeowner') return renterPct < 0.3
            return false
          })
          if (!passesAny) return false
        }
      }
      if (!t) return true
      const name = (p.catalog.name || '').toLowerCase()
      const county = (p.catalog.county_borough || '').toLowerCase()
      const st = (p.catalog.state_abbr || '').toLowerCase()
      return name.includes(t) || county.includes(t) || st.includes(t)
    })
    if (hasClimatePreferences(climatePrefs)) {
      list = list.filter((p) => {
        const cm = scoreClimateMatch(p.climate, climatePrefs)
        // No climate data at all (null) or empty object producing NaN score → pass
        if (!cm || isNaN(cm.score)) return true
        // Each dealbreaker axis must pass independently — averaging neutral axes (50) with a
        // failing dealbreaker axis can raise the average above the threshold, letting rainy/cold/hot
        // places slip through when the user said they're dealbreakers.
        // Threshold 15: rejects places greyer/colder/hotter than Seattle-level extremes.
        // NYC cluster scores ~15.8 on rain_grey; threshold of 30 incorrectly killed the entire metro.
        if (climatePrefs.rain_tolerance === 'dealbreaker' && typeof cm.axes.rain_grey === 'number' && !isNaN(cm.axes.rain_grey) && cm.axes.rain_grey < 15) return false
        if (climatePrefs.cold_tolerance === 'dealbreaker' && typeof cm.axes.cold_winter === 'number' && !isNaN(cm.axes.cold_winter) && cm.axes.cold_winter < 15) return false
        if (climatePrefs.heat_tolerance === 'dealbreaker' && typeof cm.axes.summer_heat === 'number' && !isNaN(cm.axes.summer_heat) && cm.axes.summer_heat < 15) return false
        if (climatePrefs.seasons === 'want_consistency' && typeof cm.axes.seasonal === 'number' && !isNaN(cm.axes.seasonal) && cm.axes.seasonal < 15) return false
        // Positive preferences also checked independently — a neutral axis (50) must not rescue
        // a place that scores 0 on something the user said they actively want.
        if (climatePrefs.heat_tolerance === 'love' && typeof cm.axes.summer_heat === 'number' && !isNaN(cm.axes.summer_heat) && cm.axes.summer_heat < 15) return false
        if (climatePrefs.cold_tolerance === 'love' && typeof cm.axes.cold_winter === 'number' && !isNaN(cm.axes.cold_winter) && cm.axes.cold_winter < 15) return false
        if (climatePrefs.rain_tolerance === 'vibe' && typeof cm.axes.rain_grey === 'number' && !isNaN(cm.axes.rain_grey) && cm.axes.rain_grey < 15) return false
        if (climatePrefs.seasons === 'want_4' && typeof cm.axes.seasonal === 'number' && !isNaN(cm.axes.seasonal) && cm.axes.seasonal < 15) return false
        return cm.score >= 15
      })
    }
    const sortKey: CatalogMapIndexMode | 'name' = sortByName ? 'name' : indexMode
    return sortPlaces(list, sortKey, sortDir, effectivePriorities)
  }, [
    adjustedPlaces,
    filterText,
    filterMetro,
    filterAreaTypes,
    filterArchetypes,
    filterTrajectory,
    filterPoliticalLean,
    filterSchoolType,
    filterLocalScene,
    filterCommuteMax,
    filterHousingType,
    filterTenure,
    climatePrefs,
    indexMode,
    sortByName,
    sortDir,
    effectivePriorities,
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
      const be = (p.score.livability_pillars as any)?.built_environment
      const nearestAirportKm = Number(ata?.summary?.nearest_airport_km ?? 0) || null
      const effectiveAreaType = be?.breakdown?.effective_area_type ?? be?.details?.effective_area_type ?? null
      return passesAirTravelDealbreaker(nearestAirportKm, effectiveAreaType)
    },
    quality_education: (p) => {
      const qe = (p.score.livability_pillars as any)?.quality_education
      if (qe?.status === 'fallback' || qe?.status === 'no_data') return true
      const score = typeof qe?.score === 'number' ? qe.score : null
      return passesQualityEducationDealbreaker(score)
    },
    community_safety: (p) => {
      const cs = (p.score.livability_pillars as any)?.community_safety
      if (cs?.status === 'fallback' || cs?.status === 'no_data') return true
      const score = typeof cs?.score === 'number' ? cs.score : null
      return passesCommunitySafetyDealbreaker(score)
    },
    neighborhood_amenities: (p) => {
      const na = (p.score.livability_pillars as any)?.neighborhood_amenities
      const score = na?.score
      return passesNeighborhoodAmenitiesDealbreaker(typeof score === 'number' ? score : null)
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
  // Places blocked by regular filters — always shown in "Show excluded"
  const metroFilterExcluded = useMemo(() => {
    const filteredSet = new Set(filteredPlaces)
    if (filterMetro === 'all') return adjustedPlaces.filter((p) => !filteredSet.has(p)) as CatalogMapPlaceWithMetro[]
    return adjustedPlaces.filter((p) => inferCatalogMetro(p) === filterMetro && !filteredSet.has(p)) as CatalogMapPlaceWithMetro[]
  }, [filterMetro, filteredPlaces, adjustedPlaces])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const metroFilterExcludedReasons = useMemo(() => {
    const reasons: Record<string, string[]> = {}
    for (const p of metroFilterExcluded) {
      const key = catalogRowKey(p.catalog)
      const r: string[] = []
      if (filterAreaTypes.length > 0) {
        const at = p.score.data_quality_summary?.area_classification?.area_type
        if (at && !filterAreaTypes.includes(at)) r.push('Area type')
      }
      if (filterArchetypes.length > 0) {
        const ar = p.score.status_signal_breakdown?.archetype
        if (ar && !filterArchetypes.includes(ar)) r.push('Archetype')
      }
      if (filterTrajectory !== 'all') {
        const tr = p.score.status_signal_breakdown?.trajectory
        if (tr && tr !== filterTrajectory) r.push('Trajectory')
      }
      if (filterLocalScene === 'Some' && p.score.local_scene_bucket === 'Low') r.push('Local scene')
      if (filterLocalScene === 'High' && p.score.local_scene_bucket && p.score.local_scene_bucket !== 'High') r.push('Local scene')
      if (filterCommuteMax !== 'all') {
        const cbd = p.cbd_transit_minutes
        if (typeof cbd === 'number' && cbd > Number(filterCommuteMax)) r.push('Commute')
      }
      if (filterHousingType.length > 0 && filterHousingType.length < 3) {
        const hs = (p.score as any).housing_stock
        const pctLow = typeof hs?.pct_low_density === 'number' ? hs.pct_low_density : null
        if (pctLow !== null) {
          const passesAny = filterHousingType.some((ht) => {
            if (ht === 'sf_townhouse') return pctLow >= 0.25
            if (ht === 'small_multifamily') return pctLow >= 0.1 && pctLow < 0.7
            if (ht === 'apartment') return pctLow < 0.3
            return false
          })
          if (!passesAny) r.push('Housing type')
        }
      }
      if (filterTenure.length > 0 && filterTenure.length < 3) {
        const renterPct = (p.score as any)?.livability_pillars?.housing_value?.summary?.renter_pct
        if (typeof renterPct === 'number') {
          const passesAny = filterTenure.some((t) => {
            if (t === 'renter') return renterPct >= 0.6
            if (t === 'balanced') return renterPct >= 0.3 && renterPct < 0.6
            if (t === 'homeowner') return renterPct < 0.3
            return false
          })
          if (!passesAny) r.push('Tenure')
        }
      }
      if (filterPoliticalLean.length > 0 && filterPoliticalLean.length < 5) {
        const lean = (p.score.livability_pillars as any)?.political_lean?.breakdown?.lean_2024
        if (typeof lean === 'number') {
          const matchesAny = filterPoliticalLean.some((pref) => {
            if (pref === 'strong_d') return lean >= 0.5
            if (pref === 'lean_d') return lean >= 0.15 && lean < 0.5
            if (pref === 'moderate') return lean >= -0.15 && lean < 0.15
            if (pref === 'lean_r') return lean >= -0.5 && lean < -0.15
            if (pref === 'strong_r') return lean < -0.5
            return false
          })
          if (!matchesAny) r.push('Political lean')
        }
      }
      if (hasClimatePreferences(climatePrefs)) {
        const cm = scoreClimateMatch(p.climate, climatePrefs)
        if (cm && !isNaN(cm.score)) {
          const ax = cm.axes
          const fails =
            (climatePrefs.rain_tolerance === 'dealbreaker' && typeof ax.rain_grey === 'number' && !isNaN(ax.rain_grey) && ax.rain_grey < 15) ||
            (climatePrefs.cold_tolerance === 'dealbreaker' && typeof ax.cold_winter === 'number' && !isNaN(ax.cold_winter) && ax.cold_winter < 15) ||
            (climatePrefs.heat_tolerance === 'dealbreaker' && typeof ax.summer_heat === 'number' && !isNaN(ax.summer_heat) && ax.summer_heat < 15) ||
            (climatePrefs.seasons === 'want_consistency' && typeof ax.seasonal === 'number' && !isNaN(ax.seasonal) && ax.seasonal < 15) ||
            (climatePrefs.heat_tolerance === 'love' && typeof ax.summer_heat === 'number' && !isNaN(ax.summer_heat) && ax.summer_heat < 15) ||
            (climatePrefs.cold_tolerance === 'love' && typeof ax.cold_winter === 'number' && !isNaN(ax.cold_winter) && ax.cold_winter < 15) ||
            (climatePrefs.rain_tolerance === 'vibe' && typeof ax.rain_grey === 'number' && !isNaN(ax.rain_grey) && ax.rain_grey < 15) ||
            (climatePrefs.seasons === 'want_4' && typeof ax.seasonal === 'number' && !isNaN(ax.seasonal) && ax.seasonal < 15) ||
            cm.score < 15
          if (fails) r.push('Climate')
        }
      }
      reasons[key] = r.length > 0 ? r : ['Filters']
    }
    return reasons
  }, [metroFilterExcluded, filterAreaTypes, filterArchetypes, filterTrajectory, filterLocalScene, filterCommuteMax, filterHousingType, filterTenure, filterPoliticalLean, climatePrefs])
  const { gatedPlaces, excludedPlaces, dealbreakerExcludedCount, dealbreakerZeroSurvivors } = useMemo(() => {
    if (activeDealbreakerKeys.length === 0) {
      return { gatedPlaces: filteredPlaces, excludedPlaces: metroFilterExcluded, dealbreakerExcludedCount: metroFilterExcluded.length, dealbreakerZeroSurvivors: false }
    }
    const survivors = filteredPlaces.filter((p) => activeDealbreakerKeys.every((k) => DEALBREAKER_CHECKS[k]!(p)))
    if (survivors.length === 0) {
      const allExcluded = [...filteredPlaces as CatalogMapPlaceWithMetro[], ...metroFilterExcluded]
      return { gatedPlaces: filteredPlaces, excludedPlaces: allExcluded, dealbreakerExcludedCount: allExcluded.length, dealbreakerZeroSurvivors: true }
    }
    const excluded = [...filteredPlaces.filter((p) => !activeDealbreakerKeys.every((k) => DEALBREAKER_CHECKS[k]!(p))) as CatalogMapPlaceWithMetro[], ...metroFilterExcluded]
    return {
      gatedPlaces: survivors,
      excludedPlaces: excluded,
      dealbreakerExcludedCount: excluded.length,
      dealbreakerZeroSurvivors: false,
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredPlaces, metroFilterExcluded, activeDealbreakerKeys.join(','), householdIncome])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => setShowExcluded(false), [activeDealbreakerKeys.join(',')])

  const searchResults = useMemo<{ hits: CatalogMapPlaceWithMetro[]; reasons: Record<string, string[]> } | null>(() => {
    const t = filterText.trim().toLowerCase()
    if (!t || catalogMode !== 'explorer') return null

    const hits = adjustedPlaces.filter((p) => {
      const name = (p.catalog.name || '').toLowerCase()
      const county = (p.catalog.county_borough || '').toLowerCase()
      const st = (p.catalog.state_abbr || '').toLowerCase()
      return name.includes(t) || county.includes(t) || st.includes(t)
    })

    const reasons: Record<string, string[]> = {}
    for (const p of hits) {
      const key = catalogRowKey(p.catalog)
      const r: string[] = []
      if (filterMetro !== 'all' && inferCatalogMetro(p) !== filterMetro) r.push(`Metro: ${inferCatalogMetro(p).toUpperCase()}`)
      if (filterAreaTypes.length > 0) {
        const at = p.score.data_quality_summary?.area_classification?.area_type
        if (at && !filterAreaTypes.includes(at)) r.push('Area type')
      }
      if (filterArchetypes.length > 0) {
        const ar = p.score.status_signal_breakdown?.archetype
        if (ar && !filterArchetypes.includes(ar)) r.push('Archetype')
      }
      if (filterTrajectory !== 'all') {
        const tr = p.score.status_signal_breakdown?.trajectory
        if (tr && tr !== filterTrajectory) r.push('Trajectory')
      }
      if (filterPoliticalLean.length > 0 && filterPoliticalLean.length < 5) {
        const lean = (p.score.livability_pillars as any)?.political_lean?.breakdown?.lean_2024
        const matchesAny = typeof lean === 'number' && filterPoliticalLean.some((pref) => {
          if (pref === 'strong_d') return lean >= 0.5
          if (pref === 'lean_d') return lean >= 0.15 && lean < 0.5
          if (pref === 'moderate') return lean >= -0.15 && lean < 0.15
          if (pref === 'lean_r') return lean >= -0.5 && lean < -0.15
          if (pref === 'strong_r') return lean < -0.5
          return false
        })
        if (!matchesAny) r.push('Political lean')
      }
      if (filterLocalScene === 'Some' && p.score.local_scene_bucket === 'Low') r.push('Local scene')
      if (filterLocalScene === 'High' && p.score.local_scene_bucket && p.score.local_scene_bucket !== 'High') r.push('Local scene')
      if (filterCommuteMax !== 'all') {
        const cbd = p.cbd_transit_minutes
        if (typeof cbd === 'number' && cbd > Number(filterCommuteMax)) r.push('Commute')
      }
      if (filterHousingType.length > 0 && filterHousingType.length < 3) {
        const hs = (p.score as any).housing_stock
        const pctLow = typeof hs?.pct_low_density === 'number' ? hs.pct_low_density : null
        if (pctLow !== null) {
          const passesAny = filterHousingType.some((ht) => {
            if (ht === 'sf_townhouse') return pctLow >= 0.25
            if (ht === 'small_multifamily') return pctLow >= 0.1 && pctLow < 0.7
            if (ht === 'apartment') return pctLow < 0.3
            return false
          })
          if (!passesAny) r.push('Housing type')
        }
      }
      if (filterTenure.length > 0 && filterTenure.length < 3) {
        const renterPct = (p.score as any)?.livability_pillars?.housing_value?.summary?.renter_pct
        if (typeof renterPct === 'number') {
          const passesAny = filterTenure.some((t) => {
            if (t === 'renter') return renterPct >= 0.6
            if (t === 'balanced') return renterPct >= 0.3 && renterPct < 0.6
            if (t === 'homeowner') return renterPct < 0.3
            return false
          })
          if (!passesAny) r.push('Tenure')
        }
      }
      for (const k of activeDealbreakerKeys) {
        if (!DEALBREAKER_CHECKS[k]?.(p)) r.push(`${PILLAR_META[k].name} must-have`)
      }
      if (hasClimatePreferences(climatePrefs)) {
        const cm = scoreClimateMatch(p.climate, climatePrefs)
        if (cm && !isNaN(cm.score)) {
          const ax = cm.axes
          const fails =
            (climatePrefs.rain_tolerance === 'dealbreaker' && typeof ax.rain_grey === 'number' && !isNaN(ax.rain_grey) && ax.rain_grey < 15) ||
            (climatePrefs.cold_tolerance === 'dealbreaker' && typeof ax.cold_winter === 'number' && !isNaN(ax.cold_winter) && ax.cold_winter < 15) ||
            (climatePrefs.heat_tolerance === 'dealbreaker' && typeof ax.summer_heat === 'number' && !isNaN(ax.summer_heat) && ax.summer_heat < 15) ||
            (climatePrefs.seasons === 'want_consistency' && typeof ax.seasonal === 'number' && !isNaN(ax.seasonal) && ax.seasonal < 15) ||
            (climatePrefs.heat_tolerance === 'love' && typeof ax.summer_heat === 'number' && !isNaN(ax.summer_heat) && ax.summer_heat < 15) ||
            (climatePrefs.cold_tolerance === 'love' && typeof ax.cold_winter === 'number' && !isNaN(ax.cold_winter) && ax.cold_winter < 15) ||
            (climatePrefs.rain_tolerance === 'vibe' && typeof ax.rain_grey === 'number' && !isNaN(ax.rain_grey) && ax.rain_grey < 15) ||
            (climatePrefs.seasons === 'want_4' && typeof ax.seasonal === 'number' && !isNaN(ax.seasonal) && ax.seasonal < 15) ||
            cm.score < 15
          if (fails) r.push('Climate')
        }
      }
      if (r.length > 0) reasons[key] = r
    }

    // Passing results first, filtered-out results after
    hits.sort((a, b) => {
      const aFail = (reasons[catalogRowKey(a.catalog)] ?? []).length > 0 ? 1 : 0
      const bFail = (reasons[catalogRowKey(b.catalog)] ?? []).length > 0 ? 1 : 0
      return aFail - bFail
    })

    return { hits, reasons }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterText, adjustedPlaces, catalogMode, filterMetro, filterAreaTypes, filterArchetypes, filterTrajectory, filterPoliticalLean, filterLocalScene, filterCommuteMax, filterHousingType, filterTenure, activeDealbreakerKeys.join(','), householdIncome, climatePrefs])

  const metroResultCounts = useMemo(() => {
    if (filterMetro !== 'all') return null
    const counts = { nyc: 0, la: 0, sf: 0, seattle: 0 }
    for (const p of gatedPlaces) counts[inferCatalogMetro(p)]++
    return counts
  }, [filterMetro, gatedPlaces])

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
    const keyFn = (pl: CatalogMapPlace) => catalogRowKey(pl.catalog)
    return rankTwinMatches(queryPlace, twinCandidatePlaces, twinPillarList, keyFn, 12, twinSameBand)
  }, [catalogMode, twinQueryKey, queryPlace, twinCandidatePlaces, twinPillarList, twinSameBand, twinCrossMetro])

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
      if (twinCrossMetro) return 'both'
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

  const fitKey = `${catalogMode}-${twinQueryKey ?? 'nq'}-${filterMetro}-${twinCrossMetro}-${twinPillarList.join(',')}`

  const selectedPlace = useMemo(() => {
    const fromGated = findPlaceByKey(gatedPlaces, selectedKey)
    if (fromGated) return fromGated
    if (searchResults && selectedKey) return findPlaceByKey(searchResults.hits, selectedKey) ?? null
    return null
  }, [gatedPlaces, selectedKey, searchResults])

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

  const climateActiveCount =
    (climatePrefs.cold_tolerance ? 1 : 0) +
    (climatePrefs.heat_tolerance ? 1 : 0) +
    (climatePrefs.rain_tolerance ? 1 : 0) +
    (climatePrefs.seasons ? 1 : 0)

  if (showQuiz) {
    return (
      <QuizModal
        onApply={(payload: QuizPayload) => {
          // Pillar priorities — merge with defaults so non-quiz pillars keep their values
          const merged = { ...DEFAULT_PRIORITIES, ...payload.priorities } as PillarPriorities
          setPriorities(merged)

          // Filters
          if (payload.filterAoTypes.length > 0) setFilterAoTypes(payload.filterAoTypes)
          if (payload.filterNbTypes.length > 0) setFilterNbTypes(payload.filterNbTypes)
          if (payload.filterHousingType.length > 0) setFilterHousingType(payload.filterHousingType)
          if (payload.filterTenure.length > 0) setFilterTenure(payload.filterTenure)
          if (payload.filterPoliticalLean.length > 0) setFilterPoliticalLean(payload.filterPoliticalLean)
          if (payload.filterTrajectory && payload.filterTrajectory !== 'all') setFilterTrajectory(payload.filterTrajectory as typeof filterTrajectory)
          if (payload.filterCommuteMax && payload.filterCommuteMax !== 'all') setFilterCommuteMax(payload.filterCommuteMax as typeof filterCommuteMax)
          if (payload.climatePrefs && Object.keys(payload.climatePrefs).length > 0) setClimatePrefs(payload.climatePrefs)

          // Dealbreakers
          if (payload.dealbreakers && Object.keys(payload.dealbreakers).length > 0) {
            setDealbreakers(prev => ({ ...prev, ...payload.dealbreakers }))
          }

          // Persist to sessionStorage
          try {
            const stored = sessionStorage.getItem('homefit_search_options')
            const opts = stored ? JSON.parse(stored) : {}
            sessionStorage.setItem('homefit_search_options', JSON.stringify({
              ...opts,
              priorities: merged,
              filters: {
                ...(opts.filters ?? {}),
                filterAoTypes: payload.filterAoTypes,
                filterNbTypes: payload.filterNbTypes,
                filterHousingType: payload.filterHousingType,
                filterTenure: payload.filterTenure,
                filterPoliticalLean: payload.filterPoliticalLean,
                filterTrajectory: payload.filterTrajectory,
                filterCommuteMax: payload.filterCommuteMax,
                climatePrefs: payload.climatePrefs,
              },
            }))
          } catch { /* ignore */ }

          setShowQuiz(false)
        }}
        onBack={() => setShowQuiz(false)}
      />
    )
  }

  return (
    <div className="hf-viewport hf-catalog-root flex min-h-0 flex-col">
      <HeroBand />
      <header className="z-30 shrink-0 border-b border-[var(--hf-border)] bg-white/95 backdrop-blur">
        {/* ── Desktop toolbar: Row 1 — mode, search, metro, controls ── */}
        <div className="hidden md:flex md:items-center md:gap-2 md:px-4 md:py-2">
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
              onClick={() => {
                setCatalogMode('twin')
                setViewMode('list')
                if (selectedKey && !twinQueryKey) {
                  setTwinQueryKey(selectedKey)
                  setTwinSearchText('')
                  router.replace(`/catalog?mode=twin&key=${encodeURIComponent(selectedKey)}`, { scroll: false })
                }
              }}
            >Twin finder</button>
          </div>

          <div className="h-4 w-px bg-[var(--hf-border)] shrink-0" />

          {/* Search / Twin input */}
          {catalogMode === 'explorer' ? (
            <input
              type="search"
              placeholder="Search neighborhoods…"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="w-44 rounded-lg border border-[var(--hf-border)] px-2 py-1 text-xs shrink-0"
            />
          ) : (
            <div className="relative flex items-center shrink-0">
              <input
                type="text"
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
              {!twinQueryKey && twinSearchText.trim().length > 0 && (() => {
                const q = twinSearchText.trim().toLowerCase()
                const hits = places.filter((p) => {
                  const name = (p.catalog.name || '').toLowerCase()
                  return name.includes(q) || (p.catalog.county_borough || '').toLowerCase().includes(q) || (p.catalog.state_abbr || '').toLowerCase().includes(q)
                }).slice(0, 8)
                if (hits.length === 0) return null
                return (
                  <ul className="absolute left-0 top-full z-50 mt-1 w-72 rounded-xl border border-[var(--hf-border)] bg-white shadow-lg overflow-hidden">
                    {hits.map((p) => {
                      const key = catalogRowKey(p.catalog)
                      return (
                        <li key={key}>
                          <button
                            type="button"
                            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-[var(--hf-hover-bg)]"
                            onMouseDown={(e) => { e.preventDefault(); onTwinSelectFromSearch(key) }}
                          >
                            <span className="font-semibold text-[var(--hf-text-primary)]">{p.catalog.name}</span>
                            <span className="text-[var(--hf-text-tertiary)]">{p.catalog.county_borough}, {p.catalog.state_abbr}</span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )
              })()}
            </div>
          )}

          {catalogMode === 'explorer' && (
            <>
              <div className="h-4 w-px bg-[var(--hf-border)] shrink-0" />
              {/* Metro — segmented control */}
              <div className="flex items-center shrink-0 overflow-hidden rounded-lg border border-[var(--hf-border)]">
                {(['all', 'nyc', 'la', 'sf', 'seattle'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`border-r border-[var(--hf-border)] px-2.5 py-0.5 text-[0.65rem] font-bold last:border-r-0 ${filterMetro === m ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)] hover:bg-white'}`}
                    style={filterMetro === m ? { background: 'var(--hf-primary-1)' } : {}}
                    onClick={() => setFilterMetro(m)}
                  >
                    {m === 'all' ? 'All' : m === 'seattle' ? 'SEA' : m.toUpperCase()}
                    {m !== 'all' && metroResultCounts && (
                      <span className="ml-0.5 font-normal opacity-60">({metroResultCounts[m]})</span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}

          {catalogMode === 'twin' && (
            <div className="flex items-center gap-1 shrink-0">
              {twinControlsLocked && (
                <span className="text-[0.65rem] text-[var(--hf-text-tertiary)] italic">
                  Search a neighborhood to start
                </span>
              )}
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
                  {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetypes.length > 0 ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean.length > 0 ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterAoTypes.length > 0 ? 1 : 0) + (filterHousingType.length > 0 ? 1 : 0) + (filterTenure.length > 0 ? 1 : 0) + (filterSchoolType !== 'any' ? 1 : 0) + (filterLocalScene !== 'all' ? 1 : 0) + (filterCommuteMax !== 'all' ? 1 : 0) + climateActiveCount > 0 && (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full text-[0.6rem] font-bold text-white" style={{ background: 'var(--hf-primary-1)' }}>
                      {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetypes.length > 0 ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean.length > 0 ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterAoTypes.length > 0 ? 1 : 0) + (filterHousingType.length > 0 ? 1 : 0) + (filterTenure.length > 0 ? 1 : 0) + (filterSchoolType !== 'any' ? 1 : 0) + (filterLocalScene !== 'all' ? 1 : 0) + (filterCommuteMax !== 'all' ? 1 : 0) + climateActiveCount}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  title={indexMode !== 'homefit' ? 'Weights apply to HomeFit score only' : undefined}
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

        {/* ── Desktop toolbar: Row 2 — sort (explorer only) ── */}
        {catalogMode === 'explorer' && (
          <div className="hidden md:flex md:items-center md:gap-1.5 md:px-4 md:py-1.5 border-t border-[var(--hf-border)]" style={{ background: 'var(--hf-bg-subtle)' }}>
            <span className="text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)] shrink-0 mr-0.5">Sort</span>
            {/* Score indexes — Archetype intentionally excluded from sort row */}
            {INDEXES.filter(x => x.id !== 'status').map((x) => {
              const active = indexMode === x.id && !sortByName
              const activeStyle = catalogTabActiveStyle(catalogRampKey(x.id))
              return (
                <div key={x.id} className="flex items-center gap-0.5">
                  <button
                    type="button"
                    aria-pressed={active}
                    title={x.tooltip}
                    className="rounded-full px-2.5 py-0.5 text-xs font-bold"
                    style={active ? { ...activeStyle, border: 'none' } : { background: 'transparent', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }}
                    onClick={() => setIndexModeAndListSort(x.id)}
                  >{x.label}</button>
                  <IndexInfoButton indexId={x.id} />
                </div>
              )
            })}
            <button
              type="button"
              aria-pressed={isPillarIndexMode(indexMode) && !sortByName}
              title="Color map by a specific pillar score"
              className="rounded-full px-2.5 py-0.5 text-xs font-bold"
              style={isPillarIndexMode(indexMode) && !sortByName
                ? { background: '#E1F5EE', color: '#0F6E56', border: 'none' }
                : { background: 'transparent', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }}
              onClick={() => {
                if (!isPillarIndexMode(indexMode)) setIndexModeAndListSort('active_outdoors')
                else setIndexModeAndListSort('homefit')
              }}
            >Pillar</button>
            <button
              type="button"
              aria-pressed={sortByName}
              className="rounded-full px-2.5 py-0.5 text-xs font-bold"
              style={sortByName
                ? { background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }
                : { background: 'transparent', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }}
              onClick={() => { setSortByName(true) }}
            >A–Z</button>

            <div className="h-3 w-px bg-[var(--hf-border)] mx-1" />

            {/* Direction — visible text button */}
            <button
              type="button"
              className="flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)] border border-[var(--hf-border)]"
              onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
              aria-label={sortDir === 'desc' ? 'Highest first — click to reverse' : 'Lowest first — click to reverse'}
            >
              {sortDir === 'desc'
                ? <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>Highest first</>
                : <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>Lowest first</>
              }
            </button>

          </div>
        )}

        {catalogMode === 'explorer' && isPillarIndexMode(indexMode) && !sortByName && (
          <div
            className="hidden md:flex flex-wrap gap-1.5 px-4 py-2 border-t border-[var(--hf-border)]"
            style={{ background: 'var(--hf-bg-subtle)' }}
          >
            {PILLAR_INDEX_MODES.map((p) => (
              <button
                key={p.id}
                type="button"
                aria-pressed={indexMode === p.id}
                className="rounded-full px-3 py-1 text-[0.65rem] font-bold whitespace-nowrap transition-colors"
                style={indexMode === p.id
                  ? { background: '#1D9E75', color: '#fff', border: 'none' }
                  : { background: 'var(--hf-bg)', color: 'var(--hf-text-secondary)', border: '0.5px solid var(--hf-border)' }}
                onClick={() => setIndexModeAndListSort(p.id)}
              >{p.label}</button>
            ))}
          </div>
        )}

        {/* ── Mobile header: single compact row ── */}
        <div className="md:hidden flex flex-col">
          {/* Row 1: mode tabs + view controls */}
          <div className="flex items-center gap-1.5 px-3 py-2 min-h-[48px]">
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

          <div className="ml-auto flex items-center gap-2 shrink-0">
            {/* Filters pill */}
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-full border border-[var(--hf-border)] bg-white px-3 py-1.5 text-xs font-semibold text-[var(--hf-text-primary)] shadow-sm"
              onClick={() => setFilterSheetOpen(true)}
              aria-label="Filters"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Filters
              {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetypes.length > 0 ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean.length > 0 ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterAoTypes.length > 0 ? 1 : 0) + (filterHousingType.length > 0 ? 1 : 0) + (filterTenure.length > 0 ? 1 : 0) + (filterSchoolType !== 'any' ? 1 : 0) + (filterLocalScene !== 'all' ? 1 : 0) + (filterCommuteMax !== 'all' ? 1 : 0) + climateActiveCount > 0 && (
                <span className="flex h-4 w-4 items-center justify-center rounded-full text-[0.6rem] font-bold text-white" style={{ background: 'var(--hf-primary-1)' }}>
                  {(filterAreaTypes.length > 0 ? 1 : 0) + (filterArchetypes.length > 0 ? 1 : 0) + (filterTrajectory !== 'all' ? 1 : 0) + (filterPoliticalLean.length > 0 ? 1 : 0) + (filterNbTypes.length > 0 ? 1 : 0) + (filterAoTypes.length > 0 ? 1 : 0) + (filterHousingType.length > 0 ? 1 : 0) + (filterTenure.length > 0 ? 1 : 0) + (filterSchoolType !== 'any' ? 1 : 0) + (filterLocalScene !== 'all' ? 1 : 0) + (filterCommuteMax !== 'all' ? 1 : 0) + climateActiveCount}
                </span>
              )}
            </button>
          </div>
        </div>
        {/* Row 2: metro pills */}
          {catalogMode === 'explorer' && (
            <div className="flex gap-2 px-3 pb-3 pt-1">
              {(['all', 'nyc', 'la', 'sf', 'seattle'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`flex-1 rounded-full py-1.5 text-[0.7rem] font-semibold transition-colors ${filterMetro === m ? 'text-white shadow-sm' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
                  style={filterMetro === m ? { background: 'var(--hf-primary-1)' } : {}}
                  onClick={() => setFilterMetro(m)}
                >
                  {m === 'all' ? 'All' : m === 'seattle' ? 'SEA' : m.toUpperCase()}
                  {m !== 'all' && metroResultCounts && (
                    <span className="ml-0.5 font-normal opacity-60">({metroResultCounts[m]})</span>
                  )}
                </button>
              ))}
            </div>
          )}
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
                type="text"
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
              {!twinQueryKey && twinSearchText.trim().length > 0 && (() => {
                const q = twinSearchText.trim().toLowerCase()
                const hits = places.filter((p) => {
                  const name = (p.catalog.name || '').toLowerCase()
                  return name.includes(q) || (p.catalog.county_borough || '').toLowerCase().includes(q) || (p.catalog.state_abbr || '').toLowerCase().includes(q)
                }).slice(0, 8)
                if (hits.length === 0) return null
                return (
                  <ul className="absolute left-0 top-full z-50 mt-1 w-full rounded-xl border border-[var(--hf-border)] bg-white shadow-lg overflow-hidden">
                    {hits.map((p) => {
                      const key = catalogRowKey(p.catalog)
                      return (
                        <li key={key}>
                          <button
                            type="button"
                            className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-[var(--hf-hover-bg)]"
                            onMouseDown={(e) => { e.preventDefault(); onTwinSelectFromSearch(key) }}
                          >
                            <span className="font-semibold text-[var(--hf-text-primary)]">{p.catalog.name}</span>
                            <span className="text-xs text-[var(--hf-text-tertiary)]">{p.catalog.county_borough}, {p.catalog.state_abbr}</span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )
              })()}
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
            const rw = reweightScoreResponseFromPriorities(hoverPlace.score, effectivePriorities)
            const hf = rw.total_score
            const lon = hoverPlace.score.longevity_index ?? null
            const hap = hoverPlace.score.happiness_index ?? null
            const archetype = hoverPlace.score.status_signal_breakdown?.archetype ?? null
            const pillarScore = isPillarIndexMode(indexMode)
              ? ((hoverPlace.score.livability_pillars as any)?.[indexMode]?.score ?? null) as number | null
              : null
            const pillarLabel = isPillarIndexMode(indexMode)
              ? (PILLAR_INDEX_MODES.find(p => p.id === indexMode)?.label ?? null)
              : null
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
                {pillarLabel != null ? (
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#0F6E56', marginBottom: 2 }}>
                    {pillarLabel} {pillarScore != null && Number.isFinite(pillarScore) ? pillarScore.toFixed(0) : '—'}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#1a1a2e', marginBottom: 2 }}>
                    Score {Number.isFinite(hf) ? hf.toFixed(0) : '—'}
                  </div>
                )}
                {!pillarLabel && (
                  <div style={{ fontSize: 11, color: '#6b7280', display: 'flex', gap: 8, marginBottom: archetype ? 4 : 0 }}>
                    <span>Lon {lon != null && Number.isFinite(lon) ? lon.toFixed(0) : '—'}</span>
                    <span>Hap {hap != null && Number.isFinite(hap) ? hap.toFixed(0) : '—'}</span>
                  </div>
                )}
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

      {viewMode === 'list' && catalogMode === 'explorer' && !searchResults && (dealbreakerActive || metroFilterExcluded.length > 0) && (
        <div className="flex items-center gap-2 border-b border-[var(--hf-border)] bg-[var(--hf-hover-bg)] px-4 py-2 text-xs text-[var(--hf-text-secondary)]">
          <span>
            {dealbreakerZeroSurvivors
              ? 'No places clear all your must-haves — showing closest matches anyway'
              : dealbreakerExcludedCount > 0
                ? `${gatedPlaces.length} match all your must-haves · ${dealbreakerExcludedCount} excluded`
                : `All ${gatedPlaces.length} shown clear your must-haves`}
          </span>
          {dealbreakerExcludedCount > 0 && (
            <button
              onClick={() => setShowExcluded((v) => !v)}
              className="ml-auto shrink-0 rounded-full border border-[var(--hf-border)] px-2 py-0.5 text-[0.65rem] font-semibold text-[var(--hf-text-secondary)] hover:bg-white"
            >
              {showExcluded ? 'Hide excluded' : 'Show excluded'}
            </button>
          )}
        </div>
      )}

      {viewMode === 'list' && catalogMode === 'explorer' && (
        <div className={`flex min-h-0 flex-1 flex-col pb-20 md:pb-0${dealbreakerZeroSurvivors && !searchResults ? ' opacity-60' : ''}`}>
          <CatalogListView
            places={searchResults ? searchResults.hits : showExcluded && excludedPlaces.length > 0 ? (dealbreakerZeroSurvivors ? excludedPlaces : [...gatedPlaces, ...excludedPlaces]) : gatedPlaces}
            filteredOutReasons={searchResults ? searchResults.reasons : showExcluded && excludedPlaces.length > 0 ? {
              ...Object.fromEntries(
                excludedPlaces
                  .filter((p) => !metroFilterExcludedReasons[catalogRowKey(p.catalog)])
                  .map((p) => {
                    const failedKeys = activeDealbreakerKeys.filter((k) => !DEALBREAKER_CHECKS[k]?.(p))
                    return [catalogRowKey(p.catalog), failedKeys.length > 0 ? failedKeys.map((k) => `${PILLAR_META[k].name}`) : ['Must-haves']]
                  })
              ),
              ...metroFilterExcludedReasons,
            } : undefined}
            dividerLabel="Outside your must-haves"
            priorities={effectivePriorities}
            indexMode={indexMode}
            onTwinRow={onTwinRow}
            compareIds={compareIds}
            onCompareToggle={handleCompareToggle}
            onRowExpand={setSelectedKey}
          />
        </div>
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

      {/* Floating map/list toggle — Airbnb style */}
      {catalogMode === 'explorer' && (
        <div className="md:hidden pointer-events-none fixed bottom-6 left-0 right-0 z-40 flex justify-center">
          <button
            type="button"
            className="pointer-events-auto flex items-center gap-2 rounded-full bg-[#222] px-5 py-3 text-sm font-semibold text-white shadow-xl"
            onClick={() => setViewMode(viewMode === 'map' ? 'list' : 'map')}
          >
            {viewMode === 'map'
              ? <><List className="h-4 w-4" /> Show list</>
              : <><LayoutGrid className="h-4 w-4" /> Show map</>
            }
          </button>
        </div>
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
              const rw = reweightScoreResponseFromPriorities(queryPlace.score, effectivePriorities)
              const hf = rw.total_score
              return Number.isFinite(hf) ? (
                <span style={{ color: 'var(--hf-text-secondary)' }}> · HomeFit {hf.toFixed(1)}</span>
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
        currentHomeMonthlyCostInput={currentHomeMonthlyCostInput}
        onCurrentHomeMonthlyCostInputChange={setCurrentHomeMonthlyCostInput}
        onCurrentHomeMonthlyCostBlur={() => handleCurrentHomeMonthlyCostBlur(currentHomeMonthlyCostInput)}
        onCurrentHomeMonthlyCostClear={handleCurrentHomeMonthlyCostClear}
        currentHomeMatch={currentHomeMatch}
        onCurrentHomeSelect={handleCurrentHomeSelect}
        currentHomePlaceOptions={currentHomePlaceOptions}
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
        filterArchetypes={filterArchetypes}
        onFilterArchetypesChange={setFilterArchetypes}
        archetypes={archetypes}
        filterTrajectory={filterTrajectory}
        onFilterTrajectoryChange={setFilterTrajectory}
        filterPoliticalLean={filterPoliticalLean}
        onFilterPoliticalLeanChange={setFilterPoliticalLean}
        filterNbTypes={filterNbTypes}
        onFilterNbTypesChange={setFilterNbTypes}
        filterAoTypes={filterAoTypes}
        onFilterAoTypesChange={(next) => {
          setFilterAoTypes(next)
          if (!next.includes('waterfront') || next.length >= 3) setFilterWaterfrontSubPref(null)
        }}
        filterWaterfrontSubPref={filterWaterfrontSubPref}
        onFilterWaterfrontSubPrefChange={setFilterWaterfrontSubPref}
        filterHousingType={filterHousingType}
        onFilterHousingTypeChange={setFilterHousingType}
        filterTenure={filterTenure}
        onFilterTenureChange={setFilterTenure}
        filterSchoolType={filterSchoolType}
        onFilterSchoolTypeChange={setFilterSchoolType}
        filterLocalScene={filterLocalScene}
        onFilterLocalSceneChange={setFilterLocalScene}
        filterCommuteMax={filterCommuteMax}
        onFilterCommuteMaxChange={setFilterCommuteMax}
        climatePrefs={climatePrefs}
        onClimatePrefsChange={setClimatePrefs}
        resultCount={gatedPlaces.length}
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
