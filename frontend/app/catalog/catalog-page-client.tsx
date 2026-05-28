'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { LayoutGrid, List, SlidersHorizontal, X } from 'lucide-react'
import CatalogMapView from '@/components/catalog/CatalogMapView'
import CatalogBottomSheet, { findPlaceByKey, type CatalogSheetSnap } from '@/components/catalog/CatalogBottomSheet'
import CatalogWeightPanel from '@/components/catalog/CatalogWeightPanel'
import PillarTwinDrawer from '@/components/catalog/PillarTwinDrawer'
import TwinFinderPanel from '@/components/catalog/TwinFinderPanel'
import TwinCandidateDetailContent from '@/components/catalog/TwinCandidateDetailContent'
import CatalogListView from '@/components/catalog/CatalogListView'
import { DEFAULT_PRIORITIES, type PillarPriorities } from '@/components/SearchOptions'
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
import { reweightScoreResponseFromPriorities, applyUserIncomeToScore } from '@/lib/reweight'
import { adjustNbScore, type NbPreference } from '@/lib/nbPreference'
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
  const [places, setPlaces] = useState<CatalogMapPlaceWithMetro[]>([])
  const [loadMessage, setLoadMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [catalogMode, setCatalogMode] = useState<CatalogMode>('explorer')
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map')
  const [indexMode, setIndexMode] = useState<CatalogMapIndexMode>('homefit')
  const [priorities, setPriorities] = useState<PillarPriorities>(() => ({ ...DEFAULT_PRIORITIES }))
  const [politicalPreference, setPoliticalPreference] = useState<'progressive' | 'conservative' | null>(null)
  const [nbPreference, setNbPreference] = useState<NbPreference | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [snap, setSnap] = useState<CatalogSheetSnap>('peek')
  const [weightOpen, setWeightOpen] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  const [twinPillarOpen, setTwinPillarOpen] = useState(false)
  const [layoutVersion, setLayoutVersion] = useState(0)
  const [twinQueryKey, setTwinQueryKey] = useState<string | null>(null)
  const [twinSearchText, setTwinSearchText] = useState('')
  const [twinCrossMetro, setTwinCrossMetro] = useState(true)
  const [twinPillars, setTwinPillars] = useState<Set<PillarKey>>(() => defaultTwinPillarSet())
  const [filterText, setFilterText] = useState('')
  const [filterMetro, setFilterMetro] = useState<'all' | 'nyc' | 'la'>(initialMetroFilter)
  const [filterType, setFilterType] = useState<'all' | 'neighborhood' | 'suburb'>('all')
  const [filterArchetype, setFilterArchetype] = useState<string>('all')
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
    const ORDER = ['Established', 'Upper Middle Class', 'Middle Class', 'Up-and-Coming', 'Immigrant Community', 'Working Class']
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

    // Apply political_lean preference
    const withPolitical = politicalPreference
      ? withIncome.map((p) => {
          const pl = (p.score.livability_pillars as any)?.political_lean
          const lean2024 = pl?.breakdown?.lean_2024
          if (typeof lean2024 !== 'number') return p
          const polScore = politicalPreference === 'progressive'
            ? Math.max(0, Math.min(100, ((lean2024 + 1) / 2) * 100))
            : Math.max(0, Math.min(100, ((1 - lean2024) / 2) * 100))
          return { ...p, score: { ...p.score, livability_pillars: { ...p.score.livability_pillars, political_lean: { ...pl, score: polScore } } } }
        })
      : withIncome

    // Apply natural_beauty preference (falls back gracefully if rescore hasn't run yet)
    if (!nbPreference) return withPolitical
    return withPolitical.map((p) => {
      const nb = (p.score.livability_pillars as any)?.natural_beauty
      if (!nb) return p
      const adjusted = adjustNbScore(
        nb.score,
        nb.breakdown ?? {},
        nb.summary?.water_proximity_type,
        nbPreference,
        nb.area_classification?.area_type,
      )
      if (adjusted === null) return p
      return { ...p, score: { ...p.score, livability_pillars: { ...p.score.livability_pillars, natural_beauty: { ...nb, score: adjusted } } } }
    })
  }, [places, householdIncome, politicalPreference, nbPreference])

  const filteredPlaces = useMemo(() => {
    const t = filterText.trim().toLowerCase()
    let list = adjustedPlaces.filter((p) => {
      if (filterMetro !== 'all' && inferCatalogMetro(p) !== filterMetro) return false
      if (filterType !== 'all') {
        const ty = (p.catalog.type || '').toLowerCase()
        if (filterType === 'neighborhood' && ty !== 'neighborhood') return false
        if (filterType === 'suburb' && ty !== 'suburb') return false
      }
      if (filterArchetype !== 'all') {
        const ar = p.score.status_signal_breakdown?.archetype
        if (ar !== filterArchetype) return false
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
    filterType,
    filterArchetype,
    indexMode,
    sortByName,
    sortDir,
    priorities,
  ])

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
      12
    )
  }, [catalogMode, twinQueryKey, queryPlace, twinCandidatePlaces, twinPillarList])

  const mapPlacesNoTwinQuery = useMemo(() => {
    if (catalogMode !== 'twin') return filteredPlaces
    if (!twinQueryKey) return []
    return filteredPlaces
  }, [catalogMode, twinQueryKey, filteredPlaces])

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

  const selectedPlace = useMemo(() => findPlaceByKey(places, selectedKey), [places, selectedKey])

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
        onApplyPriorities={(quizPriorities, naturalBeautyPreference) => {
          setPriorities(quizPriorities)
          if (naturalBeautyPreference?.length) {
            setNbPreference(naturalBeautyPreference[0] as import('@/lib/nbPreference').NbPreference)
          }
          setShowQuiz(false)
        }}
        onBack={() => setShowQuiz(false)}
      />
    )
  }

  return (
    <div className="hf-viewport flex min-h-0 flex-col" style={{ height: '100dvh' }}>
      <header className="z-30 flex max-h-[55vh] shrink-0 flex-col gap-1.5 overflow-y-auto border-b border-[var(--hf-border)] bg-white/95 px-3 py-2 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="text-sm font-bold text-[var(--hf-text-primary)]">Explore</span>
            <p className="text-[0.65rem] text-[var(--hf-text-secondary)] leading-tight mt-0.5">Find neighborhoods that match how you want to live</p>
          </div>
          <Link
            href="/search"
            className="flex items-center gap-1 rounded-lg border border-[var(--hf-border)] px-2.5 py-1 text-xs font-semibold text-[var(--hf-text-secondary)]"
          >
            Search any place
            <span style={{ fontSize: '0.55rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '1px 4px', borderRadius: 3, background: 'var(--hf-primary-1)', color: '#fff' }}>Beta</span>
          </Link>
          <div className="flex items-center gap-1">
            <button
              type="button"
              className={`rounded-lg p-2 ${viewMode === 'map' ? 'bg-[var(--hf-hover-bg)]' : ''}`}
              onClick={() => setViewMode('map')}
              title="Map"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              type="button"
              className={`rounded-lg p-2 ${viewMode === 'list' ? 'bg-[var(--hf-hover-bg)]' : ''}`}
              onClick={() => setViewMode('list')}
              title="List"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            className={`rounded-full px-3 py-1 text-xs font-bold ${
              catalogMode === 'explorer' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
            }`}
            style={catalogMode === 'explorer' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
            onClick={() => {
              setCatalogMode('explorer')
              setTwinQueryKey(null)
              setTwinSearchText('')
              router.replace('/catalog', { scroll: false })
            }}
          >
            Explorer
          </button>
          <button
            type="button"
            className={`rounded-full px-3 py-1 text-xs font-bold ${
              catalogMode === 'twin' ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
            }`}
            style={catalogMode === 'twin' ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : {}}
            onClick={() => {
              setCatalogMode('twin')
              setViewMode('list')
            }}
          >
            Twin finder
          </button>
        </div>

        {catalogMode === 'twin' && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[0.65rem] font-semibold uppercase text-[var(--hf-text-tertiary)]">Mode</span>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-1 text-[0.7rem] font-bold disabled:cursor-not-allowed disabled:opacity-40 ${
                  twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'
                }`}
                onClick={() => setTwinCrossMetro(true)}
              >
                Cross-metro
              </button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className={`rounded-full px-2.5 py-1 text-[0.7rem] font-bold disabled:cursor-not-allowed disabled:opacity-40 ${
                  !twinCrossMetro ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-primary-1)]' : 'bg-[var(--hf-hover-bg)]'
                }`}
                onClick={() => setTwinCrossMetro(false)}
              >
                Same metro
              </button>
              <button
                type="button"
                disabled={twinControlsLocked}
                className="ml-auto flex items-center gap-1 rounded-lg border border-[var(--hf-border)] px-2 py-1 text-[0.7rem] font-bold disabled:cursor-not-allowed disabled:opacity-40"
                onClick={() => !twinControlsLocked && setTwinPillarOpen(true)}
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Pillars ({twinPillarList.length})
              </button>
            </div>

            <div className="relative flex items-center gap-1">
              <input
                type="search"
                placeholder="Search a neighborhood to find its twin…"
                value={twinQueryKey && queryPlace ? queryPlace.catalog.name : twinSearchText}
                onChange={(e) => {
                  if (twinQueryKey) return
                  setTwinSearchText(e.target.value)
                }}
                readOnly={!!twinQueryKey}
                className="w-full rounded-lg border border-[var(--hf-border)] py-1.5 pl-2 pr-9 text-sm"
              />
              {twinQueryKey && (
                <button
                  type="button"
                  className="absolute right-1 rounded p-1 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]"
                  onClick={clearTwinQuery}
                  aria-label="Clear neighborhood"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </>
        )}

        {catalogMode === 'explorer' && (
          <>
            <input
              type="search"
              placeholder="Search name, county…"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="w-full rounded-lg border border-[var(--hf-border)] px-2 py-1.5 text-sm"
            />

            <div className="flex flex-wrap gap-1">
              {(['all', 'nyc', 'la'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`rounded-full px-2.5 py-0.5 text-[0.7rem] font-bold ${
                    filterMetro === m ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
                  }`}
                  style={filterMetro === m ? { background: 'var(--hf-primary-1)' } : {}}
                  onClick={() => setFilterMetro(m)}
                >
                  {m === 'all' ? 'All metros' : m.toUpperCase()}
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-1">
              <span className="self-center text-[0.65rem] text-[var(--hf-text-tertiary)]">Type</span>
              {(['all', 'neighborhood', 'suburb'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`rounded-full px-2 py-0.5 text-[0.65rem] font-semibold ${
                    filterType === t ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-border-strong)]' : 'bg-[var(--hf-bg-subtle)]'
                  }`}
                  onClick={() => setFilterType(t)}
                >
                  {t === 'all' ? 'All' : t === 'neighborhood' ? 'Neighborhood' : 'Suburb'}
                </button>
              ))}
            </div>

            {archetypes.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <button
                  type="button"
                  className={`rounded-full px-2 py-0.5 text-[0.65rem] ${filterArchetype === 'all' ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-border-strong)]' : ''}`}
                  onClick={() => setFilterArchetype('all')}
                >
                  All archetypes
                </button>
                {archetypes.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={`rounded-full px-2 py-0.5 text-[0.65rem] ${filterArchetype === a ? 'bg-[var(--hf-hover-bg)] ring-1 ring-[var(--hf-border-strong)]' : ''}`}
                    onClick={() => setFilterArchetype(a)}
                  >
                    {displayArchetypeLabel(a)}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-center gap-1.5">
              <span className="text-[0.65rem] text-[var(--hf-text-tertiary)] shrink-0">My income</span>
              <div className="relative flex items-center">
                <span className="absolute left-2 text-xs text-[var(--hf-text-secondary)]">$</span>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="annual household"
                  value={incomeInputValue}
                  onChange={(e) => setIncomeInputValue(e.target.value)}
                  onBlur={(e) => {
                    const v = e.target.value === '' ? null : parseInt(e.target.value.replace(/,/g, ''), 10)
                    const next = Number.isFinite(v) && (v as number) >= 10000 ? (v as number) : null
                    if (next !== householdIncome) setHouseholdIncome(next)
                    setIncomeInputValue(next ? String(next) : '')
                    try {
                      const stored = sessionStorage.getItem('homefit_search_options')
                      const opts = stored ? JSON.parse(stored) : {}
                      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, household_income: next }))
                    } catch { /* ignore */ }
                  }}
                  className="w-36 rounded-lg border border-[var(--hf-border)] py-1 pl-5 pr-2 text-xs"
                />
                {householdIncome && (
                  <button
                    type="button"
                    className="absolute right-1.5 text-[var(--hf-text-tertiary)] hover:text-[var(--hf-text-secondary)]"
                    onClick={() => {
                      setHouseholdIncome(null)
                      setIncomeInputValue('')
                      try {
                        const stored = sessionStorage.getItem('homefit_search_options')
                        const opts = stored ? JSON.parse(stored) : {}
                        sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, household_income: null }))
                      } catch { /* ignore */ }
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>

            <div
              role="group"
              aria-label="Map index and list sort"
              className="flex flex-wrap items-center gap-2"
            >
              <div className="flex flex-wrap gap-1">
                {INDEXES.map((x) => {
                  const active = indexMode === x.id && !sortByName
                  const activeStyle = catalogTabActiveStyle(catalogRampKey(x.id))
                  return (
                    <button
                      key={x.id}
                      type="button"
                      aria-pressed={active}
                      title={x.tooltip}
                      className="rounded-full px-3 py-1.5 text-xs font-bold"
                      style={
                        active
                          ? { ...activeStyle, border: 'none' }
                          : {
                              background: 'var(--hf-hover-bg)',
                              color: 'var(--hf-text-secondary)',
                              border: '0.5px solid var(--hf-border)',
                            }
                      }
                      onClick={() => setIndexModeAndListSort(x.id)}
                    >
                      {x.label}
                    </button>
                  )
                })}
              </div>
              <button
                type="button"
                aria-pressed={sortByName}
                className={`text-[0.7rem] font-semibold ${
                  sortByName ? 'text-[var(--hf-primary-1)] underline' : 'text-[var(--hf-text-secondary)]'
                }`}
                onClick={() => setSortByName(true)}
              >
                A–Z
              </button>
              <button
                type="button"
                className="text-[0.7rem] font-semibold text-[var(--hf-primary-1)]"
                onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
              >
                {sortDir === 'desc' ? 'Desc' : 'Asc'}
              </button>
            </div>

            <button
              type="button"
              title={indexMode !== 'homefit' ? 'Weights apply to Trovamo score only' : undefined}
              className="self-start rounded-lg border border-[var(--hf-border-strong)] px-3 py-1.5 text-xs font-bold text-[var(--hf-text-primary)]"
              style={{
                opacity: indexMode !== 'homefit' ? 0.4 : 1,
                pointerEvents: indexMode !== 'homefit' ? 'none' : 'auto',
              }}
              onClick={() => setWeightOpen(true)}
            >
              Adjust weights
            </button>
          </>
        )}
      </header>

      {viewMode === 'map' && (
        <div className="flex min-h-0 flex-1 flex-col">
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
          />
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
        </div>
      )}

      {viewMode === 'list' && catalogMode === 'explorer' && (
        <CatalogListView places={filteredPlaces} priorities={priorities} onTwinRow={onTwinRow} />
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
      )}

      {catalogMode === 'twin' && twinQueryKey && queryPlace && (
        <CatalogBottomSheet
          place={queryPlace}
          indexMode={indexMode}
          onIndexModeChange={setIndexModeAndListSort}
          priorities={priorities}
          snap={snap}
          onSnapChange={setSnap}
          onClose={clearTwinQuery}
          onFullBreakdown={handleFullBreakdown}
        />
      )}

      <CatalogWeightPanel
        open={weightOpen && indexMode === 'homefit'}
        onClose={() => setWeightOpen(false)}
        priorities={priorities}
        onChange={setPriorities}
        politicalPreference={politicalPreference}
        onPoliticalPreferenceChange={setPoliticalPreference}
        nbPreference={nbPreference}
        onNbPreferenceChange={setNbPreference}
        onTakeQuiz={() => { setWeightOpen(false); setShowQuiz(true) }}
      />

      <PillarTwinDrawer
        open={twinPillarOpen}
        onClose={() => setTwinPillarOpen(false)}
        selected={twinPillars}
        onChange={setTwinPillars}
        disabled={twinControlsLocked}
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
