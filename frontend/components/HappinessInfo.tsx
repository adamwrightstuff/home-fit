'use client'

import { useState } from 'react'
import { HAPPINESS_INDEX_COPY } from '@/lib/pillars'

/** Info icon + modal for Happiness Index explanation. Use next to the Happiness Index label or score. */
export default function HappinessInfo() {
  const [showModal, setShowModal] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setShowModal(true)
        }}
        title={HAPPINESS_INDEX_COPY.tooltip}
        aria-label="What is the Happiness Index?"
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
          aria-labelledby="happiness-modal-title"
          aria-describedby="happiness-modal-desc"
          onClick={() => setShowModal(false)}
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
              id="happiness-modal-title"
              style={{
                margin: 0,
                fontSize: '1.2rem',
                fontWeight: 700,
                color: 'var(--c-blue-600)',
              }}
            >
              Happiness Index
            </h2>
            <p
              id="happiness-modal-desc"
              style={{
                margin: '0.75rem 0 0',
                fontSize: '0.95rem',
                lineHeight: 1.55,
                color: 'var(--hf-text-primary)',
              }}
            >
              {HAPPINESS_INDEX_COPY.full}
            </p>
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
          </div>
        </div>
      )}
    </>
  )
}
