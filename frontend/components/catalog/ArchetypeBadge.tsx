'use client'

import { normalizeStatusArchetypeKey } from '@/lib/indexColorSystem'
import { getStatusBadgeModel } from '@/lib/statusSignalArchetype'

const BADGE: Record<
  ReturnType<typeof normalizeStatusArchetypeKey>,
  { bg: string; fg: string }
> = {
  patrician: { bg: '#EEEDFE', fg: '#3C3489' },
  parvenu: { bg: '#FFF3CD', fg: '#7B5800' },
  poseur: { bg: '#FAECE7', fg: '#712B13' },
  plebeian: { bg: '#F1EFE8', fg: '#444441' },
  typical: { bg: '#E9F1F8', fg: '#1A4A6B' },
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
