'use client'

import { useState } from 'react'

export type PriorityLevel = 'None' | 'Low' | 'Medium' | 'High'

interface PillarPriorities {
  active_outdoors: PriorityLevel
  built_beauty: PriorityLevel
  natural_beauty: PriorityLevel
  neighborhood_amenities: PriorityLevel
  air_travel_access: PriorityLevel
  public_transit_access: PriorityLevel
  healthcare_access: PriorityLevel
  quality_education: PriorityLevel
  housing_value: PriorityLevel
}

interface SearchOptions {
  priorities: PillarPriorities
  include_chains: boolean
  enable_schools: boolean
}

interface SearchOptionsProps {
  options: SearchOptions
  onChange: (options: SearchOptions) => void
  disabled?: boolean
}

const PILLAR_NAMES: Record<keyof PillarPriorities, string> = {
  active_outdoors: 'Active Outdoors',
  built_beauty: 'Built Beauty',
  natural_beauty: 'Natural Beauty',
  neighborhood_amenities: 'Neighborhood Amenities',
  air_travel_access: 'Air Travel Access',
  public_transit_access: 'Public Transit Access',
  healthcare_access: 'Healthcare Access',
  quality_education: 'Quality Education',
  housing_value: 'Housing Value',
}

const PRIORITY_LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']

const DEFAULT_PRIORITIES: PillarPriorities = {
  active_outdoors: 'Medium',
  built_beauty: 'Medium',
  natural_beauty: 'Medium',
  neighborhood_amenities: 'Medium',
  air_travel_access: 'Medium',
  public_transit_access: 'Medium',
  healthcare_access: 'Medium',
  quality_education: 'Medium',
  housing_value: 'Medium',
}

function SearchOptionsComponent({ options, onChange, disabled }: SearchOptionsProps) {
  const [expanded, setExpanded] = useState(false)

  const handlePriorityChange = (pillar: keyof PillarPriorities, priority: PriorityLevel) => {
    onChange({
      ...options,
      priorities: {
        ...options.priorities,
        [pillar]: priority,
      },
    })
  }

  const handleIncludeChainsChange = (value: boolean) => {
    onChange({
      ...options,
      include_chains: value,
    })
  }

  const handleEnableSchoolsChange = (value: boolean) => {
    onChange({
      ...options,
      enable_schools: value,
    })
  }

  const handleResetPriorities = () => {
    onChange({
      ...options,
      priorities: { ...DEFAULT_PRIORITIES },
    })
  }

  return (
    <div className="border-t border-gray-200 pt-4 mt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        disabled={disabled}
        className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-700 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span>Advanced Options</span>
        <svg
          className={`w-5 h-5 transition-transform ${expanded ? 'transform rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-4 space-y-4">
          {/* Checkboxes */}
          <div className="flex flex-col sm:flex-row gap-4">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={options.include_chains}
                onChange={(e) => handleIncludeChainsChange(e.target.checked)}
                disabled={disabled}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Include chain businesses</span>
            </label>

            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={options.enable_schools}
                onChange={(e) => handleEnableSchoolsChange(e.target.checked)}
                disabled={disabled}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">Enable school scoring</span>
            </label>
          </div>

          {/* Priorities Section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">Pillar Priorities</h3>
              <button
                onClick={handleResetPriorities}
                disabled={disabled}
                className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reset to Default
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Set priority levels for each pillar. Higher priorities receive more weight in the total score.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {(Object.keys(PILLAR_NAMES) as Array<keyof PillarPriorities>).map((pillar) => (
                <div key={pillar} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <label className="text-xs font-medium text-gray-700 flex-1">
                    {PILLAR_NAMES[pillar]}
                  </label>
                  <select
                    value={options.priorities[pillar]}
                    onChange={(e) => handlePriorityChange(pillar, e.target.value as PriorityLevel)}
                    disabled={disabled}
                    className="ml-2 text-xs border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {PRIORITY_LEVELS.map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export { DEFAULT_PRIORITIES }
export type { PillarPriorities, SearchOptions }
export default SearchOptionsComponent

