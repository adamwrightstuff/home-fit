'use client'

import { useState, FormEvent, useEffect, useRef } from 'react'

interface LocationSearchProps {
  onSearch: (location: string) => void
  disabled?: boolean
  examples?: string[]
}

const DEFAULT_EXAMPLES = ['New York, NY', '90210', '1600 Pennsylvania Avenue NW, Washington, DC']

export default function LocationSearch({ onSearch, disabled, examples = DEFAULT_EXAMPLES }: LocationSearchProps) {
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
