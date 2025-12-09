'use client'

import { useState, FormEvent } from 'react'

interface LocationSearchProps {
  onSearch: (location: string) => void
  disabled?: boolean
}

export default function LocationSearch({ onSearch, disabled }: LocationSearchProps) {
  const [location, setLocation] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (location.trim() && !disabled) {
      onSearch(location.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-2">
        <input
          type="text"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Enter an address or ZIP code (e.g., 123 Main St, New York, NY)"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || !location.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {disabled ? 'Searching...' : 'Search'}
        </button>
      </div>
      <p className="mt-2 text-sm text-gray-500">
        Examples: "New York, NY", "90210", "1600 Pennsylvania Avenue NW, Washington, DC"
      </p>
    </form>
  )
}
