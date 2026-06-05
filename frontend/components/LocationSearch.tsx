'use client'

import { useState, FormEvent, useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'

const PHOTON_API = 'https://photon.komoot.io/api'
const DEBOUNCE_MS = 350
const MIN_QUERY_LENGTH = 2
const SUGGESTION_LIMIT = 5

/** US + territories; matches data coverage (Census, FEMA, etc.). ISO 3166-1 alpha-2. */
const ALLOWED_COUNTRY_CODES = new Set(['us', 'pr', 'vi', 'gu', 'as', 'mp'])

interface PhotonFeature {
  type: string
  properties: {
    name?: string
    city?: string
    state?: string
    country?: string
    countrycode?: string
    street?: string
    housenumber?: string
    postcode?: string
    district?: string
    locality?: string
    type?: string    // 'house' | 'street' | 'district' | 'city' | 'other'
    osm_key?: string // 'place' | 'leisure' | 'tourism' | 'amenity' | etc.
    osm_value?: string
  }
  geometry: { type: string; coordinates: [number, number] }
}

interface LocationSuggestion {
  displayName: string
  /** Same string we pass to backend geocode */
  searchQuery: string
  /** Pre-built geocode result from Photon — skips Railway geocode entirely when set */
  geo?: { lat: number; lon: number; city: string; state: string; zip_code: string; display_name: string }
}

const _PLACE_PRIORITY: Record<string, number> = { district: 0, city: 1, street: 2, house: 3, other: 4 }

function _placeRank(f: PhotonFeature): number {
  return _PLACE_PRIORITY[f.properties.type ?? 'other'] ?? 4
}

function buildDisplayName(props: PhotonFeature['properties'], cityOverride?: string): string {
  const { name, city: rawCity, state, country, street, housenumber, postcode, type } = props
  const city = cityOverride ?? rawCity
  const parts: string[] = []
  // For place-type results (neighbourhood, suburb, city) use name, not street.
  const isPlace = type === 'district' || type === 'city'
  if (!isPlace && housenumber && street) parts.push(`${housenumber} ${street}`)
  else if (!isPlace && street) parts.push(street)
  else if (name) parts.push(name)
  if (city && city !== name && !city.toLowerCase().includes('township')) parts.push(city)
  if (state && state !== city) parts.push(state)
  if (postcode && !parts.includes(postcode)) parts.push(postcode)
  if (country && country !== 'United States') parts.push(country)
  return parts.filter(Boolean).join(', ')
}

function fetchPhotonSuggestions(query: string): Promise<LocationSuggestion[]> {
  const params = new URLSearchParams({
    q: query.trim(),
    limit: '15', // request extra so after filtering to US/territories we still have up to SUGGESTION_LIMIT
  })
  return fetch(`${PHOTON_API}?${params.toString()}`, { method: 'GET' })
    .then((res) => (res.ok ? res.json() : Promise.resolve({ features: [] })))
    .then((data: { features?: PhotonFeature[] }) => {
      const features = data.features ?? []
      const usFeatures = features.filter((f) => {
        const code = (f.properties.countrycode ?? '').toLowerCase()
        return code && ALLOWED_COUNTRY_CODES.has(code)
      })

      // Build district→city map from non-district results so we can fix township city names
      // e.g. Photon labels Lincoln Park's district result city as "North Chicago Township"
      // but house/other results in the same batch correctly have city="Chicago".
      const districtCityMap: Record<string, string> = {}
      for (const f of usFeatures) {
        const { district, city, type } = f.properties
        if (district && city && type !== 'district' && !city.toLowerCase().includes('township')) {
          districtCityMap[district.toLowerCase()] = city
        }
      }

      const sorted = [...usFeatures].sort((a, b) => _placeRank(a) - _placeRank(b))

      return sorted.slice(0, SUGGESTION_LIMIT).map((f) => {
        const { name, type, state, postcode } = f.properties
        const cityOverride =
          type === 'district' && name ? districtCityMap[name.toLowerCase()] : undefined
        const displayName = buildDisplayName(f.properties, cityOverride)
        const [lon, lat] = f.geometry.coordinates
        const city = cityOverride ?? (f.properties.city ?? '')
        const geo = Number.isFinite(lat) && Number.isFinite(lon) ? {
          lat, lon,
          city,
          state: state ?? '',
          zip_code: postcode ?? '',
          display_name: displayName,
        } : undefined
        return { displayName, searchQuery: displayName, geo }
      })
    })
    .catch(() => [])
}

interface LocationSearchProps {
  onSearch: (location: string, geo?: LocationSuggestion['geo']) => void
  disabled?: boolean
  examples?: string[]
  catalogLink?: string
}

const DEFAULT_EXAMPLES = ['New York, NY', '1600 Pennsylvania Avenue NW, Washington, DC']

export default function LocationSearch({ onSearch, disabled, examples = DEFAULT_EXAMPLES, catalogLink }: LocationSearchProps) {
  const [location, setLocation] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([])
  const [suggestionsOpen, setSuggestionsOpen] = useState(false)
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (inputRef.current && !disabled) {
      inputRef.current.focus()
    }
  }, [disabled])

  const runSearch = useCallback(
    (query: string, geo?: LocationSuggestion['geo']) => {
      if (!query.trim() || disabled) return
      setSubmitted(false)
      setLocation(query.trim())
      setSuggestionsOpen(false)
      onSearch(query.trim(), geo)
    },
    [disabled, onSearch]
  )

  useEffect(() => {
    const q = location.trim()
    if (q.length < MIN_QUERY_LENGTH) {
      setSuggestions([])
      setSuggestionsOpen(false)
      setSuggestionsLoading(false)
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
      return
    }

    if (debounceRef.current) clearTimeout(debounceRef.current)
    setSuggestionsLoading(true)
    setSuggestionsOpen(true)
    setActiveIndex(-1)

    debounceRef.current = setTimeout(() => {
      debounceRef.current = null
      fetchPhotonSuggestions(q).then((list) => {
        setSuggestions(list)
        setSuggestionsLoading(false)
        setActiveIndex(-1)
      })
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [location])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (location.trim() && !disabled) {
      setSuggestionsOpen(false)
      onSearch(location.trim())
    }
  }

  const handleSelectSuggestion = (s: LocationSuggestion) => {
    setLocation(s.searchQuery)
    setSuggestionsOpen(false)
    setActiveIndex(-1)
    inputRef.current?.focus()
    runSearch(s.searchQuery, s.geo)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!suggestionsOpen || suggestions.length === 0) {
      if (e.key === 'Escape') setSuggestionsOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => (i <= 0 ? suggestions.length - 1 : i - 1))
    } else if (e.key === 'Enter' && activeIndex >= 0 && suggestions[activeIndex]) {
      e.preventDefault()
      handleSelectSuggestion(suggestions[activeIndex])
    } else if (e.key === 'Escape') {
      setSuggestionsOpen(false)
      setActiveIndex(-1)
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setSuggestionsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isInvalid = submitted && !location.trim()

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div ref={containerRef} className="hf-search-input-row" style={{ position: 'relative', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 auto', minWidth: 0 }}>
          <input
            ref={inputRef}
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (suggestions.length > 0) setSuggestionsOpen(true)
              if (typeof window !== 'undefined' && window.innerWidth <= 768) {
                setTimeout(() => inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 350)
              }
            }}
            placeholder="Neighborhood, city, or address…"
            className={`hf-input ${isInvalid ? 'hf-input--invalid' : ''}`}
            disabled={disabled}
            autoComplete="off"
            inputMode="search"
            aria-label="Search for a place"
            aria-autocomplete="list"
            aria-haspopup="listbox"
            aria-expanded={suggestionsOpen && suggestions.length > 0}
            aria-controls="location-suggestions"
            aria-activedescendant={activeIndex >= 0 ? `location-suggestion-${activeIndex}` : undefined}
            role="combobox"
            data-testid="location-search-input"
          />
          {suggestionsOpen && (suggestions.length > 0 || suggestionsLoading) && (
            <ul
              id="location-suggestions"
              className="hf-location-suggestions"
              role="listbox"
              style={{ margin: 0, padding: 0, listStyle: 'none' }}
            >
              {suggestionsLoading && suggestions.length === 0 ? (
                <li className="hf-location-suggestion hf-location-suggestion--muted" role="option" aria-selected="false">
                  Searching…
                </li>
              ) : (
                suggestions.map((s, i) => (
                  <li
                    key={`${s.searchQuery}-${i}`}
                    id={`location-suggestion-${i}`}
                    role="option"
                    aria-selected={i === activeIndex ? 'true' : 'false'}
                    className={`hf-location-suggestion ${i === activeIndex ? 'hf-location-suggestion--active' : ''}`}
                    data-testid="location-suggestion"
                    onMouseEnter={() => setActiveIndex(i)}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      handleSelectSuggestion(s)
                    }}
                  >
                    {s.displayName}
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
        <button
          type="submit"
          disabled={disabled || !location.trim()}
          className="hf-btn-primary"
        >
          {disabled ? 'Searching...' : 'Search'}
        </button>
      </div>
      {isInvalid ? (
        <div className="hf-helper" style={{ color: 'var(--hf-danger)' }}>
          Please enter a location (city/state or address).
        </div>
      ) : null}
      <div className="hf-chip-row" aria-label="Search examples">
        <span className="hf-helper" style={{ marginTop: 0 }}>
          Try:
        </span>
        {examples.map((ex) => (
          <button
            key={ex}
            type="button"
            className="hf-chip"
            onClick={() => {
              onSearch(ex)
            }}
          >
            {ex.length > 26 ? `${ex.slice(0, 26)}…` : ex}
          </button>
        ))}
        {catalogLink && (
          <Link href={catalogLink} className="hf-chip--ghost">
            browse the catalog →
          </Link>
        )}
      </div>
    </form>
  )
}
