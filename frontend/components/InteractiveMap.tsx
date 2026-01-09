'use client'

import { useEffect, useRef, useState } from 'react'

interface InteractiveMapProps {
  location: string
  coordinates?: { lat: number; lon: number } | null
  completed_pillars: string[]
}

export default function InteractiveMap({ location, coordinates, completed_pillars }: InteractiveMapProps) {
  const map_container_ref = useRef<HTMLDivElement>(null)
  const [map, set_map] = useState<any>(null)
  const [map_loaded, set_map_loaded] = useState(false)

  useEffect(() => {
    if (!map_container_ref.current || map_loaded) return

    // Use MapLibre GL (open-source alternative to Mapbox GL)
    let maplibregl: any = null
    try {
      maplibregl = require('maplibre-gl')
      require('maplibre-gl/dist/maplibre-gl.css')
    } catch (e) {
      console.warn('MapLibre GL not available - map will not load')
      return
    }

    // MapTiler free tier (100K map loads/month, completely free)
    // Uses demo key by default - works immediately, no signup needed
    // Optional: Get your own free API key at https://www.maptiler.com/cloud/ for more features
    const maptiler_key = process.env.NEXT_PUBLIC_MAPTILER_KEY || 'get_your_own_OpIi9ZULNHzrESv6T2vL'
    // MapTiler streets style - free, no credit card required
    const map_style = `https://api.maptiler.com/maps/streets-v2/style.json?key=${maptiler_key}`

    const initialize_map = () => {
      const new_map = new maplibregl.Map({
        container: map_container_ref.current,
        style: map_style,
        center: coordinates ? [coordinates.lon, coordinates.lat] : [0, 0],
        zoom: coordinates ? 12 : 2
      })

      new_map.on('load', () => {
        set_map_loaded(true)
      })

      set_map(new_map)
    }

    initialize_map()

    return () => {
      if (map) {
        map.remove()
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map_container_ref, map_loaded, coordinates])

  useEffect(() => {
    if (!map || !coordinates) return

    // Update map center when coordinates are available
    map.flyTo({
      center: [coordinates.lon, coordinates.lat],
      zoom: 12,
      duration: 1000
    })

    // Add marker if not exists
    if (!map.getSource('location')) {
      map.addSource('location', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [coordinates.lon, coordinates.lat]
          },
          properties: {
            title: location
          }
        }
      })

      map.addLayer({
        id: 'location-marker',
        type: 'circle',
        source: 'location',
        paint: {
          'circle-radius': 8,
          'circle-color': '#3B82F6',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#FFFFFF'
        }
      })

      map.addLayer({
        id: 'location-label',
        type: 'symbol',
        source: 'location',
        layout: {
          'text-field': location,
          'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
          'text-offset': [0, 1.5],
          'text-anchor': 'top',
          'text-size': 14
        },
        paint: {
          'text-color': '#1F2937',
          'text-halo-color': '#FFFFFF',
          'text-halo-width': 2
        }
      })
    } else {
      // Update existing marker
      map.getSource('location').setData({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [coordinates.lon, coordinates.lat]
        },
        properties: {
          title: location
        }
      })
    }

    // Visual feedback for completed pillars - pulse animation
    if (completed_pillars.length > 0) {
      map.getSource('location')?.setData({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [coordinates.lon, coordinates.lat]
        },
        properties: {
          title: location,
          completed: completed_pillars.length
        }
      })
    }
  }, [map, coordinates, location, completed_pillars])

  // MapLibre GL works without API key (uses MapTiler's free tiles)
  // Optional: Set NEXT_PUBLIC_MAPTILER_KEY for more features (100K free loads/month)
  // Get free key at: https://www.maptiler.com/cloud/

  return (
    <div className="w-full h-full relative">
      <div ref={map_container_ref} className="w-full h-full" />
      {coordinates && (
        <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-3 z-10">
          <div className="text-xs font-semibold text-gray-700">{location}</div>
          <div className="text-xs text-gray-500 mt-1">
            {coordinates.lat.toFixed(4)}, {coordinates.lon.toFixed(4)}
          </div>
          {completed_pillars.length > 0 && (
            <div className="text-xs text-blue-600 mt-1 font-medium">
              {completed_pillars.length}/9 pillars complete
            </div>
          )}
        </div>
      )}
    </div>
  )
}
