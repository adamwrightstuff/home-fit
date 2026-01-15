'use client'

import { useState, FormEvent, useEffect, useRef } from 'react'

interface LocationSearchProps {
  onSearch: (location: string) => void
  disabled?: boolean
}

export default function LocationSearch({ onSearch, disabled }: LocationSearchProps) {
  const [location, setLocation] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Autofocus on mount
    if (inputRef.current && !disabled) {
      inputRef.current.focus()
    }
  }, [disabled])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (location.trim() && !disabled) {
      onSearch(location.trim())
    }
  }

  const isInvalid = submitted && !location.trim()

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <input
          ref={inputRef}
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Enter an address or ZIP code (e.g., 123 Main St, New York, NY)"
          className={`hf-input ${isInvalid ? 'hf-input--invalid' : ''}`}
          disabled={disabled}
        />
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
          Please enter a location (city/state, ZIP code, or address).
        </div>
      ) : null}
      <p className="hf-helper">
        Examples: &quot;New York, NY&quot;, &quot;90210&quot;, &quot;1600 Pennsylvania Avenue NW, Washington, DC&quot;
      </p>
    </form>
  )
}
