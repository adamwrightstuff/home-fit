'use client'

import { useEffect, useRef, useState } from 'react'
import AppHeader from '@/components/AppHeader'
import { scoreBandFill, homefitPillarBarFill } from '@/lib/indexColorSystem'
import type { VacationPlace, TripType } from '@/lib/vacationCatalogTypes'
import { TRIP_TYPE_LABEL, TRIP_TYPE_EMOJI, VACATION_PILLAR_LABELS } from '@/lib/vacationCatalogTypes'

const TRIP_TYPES: TripType[] = ['beach', 'mountain', 'city']

const TRIP_TYPE_COLOR: Record<TripType, string> = {
  beach: '#0ea5e9',
  mountain: '#22c55e',
  city: '#a855f7',
}

function ScoreRing({ score }: { score: number }) {
  const fill = scoreBandFill('purple', score)
  return (
    <div
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
      style={{ background: fill }}
    >
      {score.toFixed(0)}
    </div>
  )
}

function TripTypeBadge({ type }: { type: TripType }) {
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[0.65rem] font-semibold text-white"
      style={{ background: TRIP_TYPE_COLOR[type] }}
    >
      {TRIP_TYPE_EMOJI[type]} {TRIP_TYPE_LABEL[type]}
    </span>
  )
}

function PillarGrid({ pillars }: { pillars: VacationPlace['pillars'] }) {
  const entries = Object.entries(pillars).filter(([, v]) => (v.weight ?? 0) > 0)
  return (
    <div className="mt-3 space-y-1.5">
      {entries.map(([key, p]) => {
        const score = p.score ?? 0
        const fill = homefitPillarBarFill(score)
        const label = VACATION_PILLAR_LABELS[key] ?? key.replace(/_/g, ' ')
        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-32 shrink-0 truncate text-[var(--hf-text-secondary)]">{label}</span>
            <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
              {p.score != null && (
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, score)}%`, background: fill }} />
              )}
            </div>
            <span className="w-7 shrink-0 text-right tabular-nums text-[var(--hf-text-primary)]">
              {p.score != null ? score.toFixed(0) : '—'}
            </span>
            <span className="w-8 shrink-0 text-right tabular-nums text-[var(--hf-text-tertiary)]">
              {p.weight.toFixed(0)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

function PlaceCard({
  place,
  selected,
  onClick,
}: {
  place: VacationPlace
  selected: boolean
  onClick: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer rounded-xl border p-3 transition-all ${
        selected
          ? 'border-[var(--hf-accent)] bg-[var(--hf-accent-subtle)]'
          : 'border-[var(--hf-border)] bg-[var(--hf-bg-card)] hover:border-[var(--hf-accent)]'
      }`}
    >
      <div className="flex items-center gap-3">
        <ScoreRing score={place.total_score} />
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-[var(--hf-text-primary)]">{place.location}</div>
          <TripTypeBadge type={place.trip_type} />
        </div>
      </div>
      {selected && <PillarGrid pillars={place.pillars} />}
    </div>
  )
}

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

  useEffect(() => {
    if (!containerRef.current) return
    let destroyed = false

    import('maplibre-gl').then(({ Map, NavigationControl }) => {
      if (destroyed || !containerRef.current) return

      const map = new Map({
        container: containerRef.current,
        style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
        bounds: [[-125, 24], [-66, 50]],
        fitBoundsOptions: { padding: 40 },
      })
      mapRef.current = map

      map.addControl(new NavigationControl({ showCompass: false }), 'top-right')

      map.on('load', () => {
        const geojson: GeoJSON.FeatureCollection = {
          type: 'FeatureCollection',
          features: places.map((p) => ({
            type: 'Feature',
            properties: {
              key: p.key,
              score: p.total_score,
              label: p.location.split(',')[0],
              fill: scoreBandFill('purple', p.total_score),
              trip_type: p.trip_type,
            },
            geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
          })),
        }

        map.addSource('vacation', { type: 'geojson', data: geojson })

        map.addLayer({
          id: 'vacation-circles',
          type: 'circle',
          source: 'vacation',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 8, 8, 14],
            'circle-color': ['get', 'fill'],
            'circle-stroke-width': ['case', ['==', ['get', 'key'], selectedKey ?? ''], 3, 1.5],
            'circle-stroke-color': ['case', ['==', ['get', 'key'], selectedKey ?? ''], '#ffffff', 'rgba(255,255,255,0.6)'],
            'circle-opacity': 0.92,
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
          },
          paint: {
            'text-color': '#334155',
            'text-halo-color': '#ffffff',
            'text-halo-width': 1.5,
          },
        })

        map.on('click', 'vacation-circles', (e) => {
          const key = e.features?.[0]?.properties?.key as string | undefined
          onSelect(key ?? null)
        })

        map.on('mouseenter', 'vacation-circles', () => {
          map.getCanvas().style.cursor = 'pointer'
        })
        map.on('mouseleave', 'vacation-circles', () => {
          map.getCanvas().style.cursor = ''
        })
      })
    })

    return () => {
      destroyed = true
      mapRef.current?.remove()
      mapRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [places.length])

  // Update stroke when selection changes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return
    try {
      map.setPaintProperty('vacation-circles', 'circle-stroke-width', [
        'case', ['==', ['get', 'key'], selectedKey ?? ''], 3, 1.5,
      ])
      map.setPaintProperty('vacation-circles', 'circle-stroke-color', [
        'case', ['==', ['get', 'key'], selectedKey ?? ''], '#ffffff', 'rgba(255,255,255,0.6)',
      ])
    } catch {
      // map not ready yet
    }
  }, [selectedKey])

  return <div ref={containerRef} className="h-full w-full" />
}

export default function VacationExplorerPage() {
  const [places, setPlaces] = useState<VacationPlace[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<TripType | 'all'>('all')
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const selectedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/vacation-catalog')
      .then((r) => r.json())
      .then((d) => {
        setPlaces(d.places ?? [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const filtered = places
    .filter((p) => filter === 'all' || p.trip_type === filter)
    .sort((a, b) => b.total_score - a.total_score)

  const displayed = filter === 'all' ? places : filtered

  useEffect(() => {
    if (selectedKey && selectedRef.current) {
      selectedRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [selectedKey])

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        {/* Sidebar */}
        <div className="flex w-80 shrink-0 flex-col border-r border-[var(--hf-border)]">
          {/* Filter bar */}
          <div className="flex gap-1.5 border-b border-[var(--hf-border)] px-3 py-2.5">
            {(['all', ...TRIP_TYPES] as const).map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                  filter === t
                    ? 'bg-[var(--hf-accent)] text-white'
                    : 'bg-[var(--hf-bg-subtle)] text-[var(--hf-text-secondary)] hover:bg-[var(--hf-border)]'
                }`}
              >
                {t === 'all' ? 'All' : `${TRIP_TYPE_EMOJI[t]} ${TRIP_TYPE_LABEL[t]}`}
              </button>
            ))}
          </div>

          {/* Count */}
          <div className="px-3 py-1.5 text-xs text-[var(--hf-text-tertiary)]">
            {loading ? 'Loading…' : `${filtered.length} destinations`}
          </div>

          {/* List */}
          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-1 space-y-1.5">
            {filtered.map((p) => (
              <div key={p.key} ref={p.key === selectedKey ? selectedRef : undefined}>
                <PlaceCard
                  place={p}
                  selected={p.key === selectedKey}
                  onClick={() => setSelectedKey(p.key === selectedKey ? null : p.key)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Map */}
        <div className="relative min-h-0 flex-1">
          {!loading && (
            <VacationMap
              places={displayed}
              selectedKey={selectedKey}
              onSelect={(key) => setSelectedKey(key === selectedKey ? null : key)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
