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

    // Check if Mapbox GL is available
    let mapboxgl: any = null
    try {
      mapboxgl = require('mapbox-gl')
      require('mapbox-gl/dist/mapbox-gl.css')
    } catch (e) {
      console.warn('Mapbox GL not available - map will not load')
      return
    }

    const mapbox_token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || ''
    
    if (!mapbox_token) {
      console.warn('MAPBOX_TOKEN not set - map will not load')
      return
    }

    const initialize_map = () => {
      const new_map = new mapboxgl.Map({
        container: map_container_ref.current,
        style: 'mapbox://styles/mapbox/streets-v11',
        center: coordinates ? [coordinates.lon, coordinates.lat] : [0, 0],
        zoom: coordinates ? 12 : 2,
        accessToken: mapbox_token
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

  if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
    return (
      <div className="w-full h-full bg-gray-100 flex items-center justify-center">
        <div className="text-center p-8">
          <p className="text-gray-600 mb-2">Map unavailable</p>
          <p className="text-sm text-gray-500">MAPBOX_TOKEN not configured</p>
          {coordinates && (
            <div className="mt-4 text-sm text-gray-600">
              <p>Location: {location}</p>
              <p>Coordinates: {coordinates.lat.toFixed(4)}, {coordinates.lon.toFixed(4)}</p>
            </div>
          )}
        </div>
      </div>
    )
  }

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
