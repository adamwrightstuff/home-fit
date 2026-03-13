'use client'

import { useState, FormEvent, useEffect, useRef, useCallback } from 'react'

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
  }
  geometry: { type: string; coordinates: [number, number] }
}

interface LocationSuggestion {
  displayName: string
  /** Same string we pass to backend geocode */
  searchQuery: string
}

function buildDisplayName(props: PhotonFeature['properties']): string {
  const { name, city, state, country, street, housenumber, postcode } = props
  const parts: string[] = []
  if (housenumber && street) parts.push(`${housenumber} ${street}`)
  else if (street) parts.push(street)
  else if (name) parts.push(name)
  if (city && city !== name) parts.push(city)
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
      const allowed = features
        .filter((f) => {
          const code = (f.properties.countrycode ?? '').toLowerCase()
          return code && ALLOWED_COUNTRY_CODES.has(code)
        })
        .slice(0, SUGGESTION_LIMIT)
      return allowed.map((f) => {
        const displayName = buildDisplayName(f.properties)
        return { displayName, searchQuery: displayName }
      })
    })
    .catch(() => [])
}

interface LocationSearchProps {
  onSearch: (location: string) => void
  disabled?: boolean
  examples?: string[]
}

const DEFAULT_EXAMPLES = ['New York, NY', '1600 Pennsylvania Avenue NW, Washington, DC']

export default function LocationSearch({ onSearch, disabled, examples = DEFAULT_EXAMPLES }: LocationSearchProps) {
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
    (query: string) => {
      if (!query.trim() || disabled) return
      setSubmitted(false)
      setLocation(query.trim())
      setSuggestionsOpen(false)
      onSearch(query.trim())
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
    runSearch(s.searchQuery)
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
      <div ref={containerRef} style={{ position: 'relative', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 280px' }}>
          <input
            ref={inputRef}
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setSuggestionsOpen(true)}
            placeholder="Enter an address (e.g., 123 Main St, New York, NY)"
            className={`hf-input ${isInvalid ? 'hf-input--invalid' : ''}`}
            disabled={disabled}
            autoComplete="off"
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
          style={{ paddingLeft: '2.25rem', paddingRight: '2.25rem' }}
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
              setSubmitted(false)
              setLocation(ex)
              inputRef.current?.focus()
            }}
          >
            {ex.length > 26 ? `${ex.slice(0, 26)}…` : ex}
          </button>
        ))}
      </div>
    </form>
  )
}
