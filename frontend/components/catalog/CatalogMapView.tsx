'use client'

import { useEffect, useRef, useState } from 'react'
import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

type GeoJsonData = ReturnType<typeof import('@/lib/catalogMapGeo').buildCatalogFeatureCollection>

interface CatalogMapViewProps {
  data: GeoJsonData
  selectedKey: string | null
  onSelectKey: (key: string | null) => void
  /** Bumps map.resize when the bottom sheet snaps. */
  layoutVersion: number
  /** Active index — bubble stroke uses this ramp (ramp-600 @ 60%). */
  indexMode: CatalogMapIndexMode
}

const NYC_METRO_BOUNDS: [[number, number], [number, number]] = [
  [-74.35, 40.45],
  [-73.65, 41.05],
]

export default function CatalogMapView({
  data,
  selectedKey,
  onSelectKey,
  layoutVersion,
  indexMode,
}: CatalogMapViewProps) {
  const container_ref = useRef<HTMLDivElement>(null)
  const map_ref = useRef<MapLibreMap | null>(null)
  const on_select_ref = useRef(onSelectKey)
  on_select_ref.current = onSelectKey
  const [map_loaded, set_map_loaded] = useState(false)
  const [error, set_error] = useState<string | null>(null)
  const fitted_ref = useRef(false)

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

        const map = new maplibregl.Map({
          container: container_ref.current,
          style,
          bounds: NYC_METRO_BOUNDS,
          fitBoundsOptions: { padding: 24, maxZoom: 11 },
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
  }, [])

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
          map.addLayer({
            id: 'catalog-bubbles',
            type: 'circle',
            source: 'catalog',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 4, 12, 11, 14, 16],
              'circle-color': ['get', 'color'],
              'circle-opacity': 0.92,
              'circle-stroke-width': 1.5,
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
        } else {
          const src = map.getSource('catalog') as GeoJSONSource
          src.setData(data as Parameters<GeoJSONSource['setData']>[0])
        }

        if (map.getLayer('catalog-bubbles')) {
          map.setPaintProperty('catalog-bubbles', 'circle-stroke-width', 1.5)
        }

        if (!fitted_ref.current && data.features.length > 0) {
          fitted_ref.current = true
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
              { padding: 48, maxZoom: 12, duration: 0 }
            )
          }
        }
      } catch {
        // style race
      }
    }
    sync()
  }, [data, map_loaded, indexMode])

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
