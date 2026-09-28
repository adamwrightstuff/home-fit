'use client'

import { useState } from 'react'
import type { LivabilityPillars } from '@/types/api'
import { PILLAR_META, getPillarFailureType, type PillarKey } from '@/lib/pillars'
import { getPillarNarrative } from '@/lib/pillarNarratives'
import { getPillarValue, getPillarString } from '@/lib/pillarDetailsSpec'

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

/**
 * getPillarNarrative is written to describe a place neutrally (used elsewhere for a
 * general "tell me about this pillar" blurb), not to explain a shortfall. Each narrative
 * only reaches for genuinely negative wording once its own driving metric crosses that
 * function's own "weak" threshold; anywhere above that, it falls back to neutral or even
 * mildly positive default phrasing (e.g. "some signs of civic engagement", "typical crime
 * levels for the area", "many long-term residents"), which reads like a value-add under a
 * "why not higher" label even though the pillar is still a real drag on the total at its
 * weight. This mirrors each narrative's own primary branch condition (same fields, same
 * thresholds, see lib/pillarNarratives.ts) so we only borrow its wording when that
 * branch actually fired.
 */
function narrativeLeadIsWeak(key: PillarKey, pillar: Record<string, unknown>): boolean {
  switch (key) {
    case 'natural_beauty': {
      const tree = getPillarValue(pillar, 'summary.tree_score')
      if (typeof tree === 'number') return tree <= 30
      const canopy = getPillarValue(pillar, 'summary.neighborhood_canopy_pct')
      return typeof canopy === 'number' && canopy <= 20
    }
    case 'neighborhood_amenities': {
      const walk = getPillarValue(pillar, 'breakdown.home_walkability.score')
      if (typeof walk === 'number') return walk <= 30
      const biz = getPillarValue(pillar, 'breakdown.home_walkability.businesses_within_1km')
      return biz === 0
    }
    case 'active_outdoors': {
      const daily = getPillarValue(pillar, 'breakdown.daily_urban_outdoors')
      return typeof daily === 'number' && daily <= 30
    }
    case 'healthcare_access': {
      const hospital = getPillarValue(pillar, 'breakdown.hospital_access')
      return typeof hospital === 'number' && hospital <= 30
    }
    case 'public_transit_access': {
      const scores = [
        getPillarValue(pillar, 'breakdown.heavy_rail'),
        getPillarValue(pillar, 'breakdown.light_rail'),
        getPillarValue(pillar, 'breakdown.bus'),
      ].filter((n): n is number => typeof n === 'number')
      if (!scores.length) return false
      return scores.reduce((a, b) => a + b, 0) / scores.length <= 30
    }
    case 'air_travel_access': {
      const km = getPillarValue(pillar, 'summary.nearest_airport_km')
      return typeof km === 'number' && km > 60
    }
    case 'economic_opportunity': {
      const job = getPillarValue(pillar, 'base_score')
      return typeof job === 'number' && job <= 30
    }
    case 'quality_education': {
      const avg = getPillarValue(pillar, 'summary.base_avg_rating')
      return typeof avg === 'number' && avg <= 50
    }
    case 'housing_value': {
      const affordability = getPillarValue(pillar, 'breakdown.local_affordability')
      return typeof affordability === 'number' && affordability <= 30
    }
    case 'climate_risk': {
      const heat = getPillarValue(pillar, 'breakdown.lst_score')
      const air = getPillarValue(pillar, 'breakdown.aqi_score')
      const floodTier = getPillarString(pillar, 'summary.flood_risk_tier')
      return (
        (typeof heat === 'number' && heat >= 70) ||
        (typeof air === 'number' && air <= 40) ||
        floodTier === 'sfha' ||
        floodTier === 'floodway'
      )
    }
    case 'social_fabric': {
      const stability =
        getPillarValue(pillar, 'summary.stability_blend_pct') ?? getPillarValue(pillar, 'summary.same_house_pct')
      return typeof stability === 'number' && stability <= 40
    }
    case 'community_safety': {
      const raw = getPillarValue(pillar, 'breakdown.raw_score')
      return typeof raw === 'number' && raw <= 30
    }
    case 'diversity': {
      const score = getPillarValue(pillar, 'summary.diversity_entropy_score')
      return typeof score === 'number' && score <= 35
    }
    default:
      return false
  }
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

      const pillarRecord = pillar as unknown as Record<string, unknown>
      const narrative = narrativeLeadIsWeak(key, pillarRecord)
        ? getPillarNarrative(key, placeLabel, pillarRecord)
        : null
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
