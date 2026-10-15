'use client'

import { useEffect } from 'react'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import { type ClimatePreferences, type ClimateMustHaves } from '@/lib/climatePreferences'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import { X } from 'lucide-react'
import { CATALOG_METROS, CATALOG_METRO_META, type CatalogMetro } from '@/lib/catalogMetros'

const AREA_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'urban_core', label: 'Urban Core' },
  { value: 'urban_residential', label: 'Urban Neighborhood' },
  { value: 'suburban', label: 'Suburban' },
  { value: 'exurban', label: 'Exurban' },
  { value: 'rural', label: 'Rural' },
]

const MUST_HAVE_PILLARS: PillarKey[] = ['housing_value', 'quality_education', 'community_safety', 'healthcare_access', 'air_travel_access', 'public_transit_access']

/** What "fails" means per pillar; mirrors the thresholds in lib/reweight.ts. Keep in sync. */
const MUST_HAVE_DESCRIPTIONS: Partial<Record<PillarKey, string>> = {
  housing_value: 'Home price over 3x your household income',
  quality_education: 'School ratings below 3-star equivalent',
  community_safety: 'In the highest-crime quarter nationally',
  healthcare_access: 'More than 30 min drive from a hospital',
  air_travel_access: 'More than 60 min drive from an airport',
  public_transit_access: 'No rail and very few bus stops',
}

const CLIMATE_MUST_HAVES: { key: keyof ClimateMustHaves; label: string }[] = [
  { key: 'no_cold_winters', label: '❄️ Cold winters (2+ months below freezing)' },
  { key: 'no_hot_summers', label: '☀️ Hot summers (July average 78°F or higher)' },
  { key: 'no_grey_days', label: '🌧️ Very grey, rainy climate' },
  { key: 'no_big_swings', label: '🌡️ Big seasonal swings (over 45°F July to January)' },
]

interface FilterSheetProps {
  open: boolean
  onClose: () => void
  filterMetro: 'all' | CatalogMetro
  onFilterMetroChange: (v: 'all' | CatalogMetro) => void
  filterAreaTypes: string[]
  onFilterAreaTypesChange: (v: string[]) => void
  filterArchetypes: string[]
  onFilterArchetypesChange: (v: string[]) => void
  archetypes: string[]
  filterTrajectory: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'
  onFilterTrajectoryChange: (v: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining') => void
  filterPoliticalLean: string[]
  onFilterPoliticalLeanChange: (v: string[]) => void
  filterHousingType: string[]
  onFilterHousingTypeChange: (v: string[]) => void
  filterTenure: string[]
  onFilterTenureChange: (v: string[]) => void
  filterLocalScene: 'all' | 'Some' | 'High'
  onFilterLocalSceneChange: (v: 'all' | 'Some' | 'High') => void
  filterAura: boolean
  onFilterAuraChange: (v: boolean) => void
  /** Must-haves: places that fail any checked box are hidden. */
  dealbreakers?: Partial<Record<PillarKey, boolean>>
  onDealbreakerToggle?: (key: PillarKey) => void
  dealbreakerFailCounts?: Partial<Record<PillarKey, number>>
  householdIncome?: number | null
  filterCommuteMax: 'all' | '15' | '30' | '45' | '60'
  onFilterCommuteMaxChange: (v: 'all' | '15' | '30' | '45' | '60') => void
  workZoneLabel?: string | null
  commuteFailCount?: number
  climateMustHaveFailCounts?: Partial<Record<keyof ClimateMustHaves, number>>
  climatePrefs: ClimatePreferences
  onClimatePrefsChange: (v: ClimatePreferences) => void
  resultCount: number
}

const LABEL_STYLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: '#9ca3af',
  marginBottom: 8,
}

const CHIP_BASE: React.CSSProperties = {
  borderRadius: 999,
  padding: '4px 12px',
  fontSize: '0.7rem',
  fontWeight: 600,
  cursor: 'pointer',
  border: '1px solid transparent',
}

export default function FilterSheet({
  open,
  onClose,
  filterMetro,
  onFilterMetroChange,
  filterAreaTypes,
  onFilterAreaTypesChange,
  filterArchetypes,
  onFilterArchetypesChange,
  archetypes,
  filterTrajectory,
  onFilterTrajectoryChange,
  filterPoliticalLean,
  onFilterPoliticalLeanChange,
  filterHousingType,
  onFilterHousingTypeChange,
  filterTenure,
  onFilterTenureChange,
  filterLocalScene,
  onFilterLocalSceneChange,
  filterAura,
  onFilterAuraChange,
  dealbreakers,
  onDealbreakerToggle,
  dealbreakerFailCounts,
  householdIncome,
  filterCommuteMax,
  onFilterCommuteMaxChange,
  workZoneLabel,
  commuteFailCount = 0,
  climateMustHaveFailCounts,
  climatePrefs,
  onClimatePrefsChange,
  resultCount,
}: FilterSheetProps) {
  type TrajectoryOption = 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  const activeCount =
    (filterAreaTypes.length > 0 ? 1 : 0) +
    (filterArchetypes.length > 0 ? 1 : 0) +
    (filterTrajectory !== 'all' ? 1 : 0) +
    (filterPoliticalLean.length > 0 ? 1 : 0) +
    (filterHousingType.length > 0 ? 1 : 0) +
    (filterTenure.length > 0 ? 1 : 0) +
    (filterLocalScene !== 'all' ? 1 : 0) +
    (filterAura ? 1 : 0) +
    (climatePrefs.must_haves ? Object.values(climatePrefs.must_haves).filter(Boolean).length : 0)

  function handleClearAll() {
    onFilterMetroChange('all')
    onFilterAreaTypesChange([])
    onFilterArchetypesChange([])
    onFilterTrajectoryChange('all')
    onFilterPoliticalLeanChange([])
    onFilterHousingTypeChange([])
    onFilterTenureChange([])
    onFilterLocalSceneChange('all')
    onFilterAuraChange(false)
    onClimatePrefsChange({})
  }

  function toggleAreaType(value: string) {
    if (filterAreaTypes.includes(value)) {
      onFilterAreaTypesChange(filterAreaTypes.filter((v) => v !== value))
    } else {
      onFilterAreaTypesChange([...filterAreaTypes, value])
    }
  }

  function chip(active: boolean, label: string, onClick: () => void) {
    return (
      <button
        key={label}
        type="button"
        onClick={onClick}
        style={{
          ...CHIP_BASE,
          background: active ? 'var(--hf-primary-1)' : 'var(--hf-hover-bg)',
          color: active ? '#fff' : 'var(--hf-text-secondary)',
          border: active ? 'none' : '0.5px solid var(--hf-border)',
        }}
      >
        {label}
      </button>
    )
  }

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-[69] bg-black/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="filter-sheet-title"
        className="fixed z-[70] max-h-[85vh] overflow-y-auto bg-white
          bottom-0 left-0 right-0 rounded-t-2xl border-t border-gray-200
          md:bottom-auto md:left-1/2 md:right-auto md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2
          md:w-[480px] md:rounded-2xl md:border md:border-gray-200 md:shadow-xl"
      >
        <div className="flex justify-center pt-2.5 md:hidden">
          <div style={{ width: 40, height: 4, borderRadius: 2, background: '#e5e7eb' }} />
        </div>

        <div style={{ padding: '12px 16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 id="filter-sheet-title" style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>
            Filters {activeCount > 0 && <span style={{ fontSize: 12, fontWeight: 400, color: '#6b7280' }}>({activeCount} active)</span>}
          </h2>
          <button type="button" onClick={onClose} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: '#6b7280' }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: '16px 16px 0' }}>
          {/* Must-haves: the hard "never show me" filters */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Never show places with</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {MUST_HAVE_PILLARS.map((key) => {
                const fails = dealbreakerFailCounts?.[key]
                return (
                  <label key={key} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13 }}>
                    <input type="checkbox" style={{ marginTop: 3 }} checked={Boolean(dealbreakers?.[key])} onChange={() => onDealbreakerToggle?.(key)} />
                    <span>
                      {PILLAR_META[key].icon} {MUST_HAVE_DESCRIPTIONS[key]}
                      {key === 'housing_value' && !householdIncome && (
                        <span style={{ display: 'block', fontSize: 11, color: '#9ca3af' }}>Add your household income in your profile to use this.</span>
                      )}
                      {typeof fails === 'number' && fails > 0 && (key !== 'housing_value' || householdIncome) && (
                        <span style={{ display: 'block', fontSize: 11, color: '#9ca3af' }}>Removes {fails} place{fails === 1 ? '' : 's'}</span>
                      )}
                    </span>
                  </label>
                )
              })}
              {CLIMATE_MUST_HAVES.map(({ key, label }) => {
                const fails = climateMustHaveFailCounts?.[key]
                return (
                  <label key={key} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13 }}>
                    <input
                      type="checkbox"
                      style={{ marginTop: 3 }}
                      checked={Boolean(climatePrefs.must_haves?.[key])}
                      onChange={() => onClimatePrefsChange({ ...climatePrefs, must_haves: { ...climatePrefs.must_haves, [key]: !climatePrefs.must_haves?.[key] } })}
                    />
                    <span>
                      {label}
                      {typeof fails === 'number' && fails > 0 && (
                        <span style={{ display: 'block', fontSize: 11, color: '#9ca3af' }}>Removes {fails} place{fails === 1 ? '' : 's'}</span>
                      )}
                    </span>
                  </label>
                )
              })}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 12, marginBottom: 6 }}>🚆 Commute over this many minutes</div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              {workZoneLabel ? `To ${workZoneLabel}.` : 'To the metro downtown by transit. Add a work address in your profile to use your own commute.'}
              {filterCommuteMax !== 'all' && commuteFailCount > 0 ? ` Removes ${commuteFailCount} place${commuteFailCount === 1 ? '' : 's'}.` : ''}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterCommuteMax === 'all', 'Any', () => onFilterCommuteMaxChange('all'))}
              {(['15', '30', '45', '60'] as const).map((v) =>
                chip(filterCommuteMax === v, `Under ${v} min`, () => onFilterCommuteMaxChange(filterCommuteMax === v ? 'all' : v))
              )}
            </div>
          </div>

          {/* Metro */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Metro</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(['all', ...CATALOG_METROS] as const).map((m) =>
                chip(filterMetro === m, m === 'all' ? 'All metros' : CATALOG_METRO_META[m].label, () => onFilterMetroChange(m))
              )}
            </div>
          </div>

          {/* Area type */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Built environment</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {AREA_TYPE_OPTIONS.map(({ value, label }) =>
                chip(filterAreaTypes.includes(value), label, () => toggleAreaType(value))
              )}
            </div>
            {filterAreaTypes.length > 0 && (
              <button
                type="button"
                onClick={() => onFilterAreaTypesChange([])}
                style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Class */}
          {archetypes.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={LABEL_STYLE}>Class (select multiple)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {archetypes.map((a) =>
                  chip(filterArchetypes.includes(a), displayArchetypeLabel(a), () => {
                    if (filterArchetypes.includes(a)) {
                      onFilterArchetypesChange(filterArchetypes.filter((x) => x !== a))
                    } else {
                      onFilterArchetypesChange([...filterArchetypes, a])
                    }
                  })
                )}
              </div>
              {filterArchetypes.length > 0 && (
                <button
                  type="button"
                  onClick={() => onFilterArchetypesChange([])}
                  style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  Clear
                </button>
              )}
            </div>
          )}

          {/* Trajectory */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Trajectory</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(['all', 'Arrived', 'Up-and-Coming', 'Stable', 'Cooling', 'Declining'] as TrajectoryOption[]).map((t) =>
                chip(filterTrajectory === t, t === 'all' ? 'All' : t === 'Up-and-Coming' ? 'Up & Coming' : t, () => onFilterTrajectoryChange(t))
              )}
            </div>
          </div>

          {/* Housing Stock */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Housing Stock</div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              What the housing stock actually looks like. Select any that fit — a place can match more than one.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterHousingType.includes('sf_townhouse'), 'Single-Family / Townhouse', () => {
                onFilterHousingTypeChange(filterHousingType.includes('sf_townhouse')
                  ? filterHousingType.filter((v) => v !== 'sf_townhouse')
                  : [...filterHousingType, 'sf_townhouse'])
              })}
              {chip(filterHousingType.includes('small_multifamily'), 'Small Multifamily (2–4 unit)', () => {
                onFilterHousingTypeChange(filterHousingType.includes('small_multifamily')
                  ? filterHousingType.filter((v) => v !== 'small_multifamily')
                  : [...filterHousingType, 'small_multifamily'])
              })}
              {chip(filterHousingType.includes('apartment'), 'Apartment / Condo / Co-op', () => {
                onFilterHousingTypeChange(filterHousingType.includes('apartment')
                  ? filterHousingType.filter((v) => v !== 'apartment')
                  : [...filterHousingType, 'apartment'])
              })}
            </div>
            {filterHousingType.length > 0 && (
              <button
                type="button"
                onClick={() => onFilterHousingTypeChange([])}
                style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Tenure Mix */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Tenure Mix</div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              Filter by the local owner/renter split. Based on Census share of occupied units that are rented.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterTenure.includes('renter'), 'Renter-Majority', () => {
                onFilterTenureChange(filterTenure.includes('renter')
                  ? filterTenure.filter((v) => v !== 'renter')
                  : [...filterTenure, 'renter'])
              })}
              {chip(filterTenure.includes('balanced'), 'Balanced', () => {
                onFilterTenureChange(filterTenure.includes('balanced')
                  ? filterTenure.filter((v) => v !== 'balanced')
                  : [...filterTenure, 'balanced'])
              })}
              {chip(filterTenure.includes('homeowner'), 'Homeowner-Majority', () => {
                onFilterTenureChange(filterTenure.includes('homeowner')
                  ? filterTenure.filter((v) => v !== 'homeowner')
                  : [...filterTenure, 'homeowner'])
              })}
            </div>
            {filterTenure.length > 0 && (
              <button
                type="button"
                onClick={() => onFilterTenureChange([])}
                style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Political lean */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Political Lean</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterPoliticalLean.length === 0, 'All', () => onFilterPoliticalLeanChange([]))}
              {(['strong_d', 'lean_d', 'moderate', 'lean_r', 'strong_r'] as const).map((val) => {
                const labels: Record<string, string> = {
                  strong_d: '🔵 Strong D',
                  lean_d: '🔵 Lean D',
                  moderate: '🟣 Moderate',
                  lean_r: '🔴 Lean R',
                  strong_r: '🔴 Strong R',
                }
                return chip(
                  filterPoliticalLean.includes(val),
                  labels[val],
                  () => onFilterPoliticalLeanChange(
                    filterPoliticalLean.includes(val)
                      ? filterPoliticalLean.filter(v => v !== val)
                      : [...filterPoliticalLean, val]
                  )
                )
              })}
            </div>
          </div>

          {/* Local Scene */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 8 }}>
              <div style={LABEL_STYLE}>Local Scene</div>
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              Reflects the presence of independent places to spend time, like cafés, bookstores, bars, and galleries.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterLocalScene === 'all', 'All', () => onFilterLocalSceneChange('all'))}
              {chip(filterLocalScene === 'Some', 'Some+', () => onFilterLocalSceneChange(filterLocalScene === 'Some' ? 'all' : 'Some'))}
              {chip(filterLocalScene === 'High', 'High only', () => onFilterLocalSceneChange(filterLocalScene === 'High' ? 'all' : 'High'))}
            </div>
          </div>

          {/* Aura */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 8 }}>
              <div style={LABEL_STYLE}>Aura</div>
            </div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              The top 5% of places in each metro: a standout local scene backed by strong everyday livability.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(!filterAura, 'All', () => onFilterAuraChange(false))}
              {chip(filterAura, 'Aura only', () => onFilterAuraChange(!filterAura))}
            </div>
          </div>


        </div>

        <div
          style={{
            position: 'sticky',
            bottom: 0,
            background: '#fff',
            borderTop: '1px solid #f3f4f6',
            padding: '12px 16px',
            display: 'flex',
            gap: 10,
            alignItems: 'center',
          }}
        >
          <button
            type="button"
            onClick={handleClearAll}
            style={{
              flex: '0 0 auto',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 600,
              color: '#6b7280',
              padding: '8px 0',
            }}
          >
            Clear all
          </button>
          <button
            type="button"
            onClick={onClose}
            style={{
              flex: 1,
              borderRadius: 999,
              background: '#1a1a2e',
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: 700,
              padding: '10px 16px',
            }}
          >
            Show {resultCount} results
          </button>
        </div>
      </div>
    </>
  )
}
