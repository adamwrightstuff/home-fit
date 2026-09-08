'use client'

import { useRef, useState } from 'react'
import { TrajectoryIcon } from '@/components/catalog/TrajectoryChip'
import InfoSheet from '@/components/catalog/InfoSheet'
import { TRAJECTORY_COPY } from '@/lib/catalogInfoCopy'

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

export default function TrajectoryInfo({ trajectory }: TrajectoryInfoProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  const copy = trajectory ? TRAJECTORY_COPY[trajectory] : null
  const dotColor = trajectory ? (TRAJECTORY_DOT[trajectory] ?? '#64748b') : '#64748b'

  if (!trajectory) return null

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); if (copy) setOpen(true) }}
        aria-label="What is Trajectory?"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '0.15rem 0.5rem',
          marginLeft: 2,
          borderRadius: 99,
          border: '1px solid var(--hf-border)',
          background: 'var(--hf-bg-subtle)',
          color: 'var(--hf-text-primary)',
          cursor: copy ? 'pointer' : 'default',
          fontSize: '0.7rem',
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
        <TrajectoryIcon trajectory={trajectory} size={10} color={dotColor} />
        {trajectory}
      </button>
      {open && copy && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
