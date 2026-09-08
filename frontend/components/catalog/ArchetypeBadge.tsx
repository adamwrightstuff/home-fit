'use client'

import { useRef, useState } from 'react'
import { normalizeStatusArchetypeKey } from '@/lib/indexColorSystem'
import { getStatusBadgeModel } from '@/lib/statusSignalArchetype'
import InfoSheet from '@/components/catalog/InfoSheet'
import { ARCHETYPE_COPY } from '@/lib/catalogInfoCopy'

const BADGE: Record<
  ReturnType<typeof normalizeStatusArchetypeKey>,
  { bg: string; fg: string }
> = {
  elite:        { bg: '#EEEDFE', fg: '#3C3489' },
  affluent:     { bg: '#FFF3CD', fg: '#7B5800' },
  middle: { bg: '#E2E8F0', fg: '#334155' },
  working:{ bg: '#F1EFE8', fg: '#444441' },
  struggling:   { bg: '#E7E5E4', fg: '#292524' },
  transitional: { bg: '#F0FDF9', fg: '#134E4A' },
  wealthy:      { bg: '#EEEDFE', fg: '#3C3489' },
  well_off:     { bg: '#FFF3CD', fg: '#7B5800' },
  modest:       { bg: '#F1EFE8', fg: '#444441' },
}

export default function ArchetypeBadge({
  archetype,
  breakdown,
  compositeScore,
  compact = false,
}: {
  archetype: string | null | undefined
  breakdown?: { archetype?: string; signal_strength_label?: string; classifier_inputs?: Record<string, unknown> } | null
  compositeScore?: number | null
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  if (!archetype?.trim() && !breakdown) return null
  const key = normalizeStatusArchetypeKey(archetype ?? breakdown?.archetype ?? null)
  const b = BADGE[key]
  const badge = getStatusBadgeModel((breakdown ?? { archetype }) as any, compositeScore ?? null)
  const isMixed = badge.variant !== 'named'
  const archetypeKey = archetype ?? breakdown?.archetype ?? null
  const copy = archetypeKey ? ARCHETYPE_COPY[archetypeKey] : null

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); if (copy) setOpen(true) }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: compact ? 20 : 28,
          padding: compact ? '0 7px' : '0 10px',
          borderRadius: 99,
          fontSize: compact ? 11 : 13,
          fontWeight: 500,
          whiteSpace: 'nowrap',
          background: isMixed ? 'transparent' : b.bg,
          color: b.fg,
          border: isMixed ? '1px solid rgba(100, 116, 139, 0.5)' : '1px solid transparent',
          cursor: copy ? 'pointer' : 'default',
        }}
      >
        {badge.text}
      </button>
      {open && copy && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
