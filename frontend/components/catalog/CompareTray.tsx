'use client'

import Link from 'next/link'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import { catalogRowKey } from '@/lib/catalogMapTypes'
import { bedLabel, bedsPhrase, costGapReason, costSummary, minBeds, type BudgetFilter } from '@/lib/budgetCost'

interface CompareTrayProps {
  compareIds: string[]
  places: CatalogMapPlace[]
  /** Every place, unfiltered; used to find a chip's name and cost when the place is hidden by the current search or filters. */
  lookupPlaces?: CatalogMapPlace[]
  onRemove: (key: string) => void
  onClear: () => void
  /** Set once the visitor has chosen a budget; each chip then shows the place's monthly cost. */
  budget?: BudgetFilter
}

export default function CompareTray({ compareIds, places, lookupPlaces, onRemove, onClear, budget }: CompareTrayProps) {
  if (compareIds.length === 0) return null
  const pool = lookupPlaces ?? places

  function getPlaceName(key: string): string {
    const found = pool.find((p) => catalogRowKey(p.catalog) === key)
    return found ? found.catalog.name : key
  }

  function getPlaceCost(key: string): { text: string; title: string } | null {
    if (!budget) return null
    const found = pool.find((p) => catalogRowKey(p.catalog) === key)
    if (!found) return null
    const text = costSummary(found.housing_cost, budget)
    const title = text === 'no cost'
      ? `No ${bedLabel(minBeds(budget.beds))}+ bed cost: ${costGapReason(found.housing_cost, budget)}`
      : `Estimated monthly cost for a home with ${bedsPhrase(budget.beds)}, from your budget settings`
    return { text, title }
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
            {(() => {
              const c = getPlaceCost(id)
              return c ? <span title={c.title} style={{ fontWeight: 500, color: '#6b7280' }}>· {c.text}</span> : null
            })()}
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
        {compareIds.length >= 2 && (
          <Link
            href={`/saved/compare?a=${encodeURIComponent(compareIds[0])}&b=${encodeURIComponent(compareIds[1])}`}
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
        )}
      </div>
    </div>
  )
}
