'use client'

import type { StatusSignalBreakdown } from '@/types/api'
import {
  archetypeOneLiner,
  computeArchetypeMatchPercentages,
  getStatusBadgeModel,
  type NonTypicalArchetype,
} from '@/lib/statusSignalArchetype'

function clamp01(v: number): number {
  return Math.max(-1, Math.min(1, v))
}

function dotColor(variant: 'named' | 'leans' | 'mixed', archetype: string | null): string {
  if (variant === 'mixed') return '#9CA3AF'
  if (archetype === 'Patrician') return '#6366F1'
  if (archetype === 'Parvenu') return '#D97706'
  if (archetype === 'Poseur') return '#0F766E'
  if (archetype === 'Plebeian') return '#78716C'
  return '#6B7280'
}

function defaultCornerForArchetype(archetype: string | null): { x: number; y: number } {
  if (archetype === 'Patrician') return { x: -0.75, y: 0.75 }
  if (archetype === 'Parvenu') return { x: 0.75, y: 0.75 }
  if (archetype === 'Poseur') return { x: 0.75, y: -0.75 }
  if (archetype === 'Plebeian') return { x: -0.75, y: -0.75 }
  return { x: 0, y: 0 }
}

function compassPoint(matches: Record<NonTypicalArchetype, number> | null, archetype: string | null) {
  if (!matches) return defaultCornerForArchetype(archetype)
  // Quadrant blend:
  // x+: cost premium vs profile (Parvenu + Poseur), x-: established-fit (Patrician + Plebeian)
  // y+: established wealth (Patrician + Parvenu), y-: emerging/modest (Poseur + Plebeian)
  const x = clamp01((matches.Parvenu + matches.Poseur - matches.Patrician - matches.Plebeian) / 100)
  const y = clamp01((matches.Patrician + matches.Parvenu - matches.Poseur - matches.Plebeian) / 100)
  return { x, y }
}

export default function StatusArchetypeCompass({
  breakdown,
  score,
}: {
  breakdown: StatusSignalBreakdown | null | undefined
  score: number | null | undefined
}) {
  if (!breakdown) return null
  const badge = getStatusBadgeModel(breakdown, typeof score === 'number' ? score : null)
  const matches = computeArchetypeMatchPercentages(breakdown)
  const point = compassPoint(matches, breakdown.archetype ?? null)
  const xPct = 50 + point.x * 36
  const yPct = 50 - point.y * 36
  const oneLiner =
    badge.leanArchetype != null
      ? archetypeOneLiner(badge.leanArchetype)
      : breakdown.archetype && breakdown.archetype !== 'Typical'
        ? archetypeOneLiner(breakdown.archetype as NonTypicalArchetype)
        : 'This place combines characteristics from multiple status profiles without a dominant pattern.'

  return (
    <div className="hf-panel" style={{ marginTop: '1rem' }}>
      <div className="hf-label" style={{ marginBottom: '0.5rem' }}>Archetype compass</div>
      <div
        style={{
          position: 'relative',
          height: 220,
          borderRadius: 12,
          border: '1px solid var(--hf-border)',
          background:
            'linear-gradient(180deg, rgba(99,102,241,0.04), rgba(120,113,108,0.08))',
        }}
      >
        <div style={{ position: 'absolute', left: '50%', top: 8, transform: 'translateX(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Established wealth
        </div>
        <div style={{ position: 'absolute', left: '50%', bottom: 8, transform: 'translateX(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Emerging wealth
        </div>
        <div style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Cost matches profile
        </div>
        <div style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          High cost vs profile
        </div>

        <div style={{ position: 'absolute', left: '50%', top: 18, bottom: 18, width: 1, background: 'var(--hf-border)' }} />
        <div style={{ position: 'absolute', top: '50%', left: 18, right: 18, height: 1, background: 'var(--hf-border)' }} />

        <div style={{ position: 'absolute', left: 16, top: 16, fontSize: '0.7rem', fontWeight: 600, color: '#4338CA' }}>Patrician</div>
        <div style={{ position: 'absolute', right: 16, top: 16, fontSize: '0.7rem', fontWeight: 600, color: '#B45309' }}>Parvenu</div>
        <div style={{ position: 'absolute', right: 16, bottom: 16, fontSize: '0.7rem', fontWeight: 600, color: '#0F766E' }}>Poseur</div>
        <div style={{ position: 'absolute', left: 16, bottom: 16, fontSize: '0.7rem', fontWeight: 600, color: '#57534E' }}>Plebeian</div>

        <div
          aria-label="Archetype position"
          style={{
            position: 'absolute',
            left: `${xPct}%`,
            top: `${yPct}%`,
            transform: 'translate(-50%, -50%)',
            width: 14,
            height: 14,
            borderRadius: '999px',
            background: dotColor(badge.variant, breakdown.archetype ?? null),
            border: '2px solid #fff',
            boxShadow: '0 0 0 2px rgba(17,24,39,0.12)',
          }}
        />
      </div>
      <div className="hf-muted" style={{ marginTop: '0.6rem', fontSize: '0.9rem' }}>
        {typeof score === 'number' ? `Strength: ${score.toFixed(1)} / 100.` : 'Strength unavailable.'} {oneLiner}
      </div>
    </div>
  )
}

