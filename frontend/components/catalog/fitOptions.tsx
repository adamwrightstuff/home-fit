'use client'

import { type PillarKey } from '@/lib/pillars'
import { type PriorityLevel } from '@/components/SearchOptions'
import type { ClimateMustHaves } from '@/lib/climatePreferences'

/** Option lists and small pieces shared by the Fit panel and the single-place Priorities panel. */

export const GROUPS: { title: string; keys: PillarKey[] }[] = [
  {
    title: 'Lifestyle',
    keys: ['natural_beauty', 'active_outdoors', 'neighborhood_amenities'],
  },
  {
    title: 'Community',
    keys: ['social_fabric', 'quality_education', 'community_safety'],
  },
  {
    title: 'Practicality',
    keys: ['public_transit_access', 'healthcare_access', 'air_travel_access', 'housing_value'],
  },
  {
    title: 'Economics',
    keys: ['economic_opportunity', 'climate_risk'],
  },
]

export const LEVELS: PriorityLevel[] = ['None', 'Low', 'Medium', 'High']

type PersonalKey = 'commute_time' | 'social_connection'
export const PERSONAL_ROWS: { key: PersonalKey; icon: string; name: string; needs: string }[] = [
  { key: 'commute_time', icon: '🚆', name: 'Your commute', needs: 'Add a work hub to weigh your commute.' },
  { key: 'social_connection', icon: '💛', name: 'Closeness to people you know', needs: 'Add people you want to live near to weigh this.' },
]

export const NB_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean / Bay' },
  { value: 'lakes_rivers', label: 'Lakes & Rivers' },
  { value: 'canopy', label: 'Tree Canopy' },
]

export const AO_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'local_parks', label: 'Local Parks' },
  { value: 'trails_regional', label: 'Trails & Regional Parks' },
  { value: 'waterfront', label: 'Waterfront' },
]

// Multi-select. "Public" is the score's own basis (assigned or nearest district schools); "Charter" scores the nearby
// charters; both selected averages the two (only when 3+ charters are rated nearby). The stored value stays one string:
// 'any' = public, 'charter' = charter, 'both' = both ('public_only' from older sessions behaves like 'any').
export const SCHOOL_LEVEL_OPTIONS: { value: string; label: string }[] = [
  { value: 'elementary', label: 'Elementary' },
  { value: 'middle', label: 'Middle' },
  { value: 'high', label: 'High' },
]

export const SCHOOL_TYPE_OPTIONS: { value: 'public' | 'charter'; label: string }[] = [
  { value: 'public', label: 'Public' },
  { value: 'charter', label: 'Charter' },
]

export function schoolTypeSelected(v?: string): ('public' | 'charter')[] {
  if (v === 'charter') return ['charter']
  if (v === 'both') return ['public', 'charter']
  return ['public']
}

export function schoolTypeFromSelected(sel: ('public' | 'charter')[]): 'any' | 'charter' | 'both' {
  const pub = sel.includes('public'), ch = sel.includes('charter')
  if (pub && ch) return 'both'
  return ch ? 'charter' : 'any'
}

export function KindChips({ label, options, selected, onToggle }: {
  label: string
  options: { value: string; label: string }[]
  selected: string[]
  onToggle: (v: string) => void
}) {
  return (
    <div className="mt-1.5">
      <div className="mb-1 text-[0.7rem] text-[var(--hf-text-secondary)]">{label}</div>
      <div className="flex flex-wrap gap-1">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => onToggle(o.value)}
            className={`hf-sheet-chip rounded-full px-2 py-0.5 text-[0.7rem] font-semibold ${selected.includes(o.value) ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
            style={selected.includes(o.value) ? { background: 'var(--hf-primary-1)' } : undefined}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}


export const CLIMATE_MUST_HAVES: { key: keyof ClimateMustHaves; short: string; full: string }[] = [
  { key: 'no_cold_winters', short: '❄️ Cold winters', full: 'Cold winters: coldest month averages below 40°F' },
  { key: 'no_hot_summers', short: '☀️ Hot summers', full: 'Hot summers: July average above 72°F' },
  { key: 'no_grey_days', short: '🌧️ Very grey & rainy', full: 'Very grey, rainy climate' },
  { key: 'no_big_swings', short: '🌡️ Big seasonal swings', full: 'Big seasonal swings: over 40°F July to January' },
]

