'use client'

import { useEffect } from 'react'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import { X } from 'lucide-react'

const AREA_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'urban_core', label: 'Urban Core' },
  { value: 'urban_residential', label: 'Urban Neighborhood' },
  { value: 'suburban', label: 'Suburban' },
  { value: 'exurban', label: 'Exurban' },
  { value: 'rural', label: 'Rural' },
]

const NB_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean / Coast' },
  { value: 'lakes_rivers', label: 'Lakes & Rivers' },
  { value: 'canopy', label: 'Tree Canopy' },
]

const AO_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'local_parks', label: 'Local Parks' },
  { value: 'trails_regional', label: 'Trails & Regional Parks' },
  { value: 'waterfront', label: 'Waterfront' },
]

interface FilterSheetProps {
  open: boolean
  onClose: () => void
  filterMetro: 'all' | 'nyc' | 'la'
  onFilterMetroChange: (v: 'all' | 'nyc' | 'la') => void
  filterAreaTypes: string[]
  onFilterAreaTypesChange: (v: string[]) => void
  filterArchetypes: string[]
  onFilterArchetypesChange: (v: string[]) => void
  archetypes: string[]
  filterTrajectory: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'
  onFilterTrajectoryChange: (v: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining') => void
  filterPoliticalLean: string[]
  onFilterPoliticalLeanChange: (v: string[]) => void
  filterNbTypes: string[]
  onFilterNbTypesChange: (v: string[]) => void
  filterAoTypes: string[]
  onFilterAoTypesChange: (v: string[]) => void
  filterSchoolType: 'any' | 'public_only' | 'charter'
  onFilterSchoolTypeChange: (v: 'any' | 'public_only' | 'charter') => void
  filterLocalScene: 'all' | 'Some' | 'High'
  onFilterLocalSceneChange: (v: 'all' | 'Some' | 'High') => void
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
  filterNbTypes,
  onFilterNbTypesChange,
  filterAoTypes,
  onFilterAoTypesChange,
  filterSchoolType,
  onFilterSchoolTypeChange,
  filterLocalScene,
  onFilterLocalSceneChange,
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
    (filterNbTypes.length > 0 ? 1 : 0) +
    (filterAoTypes.length > 0 ? 1 : 0) +
    (filterSchoolType !== 'any' ? 1 : 0) +
    (filterLocalScene !== 'all' ? 1 : 0)

  function handleClearAll() {
    onFilterMetroChange('all')
    onFilterAreaTypesChange([])
    onFilterArchetypesChange([])
    onFilterTrajectoryChange('all')
    onFilterPoliticalLeanChange([])
    onFilterNbTypesChange([])
    onFilterAoTypesChange([])
    onFilterSchoolTypeChange('any')
    onFilterLocalSceneChange('all')
  }

  function toggleAreaType(value: string) {
    if (filterAreaTypes.includes(value)) {
      onFilterAreaTypesChange(filterAreaTypes.filter((v) => v !== value))
    } else {
      onFilterAreaTypesChange([...filterAreaTypes, value])
    }
  }

  function toggleNbType(value: string) {
    if (filterNbTypes.includes(value)) {
      onFilterNbTypesChange(filterNbTypes.filter((v) => v !== value))
    } else {
      onFilterNbTypesChange([...filterNbTypes, value])
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
          {/* Metro */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Metro</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(['all', 'nyc', 'la'] as const).map((m) =>
                chip(filterMetro === m, m === 'all' ? 'All metros' : m.toUpperCase(), () => onFilterMetroChange(m))
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

          {/* Scenery type */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Scenery (select multiple)</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {NB_TYPE_OPTIONS.map(({ value, label }) =>
                chip(filterNbTypes.includes(value), label, () => toggleNbType(value))
              )}
            </div>
            {filterNbTypes.length > 0 && (
              <button
                type="button"
                onClick={() => onFilterNbTypesChange([])}
                style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Active Outdoors type */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Active Outdoors (select multiple)</div>
            <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
              Reweights the Active Outdoors score toward your selected dimensions.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {AO_TYPE_OPTIONS.map(({ value, label }) =>
                chip(filterAoTypes.includes(value), label, () => {
                  if (filterAoTypes.includes(value)) {
                    onFilterAoTypesChange(filterAoTypes.filter((v) => v !== value))
                  } else {
                    onFilterAoTypesChange([...filterAoTypes, value])
                  }
                })
              )}
            </div>
            {filterAoTypes.length > 0 && (
              <button
                type="button"
                onClick={() => onFilterAoTypesChange([])}
                style={{ marginTop: 6, fontSize: 11, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Clear
              </button>
            )}
          </div>

          {/* School type */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Schools</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterSchoolType === 'any', 'Any', () => onFilterSchoolTypeChange('any'))}
              {chip(filterSchoolType === 'public_only', 'Public only', () => onFilterSchoolTypeChange(filterSchoolType === 'public_only' ? 'any' : 'public_only'))}
              {chip(filterSchoolType === 'charter', 'Charter', () => onFilterSchoolTypeChange(filterSchoolType === 'charter' ? 'any' : 'charter'))}
            </div>
          </div>

          {/* Political lean */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Political Lean</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {chip(filterPoliticalLean.length === 0, 'All', () => onFilterPoliticalLeanChange([]))}
              {chip(filterPoliticalLean.includes('progressive'), '🔵 Progressive', () => onFilterPoliticalLeanChange(filterPoliticalLean.includes('progressive') ? filterPoliticalLean.filter(v => v !== 'progressive') : [...filterPoliticalLean, 'progressive']))}
              {chip(filterPoliticalLean.includes('moderate'), '🟣 Moderate', () => onFilterPoliticalLeanChange(filterPoliticalLean.includes('moderate') ? filterPoliticalLean.filter(v => v !== 'moderate') : [...filterPoliticalLean, 'moderate']))}
              {chip(filterPoliticalLean.includes('conservative'), '🔴 Conservative', () => onFilterPoliticalLeanChange(filterPoliticalLean.includes('conservative') ? filterPoliticalLean.filter(v => v !== 'conservative') : [...filterPoliticalLean, 'conservative']))}
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
