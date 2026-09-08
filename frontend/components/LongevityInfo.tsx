'use client'

import { useRef, useState } from 'react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { INDEX_COPY } from '@/lib/catalogInfoCopy'

export default function LongevityInfo() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(true) }}
        aria-label="What is the Longevity Score?"
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 18, height: 18, padding: 0, marginLeft: 4, borderRadius: '50%',
          border: '1px solid var(--hf-border)', background: 'var(--hf-bg-subtle)',
          color: 'var(--hf-text-secondary)', cursor: 'pointer', fontSize: '0.7rem', fontWeight: 700, flexShrink: 0,
        }}
      >
        ?
      </button>
      {open && (
        <InfoSheet copy={INDEX_COPY.longevity} anchorRef={ref} onClose={() => setOpen(false)} />
      )}
    </>
  )
}
