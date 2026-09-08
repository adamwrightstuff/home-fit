'use client'

import { useEffect, useRef, useState, type RefObject } from 'react'
import { useIsMobile } from '@/hooks/useIsMobile'
import type { InfoCopy } from '@/lib/catalogInfoCopy'

interface InfoSheetProps {
  copy: InfoCopy
  anchorRef: RefObject<HTMLElement>
  onClose: () => void
}

function BottomSheet({ copy, onClose }: { copy: InfoCopy; onClose: () => void }) {
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--hf-card-bg, #fff)', borderRadius: '16px 16px 0 0', padding: '0 1.25rem 2rem', boxShadow: '0 -4px 32px rgba(0,0,0,0.12)', maxHeight: '60vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'center', padding: '0.75rem 0 0.5rem' }}>
          <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--hf-border, #e2e8f0)' }} />
        </div>
        <h3 style={{ margin: '0.5rem 0 0.75rem', fontSize: '1.05rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
          {copy.title}
        </h3>
        <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.6, color: 'var(--hf-text-secondary)' }}>
          {copy.body}
        </p>
        <button
          type="button"
          onClick={() => setDetailOpen(o => !o)}
          style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', padding: 0, fontSize: '0.78rem', fontWeight: 600, color: 'var(--hf-text-tertiary)', cursor: 'pointer', letterSpacing: '0.02em' }}
        >
          <span style={{ display: 'inline-block', transform: detailOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>›</span>
          How we calculate this
        </button>
        {detailOpen && (
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', lineHeight: 1.55, color: 'var(--hf-text-tertiary)' }}>
            {copy.detail}
          </p>
        )}
      </div>
    </div>
  )
}

function Popover({ copy, anchorRef, onClose }: InfoSheetProps) {
  const popRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    if (!anchorRef.current) return
    const r = anchorRef.current.getBoundingClientRect()
    const above = r.top > 260
    setPos({
      top: above ? r.top - 8 : r.bottom + 8,
      left: Math.min(r.left, window.innerWidth - 296),
      above,
    })
  }, [anchorRef])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    const onClick = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [onClose])

  if (!pos) return null

  return (
    <div
      ref={popRef}
      style={{
        position: 'fixed',
        top: pos.above ? undefined : pos.top,
        bottom: pos.above ? window.innerHeight - pos.top : undefined,
        left: pos.left,
        zIndex: 9999,
        width: 280,
        background: 'var(--hf-card-bg, #fff)',
        borderRadius: 12,
        padding: '1rem 1.1rem 1rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.14), 0 0 0 1px rgba(0,0,0,0.06)',
      }}
    >
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
        {copy.title}
      </h3>
      <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--hf-text-secondary)' }}>
        {copy.body}
      </p>
      <button
        type="button"
        onClick={() => setDetailOpen(o => !o)}
        style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: 4, background: 'none', border: 'none', padding: 0, fontSize: '0.72rem', fontWeight: 600, color: 'var(--hf-text-tertiary)', cursor: 'pointer', letterSpacing: '0.02em' }}
      >
        <span style={{ display: 'inline-block', transform: detailOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>›</span>
        How we calculate this
      </button>
      {detailOpen && (
        <p style={{ margin: '0.4rem 0 0', fontSize: '0.74rem', lineHeight: 1.55, color: 'var(--hf-text-tertiary)' }}>
          {copy.detail}
        </p>
      )}
    </div>
  )
}

export default function InfoSheet({ copy, anchorRef, onClose }: InfoSheetProps) {
  const isMobile = useIsMobile()
  if (isMobile) return <BottomSheet copy={copy} onClose={onClose} />
  return <Popover copy={copy} anchorRef={anchorRef} onClose={onClose} />
}
