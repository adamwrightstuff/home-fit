'use client'

import { useRef, useState } from 'react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { AURA_COPY } from '@/lib/catalogInfoCopy'

export default function AuraBadge({
  itScore,
  compact = false,
  threshold = 75,
}: {
  itScore: number | null | undefined
  compact?: boolean
  threshold?: number
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  if (typeof itScore !== 'number' || !Number.isFinite(itScore) || itScore < threshold) return null

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(true) }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          height: compact ? 20 : 28,
          padding: compact ? '0 7px' : '0 10px',
          borderRadius: 99,
          fontSize: compact ? 11 : 13,
          fontWeight: 600,
          whiteSpace: 'nowrap',
          background: 'linear-gradient(135deg, #fdf4ff 0%, #ede9fe 100%)',
          color: '#6b21a8',
          border: '1px solid #e9d5ff',
          letterSpacing: '0.01em',
          cursor: 'pointer',
        }}
      >
        ✦ Aura
      </button>
      {open && (
        <InfoSheet copy={AURA_COPY} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
