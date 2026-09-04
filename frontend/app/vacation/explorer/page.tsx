'use client'

import { useEffect, useRef, useState, useMemo } from 'react'
import 'maplibre-gl/dist/maplibre-gl.css'
import { scoreBandFill, homefitPillarBarFill } from '@/lib/indexColorSystem'
import type { VacationPlace, TripType } from '@/lib/vacationCatalogTypes'
import { TRIP_TYPE_LABEL, TRIP_TYPE_EMOJI, VACATION_PILLAR_LABELS } from '@/lib/vacationCatalogTypes'
import type { TravelerProfile } from '@/components/vacation/TravelerProfileSelector'
import { PROFILE_META, recomputeScoreWithProfile, getDisplayWeights } from '@/lib/travelerProfiles'

const TRIP_TYPES: TripType[] = ['beach', 'mountain', 'city']

// ── Map ──────────────────────────────────────────────────────────────────────

function VacationMap({
  places,
  selectedKey,
  onSelect,
}: {
  places: VacationPlace[]
  selectedKey: string | null
  onSelect: (key: string | null) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<import('maplibre-gl').Map | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const [mapLoaded, setMapLoaded] = useState(false)

  // Effect 1: create the map once
  useEffect(() => {
    if (typeof window === 'undefined' || !containerRef.current) return
    let cancelled = false

    ;(async () => {
      const ml = await import('maplibre-gl')
      const maplibregl = ml.default ?? ml
      if (cancelled || !containerRef.current) return

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: {
          version: 8 as const,
          sources: {
            osm: {
              type: 'raster' as const,
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              attribution: '© OpenStreetMap contributors',
            },
          },
          layers: [{ id: 'osm', type: 'raster' as const, source: 'osm' }],
          glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
        },
        bounds: [[-125, 24], [-66, 50]],
        fitBoundsOptions: { padding: 60 },
      })

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

      map.on('load', () => {
        if (cancelled) return
        mapRef.current = map
        setMapLoaded(true)
      })
    })()

    return () => {
      cancelled = true
      mapRef.current?.remove()
      mapRef.current = null
      setMapLoaded(false)
    }
  }, [])

  // Effect 2: add/update data once map is loaded
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    const geojson: GeoJSON.FeatureCollection = {
      type: 'FeatureCollection',
      features: places.map((p) => ({
        type: 'Feature',
        properties: {
          key: p.key,
          norm: p.total_score,
          label: p.location.split(',')[0],
          fill: scoreBandFill('purple', p.total_score),
        },
        geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      })),
    }

    const existing = map.getSource('vacation') as import('maplibre-gl').GeoJSONSource | undefined
    if (existing) {
      existing.setData(geojson)
      return
    }

    map.addSource('vacation', { type: 'geojson', data: geojson })

    map.addLayer({
      id: 'vacation-circles',
      type: 'circle',
      source: 'vacation',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          3, ['+', 4, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 6]],
          9, ['+', 7, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 12]],
        ],
        'circle-color': ['get', 'fill'],
        'circle-stroke-width': 1.5,
        'circle-stroke-color': 'rgba(255,255,255,0.8)',
        'circle-opacity': 0.9,
      },
    })

    map.addLayer({
      id: 'vacation-labels',
      type: 'symbol',
      source: 'vacation',
      layout: {
        'text-field': ['get', 'label'],
        'text-size': 11,
        'text-offset': [0, 1.4],
        'text-anchor': 'top',
        'text-optional': true,
        'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
      },
      paint: {
        'text-color': '#374151',
        'text-halo-color': '#ffffff',
        'text-halo-width': 1.5,
      },
    })

    map.on('click', 'vacation-circles', (e) => {
      const key = e.features?.[0]?.properties?.key as string | undefined
      onSelectRef.current(key ?? null)
    })

    map.on('click', (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['vacation-circles'] })
      if (!features.length) onSelectRef.current(null)
    })

    map.on('mouseenter', 'vacation-circles', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'vacation-circles', () => { map.getCanvas().style.cursor = '' })
  }, [mapLoaded, places])

  // Effect 3: update selection highlight
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return
    try {
      map.setPaintProperty('vacation-circles', 'circle-stroke-width', [
        'case', ['==', ['get', 'key'], selectedKey ?? ''], 3, 1.5,
      ])
      map.setPaintProperty('vacation-circles', 'circle-stroke-color', [
        'case', ['==', ['get', 'key'], selectedKey ?? ''], '#ffffff', 'rgba(255,255,255,0.7)',
      ])
    } catch { /* layer not ready */ }
  }, [selectedKey, mapLoaded])

  return <div ref={containerRef} className="h-full w-full" />
}

// ── Bottom sheet ──────────────────────────────────────────────────────────────

function BottomSheet({
  place,
  profile,
  onClose,
}: {
  place: VacationPlace | null
  profile: TravelerProfile | null
  onClose: () => void
}) {
  const displayWeights = place ? getDisplayWeights(profile, place.trip_type) : {}
  const entries = place
    ? Object.entries(place.pillars).filter(([key]) => (displayWeights[key] ?? 0) > 0)
    : []

  return (
    <div
      className="absolute bottom-0 left-0 right-0 z-20 pointer-events-none"
      style={{ transition: 'transform 0.25s ease' }}
    >
      <div
        className="pointer-events-auto rounded-t-2xl border-t border-[var(--hf-border)] bg-white shadow-[0_-4px_24px_rgba(0,0,0,0.10)]"
        style={{
          transform: place ? 'translateY(0)' : 'translateY(110%)',
          transition: 'transform 0.25s cubic-bezier(0.32,0.72,0,1)',
          maxHeight: '55vh',
          overflowY: 'auto',
        }}
      >
        {place && (
          <div className="px-4 pb-6 pt-3">
            {/* Handle */}
            <div className="mx-auto mb-3 h-1 w-8 rounded-full bg-[var(--hf-border)]" />

            {/* Header row */}
            <div className="flex items-start gap-3">
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
                style={{ background: scoreBandFill('purple', place.total_score) }}
              >
                {place.total_score.toFixed(0)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-[var(--hf-text-primary)]" style={{ fontSize: 16 }}>
                  {place.location}
                </div>
                <span
                  className="mt-0.5 inline-block rounded-full px-2 py-0.5 text-[0.65rem] font-semibold text-white"
                  style={{
                    background:
                      place.trip_type === 'beach' ? '#0ea5e9'
                      : place.trip_type === 'mountain' ? '#22c55e'
                      : '#a855f7',
                  }}
                >
                  {TRIP_TYPE_EMOJI[place.trip_type]} {TRIP_TYPE_LABEL[place.trip_type]}
                </span>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full p-1.5 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            {/* Pillar bars */}
            <div className="mt-4 space-y-2">
              {entries.map(([key, p]) => {
                const score = p.score ?? 0
                const fill = homefitPillarBarFill(score)
                const label = VACATION_PILLAR_LABELS[key] ?? key.replace(/_/g, ' ')
                return (
                  <div key={key} className="flex items-center gap-2 text-xs">
                    <span className="w-36 shrink-0 truncate text-[var(--hf-text-secondary)]">{label}</span>
                    <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                      {p.score != null && (
                        <div className="h-full rounded-full" style={{ width: `${Math.min(100, score)}%`, background: fill }} />
                      )}
                    </div>
                    <span className="w-7 shrink-0 text-right tabular-nums text-[var(--hf-text-primary)] font-semibold">
                      {p.score != null ? score.toFixed(0) : '—'}
                    </span>
                    <span className="w-8 shrink-0 text-right tabular-nums text-[var(--hf-text-tertiary)]">
                      {(displayWeights[key] ?? 0).toFixed(0)}%
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function VacationExplorerPage() {
  const [places, setPlaces] = useState<VacationPlace[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<TripType | 'all'>('all')
  const [profile, setProfile] = useState<TravelerProfile | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/vacation-catalog')
      .then((r) => r.json())
      .then((d) => { setPlaces(d.places ?? []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    const base = places.filter((p) => filter === 'all' || p.trip_type === filter)
    if (!profile) return base
    return base
      .map((p) => ({ ...p, total_score: recomputeScoreWithProfile(p, profile) }))
      .sort((a, b) => b.total_score - a.total_score)
  }, [places, filter, profile])

  const selectedPlace = selectedKey ? (filtered.find((p) => p.key === selectedKey) ?? places.find((p) => p.key === selectedKey) ?? null) : null

  return (
    <div className="hf-viewport hf-catalog-root flex min-h-0 flex-col">
      {/* ── Toolbar ── */}
      <header className="z-30 shrink-0 border-b border-[var(--hf-border)] bg-white/95 backdrop-blur">
        {/* Row 1: trip type + count */}
        <div className="flex items-center gap-2 px-3 pt-2 pb-1 md:px-4">
          <div className="flex items-center gap-1 shrink-0">
            {(['all', ...TRIP_TYPES] as const).map((t) => {
              const active = filter === t
              return (
                <button
                  key={t}
                  type="button"
                  className="rounded-full px-3 py-1 text-xs font-bold"
                  style={
                    active
                      ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))', color: '#fff', border: 'none' }
                      : { background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)', border: 'none' }
                  }
                  onClick={() => { setFilter(t); setSelectedKey(null) }}
                >
                  {t === 'all' ? 'All' : `${TRIP_TYPE_EMOJI[t]} ${TRIP_TYPE_LABEL[t]}`}
                </button>
              )
            })}
          </div>
          <span className="text-xs text-[var(--hf-text-tertiary)] shrink-0">
            {loading ? 'Loading…' : `${filtered.length} destinations`}
          </span>
        </div>

        {/* Row 2: traveler profile chips */}
        <div className="flex items-center gap-1 overflow-x-auto px-3 pb-2 md:px-4" style={{ scrollbarWidth: 'none' }}>
          <span className="shrink-0 text-[11px] text-[var(--hf-text-tertiary)] mr-1">Who:</span>
          {PROFILE_META.map((p) => {
            const active = profile === p.value
            return (
              <button
                key={p.value}
                type="button"
                onClick={() => setProfile(active ? null : p.value)}
                className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold transition-all"
                style={
                  active
                    ? { background: 'var(--hf-primary-1)', color: '#fff', border: 'none' }
                    : { background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)', border: 'none' }
                }
              >
                {p.emoji} {p.label}
              </button>
            )
          })}
          {profile && (
            <span className="shrink-0 text-[10px] text-[var(--hf-text-tertiary)] ml-1 italic">
              scores recomputed
            </span>
          )}
        </div>
      </header>

      {/* ── Map + bottom sheet ── */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        {!loading && (
          <VacationMap
            places={filtered}
            selectedKey={selectedKey}
            onSelect={(key) => setSelectedKey(key === selectedKey ? null : key)}
          />
        )}

        {/* Legend */}
        <div
          className="absolute left-3 top-3 z-10 rounded-xl border border-[var(--hf-border)] bg-white/92 px-3 py-2 shadow-sm backdrop-blur"
          style={{ fontSize: 11 }}
        >
          {[{ label: 'Score 75+', opacity: 1 }, { label: 'Score 65–74', opacity: 0.7 }, { label: 'Score <65', opacity: 0.45 }].map(({ label, opacity }) => (
            <div key={label} className="flex items-center gap-1.5 py-0.5">
              <div className="h-3 w-3 rounded-full" style={{ background: 'var(--c-purple-500)', opacity }} />
              <span className="text-[var(--hf-text-secondary)]">{label}</span>
            </div>
          ))}
          <div className="mt-1 text-[var(--hf-text-tertiary)]">Bubble size = score</div>
        </div>

        <BottomSheet
          place={selectedPlace}
          profile={profile}
          onClose={() => setSelectedKey(null)}
        />
      </div>
    </div>
  )
}
