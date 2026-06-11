'use client'

import { useState } from 'react'
import { STATUS_SIGNAL_COPY } from '@/lib/pillars'
import type { StatusSignalBreakdown } from '@/types/api'
import {
  getStatusBadgeModel,
  statusTooltipCopy,
} from '@/lib/statusSignalArchetype'

const ARCHETYPE_BADGE_STYLE: Record<string, { bg: string; text: string }> = {
  // Current bands
  Elite:              { bg: '#4338ca', text: '#e0e7ff' },
  Affluent:           { bg: '#b45309', text: '#fef3c7' },
  'Middle Class':     { bg: '#475569', text: '#f1f5f9' },
  'Working Class':    { bg: '#57534e', text: '#f5f5f4' },
  Struggling:         { bg: '#292524', text: '#e7e5e4' },
  // Legacy fallbacks
  Wealthy:            { bg: '#4338ca', text: '#e0e7ff' },
  'Well-Off':         { bg: '#b45309', text: '#fef3c7' },
  Modest:             { bg: '#57534e', text: '#f5f5f4' },
  'Up-and-Coming':    { bg: '#0f766e', text: '#ccfbf1' },
}

const TRAJECTORY_BADGE_STYLE: Record<string, { bg: string; text: string }> = {
  Arrived:          { bg: '#312e81', text: '#e0e7ff' },
  'Up-and-Coming':  { bg: '#0f766e', text: '#ccfbf1' },
  Stable:           { bg: '#334155', text: '#f1f5f9' },
  Cooling:          { bg: '#0369a1', text: '#e0f2fe' },
  Declining:        { bg: '#9f1239', text: '#ffe4e6' },
}

export interface StatusSignalInfoProps {
  /** When provided, show refresh in the modal and call it on click. */
  onRefresh?: () => void | Promise<void>
  refreshing?: boolean
  /** When provided, show archetype badge and tooltip content (archetype, insight, top drivers, radius note). */
  breakdown?: StatusSignalBreakdown | null
  /** Top-level composite 0-100; used to derive strength label when breakdown omits signal_strength_label (older saves). */
  compositeScore?: number | null
  /** Gate the Refresh button to logged-in users viewing their own saved places. */
  isSignedIn?: boolean
  savedScoreId?: string | null
  /**
   * When true (default), clicking the Archetype pill opens the full detail modal.
   * Set false on Public page where the detail modal is not shown.
   */
  allowDetailModal?: boolean
}

/**
 * Archetype pill badge. Clicking opens the full Archetype detail modal (on Results/Saved).
 * The combined "?" for Archetype+Trajectory lives in ArchetypeTrajectoryInfo — not here.
 */
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
  const [showModal, setShowModal] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const archetype = breakdown?.archetype ?? 'Working Class'
  const badgeStyle = ARCHETYPE_BADGE_STYLE[archetype] ?? ARCHETYPE_BADGE_STYLE['Working Class']
  const badgeModel = getStatusBadgeModel(breakdown ?? null, compositeScore)
  const helpCopy = statusTooltipCopy(breakdown ?? null, compositeScore)

  return (
    <>
      {breakdown?.status_label && (
        allowDetailModal ? (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setRefreshError(null); setShowModal(true) }}
            title={helpCopy ?? breakdown?.status_insight ?? STATUS_SIGNAL_COPY.tooltip}
            aria-label={`Archetype: ${badgeModel.text}. Click for details.`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.2rem 0.5rem',
              marginLeft: 6,
              borderRadius: 6,
              fontSize: '0.7rem',
              fontWeight: 600,
              background: badgeModel.variant === 'named' ? badgeStyle.bg : 'transparent',
              color: badgeStyle.text,
              border: badgeModel.variant === 'named' ? '1px solid transparent' : '1px solid var(--hf-border)',
              cursor: 'pointer',
            }}
          >
            {badgeModel.text}
          </button>
        ) : (
          <span
            className="hf-status-signature-badge"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.2rem 0.5rem',
              marginLeft: 6,
              borderRadius: 6,
              fontSize: '0.7rem',
              fontWeight: 600,
              background: badgeModel.variant === 'named' ? badgeStyle.bg : 'transparent',
              color: badgeStyle.text,
              border: badgeModel.variant === 'named' ? '1px solid transparent' : '1px solid var(--hf-border)',
            }}
            title={helpCopy ?? breakdown?.status_insight ?? undefined}
          >
            {badgeModel.text}
          </span>
        )
      )}

      {showModal && (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="archetype-index-modal-title"
          aria-describedby="archetype-index-modal-desc"
          onClick={() => { setRefreshError(null); setShowModal(false) }}
        >
          <div
            className="tr-panel"
            style={{
              maxWidth: 420,
              width: '100%',
              padding: '1.5rem 1.75rem',
              borderRadius: 12,
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2
              id="archetype-index-modal-title"
              style={{
                margin: 0,
                fontSize: '1.2rem',
                fontWeight: 700,
                color: 'var(--hf-text-primary)',
              }}
            >
              Archetype
              {breakdown?.archetype && (
                <span style={{ marginLeft: 8, fontSize: '0.85rem', fontWeight: 600, color: 'var(--hf-text-secondary)' }}>
                  — {breakdown.archetype}
                </span>
              )}
            </h2>
            <p
              id="archetype-index-modal-desc"
              style={{
                margin: '0.75rem 0 0',
                fontSize: '0.95rem',
                lineHeight: 1.55,
                color: 'var(--hf-text-primary)',
              }}
            >
              {(breakdown as { llm_summary?: string } | null)?.llm_summary ?? helpCopy ?? breakdown?.status_insight ?? STATUS_SIGNAL_COPY.full}
            </p>
            {breakdown?.top_drivers && breakdown.top_drivers.length > 0 && (
              <p style={{ margin: '0.75rem 0 0', fontSize: '0.9rem', color: 'var(--hf-text-secondary)' }}>
                <strong>Top drivers:</strong>{' '}
                {breakdown.top_drivers.map((d, i) => `${d.label} (${d.score})`).join(', ')}
              </p>
            )}
            {breakdown?.analysis_radius_note && (
              <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', fontStyle: 'italic', color: 'var(--hf-text-secondary)' }}>
                {breakdown.analysis_radius_note}
              </p>
            )}

            {showRefresh && (
              <div style={{ marginTop: '1.25rem' }}>
                {refreshError && (
                  <p role="alert" style={{ margin: '0 0 0.75rem', fontSize: '0.9rem', color: 'var(--hf-danger, #c00)' }}>
                    {refreshError}
                  </p>
                )}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => { setRefreshError(null); setShowModal(false) }}
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
                        setShowModal(false)
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
            )}
            {!showRefresh && (
              <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="hf-btn-primary"
                  style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem' }}
                >
                  Got it
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
