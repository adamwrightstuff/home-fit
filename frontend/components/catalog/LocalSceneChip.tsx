'use client'

import { useRef, useState } from 'react'
import { Wine } from 'lucide-react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { SCENE_COPY } from '@/lib/catalogInfoCopy'

type Bucket = 'High' | 'Some' | 'Low'

const STYLE: Record<Bucket, { bg: string; fg: string; icon: string }> = {
  High: { bg: '#fef3c7', fg: '#92400e', icon: '#d97706' },
  Some: { bg: '#f1f5f9', fg: '#334155', icon: '#64748b' },
  Low:  { bg: '#f8fafc', fg: '#94a3b8', icon: '#cbd5e1' },
}

const LABEL: Record<Bucket, string> = {
  High: 'Vibrant Scene',
  Some: 'Some Scene',
  Low:  'Quiet Area',
}

const SCENE_BUCKET_KEY: Record<Bucket, string> = {
  High: 'High',
  Some: 'Some',
  Low:  'Low',
}

export default function LocalSceneChip({
  bucket,
  compact = false,
}: {
  bucket: string | null | undefined
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  if (!bucket) return null
  const style = STYLE[bucket as Bucket]
  if (!style) return null
  const copy = SCENE_COPY[SCENE_BUCKET_KEY[bucket as Bucket]]

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
          {LABEL[bucket as Bucket]}
        </span>
      </button>
      {open && copy && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
