'use client'

import { useState, useRef, useCallback } from 'react'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

interface PillarInfoIconProps {
  pillarKey: PillarKey
}

export default function PillarInfoIcon({ pillarKey }: PillarInfoIconProps) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const description = PILLAR_META[pillarKey].description

  const open = useCallback(() => {
    if (!btnRef.current) return
    const r = btnRef.current.getBoundingClientRect()
    setPos({ x: r.left + r.width / 2, y: r.top })
  }, [])

  const close = useCallback(() => setPos(null), [])

  const toggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (pos) close()
    else open()
  }, [pos, open, close])

  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}>
      <button
        ref={btnRef}
        type="button"
        aria-label={`About ${PILLAR_META[pillarKey].name}`}
        onMouseEnter={open}
        onMouseLeave={close}
        onClick={toggle}
        style={{
          width: 15,
          height: 15,
          borderRadius: '50%',
          border: '1px solid var(--hf-border)',
          background: 'var(--hf-bg-subtle)',
          fontSize: '0.6rem',
          fontWeight: 800,
          color: 'var(--hf-text-secondary)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          lineHeight: 1,
          padding: 0,
        }}
      >
        ?
      </button>
      {pos && (
        <span
          role="tooltip"
          style={{
            position: 'fixed',
            bottom: `calc(100vh - ${pos.y - 8}px)`,
            left: pos.x,
            transform: 'translateX(-50%)',
            background: 'var(--hf-bg-panel, var(--hf-card-bg))',
            border: '1px solid var(--hf-border)',
            borderRadius: 8,
            padding: '8px 11px',
            fontSize: '0.8rem',
            lineHeight: 1.45,
            color: 'var(--hf-text-primary)',
            width: 230,
            zIndex: 9999,
            boxShadow: '0 4px 16px rgba(0,0,0,0.16)',
            pointerEvents: 'none',
            fontWeight: 400,
          }}
        >
          {description}
        </span>
      )}
    </span>
  )
}
