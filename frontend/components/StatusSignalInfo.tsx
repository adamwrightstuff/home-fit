'use client'

import { useState } from 'react'
import { STATUS_SIGNAL_COPY } from '@/lib/pillars'

export interface StatusSignalInfoProps {
  /** When provided, show "Refresh Status Signal" in the modal and call it on click. */
  onRefresh?: () => void | Promise<void>
  refreshing?: boolean
}

/** "?" button + modal for Status Signal explanation and optional refresh. Use next to the Status Signal label or score. */
export default function StatusSignalInfo({ onRefresh, refreshing = false }: StatusSignalInfoProps) {
  const [showModal, setShowModal] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setRefreshError(null)
          setShowModal(true)
        }}
        title={STATUS_SIGNAL_COPY.tooltip}
        aria-label="What is Status Signal?"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 20,
          height: 20,
          padding: 0,
          marginLeft: 4,
          borderRadius: '50%',
          border: '1px solid var(--hf-border)',
          background: 'var(--hf-bg-subtle)',
          color: 'var(--hf-text-secondary)',
          cursor: 'pointer',
          fontSize: '0.75rem',
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        ?
      </button>

      {showModal && (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="status-signal-modal-title"
          aria-describedby="status-signal-modal-desc"
          onClick={() => { setRefreshError(null); setShowModal(false) }}
        >
          <div
            className="hf-panel"
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
              id="status-signal-modal-title"
              style={{
                margin: 0,
                fontSize: '1.2rem',
                fontWeight: 700,
                color: 'var(--hf-text-primary)',
              }}
            >
              Status Signal
            </h2>
            <p
              id="status-signal-modal-desc"
              style={{
                margin: '0.75rem 0 0',
                fontSize: '0.95rem',
                lineHeight: 1.55,
                color: 'var(--hf-text-primary)',
              }}
            >
              {STATUS_SIGNAL_COPY.full}
            </p>
            {onRefresh != null && (
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
                        await onRefresh()
                        setShowModal(false)
                      } catch (err) {
                        setRefreshError(err instanceof Error ? err.message : 'Refresh failed.')
                      }
                    }}
                    disabled={refreshing}
                    className="hf-btn-primary"
                    style={{ padding: '0.5rem 1.25rem', fontSize: '0.9rem' }}
                  >
                    {refreshing ? 'Refreshing…' : 'Refresh Status Signal'}
                  </button>
                </div>
              </div>
            )}
            {onRefresh == null && (
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
