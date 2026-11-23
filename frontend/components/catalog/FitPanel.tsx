'use client'

import { useEffect, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { X } from 'lucide-react'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'
import PillarInfoIcon from '@/components/PillarInfoIcon'
import { DEFAULT_PRIORITIES, type PillarPriorities, type PriorityLevel } from '@/components/SearchOptions'
import { ALL_BEDS, DEFAULT_BUDGET, MORTGAGE_RATE, bedLabel, minBeds, setMinBed, type BudgetFilter } from '@/lib/budgetCost'
import { SCENE_LABEL, SCENE_FILTER_LEVELS, toggleSceneLevel, type SceneFilter } from '@/lib/sceneLevels'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import type { ClimatePreferences } from '@/lib/climatePreferences'
import { GATE_DEFAULT_LEVEL } from '@/lib/reweight'
import {
  GROUPS, LEVELS, PERSONAL_ROWS, NB_TYPE_OPTIONS, AO_TYPE_OPTIONS, SCHOOL_LEVEL_OPTIONS, SCHOOL_TYPE_OPTIONS,
  schoolTypeSelected, schoolTypeFromSelected, KindChips,
  CLIMATE_MUST_HAVES,
} from '@/components/catalog/fitOptions'

/**
 * One panel for everything that shapes the list. Two sections with different verbs:
 *  - Must have: hides places that do not fit. Every requirement is added by the user; none is ever on by default.
 *  - What matters: ranks places and hides nothing.
 * It holds no state of its own beyond which requirement rows are open; every control reads and writes the same
 * state the old Filters sheet and Priorities panel used, so the filtering itself is unchanged.
 * Design notes: docs/UX_PRINCIPLES_DRAFT.md (2026-11-23).
 */

type ReqId =
  | 'schools' | 'safety' | 'commute' | 'transit' | 'airport' | 'health' | 'budget'
  | 'area' | 'stock' | 'tenure' | 'climate' | 'scene' | 'trajectory' | 'class' | 'politics' | 'life'

const AREA_TYPE_OPTIONS = [
  { value: 'urban_residential', label: 'Urban Neighborhood' },
  { value: 'suburban', label: 'Suburban' },
  { value: 'exurban', label: 'Exurban' },
  { value: 'rural', label: 'Rural' },
]
const HOUSING_OPTIONS = [
  { value: 'sf_townhouse', label: 'Single-Family / Townhouse' },
  { value: 'small_multifamily', label: 'Small Multifamily (2–4 unit)' },
  { value: 'apartment', label: 'Apartment / Condo / Co-op' },
]
const TENURE_OPTIONS = [
  { value: 'renter', label: 'Renter-Majority' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'homeowner', label: 'Homeowner-Majority' },
]
const POLITICS_OPTIONS = [
  { value: 'strong_d', label: 'Strong D' },
  { value: 'lean_d', label: 'Lean D' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'lean_r', label: 'Lean R' },
  { value: 'strong_r', label: 'Strong R' },
]
const LIFE_OPTIONS = [
  { value: 'children', label: 'Families with kids' },
  { value: 'young_professionals', label: 'Young professionals' },
  { value: 'older', label: 'Older adults' },
]
const TRAJECTORY_OPTIONS = [
  { value: 'Up-and-Coming', label: 'Up & Coming' },
  { value: 'Stable', label: 'Stable' },
  { value: 'Declining', label: 'Declining' },
]
// Percentile cutoffs for the Schools requirement. 50 is the state median the old gate used; 75 and 90 are not
// evidence-backed and are the owner's call.
const SCHOOL_MIN_OPTIONS = [
  { value: 0, label: 'Any' },
  { value: 50, label: 'Above state average' },
  { value: 75, label: 'Top 25% in state' },
  { value: 90, label: 'Top 10% in state' },
]

const REQ_GROUPS: { title: string; ids: ReqId[] }[] = [
  { title: 'Schools and safety', ids: ['schools', 'safety'] },
  { title: 'Getting around', ids: ['commute', 'transit', 'airport', 'health'] },
  { title: 'Money', ids: ['budget'] },
  { title: 'The place itself', ids: ['area', 'stock', 'tenure', 'climate', 'scene', 'trajectory', 'class'] },
  { title: 'About the people', ids: ['politics', 'life'] },
]

const REQ_NAME: Record<ReqId, string> = {
  schools: 'Schools',
  safety: 'Crime level',
  commute: 'Commute to work',
  transit: 'Public transit',
  airport: 'Airport',
  health: 'Hospital',
  budget: 'Monthly cost',
  area: 'Area type',
  stock: 'Housing stock',
  tenure: 'Tenure mix',
  climate: 'Climate',
  scene: 'Local scene',
  trajectory: 'Trajectory',
  class: 'Class',
  politics: 'Political lean',
  life: 'Life stage',
}

// Graded requirements that map to a pillar's existing pass/fail gate. Options run loosest to strictest; value 0 is Any.
// Only the first option of each is the original cutoff; the stricter ones are not evidence-backed and are the owner's call.
const GATE: Partial<Record<ReqId, { key: PillarKey; cap?: string; options: { value: number; label: string }[] }>> = {
  safety: {
    key: 'community_safety',
    cap: 'Compared with places nationwide. Stricter levels hide most city neighborhoods.',
    options: [
      { value: 0, label: 'Any' },
      { value: 25, label: 'Not in the highest-crime quarter' },
      { value: 50, label: 'Safer than half of places' },
      { value: 75, label: 'Safer than 3 in 4 places' },
    ],
  },
  health: {
    key: 'healthcare_access',
    cap: 'Estimated drive time to the nearest hospital.',
    options: [
      { value: 0, label: 'Any' },
      { value: 45, label: 'Within 45 min' },
      { value: 30, label: 'Within 30 min' },
      { value: 20, label: 'Within 20 min' },
      { value: 15, label: 'Within 15 min' },
    ],
  },
  airport: {
    key: 'air_travel_access',
    cap: 'Estimated drive time to the nearest airport.',
    options: [
      { value: 0, label: 'Any' },
      { value: 90, label: 'Within 90 min' },
      { value: 60, label: 'Within 60 min' },
      { value: 45, label: 'Within 45 min' },
      { value: 30, label: 'Within 30 min' },
    ],
  },
  transit: {
    key: 'public_transit_access',
    options: [
      { value: 0, label: 'Any' },
      { value: 1, label: 'Rail or several bus stops' },
      { value: 2, label: 'Rail nearby' },
    ],
  },
}

function Pill({ on, onClick, children, title }: { on: boolean; onClick: () => void; children: ReactNode; title?: string }) {
  return (
    <button
      type="button"
      title={title}
      aria-pressed={on}
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-[0.72rem] font-semibold ${on ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
      style={on ? { background: 'var(--hf-primary-1)' } : undefined}
    >
      {children}
    </button>
  )
}

function PillRow({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-1.5">{children}</div>
}

function Cap({ children }: { children: ReactNode }) {
  return <p className="m-0 mb-1.5 text-[0.7rem] leading-snug text-[var(--hf-text-secondary)]">{children}</p>
}

export interface FitPanelProps {
  open: boolean
  onClose: () => void
  /** Priorities (What matters) only apply to the HomeFit index. */
  showMatters: boolean
  resultCount: number
  onClearRequirements: () => void

  priorities: PillarPriorities
  onPrioritiesChange: (next: PillarPriorities) => void
  onTakeQuiz?: () => void
  hasWorkHub: boolean
  hasPeople: boolean
  peopleCount: number
  workZoneLabel: string | null

  filterNbTypes: string[]
  onFilterNbTypesChange: (v: string[]) => void
  filterAoTypes: string[]
  onFilterAoTypesChange: (v: string[]) => void
  filterSchoolType: 'any' | 'public_only' | 'charter' | 'both'
  onFilterSchoolTypeChange: (v: 'any' | 'public_only' | 'charter' | 'both') => void
  filterSchoolLevels: string[]
  onFilterSchoolLevelsChange: (v: string[]) => void

  dealbreakers: Partial<Record<PillarKey, boolean>>
  onDealbreakerToggle: (key: PillarKey) => void
  dealbreakerFailCounts: Partial<Record<PillarKey, number>>
  schoolMinScore: number
  onSchoolMinScoreChange: (v: number) => void
  gateLevels: Record<string, number>
  onGateLevelChange: (key: PillarKey, level: number) => void

  filterCommuteMax: 'all' | '15' | '30' | '45' | '60'
  onFilterCommuteMaxChange: (v: 'all' | '15' | '30' | '45' | '60') => void
  commuteFailCount: number

  filterBudget: BudgetFilter
  onFilterBudgetChange: (v: BudgetFilter) => void
  suggestedCaps: { label: string; value: number }[]

  filterAreaTypes: string[]
  onFilterAreaTypesChange: (v: string[]) => void
  filterHousingType: string[]
  onFilterHousingTypeChange: (v: string[]) => void
  filterTenure: string[]
  onFilterTenureChange: (v: string[]) => void
  climatePrefs: ClimatePreferences
  onClimatePrefsChange: (v: ClimatePreferences) => void
  climateMustHaveFailCounts?: Record<string, number>
  filterLocalScene: SceneFilter
  onFilterLocalSceneChange: (v: SceneFilter) => void
  filterTrajectory: 'all' | 'Up-and-Coming' | 'Stable' | 'Declining'
  onFilterTrajectoryChange: (v: 'all' | 'Up-and-Coming' | 'Stable' | 'Declining') => void
  filterArchetypes: string[]
  onFilterArchetypesChange: (v: string[]) => void
  archetypes: string[]
  filterPoliticalLean: string[]
  onFilterPoliticalLeanChange: (v: string[]) => void
  filterLifeStage: string[]
  onFilterLifeStageChange: (v: string[]) => void
}

function toggleIn(list: string[], v: string): string[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v]
}

export default function FitPanel(p: FitPanelProps) {
  const [added, setAdded] = useState<ReqId[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [bedHint, setBedHint] = useState(false)

  useEffect(() => {
    if (p.open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
      setAdded([])
      setMenuOpen(false)
    }
    return () => { document.body.style.overflow = '' }
  }, [p.open])

  if (!p.open) return null

  const must = p.climatePrefs.must_haves ?? {}
  const gateOn = (id: ReqId) => Boolean(GATE[id] && p.dealbreakers[GATE[id]!.key])
  // The selected level; a gate switched on in an older session has none stored and keeps its original cutoff.
  const gateLevel = (id: ReqId): number => {
    const g = GATE[id]
    if (!g || !gateOn(id)) return 0
    return p.gateLevels[g.key] || GATE_DEFAULT_LEVEL[g.key] || 0
  }
  const setGate = (id: ReqId, level: number) => {
    const g = GATE[id]
    if (g) p.onGateLevelChange(g.key, level)
  }

  const active: Record<ReqId, boolean> = {
    schools: p.schoolMinScore > 0,
    safety: gateOn('safety'),
    commute: p.filterCommuteMax !== 'all',
    transit: gateOn('transit'),
    airport: gateOn('airport'),
    health: gateOn('health'),
    budget: p.filterBudget.chosen,
    area: p.filterAreaTypes.length > 0,
    stock: p.filterHousingType.length > 0,
    tenure: p.filterTenure.length > 0,
    climate: Object.values(must).some(Boolean),
    scene: p.filterLocalScene.length > 0,
    trajectory: p.filterTrajectory !== 'all',
    class: p.filterArchetypes.length > 0,
    politics: p.filterPoliticalLean.length > 0,
    life: p.filterLifeStage.length > 0,
  }
  const visible = (id: ReqId) => active[id] || added.includes(id)

  function clearReq(id: ReqId) {
    switch (id) {
      case 'schools': p.onSchoolMinScoreChange(0); break
      case 'safety': case 'transit': case 'airport': case 'health': setGate(id, 0); break
      case 'commute': p.onFilterCommuteMaxChange('all'); break
      case 'budget': p.onFilterBudgetChange(DEFAULT_BUDGET); break
      case 'area': p.onFilterAreaTypesChange([]); break
      case 'stock': p.onFilterHousingTypeChange([]); break
      case 'tenure': p.onFilterTenureChange([]); break
      case 'climate': p.onClimatePrefsChange({ ...p.climatePrefs, must_haves: {} }); break
      case 'scene': p.onFilterLocalSceneChange([]); break
      case 'trajectory': p.onFilterTrajectoryChange('all'); break
      case 'class': p.onFilterArchetypesChange([]); break
      case 'politics': p.onFilterPoliticalLeanChange([]); break
      case 'life': p.onFilterLifeStageChange([]); break
    }
  }
  function removeReq(id: ReqId) {
    clearReq(id)
    setAdded((a) => a.filter((x) => x !== id))
  }
  function addReq(id: ReqId) {
    setAdded((a) => (a.includes(id) ? a : [...a, id]))
    setMenuOpen(false)
  }

  const failCount = (id: ReqId): number => {
    if (id === 'schools') return p.dealbreakerFailCounts.quality_education ?? 0
    if (id === 'commute') return p.commuteFailCount
    const g = GATE[id]
    return g ? p.dealbreakerFailCounts[g.key] ?? 0 : 0
  }

  function renderBody(id: ReqId): ReactNode {
    switch (id) {
      case 'schools':
        return (
          <>
            <Cap>Each grade you pick must rank at least this high among all schools in its state.</Cap>
            <PillRow>
              {SCHOOL_MIN_OPTIONS.map((o) => (
                <Pill key={o.value} on={p.schoolMinScore === o.value} onClick={() => p.onSchoolMinScoreChange(o.value)}>{o.label}</Pill>
              ))}
            </PillRow>
            <div className="mt-2">
              <Cap>Which grades? (pick any)</Cap>
              <PillRow>
                {SCHOOL_LEVEL_OPTIONS.map((o) => (
                  <Pill key={o.value} on={p.filterSchoolLevels.includes(o.value)} onClick={() => {
                    const next = toggleIn(p.filterSchoolLevels, o.value)
                    if (next.length) p.onFilterSchoolLevelsChange(next)
                  }}>{o.label}</Pill>
                ))}
              </PillRow>
            </div>
          </>
        )
      case 'safety': case 'transit': case 'airport': case 'health': {
        const g = GATE[id]!
        const cur = gateLevel(id)
        return (
          <>
            {g.cap && <Cap>{g.cap}</Cap>}
            <PillRow>
              {g.options.map((o) => (
                <Pill key={o.value} on={cur === o.value} onClick={() => setGate(id, o.value)}>{o.label}</Pill>
              ))}
            </PillRow>
          </>
        )
      }
      case 'commute':
        if (!p.workZoneLabel) {
          return <Cap>Needs a work address. <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">Add one in your profile</Link></Cap>
        }
        return (
          <>
            <Cap>To {p.workZoneLabel}. <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">Change in your profile</Link></Cap>
            <PillRow>
              <Pill on={p.filterCommuteMax === 'all'} onClick={() => p.onFilterCommuteMaxChange('all')}>Any</Pill>
              {(['15', '30', '45', '60'] as const).map((v) => (
                <Pill key={v} on={p.filterCommuteMax === v} onClick={() => p.onFilterCommuteMaxChange(p.filterCommuteMax === v ? 'all' : v)}>Under {v} min</Pill>
              ))}
            </PillRow>
          </>
        )
      case 'budget': {
        const b = p.filterBudget
        const inputCls = 'mt-1 block h-[var(--hf-control-h-touch)] w-[130px] rounded-[var(--hf-control-radius)] border border-[var(--hf-border)] px-2 text-sm text-[var(--hf-text-primary)]'
        return (
          <>
            <Cap>
              Estimated monthly cost of a typical home with at least your bedrooms: mortgage at {Math.round(MORTGAGE_RATE * 100)}% over 30 years, property tax and insurance.
              A place stays if any size from your minimum up fits. Places with no data are not hidden.
            </Cap>
            <div className="mb-1 text-[0.7rem] text-[var(--hf-text-secondary)]">Bedrooms (at least)</div>
            <PillRow>
              {ALL_BEDS.map((n) => (
                <Pill key={n} on={b.chosen && b.beds.includes(n)} onClick={() => {
                  const next = setMinBed(b, n)
                  setBedHint(next === b)
                  p.onFilterBudgetChange(next)
                }}>{bedLabel(n)}{n < 5 ? '+' : ''}</Pill>
              ))}
            </PillRow>
            {bedHint && <p className="m-0 mt-1 text-[0.7rem] text-amber-700">Your minimum stays at {bedLabel(minBeds(b.beds))}+ while a cap or down payment is set. Remove the requirement to turn the budget off.</p>}
            <div className="mt-2 flex flex-wrap gap-3">
              <label className="text-[0.7rem] text-[var(--hf-text-secondary)]">
                Down payment ($)
                <input
                  type="text" inputMode="numeric" autoComplete="off"
                  value={b.down == null ? '' : b.down.toLocaleString('en-US')}
                  placeholder="20% of price"
                  onChange={(e) => {
                    const digits = e.target.value.replace(/[^0-9]/g, '')
                    p.onFilterBudgetChange({ ...b, down: digits === '' ? null : parseInt(digits, 10), chosen: b.chosen || digits !== '' })
                  }}
                  className={inputCls}
                />
              </label>
              <label className="text-[0.7rem] text-[var(--hf-text-secondary)]">
                Max per month ($)
                <input
                  type="number" min={0} step={500}
                  value={b.max ?? ''}
                  placeholder="No limit"
                  onChange={(e) => {
                    const n = Number(e.target.value)
                    p.onFilterBudgetChange({ ...b, max: e.target.value !== '' && n > 0 ? n : null, chosen: true })
                  }}
                  className={inputCls}
                />
              </label>
            </div>
            {p.suggestedCaps.length > 0 && (
              <div className="mt-2"><PillRow>
                {p.suggestedCaps.map((c) => (
                  <Pill key={c.label} on={b.max === c.value} onClick={() => p.onFilterBudgetChange({ ...b, max: c.value, chosen: true })}>
                    {c.label} ${c.value.toLocaleString('en-US')}
                  </Pill>
                ))}
              </PillRow></div>
            )}
          </>
        )
      }
      case 'area':
        return <PillRow>{AREA_TYPE_OPTIONS.map((o) => <Pill key={o.value} on={p.filterAreaTypes.includes(o.value)} onClick={() => p.onFilterAreaTypesChange(toggleIn(p.filterAreaTypes, o.value))}>{o.label}</Pill>)}</PillRow>
      case 'stock':
        return (<><Cap>What the housing stock actually looks like. A place can match more than one.</Cap>
          <PillRow>{HOUSING_OPTIONS.map((o) => <Pill key={o.value} on={p.filterHousingType.includes(o.value)} onClick={() => p.onFilterHousingTypeChange(toggleIn(p.filterHousingType, o.value))}>{o.label}</Pill>)}</PillRow></>)
      case 'tenure':
        return (<><Cap>Based on the Census share of occupied units that are rented.</Cap>
          <PillRow>{TENURE_OPTIONS.map((o) => <Pill key={o.value} on={p.filterTenure.includes(o.value)} onClick={() => p.onFilterTenureChange(toggleIn(p.filterTenure, o.value))}>{o.label}</Pill>)}</PillRow></>)
      case 'climate':
        return (<><Cap>Hide places with:</Cap>
          <PillRow>{CLIMATE_MUST_HAVES.map(({ key, short, full }) => {
            const n = p.climateMustHaveFailCounts?.[key as string] ?? 0
            return <Pill key={key} title={full} on={Boolean(must[key])} onClick={() => p.onClimatePrefsChange({ ...p.climatePrefs, must_haves: { ...must, [key]: !must[key] } })}>{short}{must[key] && n > 0 ? ` · ${n}` : ''}</Pill>
          })}</PillRow></>)
      case 'scene':
        return (<><Cap>How much of a scene there is nearby (independent cafés, bars, galleries, bookstores, theaters), compared with similar places. Pick any levels.</Cap>
          <PillRow>{SCENE_FILTER_LEVELS.map((lv) => <Pill key={lv} on={p.filterLocalScene.includes(lv)} onClick={() => p.onFilterLocalSceneChange(toggleSceneLevel(p.filterLocalScene, lv))}>{SCENE_LABEL[lv]}</Pill>)}</PillRow></>)
      case 'trajectory':
        return <PillRow>{TRAJECTORY_OPTIONS.map((o) => <Pill key={o.value} on={p.filterTrajectory === o.value} onClick={() => p.onFilterTrajectoryChange(p.filterTrajectory === o.value ? 'all' : (o.value as 'Up-and-Coming' | 'Stable' | 'Declining'))}>{o.label}</Pill>)}</PillRow>
      case 'class':
        return <PillRow>{p.archetypes.map((a) => <Pill key={a} on={p.filterArchetypes.includes(a)} onClick={() => p.onFilterArchetypesChange(toggleIn(p.filterArchetypes, a))}>{displayArchetypeLabel(a)}</Pill>)}</PillRow>
      case 'politics':
        return (<><Cap>Only if you choose it.</Cap>
          <PillRow>{POLITICS_OPTIONS.map((o) => <Pill key={o.value} on={p.filterPoliticalLean.includes(o.value)} onClick={() => p.onFilterPoliticalLeanChange(toggleIn(p.filterPoliticalLean, o.value))}>{o.label}</Pill>)}</PillRow></>)
      case 'life':
        return (<><Cap>Chosen by you, never guessed.</Cap>
          <PillRow>{LIFE_OPTIONS.map((o) => <Pill key={o.value} on={p.filterLifeStage.includes(o.value)} onClick={() => p.onFilterLifeStageChange(toggleIn(p.filterLifeStage, o.value))}>{o.label}</Pill>)}</PillRow></>)
    }
  }

  const shown = REQ_GROUPS.flatMap((g) => g.ids).filter((id) => visible(id) && !(id === 'class' && p.archetypes.length === 0))
  const activeCount = Object.values(active).filter(Boolean).length

  function setLevel(key: string, level: PriorityLevel) {
    p.onPrioritiesChange({ ...p.priorities, [key]: level } as PillarPriorities)
  }
  const prioritiesChanged = JSON.stringify(p.priorities) !== JSON.stringify(DEFAULT_PRIORITIES)

  function LevelRow({ keyName, label, icon, info }: { keyName: string; label: string; icon: string; info?: PillarKey }) {
    const current = ((p.priorities as unknown as Record<string, PriorityLevel | undefined>)[keyName] ?? 'None') as PriorityLevel
    return (
      <div className="mb-1 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1 text-xs font-medium text-[var(--hf-text-primary)]">
          <span>{icon} {label}</span>
          {info && <PillarInfoIcon pillarKey={info} />}
        </div>
        <div className="flex gap-1">
          {LEVELS.map((lv) => (
            <button
              key={lv}
              type="button"
              aria-pressed={current === lv}
              className={`rounded-lg px-2 py-1 text-xs font-semibold transition-colors ${current === lv ? 'text-white' : 'bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)]'}`}
              style={current === lv ? { background: 'linear-gradient(135deg, var(--hf-primary-1), var(--hf-primary-2))' } : undefined}
              onClick={() => setLevel(keyName, lv)}
            >
              {lv}
            </button>
          ))}
        </div>
      </div>
    )
  }

  const gradesInRequirement = visible('schools')

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-end bg-black/40 sm:items-start sm:justify-end sm:pt-16"
      role="dialog"
      aria-modal="true"
      aria-labelledby="fit-panel-title"
      onClick={(e) => e.target === e.currentTarget && p.onClose()}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-md flex-col overflow-hidden rounded-t-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] shadow-[var(--hf-card-shadow)] sm:mr-4 sm:max-h-[calc(100vh-4rem)] sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-[var(--hf-border)] px-4 py-3">
          <div>
            <h2 id="fit-panel-title" className="m-0 text-base font-bold text-[var(--hf-text-primary)]">Make it yours</h2>
            <p className="m-0 mt-0.5 text-xs text-[var(--hf-text-secondary)]">Nothing is hidden until you add a requirement.</p>
          </div>
          <button type="button" className="rounded-lg p-2 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]" onClick={p.onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          <div className="mb-2 text-xs font-bold text-[var(--hf-text-primary)]">
            Must have <span className="font-normal text-[var(--hf-text-secondary)]">· hides places that don&apos;t fit</span>
          </div>

          {shown.length === 0 && <p className="m-0 mb-2 text-xs text-[var(--hf-text-secondary)]">Nothing required. Every place stays in the list.</p>}
          {shown.map((id) => (
            <div key={id} className="mb-2 rounded-xl border border-[var(--hf-border)] px-3 py-2.5">
              <div className="mb-1 flex items-center justify-between text-sm font-semibold text-[var(--hf-text-primary)]">
                <span>
                  {REQ_NAME[id]}
                  {active[id] && failCount(id) > 0 && (
                    <span className="ml-2 text-[0.7rem] font-normal text-[var(--hf-text-secondary)]">Hides {failCount(id)} places</span>
                  )}
                </span>
                <button type="button" aria-label={`Remove ${REQ_NAME[id]}`} className="rounded p-1 text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)]" onClick={() => removeReq(id)}>
                  <X className="h-4 w-4" />
                </button>
              </div>
              {renderBody(id)}
            </div>
          ))}

          {menuOpen ? (
            <div className="mb-1 rounded-xl border border-[var(--hf-border)] px-3 py-2">
              {REQ_GROUPS.map((g) => {
                const ids = g.ids.filter((id) => !visible(id) && !(id === 'class' && p.archetypes.length === 0))
                if (ids.length === 0) return null
                return (
                  <div key={g.title} className="mb-2">
                    <div className="mb-1 text-[0.7rem] text-[var(--hf-text-muted,var(--hf-text-secondary))]">{g.title}</div>
                    <PillRow>{ids.map((id) => <Pill key={id} on={false} onClick={() => addReq(id)}>{REQ_NAME[id]}</Pill>)}</PillRow>
                  </div>
                )
              })}
              <button type="button" className="text-xs font-semibold text-[var(--hf-text-secondary)]" onClick={() => setMenuOpen(false)}>Cancel</button>
            </div>
          ) : (
            <button
              type="button"
              className="rounded-full border border-[var(--hf-border-strong)] px-3 py-1 text-xs font-semibold text-[var(--hf-text-primary)] hover:bg-[var(--hf-hover-bg)]"
              onClick={() => setMenuOpen(true)}
            >
              + Add a requirement
            </button>
          )}

          {p.showMatters && (
            <>
              <div className="mb-1 mt-5 text-xs font-bold text-[var(--hf-text-primary)]">
                What matters <span className="font-normal text-[var(--hf-text-secondary)]">· ranks places, hides nothing</span>
              </div>
              <div className="mb-2 flex flex-wrap gap-x-3">
                {prioritiesChanged && (
                  <button type="button" className="text-xs font-semibold text-[var(--hf-primary-1)]" onClick={() => p.onPrioritiesChange({ ...DEFAULT_PRIORITIES })}>
                    Reset priorities
                  </button>
                )}
                {p.onTakeQuiz && (
                  <button type="button" className="text-xs font-semibold text-[var(--hf-primary-1)]" onClick={p.onTakeQuiz}>
                    Not sure what matters to you? Take the quiz →
                  </button>
                )}
              </div>

              {GROUPS.map((g) => (
                <details key={g.title} className="mb-2 rounded-xl border border-[var(--hf-border)]">
                  <summary className="cursor-pointer select-none px-3 py-2 text-sm font-bold text-[var(--hf-text-primary)]">
                    {g.title}
                    <span className="ml-2 text-[0.7rem] font-normal text-[var(--hf-text-secondary)]">
                      {(() => {
                        const changed = g.keys.filter((k) => p.priorities[k] !== DEFAULT_PRIORITIES[k])
                        if (changed.length === 0) return 'All at Medium'
                        const shown = changed.slice(0, 2).map((k) => `${PILLAR_META[k].name} ${p.priorities[k]}`).join(', ')
                        return changed.length > 2 ? `${shown} +${changed.length - 2} more` : shown
                      })()}
                    </span>
                  </summary>
                  <div className="space-y-3 border-t border-[var(--hf-border)] px-3 pb-3 pt-2">
                    {g.keys.map((key) => {
                      const meta = PILLAR_META[key]
                      const current = p.priorities[key]
                      return (
                        <div key={key}>
                          <LevelRow keyName={key} label={meta.name} icon={meta.icon} info={key} />
                          {key === 'natural_beauty' && current !== 'None' && (
                            <KindChips label="Which scenery? (blank = all)" options={NB_TYPE_OPTIONS} selected={p.filterNbTypes}
                              onToggle={(v) => p.onFilterNbTypesChange(toggleIn(p.filterNbTypes, v))} />
                          )}
                          {key === 'active_outdoors' && current !== 'None' && (
                            <KindChips label="Which kind? (blank = all)" options={AO_TYPE_OPTIONS} selected={p.filterAoTypes}
                              onToggle={(v) => p.onFilterAoTypesChange(toggleIn(p.filterAoTypes, v))} />
                          )}
                          {key === 'quality_education' && current !== 'None' && (
                            <>
                              <KindChips label="Which schools? (pick one or both)" options={SCHOOL_TYPE_OPTIONS} selected={schoolTypeSelected(p.filterSchoolType)}
                                onToggle={(v) => {
                                  const cur = schoolTypeSelected(p.filterSchoolType)
                                  const next = cur.includes(v as 'public' | 'charter') ? cur.filter((x) => x !== v) : [...cur, v as 'public' | 'charter']
                                  p.onFilterSchoolTypeChange(schoolTypeFromSelected(next.length ? next : ['public']))
                                }} />
                              {!gradesInRequirement && (
                                <KindChips label="Which grades? (pick any)" options={SCHOOL_LEVEL_OPTIONS} selected={p.filterSchoolLevels}
                                  onToggle={(v) => {
                                    const next = toggleIn(p.filterSchoolLevels, v)
                                    if (next.length) p.onFilterSchoolLevelsChange(next)
                                  }} />
                              )}
                            </>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </details>
              ))}

              <div className="mb-2 rounded-xl border border-[var(--hf-border)] px-3 py-2.5">
                <div className="mb-1 text-sm font-bold text-[var(--hf-text-primary)]">Personal</div>
                {PERSONAL_ROWS.map((row) => {
                  const available = row.key === 'commute_time' ? p.hasWorkHub : p.hasPeople
                  return available ? (
                    <div key={row.key} className="mb-2">
                      <LevelRow keyName={row.key} label={row.name} icon={row.icon} />
                      <p className="m-0 text-[0.7rem] text-[var(--hf-text-secondary)]">
                        {row.key === 'commute_time'
                          ? `To ${p.workZoneLabel ?? 'your work address'}. `
                          : `${p.peopleCount} ${p.peopleCount === 1 ? 'person' : 'people'} you want to live near. `}
                        <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">
                          {row.key === 'commute_time' ? 'Change in your profile' : 'Edit in your profile'}
                        </Link>
                      </p>
                    </div>
                  ) : (
                    <p key={row.key} className="m-0 mb-1 text-xs text-[var(--hf-text-secondary)]">
                      {row.icon} {row.needs}{' '}
                      <Link href="/profile" className="font-semibold text-[var(--hf-primary-1)]">Open your profile</Link>
                    </p>
                  )
                })}
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 border-t border-[var(--hf-border)] bg-[var(--hf-card-bg)] px-4 py-3">
          {activeCount > 0 && (
            <button
              type="button"
              className="shrink-0 text-sm font-semibold text-[var(--hf-text-secondary)]"
              onClick={() => { p.onClearRequirements(); setAdded([]) }}
            >
              Clear requirements
            </button>
          )}
          <button
            type="button"
            className="flex-1 rounded-full py-2.5 text-sm font-bold text-white"
            style={{ background: '#1a1a2e' }}
            onClick={p.onClose}
          >
            Show {p.resultCount} places
          </button>
        </div>
      </div>
    </div>
  )
}
