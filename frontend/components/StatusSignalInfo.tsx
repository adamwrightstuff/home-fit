'use client'

import { useRef, useState } from 'react'
import { STATUS_SIGNAL_COPY } from '@/lib/pillars'
import type { StatusSignalBreakdown } from '@/types/api'
import { getStatusBadgeModel, statusTooltipCopy } from '@/lib/statusSignalArchetype'
import { normalizeStatusArchetypeKey } from '@/lib/indexColorSystem'
import InfoSheet from '@/components/catalog/InfoSheet'
import { ARCHETYPE_COPY, type InfoCopy } from '@/lib/catalogInfoCopy'

const BADGE: Record<
  ReturnType<typeof normalizeStatusArchetypeKey>,
  { bg: string; fg: string }
> = {
  elite:        { bg: '#EEEDFE', fg: '#3C3489' },
  affluent:     { bg: '#FFF3CD', fg: '#7B5800' },
  middle:       { bg: '#E2E8F0', fg: '#334155' },
  working:      { bg: '#F1EFE8', fg: '#444441' },
  struggling:   { bg: '#E7E5E4', fg: '#292524' },
  transitional: { bg: '#F0FDF9', fg: '#134E4A' },
  wealthy:      { bg: '#EEEDFE', fg: '#3C3489' },
  well_off:     { bg: '#FFF3CD', fg: '#7B5800' },
  modest:       { bg: '#F1EFE8', fg: '#444441' },
}

export interface StatusSignalInfoProps {
  onRefresh?: () => void | Promise<void>
  refreshing?: boolean
  breakdown?: StatusSignalBreakdown | null
  compositeScore?: number | null
  isSignedIn?: boolean
  savedScoreId?: string | null
  allowDetailModal?: boolean
}

export default function StatusSignalInfo({
  onRefresh,
  refreshing = false,
  breakdown,
  compositeScore = null,
  isSignedIn,
  savedScoreId,
  allowDetailModal = true,
}: StatusSignalInfoProps) {
  const showRefresh = onRefresh != null && isSignedIn === true && !!savedScoreId
  const [open, setOpen] = useState(false)
  const [showRefreshModal, setShowRefreshModal] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const ref = useRef<HTMLButtonElement>(null)

  if (!breakdown?.status_label) return null

  const archetype = breakdown?.archetype ?? 'Working Class'
  const key = normalizeStatusArchetypeKey(archetype)
  const b = BADGE[key]
  const badgeModel = getStatusBadgeModel(breakdown ?? null, compositeScore)
  const helpCopy = statusTooltipCopy(breakdown ?? null, compositeScore)

  const copy: InfoCopy = {
    title: archetype,
    body: (breakdown as { llm_summary?: string } | null)?.llm_summary ?? helpCopy ?? breakdown?.status_insight ?? ARCHETYPE_COPY[archetype]?.body ?? STATUS_SIGNAL_COPY.full,
    detail: breakdown?.top_drivers?.length
      ? 'Top drivers: ' + breakdown.top_drivers.map(d => `${d.label} (${d.score})`).join(', ')
      : (ARCHETYPE_COPY[archetype]?.detail ?? ''),
  }

  const badgeStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '0.2rem 0.5rem',
    marginLeft: 6,
    borderRadius: 6,
    fontSize: '0.7rem',
    fontWeight: 600,
    background: badgeModel.variant === 'named' ? b.bg : 'transparent',
    color: b.fg,
    border: badgeModel.variant === 'named' ? '1px solid transparent' : '1px solid var(--hf-border)',
    cursor: allowDetailModal ? 'pointer' : 'default',
  }

  if (!allowDetailModal) {
    return (
      <span style={badgeStyle}>
        {badgeModel.text}
      </span>
    )
  }

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={e => {
          e.stopPropagation()
          if (showRefresh) {
            setRefreshError(null)
            setShowRefreshModal(true)
          } else {
            setOpen(true)
          }
        }}
        aria-label={`Archetype: ${badgeModel.text}. Click for details.`}
        style={badgeStyle}
      >
        {badgeModel.text}
      </button>

      {open && !showRefresh && (
        <InfoSheet copy={copy} anchorRef={ref} onClose={() => setOpen(false)} />
      )}

      {showRefreshModal && showRefresh && (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={() => { setRefreshError(null); setShowRefreshModal(false) }}
        >
          <div
            className="tr-panel"
            style={{ maxWidth: 420, width: '100%', padding: '1.5rem 1.75rem', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
              Archetype
              {breakdown?.archetype && (
                <span style={{ marginLeft: 8, fontSize: '0.85rem', fontWeight: 600, color: 'var(--hf-text-secondary)' }}>
                  — {breakdown.archetype}
                </span>
              )}
            </h2>
            <p style={{ margin: '0.75rem 0 0', fontSize: '0.95rem', lineHeight: 1.55, color: 'var(--hf-text-primary)' }}>
              {copy.body}
            </p>
            {breakdown?.top_drivers && breakdown.top_drivers.length > 0 && (
              <p style={{ margin: '0.75rem 0 0', fontSize: '0.9rem', color: 'var(--hf-text-secondary)' }}>
                <strong>Top drivers:</strong>{' '}
                {breakdown.top_drivers.map(d => `${d.label} (${d.score})`).join(', ')}
              </p>
            )}
            {refreshError && (
              <p role="alert" style={{ margin: '0.75rem 0 0', fontSize: '0.9rem', color: 'var(--hf-danger, #c00)' }}>
                {refreshError}
              </p>
            )}
            <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => { setRefreshError(null); setShowRefreshModal(false) }}
                className="hf-btn-link"
                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              >
                Close
              </button>
              <button
                type="button"
                onClick={async () => {
                  setRefreshError(null)
                  try {
                    await onRefresh!()
                    setShowRefreshModal(false)
                  } catch (err) {
                    setRefreshError(err instanceof Error ? err.message : 'Refresh failed.')
                  }
                }}
                disabled={refreshing}
                className="hf-btn-primary"
                style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem' }}
              >
                {refreshing ? 'Refreshing…' : 'Refresh archetype'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
