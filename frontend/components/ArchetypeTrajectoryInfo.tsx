'use client'

import { useState } from 'react'
import { TRAJECTORY_COPY } from '@/lib/pillars'
import type { StatusSignalBreakdown } from '@/types/api'

interface ArchetypeTrajectoryInfoProps {
  breakdown?: StatusSignalBreakdown | null
  trajectory?: string | null
}

/**
 * Combined "?" button for Archetype + Trajectory in the score header bar.
 * Renders only when at least one of archetype or trajectory is present.
 * Covers both concepts in a single quick-reference modal.
 */
export default function ArchetypeTrajectoryInfo({ breakdown, trajectory }: ArchetypeTrajectoryInfoProps) {
  const [showModal, setShowModal] = useState(false)

  const hasArchetype = Boolean(breakdown?.status_label || breakdown?.archetype)
  const hasTrajectory = Boolean(trajectory)

  if (!hasArchetype && !hasTrajectory) return null

  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setShowModal(true) }}
        title="About Archetype & Trajectory"
        aria-label="What are Archetype and Trajectory?"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 20,
          height: 20,
          padding: 0,
          marginLeft: 4,
          borderRadius: '50%',
          border: '1px solid var(--hf-border)',
          background: 'var(--hf-bg-subtle)',
          color: 'var(--hf-text-secondary)',
          cursor: 'pointer',
          fontSize: '0.75rem',
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        ?
      </button>

      {showModal && (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="at-modal-title"
          onClick={() => setShowModal(false)}
        >
          <div
            className="tr-panel"
            style={{ maxWidth: 440, width: '100%', padding: '1.5rem 1.75rem', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="at-modal-title" style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
              Archetype &amp; Trajectory
            </h2>
            <p style={{ margin: '0.75rem 0 0', fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--hf-text-primary)' }}>
              Archetype describes a neighborhood&apos;s social character — who lives there, what they earn, what they do.
              Trajectory shows which way the market has moved over the past three years.
            </p>

            {/* Trajectory table */}
            <div style={{ marginTop: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {TRAJECTORY_COPY.tableRows.map(({ label, desc }) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--hf-text-primary)', minWidth: 110, flexShrink: 0 }}>
                      {label}
                    </span>
                    <span style={{ fontSize: '0.85rem', color: 'var(--hf-text-secondary)' }}>
                      {desc}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <p style={{ margin: '1.25rem 0 0', fontSize: '0.75rem', color: 'var(--hf-text-secondary)', lineHeight: 1.5 }}>
              Archetype based on Census ACS + Status Signal model. {TRAJECTORY_COPY.source}
            </p>

            <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="hf-btn-primary"
                style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem' }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
