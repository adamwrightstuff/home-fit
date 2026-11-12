'use client'

import { useRef, useState } from 'react'
import { Wine } from 'lucide-react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { SCENE_COPY } from '@/lib/catalogInfoCopy'
import { SCENE_LABEL, isSceneLevel, type SceneLevel } from '@/lib/sceneLevels'

const STYLE: Record<SceneLevel, { bg: string; fg: string; icon: string }> = {
  buzzing: { bg: '#fef3c7', fg: '#92400e', icon: '#d97706' },
  lively: { bg: '#fef9c3', fg: '#854d0e', icon: '#ca8a04' },
  low_key: { bg: '#f1f5f9', fg: '#334155', icon: '#64748b' },
  quiet: { bg: '#f8fafc', fg: '#94a3b8', icon: '#cbd5e1' },
}

export default function LocalSceneChip({
  level,
  compact = false,
}: {
  level: string | null | undefined
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  if (!isSceneLevel(level)) return null
  const style = STYLE[level]
  const copy = SCENE_COPY[level]

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(true) }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 4 : 5,
          height: compact ? 20 : 28,
          padding: compact ? '0 7px' : '0 10px',
          borderRadius: 99,
          background: compact ? '#f1f5f9' : style.bg,
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        <Wine size={compact ? 10 : 13} style={{ flexShrink: 0, color: style.icon }} />
        <span style={{ fontSize: compact ? 11 : 13, fontWeight: 500, color: compact ? '#475569' : style.fg }}>
          {SCENE_LABEL[level]}
        </span>
      </button>
      {open && copy && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
