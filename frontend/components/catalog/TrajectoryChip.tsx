'use client'

import { trajectoryOneLiner } from '@/lib/statusSignalArchetype'

const TRAJECTORY_STYLE: Record<string, { bg: string; fg: string; dot: string }> = {
  Arrived:          { bg: '#ede9fe', fg: '#3730a3', dot: '#4338ca' },
  'Up-and-Coming':  { bg: '#f0fdfa', fg: '#134e4a', dot: '#0f766e' },
  Stable:           { bg: '#f1f5f9', fg: '#334155', dot: '#64748b' },
  Cooling:          { bg: '#e0f2fe', fg: '#0c4a6e', dot: '#0369a1' },
  Declining:        { bg: '#ffe4e6', fg: '#881337', dot: '#be123c' },
}

export default function TrajectoryChip({
  trajectory,
  size = 'sm',
}: {
  trajectory: string | null | undefined
  size?: 'sm' | 'xs'
}) {
  if (!trajectory) return null
  const style = TRAJECTORY_STYLE[trajectory]
  if (!style) return null

  const fontSize = size === 'xs' ? '0.65rem' : '0.75rem'
  const padding = size === 'xs' ? '3px 8px 3px 6px' : '4px 10px 4px 7px'
  const dotSize = size === 'xs' ? 6 : 8

  return (
    <div
      className="inline-flex max-w-full items-center gap-1.5 rounded-full"
      style={{ padding, background: style.bg }}
      title={trajectoryOneLiner(trajectory)}
    >
      <span
        style={{ width: dotSize, height: dotSize, borderRadius: '50%', flexShrink: 0, background: style.dot }}
        aria-hidden
      />
      <span style={{ fontSize, fontWeight: 500, color: style.fg }}>{trajectory}</span>
    </div>
  )
}
