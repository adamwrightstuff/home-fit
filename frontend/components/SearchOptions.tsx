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
  economic_security: PriorityLevel
  quality_education: PriorityLevel
  housing_value: PriorityLevel
  climate_risk: PriorityLevel
  social_fabric: PriorityLevel
}

interface SearchOptions {
  priorities: PillarPriorities
  include_chains: boolean
  enable_schools: boolean
  job_categories: string[]
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
  'economic_security',
  'quality_education',
  'housing_value',
  'climate_risk',
  'social_fabric',
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
  economic_security: 'Medium',
  quality_education: 'Medium',
  housing_value: 'Medium',
  climate_risk: 'Medium',
   social_fabric: 'Medium',
}

const JOB_CATEGORY_OPTIONS: Array<{ key: string; label: string; description: string }> = [
  { key: 'tech_professional', label: 'Tech / Product', description: 'Software, data, engineering, product, UX/UI' },
  { key: 'business_finance_law', label: 'Business / Finance / Law', description: 'Finance, consulting, corporate, legal, accounting' },
  { key: 'healthcare_education', label: 'Healthcare / Education', description: 'Doctors, nurses, teachers, professors, admin' },
  { key: 'skilled_trades_logistics', label: 'Skilled trades / Logistics', description: 'Construction, manufacturing, transport, mechanics, electricians' },
  { key: 'service_retail_hospitality', label: 'Service / Retail / Hospitality', description: 'Restaurants, retail, tourism, personal services' },
  { key: 'public_sector_nonprofit', label: 'Public sector', description: 'Government and public administration (nonprofit proxy is limited)' },
  { key: 'remote_flexible', label: 'Remote / Flexible', description: 'Work-from-home prevalence + earnings proxy' },
]

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

  const handleJobCategoryToggle = (key: string, checked: boolean) => {
    const current = Array.isArray(options.job_categories) ? options.job_categories : []
    const next = checked ? Array.from(new Set([...current, key])) : current.filter((k) => k !== key)
    onChange({
      ...options,
      job_categories: next,
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
                <div className="hf-premium-banner" style={{ marginTop: '0.75rem', position: 'relative' }}>
                  <button
                    type="button"
                    aria-label="Close premium banner"
                    className="hf-premium-close"
                    onClick={() => {
                      setShowSchoolsWaitlist(false)
                      setPremiumCodeMessage('')
                    }}
                  >
                    ×
                  </button>
                  <div style={{ fontWeight: 800, fontSize: '1rem', marginBottom: '0.35rem' }}>
                    School scoring is Premium-gated.
                  </div>
                  <div style={{ opacity: 0.95, fontSize: '0.95rem' }}>
                    Join the waitlist. After approval, you’ll receive a Premium code to paste here.
                  </div>

                  <div style={{ marginTop: '0.9rem', display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      value={premiumCodeInput}
                      onChange={(e) => setPremiumCodeInput(e.target.value)}
                      placeholder="Enter Premium code"
                      className="hf-input"
                      disabled={disabled}
                      style={{ flex: 1, minWidth: 220 }}
                    />
                    <button type="button" onClick={handleSavePremiumCode} disabled={disabled} className="hf-premium-btn">
                      Save
                    </button>
                    {premiumCode ? (
                      <button
                        type="button"
                        onClick={handleClearPremiumCode}
                        disabled={disabled}
                        className="hf-premium-btn hf-premium-btn--outline"
                      >
                        Clear
                      </button>
                    ) : null}
                  </div>

                  {premiumCodeMessage ? (
                    <div style={{ marginTop: '0.6rem', fontSize: '0.95rem', opacity: 0.95 }}>
                      {premiumCodeMessage}
                    </div>
                  ) : null}

                  <div style={{ marginTop: '0.75rem', fontSize: '0.95rem', opacity: 0.95 }}>
                    {waitlistUrl ? (
                      <a href={waitlistUrl} target="_blank" rel="noreferrer">
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

          {/* Economic Opportunity: Job category toggles */}
          <div style={{ marginTop: '1.5rem' }}>
            <div className="flex items-center justify-between mb-2">
              <h4 className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Economic Opportunity Focus (optional)
              </h4>
            </div>
            <p className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '1rem' }}>
              Select job categories you care about. This will personalize the Economic Opportunity pillar and affect the total score. Scoring may take a bit longer when categories are selected.
            </p>
            <div className="hf-panel" style={{ padding: '1rem' }}>
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {JOB_CATEGORY_OPTIONS.map((opt) => {
                  const checked = Array.isArray(options.job_categories) && options.job_categories.includes(opt.key)
                  return (
                    <label key={opt.key} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={(e) => handleJobCategoryToggle(opt.key, e.target.checked)}
                        style={{ marginTop: '0.2rem' }}
                      />
                      <span style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>{opt.label}</div>
                        <div className="hf-muted" style={{ fontSize: '0.9rem' }}>{opt.description}</div>
                      </span>
                    </label>
                  )
                })}
              </div>
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
