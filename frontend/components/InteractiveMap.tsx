'use client'

import { useEffect, useRef, useState } from 'react'

// Import MapLibre GL CSS
if (typeof window !== 'undefined') {
  require('maplibre-gl/dist/maplibre-gl.css')
}

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
    if (!map_container_ref.current || map_loaded) {
      console.log('InteractiveMap: Skipping init - container:', !!map_container_ref.current, 'loaded:', map_loaded)
      return
    }

    console.log('InteractiveMap: Initializing map...')

    // Dynamically import MapLibre GL (works better with Next.js)
    let maplibregl: any = null
    
    const loadMapLibre = async () => {
      try {
        const maplibreModule = await import('maplibre-gl')
        maplibregl = maplibreModule.default || maplibreModule
        console.log('InteractiveMap: MapLibre GL loaded successfully', maplibregl)
        
        // Wait a tick to ensure container is ready
        await new Promise(resolve => setTimeout(resolve, 100))
        
        // Initialize map after library is loaded
        initializeMapWithLib(maplibregl)
      } catch (e) {
        console.error('InteractiveMap: MapLibre GL not available:', e)
        return
      }
    }
    
    const initializeMapWithLib = (maplibregl: any) => {
      if (!map_container_ref.current) {
        console.error('InteractiveMap: Container ref is null after load')
        return
      }

      // MapTiler free tier (100K map loads/month, completely free)
      // Uses demo key by default - works immediately, no signup needed
      // Optional: Get your own free API key at https://www.maptiler.com/cloud/ for more features
      const maptiler_key = process.env.NEXT_PUBLIC_MAPTILER_KEY || 'get_your_own_OpIi9ZULNHzrESv6T2vL'
      // MapTiler streets style - free, no credit card required
      const map_style = `https://api.maptiler.com/maps/streets-v2/style.json?key=${maptiler_key}`

      console.log('InteractiveMap: Creating map instance, coordinates:', coordinates)
      console.log('InteractiveMap: Container dimensions:', {
        width: map_container_ref.current.offsetWidth,
        height: map_container_ref.current.offsetHeight
      })
      
      try {
        const new_map = new maplibregl.Map({
          container: map_container_ref.current,
          style: map_style,
          center: coordinates ? [coordinates.lon, coordinates.lat] : [0, 0],
          zoom: coordinates ? 12 : 2
        })

        new_map.on('load', () => {
          console.log('InteractiveMap: Map load event fired')
          // Ensure style is fully loaded
          if (new_map.isStyleLoaded()) {
            console.log('InteractiveMap: Style already loaded')
            set_map_loaded(true)
          } else {
            console.log('InteractiveMap: Waiting for style.load event')
            new_map.once('style.load', () => {
              console.log('InteractiveMap: Style.load event fired')
              set_map_loaded(true)
            })
          }
        })

        new_map.on('error', (e: any) => {
          console.error('InteractiveMap: Map error:', e)
        })

        new_map.on('styledata', () => {
          console.log('InteractiveMap: Style data loaded')
        })

        set_map(new_map)
        console.log('InteractiveMap: Map instance created successfully')
      } catch (error) {
        console.error('InteractiveMap: Error creating map:', error)
      }
    }

    loadMapLibre()

    return () => {
      console.log('InteractiveMap: Cleanup - removing map')
      if (map) {
        map.remove()
        set_map(null)
        set_map_loaded(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map_container_ref, map_loaded])

  useEffect(() => {
    if (!map || !coordinates || !map_loaded) return

    // Wait for map style to fully load before adding sources/layers
    const add_marker = () => {
      // Double-check style is loaded
      if (!map.isStyleLoaded()) {
        map.once('style.load', add_marker)
        return
      }

      try {
        // Update map center when coordinates are available
        map.flyTo({
          center: [coordinates.lon, coordinates.lat],
          zoom: 12,
          duration: 1000
        })

        // Add marker if not exists (only after style is loaded)
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
                title: location,
                completed: completed_pillars.length
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
          const source = map.getSource('location') as any
          if (source && source.setData) {
            source.setData({
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
        }
      } catch (error) {
        // Retry if style wasn't ready
        if (error instanceof Error && error.message.includes('not done loading')) {
          console.log('Map style not ready, waiting...')
          map.once('style.load', add_marker)
        } else {
          console.warn('Error updating map marker:', error)
        }
      }
    }

    add_marker()
  }, [map, coordinates, location, completed_pillars, map_loaded])

  // MapLibre GL works without API key (uses MapTiler's free tiles)
  // Optional: Set NEXT_PUBLIC_MAPTILER_KEY for more features (100K free loads/month)
  // Get free key at: https://www.maptiler.com/cloud/

  return (
    <div className="w-full h-full relative" style={{ minHeight: '100vh', position: 'relative' }}>
      <div 
        ref={map_container_ref} 
        className="w-full h-full" 
        style={{ 
          minHeight: '100vh', 
          width: '100%',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0
        }}
      />
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
