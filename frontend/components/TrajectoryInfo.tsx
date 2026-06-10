'use client'

import { useState } from 'react'
import { TRAJECTORY_COPY } from '@/lib/pillars'
import { trajectoryExplainer } from '@/lib/statusSignalArchetype'
import { TrajectoryIcon } from '@/components/catalog/TrajectoryChip'

const TRAJECTORY_DOT: Record<string, string> = {
  Arrived:          '#4338ca',
  'Up-and-Coming':  '#0f766e',
  Stable:           '#64748b',
  Cooling:          '#0369a1',
  Declining:        '#be123c',
}

interface TrajectoryInfoProps {
  trajectory?: string | null
}

/** "?" button + modal for Trajectory. Use next to the Trajectory label in the score header. */
export default function TrajectoryInfo({ trajectory }: TrajectoryInfoProps) {
  const [showModal, setShowModal] = useState(false)

  const exp = trajectory ? trajectoryExplainer(trajectory) : null
  const dotColor = trajectory ? (TRAJECTORY_DOT[trajectory] ?? '#64748b') : '#64748b'

  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setShowModal(true) }}
        title={TRAJECTORY_COPY.tooltip}
        aria-label="What is Trajectory?"
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
          aria-labelledby="trajectory-modal-title"
          aria-describedby="trajectory-modal-desc"
          onClick={() => setShowModal(false)}
        >
          <div
            className="tr-panel"
            style={{ maxWidth: 420, width: '100%', padding: '1.5rem 1.75rem', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.75rem' }}>
              {trajectory && <TrajectoryIcon trajectory={trajectory} size={18} color={dotColor} />}
              <h2
                id="trajectory-modal-title"
                style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}
              >
                Trajectory{exp ? ` — ${exp.headline}` : ''}
              </h2>
            </div>

            {exp ? (
              <p id="trajectory-modal-desc" style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--hf-text-primary)' }}>
                {exp.body}
              </p>
            ) : (
              <>
                <p id="trajectory-modal-desc" style={{ margin: 0, fontSize: '0.95rem', lineHeight: 1.55, color: 'var(--hf-text-primary)' }}>
                  {TRAJECTORY_COPY.tooltip}
                </p>
                <div style={{ marginTop: '1rem' }}>
                  {TRAJECTORY_COPY.tableRows.map(({ label, desc }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--hf-text-primary)', minWidth: 110 }}>{label}</span>
                      <span style={{ fontSize: '0.8rem', color: 'var(--hf-text-secondary)' }}>{desc}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            <p style={{ margin: '0.75rem 0 0', fontSize: '0.75rem', color: 'var(--hf-text-secondary)' }}>
              {TRAJECTORY_COPY.source}
            </p>

            <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button type="button" onClick={() => setShowModal(false)} className="hf-btn-primary" style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem' }}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
