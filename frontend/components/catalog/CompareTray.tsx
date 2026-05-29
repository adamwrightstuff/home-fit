'use client'

import Link from 'next/link'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import { catalogRowKey } from '@/lib/catalogMapTypes'

interface CompareTrayProps {
  compareIds: string[]
  places: CatalogMapPlace[]
  onRemove: (key: string) => void
  onClear: () => void
}

export default function CompareTray({ compareIds, places, onRemove, onClear }: CompareTrayProps) {
  if (compareIds.length === 0) return null

  function getPlaceName(key: string): string {
    const found = places.find((p) => catalogRowKey(p.catalog) === key)
    return found ? found.catalog.name : key
  }

  return (
    <div
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 40,
        background: '#fff',
        borderTop: '1px solid #f3f4f6',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0, flexWrap: 'wrap' }}>
        {compareIds.map((id) => (
          <div
            key={id}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              background: '#f3f4f6',
              borderRadius: 999,
              padding: '4px 10px',
              fontSize: 12,
              fontWeight: 600,
              color: '#1a1a2e',
            }}
          >
            {getPlaceName(id)}
            <button
              type="button"
              aria-label={`Remove ${getPlaceName(id)}`}
              onClick={() => onRemove(id)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: 13,
                color: '#9ca3af',
                lineHeight: 1,
                padding: 0,
                marginLeft: 2,
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <button
          type="button"
          onClick={onClear}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
            color: '#6b7280',
            padding: '4px 0',
          }}
        >
          Clear
        </button>
        <Link
          href={`/compare?ids=${compareIds.join(',')}`}
          style={{
            display: 'inline-block',
            borderRadius: 999,
            background: '#1a1a2e',
            color: '#fff',
            padding: '8px 16px',
            fontSize: 13,
            fontWeight: 700,
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          Compare now →
        </Link>
      </div>
    </div>
  )
}
