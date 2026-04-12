'use client'

import { useEffect, useRef, useState } from 'react'
import type { ExpressionSpecification, Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

type CatalogMapGeoJson =
  | ReturnType<typeof import('@/lib/catalogMapGeo').buildCatalogFeatureCollection>
  | ReturnType<typeof import('@/lib/catalogMapGeo').buildTwinMatchFeatureCollection>

export type CatalogMapRegion = 'nyc' | 'la' | 'both'

interface CatalogMapViewProps {
  data: CatalogMapGeoJson
  selectedKey: string | null
  onSelectKey: (key: string | null) => void
  /** Bumps map.resize when the bottom sheet snaps. */
  layoutVersion: number
  /** Active index — bubble stroke uses this ramp (ramp-600 @ 60%). */
  indexMode: CatalogMapIndexMode
  /** Initial map bounds; `both` fits NYC+LA. */
  region: CatalogMapRegion
  /** Explorer = index-colored bubbles; twin = match % labels + top highlight. */
  mapVariant: 'explorer' | 'twin'
  /** When set, draw a line (e.g. query → top twin). */
  twinLineGeoJson?: {
    type: 'FeatureCollection'
    features: Array<{
      type: 'Feature'
      properties?: Record<string, unknown>
      geometry: { type: 'LineString'; coordinates: [number, number][] }
    }>
  } | null
  /** Change when the visible dataset changes to re-run fitBounds. */
  fitKey?: string
}

const NYC_METRO_BOUNDS: [[number, number], [number, number]] = [
  [-74.35, 40.45],
  [-73.65, 41.05],
]

const LA_METRO_BOUNDS: [[number, number], [number, number]] = [
  [-118.75, 33.55],
  [-117.55, 34.45],
]

const BOTH_METRO_BOUNDS: [[number, number], [number, number]] = [
  [-118.8, 33.5],
  [-73.6, 41.1],
]

/** MapLibre: `zoom` may only index a *top-level* `interpolate`/`step` — not nested under `+`. */
const EXPLORER_CIRCLE_RADIUS: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  9,
  ['+', 3, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 10]],
  14,
  ['+', 11, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 10]],
]

const TWIN_CIRCLE_RADIUS: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  9,
  [
    'case',
    ['==', ['coalesce', ['get', 'isTop'], 0], 1],
    ['+', 5, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 12]],
    ['+', 3, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 8]],
  ],
  14,
  [
    'case',
    ['==', ['coalesce', ['get', 'isTop'], 0], 1],
    ['+', 14, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 12]],
    ['+', 10, ['*', ['/', ['coalesce', ['get', 'norm'], 0], 100], 8]],
  ],
]

export default function CatalogMapView({
  data,
  selectedKey,
  onSelectKey,
  layoutVersion,
  indexMode,
  region = 'nyc',
  mapVariant,
  twinLineGeoJson,
  fitKey = 'default',
}: CatalogMapViewProps) {
  const container_ref = useRef<HTMLDivElement>(null)
  const map_ref = useRef<MapLibreMap | null>(null)
  const on_select_ref = useRef(onSelectKey)
  on_select_ref.current = onSelectKey
  const [map_loaded, set_map_loaded] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const fitted_ref = useRef<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !container_ref.current) return
    let cancelled = false

    ;(async () => {
      try {
        const maplibre = await import('maplibre-gl')
        const maplibregl = maplibre.default
        if (cancelled || !container_ref.current) return

        const style = {
          version: 8 as const,
          sources: {
            'osm-tiles': {
              type: 'raster' as const,
              tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
              tileSize: 256,
              attribution: '© OpenStreetMap contributors',
            },
          },
          layers: [
            {
              id: 'osm-tiles',
              type: 'raster' as const,
              source: 'osm-tiles',
              minzoom: 0,
              maxzoom: 19,
            },
          ],
        }

        const initialBounds =
          region === 'la' ? LA_METRO_BOUNDS : region === 'both' ? BOTH_METRO_BOUNDS : NYC_METRO_BOUNDS
        const map = new maplibregl.Map({
          container: container_ref.current,
          style,
          bounds: initialBounds,
          fitBoundsOptions: { padding: 24, maxZoom: mapVariant === 'twin' ? 11 : 11 },
        })

        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

        map.on('load', () => {
          if (cancelled) return
          map_ref.current = map
          set_map_loaded(true)
        })

        map.on('error', (e: { error?: { message?: string } }) => {
          set_error(e.error?.message || 'Map error')
        })
      } catch (e: unknown) {
        set_error(e instanceof Error ? e.message : 'Failed to load map')
      }
    })()

    return () => {
      cancelled = true
      if (map_ref.current) {
        try {
          map_ref.current.remove()
        } catch {
          // ignore
        }
        map_ref.current = null
        set_map_loaded(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- remount base map only when region changes
  }, [region])

  useEffect(() => {
    if (!map_ref.current || !map_loaded) return
    const map = map_ref.current
    const sync = () => {
      if (!map.isStyleLoaded()) {
        map.once('styledata', sync)
        return
      }
      try {
        if (!map.getSource('catalog')) {
          map.addSource('catalog', { type: 'geojson', data })
          const opacityExpr: ExpressionSpecification = [
            'interpolate',
            ['linear'],
            ['coalesce', ['get', 'norm'], 0],
            0,
            0.38,
            100,
            0.94,
          ]
          map.addLayer({
            id: 'catalog-bubbles',
            type: 'circle',
            source: 'catalog',
            paint: {
              'circle-radius': mapVariant === 'twin' ? TWIN_CIRCLE_RADIUS : EXPLORER_CIRCLE_RADIUS,
              'circle-color': ['get', 'color'],
              'circle-opacity': opacityExpr,
              'circle-stroke-width': mapVariant === 'twin' ? ['case', ['==', ['coalesce', ['get', 'isTop'], 0], 1], 3, 1.5] : 1.5,
              'circle-stroke-color': ['get', 'strokeColor'],
            },
          })
          map.on('click', 'catalog-bubbles', (e) => {
            const f = e.features?.[0]
            const key = f?.properties?.key
            if (typeof key === 'string') on_select_ref.current(key)
          })
          map.on('mouseenter', 'catalog-bubbles', () => {
            map.getCanvas().style.cursor = 'pointer'
          })
          map.on('mouseleave', 'catalog-bubbles', () => {
            map.getCanvas().style.cursor = ''
          })

          if (mapVariant === 'twin') {
            map.addLayer({
              id: 'catalog-match-labels',
              type: 'symbol',
              source: 'catalog',
              layout: {
                'text-field': ['get', 'label'],
                'text-size': 10,
                'text-offset': [0, 1.35],
                'text-anchor': 'top',
                'text-allow-overlap': false,
                'text-ignore-placement': false,
              },
              paint: {
                'text-color': '#1a1a2e',
                'text-halo-color': '#ffffff',
                'text-halo-width': 1.5,
              },
              minzoom: 8,
            })
          }
        } else {
          const src = map.getSource('catalog') as GeoJSONSource
          src.setData(data as Parameters<GeoJSONSource['setData']>[0])
        }

        if (map.getLayer('catalog-bubbles')) {
          const opacityExpr: ExpressionSpecification = [
            'interpolate',
            ['linear'],
            ['coalesce', ['get', 'norm'], 0],
            0,
            0.38,
            100,
            0.94,
          ]
          map.setPaintProperty(
            'catalog-bubbles',
            'circle-radius',
            mapVariant === 'twin' ? TWIN_CIRCLE_RADIUS : EXPLORER_CIRCLE_RADIUS
          )
          map.setPaintProperty('catalog-bubbles', 'circle-opacity', opacityExpr)
          map.setPaintProperty(
            'catalog-bubbles',
            'circle-stroke-width',
            mapVariant === 'twin' ? ['case', ['==', ['coalesce', ['get', 'isTop'], 0], 1], 3, 1.5] : 1.5
          )
        }

        const hasTwinLabels = map.getLayer('catalog-match-labels')
        if (mapVariant === 'twin' && !hasTwinLabels && map.getSource('catalog')) {
          map.addLayer({
            id: 'catalog-match-labels',
            type: 'symbol',
            source: 'catalog',
            layout: {
              'text-field': ['get', 'label'],
              'text-size': 10,
              'text-offset': [0, 1.35],
              'text-anchor': 'top',
            },
            paint: {
              'text-color': '#1a1a2e',
              'text-halo-color': '#ffffff',
              'text-halo-width': 1.5,
            },
            minzoom: 8,
          })
        }
        if (mapVariant !== 'twin' && hasTwinLabels) {
          map.removeLayer('catalog-match-labels')
        }

        if (twinLineGeoJson && twinLineGeoJson.features.length > 0) {
          if (!map.getSource('twin-line')) {
            map.addSource('twin-line', {
              type: 'geojson',
              data: twinLineGeoJson as Parameters<GeoJSONSource['setData']>[0],
            })
            map.addLayer({
              id: 'twin-line-layer',
              type: 'line',
              source: 'twin-line',
              paint: {
                'line-color': '#6B5CE7',
                'line-width': 2,
                'line-dasharray': [1.2, 1.2],
              },
            })
          } else {
            ;(map.getSource('twin-line') as GeoJSONSource).setData(
              twinLineGeoJson as Parameters<GeoJSONSource['setData']>[0]
            )
          }
        } else if (map.getLayer('twin-line-layer')) {
          map.removeLayer('twin-line-layer')
          if (map.getSource('twin-line')) map.removeSource('twin-line')
        }

        if (fitted_ref.current !== fitKey && data.features.length > 0) {
          fitted_ref.current = fitKey
          const coords = data.features.map((f) => (f.geometry as { coordinates: [number, number] }).coordinates)
          let minLon = Infinity
          let minLat = Infinity
          let maxLon = -Infinity
          let maxLat = -Infinity
          for (const [lon, lat] of coords) {
            minLon = Math.min(minLon, lon)
            minLat = Math.min(minLat, lat)
            maxLon = Math.max(maxLon, lon)
            maxLat = Math.max(maxLat, lat)
          }
          if (Number.isFinite(minLon)) {
            map.fitBounds(
              [
                [minLon, minLat],
                [maxLon, maxLat],
              ],
              { padding: 52, maxZoom: mapVariant === 'twin' ? 12 : 12, duration: 0 }
            )
          }
        }
      } catch {
        // style race
      }
    }
    sync()
  }, [data, map_loaded, indexMode, mapVariant, twinLineGeoJson, fitKey])

  useEffect(() => {
    if (!map_ref.current || !map_loaded) return
    try {
      map_ref.current.resize()
    } catch {
      // ignore
    }
  }, [layoutVersion, map_loaded])

  useEffect(() => {
    if (!map_ref.current || !map_loaded || !selectedKey) return
    const map = map_ref.current
    const f = data.features.find((x) => x.properties?.key === selectedKey)
    if (!f || f.geometry.type !== 'Point') return
    const [lon, lat] = f.geometry.coordinates
    map.easeTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 12.5), duration: 600 })
  }, [selectedKey, data, map_loaded])

  return (
    <div className="relative w-full flex-1 min-h-0" style={{ background: '#e5e7eb' }}>
      <div ref={container_ref} className="absolute inset-0 w-full h-full" />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center z-10 bg-white/90 p-4">
          <p className="text-center text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  )
}
