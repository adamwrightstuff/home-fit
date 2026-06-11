'use client'

import { useState } from 'react'
import { TrendingUp, TrendingDown, Minus, ArrowDown, Circle } from 'lucide-react'
import { trajectoryExplainer } from '@/lib/statusSignalArchetype'

const TRAJECTORY_STYLE: Record<string, { bg: string; fg: string; dot: string }> = {
  Arrived:          { bg: '#ede9fe', fg: '#3730a3', dot: '#4338ca' },
  'Up-and-Coming':  { bg: '#f0fdfa', fg: '#134e4a', dot: '#0f766e' },
  Stable:           { bg: '#f1f5f9', fg: '#334155', dot: '#64748b' },
  Cooling:          { bg: '#e0f2fe', fg: '#0c4a6e', dot: '#0369a1' },
  Declining:        { bg: '#ffe4e6', fg: '#881337', dot: '#be123c' },
}

function TrajectoryIcon({ trajectory, size = 12, color }: { trajectory: string; size?: number; color: string }) {
  const s = { width: size, height: size, flexShrink: 0 as const, color }
  switch (trajectory) {
    case 'Arrived':       return <Circle size={size} style={{ ...s, fill: color, stroke: 'none' }} />
    case 'Up-and-Coming': return <TrendingUp size={size} style={s} />
    case 'Stable':        return <Minus size={size} style={s} />
    case 'Cooling':       return <TrendingDown size={size} style={s} />
    case 'Declining':     return <ArrowDown size={size} style={s} />
    default:              return null
  }
}

export { TrajectoryIcon }

export default function TrajectoryChip({
  trajectory,
  size = 'sm',
  interactive = false,
}: {
  trajectory: string | null | undefined
  size?: 'sm' | 'xs'
  /** When true, clicking the pill opens the Trajectory detail modal. False for catalog/public display-only use. */
  interactive?: boolean
}) {
  const [showModal, setShowModal] = useState(false)

  if (!trajectory) return null
  const style = TRAJECTORY_STYLE[trajectory]
  if (!style) return null

  const exp = trajectoryExplainer(trajectory)
  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); if (interactive && exp) setShowModal(true) }}
        title={exp?.signals}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          height: 28,
          padding: '0 10px',
          borderRadius: 99,
          background: style.bg,
          border: 'none',
          cursor: interactive && exp ? 'pointer' : 'default',
          whiteSpace: 'nowrap',
        }}
      >
        {/* Icon: explicit font-size: 13px prevents parent font-size inheritance */}
        <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: 13, flexShrink: 0 }}>
          <TrajectoryIcon trajectory={trajectory} size={13} color={style.dot} />
        </span>
        {/* Hidden on mobile (≤768px) via globals.css .tr-trajectory-label */}
        <span className="tr-trajectory-label" style={{ fontSize: 13, fontWeight: 500, color: style.fg }}>
          {trajectory}
        </span>
      </button>

      {showModal && exp && (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="traj-chip-modal-title"
          onClick={(e) => { e.stopPropagation(); setShowModal(false) }}
        >
          <div
            className="tr-panel"
            style={{ maxWidth: 400, width: '100%', padding: '1.5rem 1.75rem', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.75rem' }}>
              <TrajectoryIcon trajectory={trajectory} size={16} color={style.dot} />
              <h2 id="traj-chip-modal-title" style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                Trajectory — {exp.headline}
              </h2>
            </div>
            <p style={{ margin: 0, fontSize: '0.92rem', lineHeight: 1.6, color: 'var(--hf-text-primary)' }}>
              {exp.body}
            </p>
            <p style={{ margin: '1rem 0 0', fontSize: '0.75rem', color: 'var(--hf-text-secondary)' }}>
              Based on 3-year home value trend data.
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
