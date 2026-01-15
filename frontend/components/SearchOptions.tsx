'use client'

import { useState, useEffect, useRef } from 'react'
import { Info } from 'lucide-react'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

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

const PILLAR_ORDER: Array<keyof PillarPriorities> = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'quality_education',
  'housing_value',
]

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
    <div style={{ borderTop: '1px solid var(--hf-border)', paddingTop: '1.5rem', marginTop: '1.5rem' }}>
      <button
        onClick={() => setExpanded(!expanded)}
        disabled={disabled}
        className="hf-btn-link"
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          textAlign: 'left',
          padding: '0.75rem 1rem',
          fontSize: '1rem',
        }}
      >
        <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>
          Customize your score
        </span>
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
        <div className="hf-panel" style={{ marginTop: '1rem' }}>
          {/* Scoring Inputs Section */}
          <div>
            <h4 className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '0.75rem' }}>
              Scoring Inputs
            </h4>
            <div className="space-y-4">
              {/* School Scoring Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <label htmlFor="enable_schools" className="text-sm font-medium cursor-pointer" style={{ color: 'var(--hf-text-primary)' }}>
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
                  <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[rgba(102,126,234,0.25)] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#667eea]"></div>
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
                  <label htmlFor="include_chains" className="text-sm font-medium cursor-pointer" style={{ color: 'var(--hf-text-primary)' }}>
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
                  <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[rgba(102,126,234,0.25)] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#667eea]"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Pillar Priorities Section */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h4 className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Pillar Priorities
              </h4>
              <button
                onClick={handleResetPriorities}
                disabled={disabled}
                className="hf-btn-link"
                style={{ fontSize: '0.9rem' }}
              >
                Reset to Default
              </button>
            </div>
            <p className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '1rem' }}>
              Set priority levels for each pillar. Higher priorities receive more weight in the total score.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {PILLAR_ORDER.map((pillar) => {
                const currentValue = options.priorities[pillar]
                const meta = PILLAR_META[pillar as PillarKey]
                return (
                  <div
                    key={pillar}
                    className="hf-panel"
                    style={{
                      padding: '1rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '1rem',
                    }}
                  >
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1 }}>
                      <span style={{ fontSize: '1.25rem' }}>{meta.icon}</span>
                      <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>{meta.name}</span>
                    </label>
                    <div className="priority-buttons" aria-label={`${meta.name} priority`}>
                      {PRIORITY_LEVELS.map((level) => {
                        const isSelected = currentValue === level
                        return (
                          <button
                            key={level}
                            type="button"
                            onClick={() => handlePriorityChange(pillar, level)}
                            disabled={disabled}
                            className={`priority-btn ${isSelected ? 'active' : ''}`}
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
