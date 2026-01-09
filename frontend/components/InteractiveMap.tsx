'use client'

import { useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'

interface InteractiveMapProps {
  location: string
  coordinates?: { lat: number; lon: number } | null
  completed_pillars: string[]
}

// Load MapLibre CSS
if (typeof window !== 'undefined') {
  import('maplibre-gl/dist/maplibre-gl.css').catch(() => {
    console.warn('Could not load MapLibre CSS')
  })
}

export default function InteractiveMap({ location, coordinates, completed_pillars }: InteractiveMapProps) {
  const map_container_ref = useRef<HTMLDivElement>(null)
  const map_ref = useRef<any>(null)
  const [map_loaded, set_map_loaded] = useState(false)
  const [init_error, set_init_error] = useState<string | null>(null)
  const [is_initializing, set_is_initializing] = useState(false)

  useEffect(() => {
    // Only run on client
    if (typeof window === 'undefined') return
    
    // Prevent multiple initializations
    if (is_initializing || map_loaded || map_ref.current) {
      return
    }

    if (!map_container_ref.current) {
      console.log('InteractiveMap: Waiting for container ref...')
      return
    }

    const container = map_container_ref.current
    const containerWidth = container.offsetWidth || container.clientWidth
    const containerHeight = container.offsetHeight || container.clientHeight

    console.log('InteractiveMap: Initializing map...')
    console.log('InteractiveMap: Container dimensions:', {
      width: containerWidth,
      height: containerHeight,
      offsetWidth: container.offsetWidth,
      offsetHeight: container.offsetHeight,
      clientWidth: container.clientWidth,
      clientHeight: container.clientHeight
    })

    // Check if container has dimensions
    if (containerWidth === 0 || containerHeight === 0) {
      console.warn('InteractiveMap: Container has zero dimensions, waiting...')
      // Retry after a short delay
      const retryTimer = setTimeout(() => {
        if (container.offsetWidth > 0 && container.offsetHeight > 0) {
          set_is_initializing(true)
          initializeMap()
        }
      }, 500)
      return () => clearTimeout(retryTimer)
    }

    set_is_initializing(true)
    initializeMap()

    async function initializeMap() {
      try {
        console.log('InteractiveMap: Loading MapLibre GL...')
        
        // Dynamic import for MapLibre GL
        const maplibreModule = await import('maplibre-gl')
        const maplibregl = maplibreModule.default || maplibreModule
        
        if (!map_container_ref.current) {
          console.error('InteractiveMap: Container ref lost during import')
          set_init_error('Container not available')
          set_is_initializing(false)
          return
        }
        
        console.log('InteractiveMap: MapLibre GL loaded successfully')
        console.log('InteractiveMap: MapLibre version:', maplibregl.version || 'unknown')

        // Use OpenStreetMap tiles (free, no API key required)
        // Alternative: Use MapTiler if API key is provided
        const maptiler_key = process.env.NEXT_PUBLIC_MAPTILER_KEY
        let map_style: string
        
        if (maptiler_key && maptiler_key !== 'get_your_own_OpIi9ZULNHzrESv6T2vL') {
          // Use MapTiler if valid key is provided
          map_style = `https://api.maptiler.com/maps/streets-v2/style.json?key=${maptiler_key}`
        } else {
          // Use OpenStreetMap style (free, no API key needed)
          map_style = {
            version: 8,
            sources: {
              'osm-tiles': {
                type: 'raster',
                tiles: [
                  'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
                ],
                tileSize: 256,
                attribution: '© OpenStreetMap contributors'
              }
            },
            layers: [
              {
                id: 'osm-tiles',
                type: 'raster',
                source: 'osm-tiles',
                minzoom: 0,
                maxzoom: 19
              }
            ]
          } as any
        }

        console.log('InteractiveMap: Creating map instance')
        console.log('InteractiveMap: Using style:', typeof map_style === 'string' ? map_style : 'OpenStreetMap')
        console.log('InteractiveMap: Coordinates:', coordinates)
        console.log('InteractiveMap: Container:', map_container_ref.current)
        
        const new_map = new maplibregl.Map({
          container: map_container_ref.current,
          style: map_style,
          center: coordinates ? [coordinates.lon, coordinates.lat] : [0, 0],
          zoom: coordinates ? 12 : 2
        })

        new_map.on('load', () => {
          console.log('InteractiveMap: Map load event fired')
          set_map_loaded(true)
          map_ref.current = new_map
          set_is_initializing(false)
        })

        new_map.on('error', (e: any) => {
          console.error('InteractiveMap: Map error:', e)
          const errorMsg = e.error?.message || e.message || 'Map initialization error'
          set_init_error(errorMsg)
          set_is_initializing(false)
        })

        new_map.on('styledata', () => {
          console.log('InteractiveMap: Style data loaded')
        })

        new_map.on('data', () => {
          console.log('InteractiveMap: Map data event')
        })

        // Set map reference immediately
        map_ref.current = new_map
        console.log('InteractiveMap: Map instance created')
        
      } catch (e: any) {
        console.error('InteractiveMap: Error loading MapLibre:', e)
        set_init_error(e.message || 'Failed to load map library')
        set_is_initializing(false)
      }
    }

    return () => {
      console.log('InteractiveMap: Cleanup - removing map')
      if (map_ref.current) {
        try {
          map_ref.current.remove()
        } catch (e) {
          console.warn('InteractiveMap: Error removing map:', e)
        }
        map_ref.current = null
        set_map_loaded(false)
        set_is_initializing(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run once on mount

  // Update map when coordinates change
  useEffect(() => {
    if (!map_ref.current || !coordinates || !map_loaded) return

    const updateMap = () => {
      if (!map_ref.current) return
      
      if (!map_ref.current.isStyleLoaded()) {
        map_ref.current.once('style.load', updateMap)
        return
      }

      try {
        console.log('InteractiveMap: Updating map center to:', coordinates)
        map_ref.current.flyTo({
          center: [coordinates.lon, coordinates.lat],
          zoom: 12,
          duration: 1000
        })

        // Add or update marker
        if (!map_ref.current.getSource('location')) {
          map_ref.current.addSource('location', {
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

          map_ref.current.addLayer({
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

          map_ref.current.addLayer({
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
          const source = map_ref.current.getSource('location') as any
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
          map_ref.current.once('style.load', updateMap)
        } else {
          console.warn('InteractiveMap: Error updating map:', error)
        }
      }
    }

    updateMap()
  }, [coordinates, location, completed_pillars, map_loaded])

  return (
    <div 
      className="w-full h-full relative" 
      style={{ 
        height: '100vh',
        width: '100%',
        position: 'relative',
        backgroundColor: '#f3f4f6' // Light gray background while loading
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
      {is_initializing && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 bg-opacity-75 z-10">
          <div className="text-center p-4">
            <div className="text-gray-600 font-semibold mb-2">Loading map...</div>
            <div className="text-xs text-gray-500">Initializing MapLibre GL</div>
          </div>
        </div>
      )}
      {init_error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
          <div className="text-center p-4">
            <div className="text-red-600 font-semibold mb-2">Map Error</div>
            <div className="text-sm text-gray-600">{init_error}</div>
            <div className="text-xs text-gray-500 mt-2">Check browser console for details</div>
          </div>
        </div>
      )}
      {coordinates && map_loaded && (
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
