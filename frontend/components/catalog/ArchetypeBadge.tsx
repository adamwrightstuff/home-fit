'use client'

import { normalizeStatusArchetypeKey } from '@/lib/indexColorSystem'

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

export default function ArchetypeBadge({ archetype }: { archetype: string | null | undefined }) {
  if (!archetype?.trim()) return null
  const key = normalizeStatusArchetypeKey(archetype)
  const b = BADGE[key]
  return (
    <span
      className="inline-flex max-w-full items-center rounded-full px-2 py-0.5 text-[0.65rem] font-semibold"
      style={{ background: b.bg, color: b.fg }}
    >
      {archetype}
    </span>
  )
}
