'use client'

import { useEffect, useRef, useState } from 'react'

// Import MapLibre GL CSS - must be done client-side
if (typeof window !== 'undefined') {
  try {
    require('maplibre-gl/dist/maplibre-gl.css')
  } catch (e) {
    console.warn('Could not load MapLibre CSS:', e)
  }
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
  const [init_error, set_init_error] = useState<string | null>(null)

  useEffect(() => {
    // Only run on client
    if (typeof window === 'undefined') return
    
    if (!map_container_ref.current) {
      console.log('InteractiveMap: Waiting for container ref...')
      return
    }
    
    if (map_loaded || map) {
      console.log('InteractiveMap: Map already loaded, skipping init')
      return
    }

    console.log('InteractiveMap: Initializing map...')
    console.log('InteractiveMap: Container element:', map_container_ref.current)
    console.log('InteractiveMap: Container dimensions:', {
      width: map_container_ref.current.offsetWidth,
      height: map_container_ref.current.offsetHeight,
      clientWidth: map_container_ref.current.clientWidth,
      clientHeight: map_container_ref.current.clientHeight
    })

    let is_mounted = true

    const loadMapLibre = async () => {
      try {
        // Dynamic import for MapLibre GL
        const maplibreModule = await import('maplibre-gl')
        const maplibregl = maplibreModule.default || maplibreModule
        
        if (!is_mounted || !map_container_ref.current) {
          console.log('InteractiveMap: Component unmounted or container gone')
          return
        }
        
        console.log('InteractiveMap: MapLibre GL loaded successfully')
        
        // Wait a moment to ensure container is ready
        await new Promise(resolve => setTimeout(resolve, 50))
        
        if (!map_container_ref.current) {
          console.error('InteractiveMap: Container ref lost after delay')
          return
        }

        // MapTiler free tier
        const maptiler_key = process.env.NEXT_PUBLIC_MAPTILER_KEY || 'get_your_own_OpIi9ZULNHzrESv6T2vL'
        const map_style = `https://api.maptiler.com/maps/streets-v2/style.json?key=${maptiler_key}`

        console.log('InteractiveMap: Creating map instance')
        console.log('InteractiveMap: Style URL:', map_style)
        console.log('InteractiveMap: Coordinates:', coordinates)
        
        const new_map = new maplibregl.Map({
          container: map_container_ref.current,
          style: map_style,
          center: coordinates ? [coordinates.lon, coordinates.lat] : [0, 0],
          zoom: coordinates ? 12 : 2
        })

        new_map.on('load', () => {
          if (!is_mounted) return
          console.log('InteractiveMap: Map load event fired')
          if (new_map.isStyleLoaded()) {
            console.log('InteractiveMap: Style already loaded')
            set_map_loaded(true)
            set_map(new_map)
          } else {
            console.log('InteractiveMap: Waiting for style.load event')
            new_map.once('style.load', () => {
              if (!is_mounted) return
              console.log('InteractiveMap: Style.load event fired')
              set_map_loaded(true)
              set_map(new_map)
            })
          }
        })

        new_map.on('error', (e: any) => {
          console.error('InteractiveMap: Map error:', e)
          if (e.error) {
            set_init_error(e.error.message || 'Map initialization error')
          }
        })

        new_map.on('styledata', () => {
          console.log('InteractiveMap: Style data loaded')
        })

        // Set map immediately so we can use it
        set_map(new_map)
        console.log('InteractiveMap: Map instance created')
        
      } catch (e: any) {
        console.error('InteractiveMap: Error loading MapLibre:', e)
        set_init_error(e.message || 'Failed to load map library')
      }
    }

    loadMapLibre()

    return () => {
      is_mounted = false
      console.log('InteractiveMap: Cleanup - removing map')
      if (map) {
        try {
          map.remove()
        } catch (e) {
          console.warn('InteractiveMap: Error removing map:', e)
        }
        set_map(null)
        set_map_loaded(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run once on mount

  // Update map when coordinates change
  useEffect(() => {
    if (!map || !coordinates || !map_loaded) return

    const updateMap = () => {
      if (!map.isStyleLoaded()) {
        map.once('style.load', updateMap)
        return
      }

      try {
        console.log('InteractiveMap: Updating map center to:', coordinates)
        map.flyTo({
          center: [coordinates.lon, coordinates.lat],
          zoom: 12,
          duration: 1000
        })

        // Add or update marker
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
        if (error instanceof Error && error.message.includes('not done loading')) {
          console.log('InteractiveMap: Style not ready, waiting...')
          map.once('style.load', updateMap)
        } else {
          console.warn('InteractiveMap: Error updating map:', error)
        }
      }
    }

    updateMap()
  }, [map, coordinates, location, completed_pillars, map_loaded])

  return (
    <div 
      className="w-full h-full relative" 
      style={{ 
        minHeight: '100vh', 
        height: '100vh',
        width: '100%',
        position: 'relative'
      }}
    >
      <div 
        ref={map_container_ref} 
        className="w-full h-full" 
        style={{ 
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: '100%',
          height: '100%'
        }}
      />
      {init_error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
          <div className="text-center p-4">
            <div className="text-red-600 font-semibold mb-2">Map Error</div>
            <div className="text-sm text-gray-600">{init_error}</div>
          </div>
        </div>
      )}
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
