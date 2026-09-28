'use client'

import { useState } from 'react'
import type { LivabilityPillars } from '@/types/api'
import { PILLAR_META, getPillarFailureType, type PillarKey } from '@/lib/pillars'
import { getPillarNarrative } from '@/lib/pillarNarratives'

interface WhyNotHigherProps {
  livability_pillars: LivabilityPillars
  available_pillars: PillarKey[]
  schoolsDisabled: boolean
  placeLabel: string
}

interface Drag {
  key: PillarKey
  score: number
  pointsLost: number
  cause: string
}

/** First sentence of a narrative (the location-specific one) — keeps the drag line skimmable. */
function firstSentence(text: string): string {
  const match = text.match(/^.*?[.!?](?=\s|$)/)
  return (match ? match[0] : text).trim()
}

function buildDrags(
  livability_pillars: LivabilityPillars,
  available_pillars: PillarKey[],
  schoolsDisabled: boolean,
  placeLabel: string
): Drag[] {
  return available_pillars
    .map((key): Drag | null => {
      if (key === 'quality_education' && schoolsDisabled) return null
      const pillar = (livability_pillars as any)?.[key]
      if (!pillar) return null
      if ((pillar.breakdown as any)?.coming_soon) return null
      if (getPillarFailureType(pillar) === 'execution_error') return null

      const score = typeof pillar.score === 'number' && Number.isFinite(pillar.score) ? pillar.score : null
      const weight = typeof pillar.weight === 'number' && Number.isFinite(pillar.weight) ? pillar.weight : 0
      if (score == null || weight <= 0) return null

      // Same math the backend uses for contribution (score * weight / 100): the gap
      // between that and a perfect 100 score is what this pillar is costing the total.
      const pointsLost = Math.max(0, weight * (1 - score / 100))
      if (pointsLost < 0.5) return null

      const narrative = getPillarNarrative(key, placeLabel, pillar as unknown as Record<string, unknown>)
      const cause = narrative
        ? firstSentence(narrative)
        : `Scored ${score.toFixed(0)}/100 here, below where it's pulling its weight in your total.`

      return { key, score, pointsLost, cause }
    })
    .filter((d): d is Drag => d !== null)
    .sort((a, b) => b.pointsLost - a.pointsLost)
    .slice(0, 3)
}

export default function WhyNotHigher({
  livability_pillars,
  available_pillars,
  schoolsDisabled,
  placeLabel,
}: WhyNotHigherProps) {
  const [open, setOpen] = useState(false)
  const drags = buildDrags(livability_pillars, available_pillars, schoolsDisabled, placeLabel)

  if (drags.length === 0) return null

  return (
    <div style={{ margin: '0.85rem 0', paddingTop: '0.1rem' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          appearance: 'none',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          fontFamily: 'inherit',
          fontSize: '0.82rem',
          fontWeight: 700,
          lineHeight: 1,
          color: open ? '#ffffff' : 'var(--hf-primary-2)',
          background: open ? 'var(--hf-primary-1)' : '#ffffff',
          border: `1.5px solid ${open ? 'var(--hf-primary-1)' : 'var(--hf-border-strong)'}`,
          borderRadius: 999,
          padding: '0.45rem 0.8rem',
          boxShadow: '0 1px 3px rgba(28,25,23,0.08)',
          transition: 'background 0.15s ease, color 0.15s ease',
        }}
      >
        <span aria-hidden style={{ fontSize: '0.95rem' }}>💡</span>
        Why not higher?
        <svg
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease', flexShrink: 0 }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div
          style={{
            marginTop: '0.75rem',
            border: '1px solid var(--hf-border)',
            borderRadius: 12,
            overflow: 'hidden',
            background: 'var(--hf-bg-subtle)',
          }}
        >
          {drags.map((drag, i) => {
            const meta = PILLAR_META[drag.key]
            return (
              <div
                key={drag.key}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.7rem',
                  padding: '0.8rem 0.9rem',
                  borderTop: i === 0 ? 'none' : '1px solid var(--hf-border)',
                }}
              >
                <span style={{ fontSize: '1.1rem', flexShrink: 0, lineHeight: 1.3 }} aria-hidden>
                  {meta.icon}
                </span>
                <div style={{ minWidth: 0, flex: '1 1 0' }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: '0.6rem',
                    }}
                  >
                    <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--hf-text-primary)' }}>
                      {meta.name}
                    </span>
                    <span
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: 'var(--hf-primary-2)',
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                      }}
                    >
                      &minus;{drag.pointsLost.toFixed(1)} pts
                    </span>
                  </div>
                  <p style={{ margin: '0.2rem 0 0', fontSize: '0.85rem', lineHeight: 1.45, color: 'var(--hf-text-secondary)' }}>
                    {drag.cause}
                  </p>
                </div>
              </div>
            )
          })}
          <div
            style={{
              padding: '0.6rem 0.9rem',
              fontSize: '0.76rem',
              color: 'var(--hf-text-tertiary)',
              borderTop: '1px solid var(--hf-border)',
            }}
          >
            Ranked by points lost against your priority weights — raise a pillar&apos;s importance and it moves up this list.
          </div>
        </div>
      )}
    </div>
  )
}
