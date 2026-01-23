'use client'

import { useEffect, useRef, useState } from 'react'

interface InteractiveMapProps {
  location: string
  coordinates?: { lat: number; lon: number } | null
  completed_pillars: string[]
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

        // ALWAYS use OpenStreetMap tiles (free, no API key required)
        // MapTiler requires a valid paid API key, so we'll use OSM by default
        console.log('InteractiveMap: Using OpenStreetMap tiles (free, no API key required)')
        // Define style with explicit type to satisfy MapLibre's StyleSpecification
        // Using type assertion to ensure version is literal type 8
        const map_style = {
          version: 8 as const,
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
        }

        console.log('InteractiveMap: Creating map instance')
        console.log('InteractiveMap: Using OpenStreetMap style')
        console.log('InteractiveMap: Coordinates:', coordinates)
        console.log('InteractiveMap: Container:', map_container_ref.current)
        
        const new_map = new maplibregl.Map({
          container: map_container_ref.current,
          // @ts-ignore - MapLibre type definitions are strict about version literal type
          style: map_style,
          center: coordinates ? [coordinates.lon, coordinates.lat] : [-98, 39], // Center of continental US
          zoom: coordinates ? 12 : 4 // Slightly zoomed in to show US better
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
  }, []) // Only run once on mount - map_ref is stable

  // Keep the map sized correctly when its container changes (mobile Safari / flex layout)
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!map_ref.current) return
    if (!map_container_ref.current) return

    const map = map_ref.current

    const safeResize = () => {
      try {
        map.resize()
      } catch {
        // ignore resize errors during initialization/teardown
      }
    }

    window.addEventListener('resize', safeResize)
    safeResize()

    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => safeResize())
      ro.observe(map_container_ref.current)
    }

    return () => {
      window.removeEventListener('resize', safeResize)
      ro?.disconnect()
    }
  }, [map_loaded])

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
              'circle-color': '#667eea',
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
        height: '100%',
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
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'rgba(248,249,250,0.85)' }}>
          <div className="hf-panel" style={{ maxWidth: 320, textAlign: 'center' }}>
            <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', marginBottom: '0.25rem' }}>Loading map…</div>
            <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
              Initializing MapLibre GL
            </div>
          </div>
        </div>
      )}
      {init_error && (
        <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'rgba(248,249,250,0.92)' }}>
          <div className="hf-error" style={{ maxWidth: 420 }}>
            <div style={{ fontWeight: 800, marginBottom: '0.35rem' }}>Map error</div>
            <div style={{ marginBottom: '0.5rem' }}>{init_error}</div>
            <div style={{ fontSize: '0.9rem', opacity: 0.9 }}>Check the browser console for details.</div>
          </div>
        </div>
      )}
      {coordinates && map_loaded && (
        <div className="absolute top-4 left-4 z-10 hf-panel" style={{ padding: '0.85rem 1rem' }}>
          <div style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--hf-text-primary)' }}>{location}</div>
          <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.25rem' }}>
            {coordinates.lat.toFixed(4)}, {coordinates.lon.toFixed(4)}
          </div>
          {completed_pillars.length > 0 && (
            <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.35rem', fontWeight: 700 }}>
              {completed_pillars.length}/9 pillars complete
            </div>
          )}
        </div>
      )}
    </div>
  )
}
