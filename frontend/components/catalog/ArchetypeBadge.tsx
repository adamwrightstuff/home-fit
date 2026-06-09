'use client'

import { normalizeStatusArchetypeKey } from '@/lib/indexColorSystem'
import { getStatusBadgeModel } from '@/lib/statusSignalArchetype'

const BADGE: Record<
  ReturnType<typeof normalizeStatusArchetypeKey>,
  { bg: string; fg: string }
> = {
  wealthy:      { bg: '#EEEDFE', fg: '#3C3489' },
  well_off:     { bg: '#FFF3CD', fg: '#7B5800' },
  middle_class: { bg: '#E2E8F0', fg: '#334155' },
  modest:       { bg: '#FEF3C7', fg: '#7A5C38' },
  working_class:{ bg: '#F1EFE8', fg: '#444441' },
  struggling:   { bg: '#E7E5E4', fg: '#292524' },
  transitional: { bg: '#F0FDF9', fg: '#134E4A' },
}

export default function ArchetypeBadge({
  archetype,
  breakdown,
  compositeScore,
}: {
  archetype: string | null | undefined
  breakdown?: { archetype?: string; signal_strength_label?: string; classifier_inputs?: Record<string, unknown> } | null
  compositeScore?: number | null
}) {
  if (!archetype?.trim() && !breakdown) return null
  const key = normalizeStatusArchetypeKey(archetype ?? breakdown?.archetype ?? null)
  const b = BADGE[key]
  const badge = getStatusBadgeModel((breakdown ?? { archetype }) as any, compositeScore ?? null)
  const isMixed = badge.variant !== 'named'
  return (
    <span
      className="inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[0.65rem] font-semibold"
      style={{
        background: isMixed ? 'transparent' : b.bg,
        color: b.fg,
        border: isMixed ? '1px solid rgba(100, 116, 139, 0.5)' : '1px solid transparent',
      }}
    >
      {badge.text}
    </span>
  )
}
