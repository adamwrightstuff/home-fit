'use client'

import { useRef, useState } from 'react'
import InfoSheet from '@/components/catalog/InfoSheet'
import { INDEX_COPY } from '@/lib/catalogInfoCopy'

type IndexId = 'homefit' | 'longevity' | 'happiness' | 'status' | 'trajectory'

interface IndexInfoButtonProps {
  indexId: IndexId
}

const INDEX_KEY_MAP: Record<IndexId, string | null> = {
  homefit:    'homefit',
  longevity:  'longevity',
  happiness:  'happiness',
  status:     null, // handled by ArchetypeBadge / StatusSignalInfo
  trajectory: null, // handled by TrajectoryChip
}

export default function IndexInfoButton({ indexId }: IndexInfoButtonProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLButtonElement>(null)

  const copyKey = INDEX_KEY_MAP[indexId]
  const copy = copyKey ? INDEX_COPY[copyKey] : null
  if (!copy) return null

  return (
    <>
      <button
        ref={ref}
        type="button"
        aria-label={`Learn about ${copy.title}`}
        onClick={e => { e.stopPropagation(); setOpen(v => !v) }}
        style={{
          width: 15,
          height: 15,
          borderRadius: '50%',
          border: '1px solid #e5e7eb',
          background: '#f9fafb',
          fontSize: 9,
          color: '#9ca3af',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          cursor: 'pointer',
          padding: 0,
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
