'use client'

import { useRef, useState } from 'react'
import type { StatusSignalBreakdown } from '@/types/api'
import InfoSheet from '@/components/catalog/InfoSheet'
import { ARCHETYPE_COPY, TRAJECTORY_COPY } from '@/lib/catalogInfoCopy'

interface ArchetypeTrajectoryInfoProps {
  breakdown?: StatusSignalBreakdown | null
  trajectory?: string | null
}

export default function ArchetypeTrajectoryInfo({ breakdown, trajectory }: ArchetypeTrajectoryInfoProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  const hasArchetype = Boolean(breakdown?.status_label || breakdown?.archetype)
  const hasTrajectory = Boolean(trajectory)

  if (!hasArchetype && !hasTrajectory) return null

  const archetype = breakdown?.archetype ?? null
  const archetypeCopy = archetype ? ARCHETYPE_COPY[archetype] : null
  const trajectoryCopy = trajectory ? TRAJECTORY_COPY[trajectory] : null

  // Prefer trajectory copy if both exist; fall back to archetype
  const copy = trajectoryCopy ?? archetypeCopy
  if (!copy) return null

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(true) }}
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
      {open && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
