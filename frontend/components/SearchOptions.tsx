'use client'

import { useState, useEffect, useRef } from 'react'
import { Info } from 'lucide-react'

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
  expanded?: boolean
  onExpandedChange?: (expanded: boolean) => void
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

// Session storage key
const STORAGE_KEY = 'homefit_search_options'
const PREMIUM_CODE_KEY = 'homefit_premium_code'

function SearchOptionsComponent({ options, onChange, disabled, expanded: externalExpanded, onExpandedChange }: SearchOptionsProps) {
  const [internalExpanded, setInternalExpanded] = useState(false)
  const [showTooltip, setShowTooltip] = useState<{ type: string | null }>({ type: null })
  const [showSchoolsWaitlist, setShowSchoolsWaitlist] = useState(false)
  const [premiumCode, setPremiumCode] = useState<string>('')
  const [premiumCodeInput, setPremiumCodeInput] = useState<string>('')
  const [premiumCodeMessage, setPremiumCodeMessage] = useState<string>('')
  const waitlistUrl = process.env.NEXT_PUBLIC_WAITLIST_URL || ''
  
  // Use external expanded state if provided, otherwise use internal
  const expanded = externalExpanded !== undefined ? externalExpanded : internalExpanded
  const setExpanded = (value: boolean) => {
    if (externalExpanded !== undefined && onExpandedChange) {
      onExpandedChange(value)
    } else {
      setInternalExpanded(value)
    }
  }

  // Load from session storage on mount - but only on initial mount, never overwrite programmatic changes
  // Use a ref to track if we've already loaded to prevent multiple loads
  const hasLoadedRef = useRef(false)
  
  useEffect(() => {
    // Only load once on initial mount
    if (hasLoadedRef.current) {
      return
    }
    
    try {
      const storedPremiumCode = sessionStorage.getItem(PREMIUM_CODE_KEY)
      if (storedPremiumCode) {
        setPremiumCode(storedPremiumCode)
        setPremiumCodeInput(storedPremiumCode)
      }

      const stored = sessionStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Migration: if schools were previously enabled but no premium code is saved,
        // force schools off (prevents confusing "schools on" state without access).
        const migrated = {
          ...parsed,
          enable_schools: parsed.enable_schools && !storedPremiumCode ? false : parsed.enable_schools,
        }
        onChange({ ...options, ...migrated })
      }
      hasLoadedRef.current = true
    } catch (e) {
      hasLoadedRef.current = true // Mark as loaded even on error to prevent retries
      // Ignore storage errors
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Save to session storage when options change
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(options))
    } catch (e) {
      // Ignore storage errors
    }
  }, [options])

  const handlePriorityChange = (pillar: keyof PillarPriorities, priority: PriorityLevel) => {
    const newOptions = {
      ...options,
      priorities: {
        ...options.priorities,
        [pillar]: priority,
      },
    }
    onChange(newOptions)
  }

  const handleIncludeChainsChange = (value: boolean) => {
    onChange({
      ...options,
      include_chains: value,
    })
  }

  const handleEnableSchoolsChange = (value: boolean) => {
    if (value) {
      // Premium-gated feature: require a saved premium code before enabling.
      if (!premiumCode) {
        setShowSchoolsWaitlist(true)
        setPremiumCodeMessage('Enter a Premium code to enable school scoring.')
        onChange({
          ...options,
          enable_schools: false,
        })
        return
      }

      setShowSchoolsWaitlist(false)
      setPremiumCodeMessage('')
      onChange({
        ...options,
        enable_schools: true,
      })
      return
    }

    setShowSchoolsWaitlist(false)
    setPremiumCodeMessage('')
    onChange({
      ...options,
      enable_schools: false,
    })
  }

  const handleSavePremiumCode = () => {
    const cleaned = premiumCodeInput.trim()
    if (!cleaned) {
      setPremiumCode('')
      setPremiumCodeMessage('Please enter a code.')
      try {
        sessionStorage.removeItem(PREMIUM_CODE_KEY)
      } catch {
        // ignore
      }
      return
    }

    setPremiumCode(cleaned)
    setPremiumCodeInput(cleaned)
    setPremiumCodeMessage('Code saved. You can now enable school scoring.')
    try {
      sessionStorage.setItem(PREMIUM_CODE_KEY, cleaned)
    } catch {
      // ignore
    }
  }

  const handleClearPremiumCode = () => {
    setPremiumCode('')
    setPremiumCodeInput('')
    setPremiumCodeMessage('Code cleared.')
    try {
      sessionStorage.removeItem(PREMIUM_CODE_KEY)
    } catch {
      // ignore
    }
    // If schools were enabled, turn them off.
    if (options.enable_schools) {
      onChange({ ...options, enable_schools: false })
    }
  }

  const handleResetPriorities = () => {
    onChange({
      ...options,
      priorities: { ...DEFAULT_PRIORITIES },
    })
  }

  return (
    <div className="border-t border-gray-200 pt-6 mt-6">
      <button
        onClick={() => setExpanded(!expanded)}
        disabled={disabled}
        className="flex items-center justify-between w-full text-left text-sm font-semibold text-homefit-text-primary hover:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-homefit-accent-primary focus:ring-offset-2 rounded px-2 -mx-2"
      >
        <span>Customize your score</span>
        <svg
          className={`w-5 h-5 transition-transform duration-200 ${expanded ? 'transform rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-4 space-y-6 bg-gray-50 -mx-2 px-4 py-4 rounded-lg">
          {/* Scoring Inputs Section */}
          <div>
            <h4 className="text-xs font-semibold text-homefit-text-primary uppercase tracking-wider mb-3">
              Scoring Inputs
            </h4>
            <div className="space-y-4">
              {/* School Scoring Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label htmlFor="enable_schools" className="text-sm font-medium text-homefit-text-primary cursor-pointer">
                    School scoring
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onMouseEnter={() => setShowTooltip({ type: 'schools' })}
                      onMouseLeave={() => setShowTooltip({ type: null })}
                      className="text-gray-400 hover:text-gray-600 focus:outline-none"
                      aria-label="School scoring info"
                    >
                      <Info className="w-4 h-4" />
                    </button>
                    {showTooltip.type === 'schools' && (
                      <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10">
                        Premium feature: enter a Premium code to enable school scoring
                      </div>
                    )}
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    id="enable_schools"
                    checked={options.enable_schools}
                    onChange={(e) => handleEnableSchoolsChange(e.target.checked)}
                    disabled={disabled}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-homefit-accent-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-homefit-accent-primary"></div>
                </label>
              </div>

              {showSchoolsWaitlist && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  <div className="font-semibold">School scoring is Premium-gated.</div>
                  <div className="mt-1">
                    Join the waitlist with your email. After approval, you’ll receive a Premium code to paste here.
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      value={premiumCodeInput}
                      onChange={(e) => setPremiumCodeInput(e.target.value)}
                      placeholder="Enter Premium code"
                      className="flex-1 rounded border border-amber-200 bg-white px-2 py-1 text-xs text-amber-950 placeholder:text-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-300"
                      disabled={disabled}
                    />
                    <button
                      type="button"
                      onClick={handleSavePremiumCode}
                      disabled={disabled}
                      className="rounded bg-amber-900 px-2 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Save
                    </button>
                    {premiumCode && (
                      <button
                        type="button"
                        onClick={handleClearPremiumCode}
                        disabled={disabled}
                        className="rounded border border-amber-300 bg-transparent px-2 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  {premiumCodeMessage && <div className="mt-2 text-xs">{premiumCodeMessage}</div>}

                  <div className="mt-2">
                    {waitlistUrl ? (
                      <a
                        href={waitlistUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="underline hover:opacity-80"
                      >
                        Join the Premium waitlist
                      </a>
                    ) : (
                      <span>Join the Premium waitlist (link not configured).</span>
                    )}
                  </div>
                </div>
              )}

              {/* Chain Businesses Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label htmlFor="include_chains" className="text-sm font-medium text-homefit-text-primary cursor-pointer">
                    Chain businesses
                  </label>
                  <div className="relative">
                    <button
                      type="button"
                      onMouseEnter={() => setShowTooltip({ type: 'chains' })}
                      onMouseLeave={() => setShowTooltip({ type: null })}
                      className="text-gray-400 hover:text-gray-600 focus:outline-none"
                      aria-label="Chain businesses info"
                    >
                      <Info className="w-4 h-4" />
                    </button>
                    {showTooltip.type === 'chains' && (
                      <div className="absolute left-0 bottom-full mb-2 w-48 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-10">
                        Include chain restaurants and businesses in neighborhood amenities count
                      </div>
                    )}
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    id="include_chains"
                    checked={options.include_chains}
                    onChange={(e) => handleIncludeChainsChange(e.target.checked)}
                    disabled={disabled}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-homefit-accent-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-homefit-accent-primary"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Pillar Priorities Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-xs font-semibold text-homefit-text-primary uppercase tracking-wider">
                Pillar Priorities
              </h4>
              <button
                onClick={handleResetPriorities}
                disabled={disabled}
                className="text-xs text-homefit-accent-primary hover:opacity-80 font-medium disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-homefit-accent-primary focus:ring-offset-1 rounded px-2 py-1"
              >
                Reset to Default
              </button>
            </div>
            <p className="text-xs text-homefit-text-secondary mb-4 leading-relaxed">
              Set priority levels for each pillar. Higher priorities receive more weight in the total score.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(Object.keys(PILLAR_NAMES) as Array<keyof PillarPriorities>).map((pillar) => {
                const currentValue = options.priorities[pillar]
                return (
                  <div key={pillar} className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
                    <label className="text-sm font-medium text-homefit-text-primary flex-1 mr-3">
                      {PILLAR_NAMES[pillar]}
                    </label>
                    <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                      {PRIORITY_LEVELS.map((level) => {
                        const isSelected = currentValue === level
                        return (
                          <button
                            key={level}
                            type="button"
                            onClick={() => handlePriorityChange(pillar, level)}
                            disabled={disabled}
                            className={`px-2.5 py-1 text-xs font-medium rounded transition-all focus:outline-none focus:ring-2 focus:ring-homefit-accent-primary focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed ${
                              isSelected
                                ? 'bg-homefit-accent-primary text-white shadow-sm'
                                : 'text-homefit-text-secondary hover:text-homefit-text-primary hover:bg-gray-200'
                            }`}
                          >
                            {level}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
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
