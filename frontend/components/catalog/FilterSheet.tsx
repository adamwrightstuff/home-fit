'use client'

import { useEffect } from 'react'
import { displayArchetypeLabel } from '@/lib/statusSignalArchetype'
import { X } from 'lucide-react'

interface FilterSheetProps {
  open: boolean
  onClose: () => void
  filterMetro: 'all' | 'nyc' | 'la'
  onFilterMetroChange: (v: 'all' | 'nyc' | 'la') => void
  filterType: 'all' | 'neighborhood' | 'suburb'
  onFilterTypeChange: (v: 'all' | 'neighborhood' | 'suburb') => void
  filterArchetype: string
  onFilterArchetypeChange: (v: string) => void
  archetypes: string[]
  filterTrajectory: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining'
  onFilterTrajectoryChange: (v: 'all' | 'Arrived' | 'Up-and-Coming' | 'Stable' | 'Cooling' | 'Declining') => void
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
  filterType,
  onFilterTypeChange,
  filterArchetype,
  onFilterArchetypeChange,
  archetypes,
  filterTrajectory,
  onFilterTrajectoryChange,
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
    (filterType !== 'all' ? 1 : 0) +
    (filterArchetype !== 'all' ? 1 : 0) +
    (filterTrajectory !== 'all' ? 1 : 0)

  function handleClearAll() {
    onFilterMetroChange('all')
    onFilterTypeChange('all')
    onFilterArchetypeChange('all')
    onFilterTrajectoryChange('all')
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
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-[69] bg-black/40"
      />
      {/* Mobile: bottom sheet — Desktop: centered modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="filter-sheet-title"
        className="fixed z-[70] max-h-[85vh] overflow-y-auto bg-white
          bottom-0 left-0 right-0 rounded-t-2xl border-t border-gray-200
          md:bottom-auto md:left-1/2 md:right-auto md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2
          md:w-[480px] md:rounded-2xl md:border md:border-gray-200 md:shadow-xl"
      >
        {/* Handle bar — mobile only */}
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

          {/* Type */}
          <div style={{ marginBottom: 20 }}>
            <div style={LABEL_STYLE}>Type</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(['all', 'neighborhood', 'suburb'] as const).map((t) =>
                chip(filterType === t, t === 'all' ? 'All' : t === 'neighborhood' ? 'Neighborhood' : 'Suburb', () => onFilterTypeChange(t))
              )}
            </div>
          </div>

          {/* Class */}
          {archetypes.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={LABEL_STYLE}>Class</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {chip(filterArchetype === 'all', 'All classes', () => onFilterArchetypeChange('all'))}
                {archetypes.map((a) =>
                  chip(filterArchetype === a, displayArchetypeLabel(a), () => onFilterArchetypeChange(a))
                )}
              </div>
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

        </div>

        {/* Sticky footer */}
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
