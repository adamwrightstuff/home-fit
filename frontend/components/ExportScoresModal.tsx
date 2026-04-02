'use client'

import { useState, useCallback, useEffect } from 'react'
import { slugifyLocationForFilename } from '@/lib/exportScores'

const PREVIEW_MAX_CHARS = 120

function truncateWithEllipsis(line: string, maxChars: number): string {
  if (line.length <= maxChars) return line
  return line.slice(0, maxChars - 3) + '…'
}

export interface ExportScoresModalProps {
  isOpen: boolean
  onClose: () => void
  locationName: string
  csvHeaderLine: string
  csvDataLine: string
  copyBlock: string
}

export default function ExportScoresModal({
  isOpen,
  onClose,
  locationName,
  csvHeaderLine,
  csvDataLine,
  copyBlock,
}: ExportScoresModalProps) {
  const [format, setFormat] = useState<'csv' | 'copy'>('csv')
  const [success, setSuccess] = useState<'download' | 'copy' | null>(null)

  const handleDownloadCsv = useCallback(() => {
    const filename = `homefit_scores_${slugifyLocationForFilename(locationName)}.csv`
    const content = csvHeaderLine + '\n' + csvDataLine
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    setSuccess('download')
  }, [locationName, csvHeaderLine, csvDataLine])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(copyBlock)
      setSuccess('copy')
    } catch (_) {
      // fallback not required for this flow
    }
  }, [copyBlock])

  const handlePrimaryAction = useCallback(() => {
    if (format === 'csv') {
      handleDownloadCsv()
    } else {
      handleCopy()
    }
  }, [format, handleDownloadCsv, handleCopy])

  const handleBackdropClick = useCallback(() => {
    onClose()
  }, [onClose])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const headerPreview = truncateWithEllipsis(csvHeaderLine, PREVIEW_MAX_CHARS)
  const dataPreview = truncateWithEllipsis(csvDataLine, PREVIEW_MAX_CHARS)

  return (
    <div
      className="hf-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-scores-modal-title"
      aria-describedby="export-scores-desc"
      onClick={handleBackdropClick}
    >
      <div
        className="hf-panel"
        style={{
          maxWidth: 480,
          width: '100%',
          padding: '1.5rem 1.75rem',
          borderRadius: 12,
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', marginBottom: '0.5rem' }}>
          <h2
            id="export-scores-modal-title"
            style={{
              margin: 0,
              fontSize: '1.2rem',
              fontWeight: 700,
              color: 'var(--hf-text-primary)',
            }}
          >
            Export your scores
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              padding: '0.25rem',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '1.25rem',
              lineHeight: 1,
              color: 'var(--hf-text-secondary)',
            }}
          >
            ×
          </button>
        </div>
        <p id="export-scores-desc" className="hf-muted" style={{ fontSize: '0.9rem', margin: '0 0 1rem' }}>
          {locationName}
        </p>

        <p className="hf-muted" style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>
          One row per place — run this for each location and paste into one spreadsheet to compare.
        </p>

        <div
          style={{
            fontFamily: 'ui-monospace, monospace',
            fontSize: '0.8rem',
            background: 'var(--hf-bg-subtle)',
            border: '1px solid var(--hf-border)',
            borderRadius: 8,
            padding: '0.75rem 1rem',
            overflowX: 'auto',
            whiteSpace: 'pre',
            marginBottom: '1rem',
            maxHeight: 120,
            overflowY: 'auto',
          }}
        >
          {headerPreview}
          {'\n'}
          {dataPreview}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <span className="hf-muted" style={{ fontSize: '0.85rem', marginRight: '0.75rem' }}>Format:</span>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', marginRight: '1rem', cursor: 'pointer' }}>
            <input
              type="radio"
              name="export-format"
              checked={format === 'csv'}
              onChange={() => setFormat('csv')}
            />
            <span style={{ fontSize: '0.9rem' }}>CSV</span>
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
            <input
              type="radio"
              name="export-format"
              checked={format === 'copy'}
              onChange={() => setFormat('copy')}
            />
            <span style={{ fontSize: '0.9rem' }}>Copy</span>
          </label>
        </div>

        {success === 'download' && (
          <p style={{ fontSize: '0.9rem', color: 'var(--c-purple-600)', marginBottom: '0.75rem' }}>
            CSV downloaded.
          </p>
        )}
        {success === 'copy' && (
          <p style={{ fontSize: '0.9rem', color: 'var(--c-purple-600)', marginBottom: '0.75rem' }}>
            Scores copied to your clipboard.
          </p>
        )}

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <button type="button" onClick={onClose} className="hf-btn-link" style={{ padding: '0.5rem 1rem' }}>
            Close
          </button>
          <button
            type="button"
            onClick={handlePrimaryAction}
            className="hf-btn-primary"
            style={{ padding: '0.5rem 1.25rem', fontSize: '0.95rem' }}
          >
            {format === 'csv' ? 'Download CSV' : 'Copy scores'}
          </button>
        </div>
      </div>
    </div>
  )
}
