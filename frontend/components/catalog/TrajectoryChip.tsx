'use client'

import { useRef, useState } from 'react'
import { TrendingUp, TrendingDown, Minus, ArrowDown, Circle } from 'lucide-react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { TRAJECTORY_COPY } from '@/lib/catalogInfoCopy'

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
  compact = false,
}: {
  trajectory: string | null | undefined
  size?: 'sm' | 'xs'
  interactive?: boolean
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  if (!trajectory) return null
  const style = TRAJECTORY_STYLE[trajectory]
  if (!style) return null
  const copy = TRAJECTORY_COPY[trajectory]

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); if (copy) setOpen(true) }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 4 : 5,
          height: compact ? 20 : 28,
          padding: compact ? '0 7px' : '0 10px',
          borderRadius: 99,
          background: compact ? '#f1f5f9' : style.bg,
          border: 'none',
          cursor: copy ? 'pointer' : 'default',
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}>
          <TrajectoryIcon trajectory={trajectory} size={compact ? 10 : 13} color={style.dot} />
        </span>
        <span className="tr-trajectory-label" style={{ fontSize: compact ? 11 : 13, fontWeight: 500, color: compact ? '#475569' : style.fg }}>
          {trajectory}
        </span>
      </button>
      {open && copy && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
