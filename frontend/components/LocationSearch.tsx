'use client'

import { useState, FormEvent, useEffect, useRef } from 'react'

interface LocationSearchProps {
  onSearch: (location: string) => void
  disabled?: boolean
}

export default function LocationSearch({ onSearch, disabled }: LocationSearchProps) {
  const [location, setLocation] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Autofocus on mount
    if (inputRef.current && !disabled) {
      inputRef.current.focus()
    }
  }, [disabled])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (location.trim() && !disabled) {
      onSearch(location.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-3">
        <input
          ref={inputRef}
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Enter an address or ZIP code (e.g., 123 Main St, New York, NY)"
          className="flex-1 px-4 py-3.5 border-2 border-gray-400 rounded-lg focus:outline-none focus:ring-2 focus:ring-homefit-accent-primary focus:border-homefit-accent-primary text-homefit-text-primary text-base"
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || !location.trim()}
          className="px-6 py-3.5 bg-homefit-accent-primary text-white rounded-lg font-semibold hover:opacity-90 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-base"
        >
          {disabled ? 'Searching...' : 'Search'}
        </button>
      </div>
      <p className="mt-2 text-xs text-homefit-text-secondary opacity-70">
        Examples: &quot;New York, NY&quot;, &quot;90210&quot;, &quot;1600 Pennsylvania Avenue NW, Washington, DC&quot;
      </p>
    </form>
  )
}
