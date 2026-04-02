'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import CatalogMapView from '@/components/catalog/CatalogMapView'
import CatalogBottomSheet, {
  findPlaceByKey,
  type CatalogSheetSnap,
} from '@/components/catalog/CatalogBottomSheet'
import CatalogWeightPanel from '@/components/catalog/CatalogWeightPanel'
import { DEFAULT_PRIORITIES, type PillarPriorities } from '@/components/SearchOptions'
import { buildCatalogFeatureCollection } from '@/lib/catalogMapGeo'
import type { CatalogMapIndexMode, CatalogMapPlace } from '@/lib/catalogMapTypes'
import { writeCatalogResultsHydrate } from '@/lib/catalogResultsHydrate'
import { buildResultsCacheKey, buildResultsUrl } from '@/lib/resultsShare'

const INDEXES: { id: CatalogMapIndexMode; label: string }[] = [
  { id: 'homefit', label: 'HomeFit' },
  { id: 'longevity', label: 'Longevity' },
  { id: 'happiness', label: 'Happiness' },
  { id: 'status', label: 'Status' },
]

export default function CatalogMapClient() {
  const router = useRouter()
  const [places, setPlaces] = useState<CatalogMapPlace[]>([])
  const [loadMessage, setLoadMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [indexMode, setIndexMode] = useState<CatalogMapIndexMode>('homefit')
  const [priorities, setPriorities] = useState<PillarPriorities>(() => ({ ...DEFAULT_PRIORITIES }))
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [snap, setSnap] = useState<CatalogSheetSnap>('peek')
  const [weightOpen, setWeightOpen] = useState(false)
  const [layoutVersion, setLayoutVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch('/api/catalog-map')
        const j = (await r.json()) as {
          places?: CatalogMapPlace[]
          source?: string
          detail?: string
        }
        if (cancelled) return
        setPlaces(Array.isArray(j.places) ? j.places : [])
        if (j.detail && (!j.places || j.places.length === 0)) setLoadMessage(j.detail)
        else if (j.source === 'missing') setLoadMessage(j.detail ?? 'Catalog data not found on server.')
      } catch (e) {
        if (!cancelled) setLoadMessage(e instanceof Error ? e.message : 'Failed to load catalog.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const geojson = useMemo(
    () => buildCatalogFeatureCollection(places, indexMode, priorities),
    [places, indexMode, priorities]
  )

  const selectedPlace = useMemo(() => findPlaceByKey(places, selectedKey), [places, selectedKey])

  const onSelectKey = useCallback((key: string | null) => {
    setSelectedKey(key)
    if (key) setSnap('expanded')
  }, [])

  useEffect(() => {
    setLayoutVersion((v) => v + 1)
  }, [snap])

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

  return (
    <div className="hf-viewport flex min-h-0 flex-col" style={{ height: '100dvh' }}>
      <header className="z-30 flex shrink-0 flex-col gap-2 border-b border-[var(--hf-border)] bg-white/95 px-3 py-2 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <Link href="/" className="text-sm font-semibold" style={{ color: 'var(--hf-primary-1)' }}>
            ← Home
          </Link>
          <span className="text-sm font-bold text-[var(--hf-text-primary)]">NYC metro catalog</span>
          <span className="w-14" aria-hidden />
        </div>
        <div className="flex flex-wrap gap-1">
          {INDEXES.map((x) => (
            <button
              key={x.id}
              type="button"
              className={`rounded-full px-3 py-1.5 text-xs font-bold ${
                indexMode === x.id ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'
              }`}
              style={indexMode === x.id ? { background: 'var(--hf-primary-gradient)' } : undefined}
              onClick={() => setIndexMode(x.id)}
            >
              {x.label}
            </button>
          ))}
        </div>
        {indexMode === 'homefit' && (
          <button
            type="button"
            className="self-start rounded-lg border border-[var(--hf-border-strong)] px-3 py-1.5 text-xs font-bold text-[var(--hf-text-primary)]"
            onClick={() => setWeightOpen(true)}
          >
            Adjust weights
          </button>
        )}
      </header>

      <CatalogMapView
        data={geojson}
        selectedKey={selectedKey}
        onSelectKey={onSelectKey}
        layoutVersion={layoutVersion}
      />

      <CatalogBottomSheet
        place={selectedPlace}
        indexMode={indexMode}
        priorities={priorities}
        snap={snap}
        onSnapChange={setSnap}
        onClose={() => {
          setSelectedKey(null)
          setSnap('peek')
        }}
        onFullBreakdown={handleFullBreakdown}
      />

      <CatalogWeightPanel
        open={weightOpen && indexMode === 'homefit'}
        onClose={() => setWeightOpen(false)}
        priorities={priorities}
        onChange={setPriorities}
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
