'use client'

import type { StatusSignalBreakdown } from '@/types/api'
import { archetypeOneLiner, getStatusBadgeModel } from '@/lib/statusSignalArchetype'

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function dotColor(archetype: string | null): string {
  if (archetype === 'Established') return '#6366F1'
  if (archetype === 'Upper Middle Class' || archetype === 'Affluent') return '#D97706'
  if (archetype === 'Middle Class') return '#64748B'
  if (archetype === 'Up-and-Coming' || archetype === 'Transitional') return '#0F766E'
  if (archetype === 'Immigrant Community') return '#9333EA'
  if (archetype === 'Working Class') return '#78716C'
  return '#6B7280'
}

function compassPoint(breakdown: StatusSignalBreakdown | null): { x: number; y: number } {
  const ci = (breakdown as { classifier_inputs?: Record<string, number> } | null)?.classifier_inputs
  const edu = typeof ci?.education === 'number' ? ci.education : 50
  const occ = typeof ci?.occupation === 'number' ? ci.occupation : 50
  const wealth = typeof ci?.wealth === 'number' ? ci.wealth : 50
  const homeCost = typeof ci?.home_cost === 'number' ? ci.home_cost : 50
  // x: credential profile — left = modest, right = elite
  const credScore = (edu + occ) / 2
  const x = clamp((credScore - 50) / 40, -1, 1)
  // y: cost-vs-wealth pressure — bottom = wealth ≥ cost, top = cost > wealth
  const y = clamp((homeCost - wealth) / 40, -1, 1)
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
  // Use the named archetype only if the badge model considers it active (filters out retired labels).
  const archetype = badge.variant === 'named' ? (breakdown.archetype ?? null) : null
  const point = compassPoint(breakdown)
  const xPct = 50 + point.x * 36
  const yPct = 50 + point.y * 36
  const oneLiner =
    archetype
      ? archetypeOneLiner(archetype)
      : badge.leanArchetype
        ? archetypeOneLiner(badge.leanArchetype)
        : 'Every neighborhood has a social character. Archetype captures it — classifying places by how wealth and status are expressed, using income, education, occupation, and housing data.'

  return (
    <div className="tr-panel" style={{ marginTop: '1rem' }}>
      <div className="tr-label" style={{ marginBottom: '0.5rem' }}>Archetype compass</div>
      <div
        style={{
          position: 'relative',
          height: 220,
          borderRadius: 12,
          border: '1px solid var(--hf-border)',
          background:
            'linear-gradient(180deg, rgba(13,148,136,0.04), rgba(99,102,241,0.04))',
        }}
      >
        <div style={{ position: 'absolute', left: '50%', top: 8, transform: 'translateX(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Cost exceeds wealth
        </div>
        <div style={{ position: 'absolute', left: '50%', bottom: 8, transform: 'translateX(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Wealth exceeds cost
        </div>
        <div style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Modest
        </div>
        <div style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', fontSize: '0.72rem', color: 'var(--hf-text-secondary)' }}>
          Elite
        </div>

        <div style={{ position: 'absolute', left: '50%', top: 18, bottom: 18, width: 1, background: 'var(--hf-border)' }} />
        <div style={{ position: 'absolute', top: '50%', left: 18, right: 18, height: 1, background: 'var(--hf-border)' }} />

        <div style={{ position: 'absolute', left: 16, top: 16, fontSize: '0.7rem', fontWeight: 600, color: '#0F766E' }}>Transitional</div>
        <div style={{ position: 'absolute', right: 16, top: 16, fontSize: '0.7rem', fontWeight: 600, color: '#0F766E', textAlign: 'right' }}>Transitional+</div>
        <div style={{ position: 'absolute', right: 16, bottom: 16, fontSize: '0.7rem', fontWeight: 600, color: '#4338CA' }}>Established</div>
        <div style={{ position: 'absolute', left: 16, bottom: 16, fontSize: '0.7rem', fontWeight: 600, color: '#78716C' }}>Working Class</div>

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
            background: dotColor(archetype),
            border: '2px solid #fff',
            boxShadow: '0 0 0 2px rgba(17,24,39,0.12)',
          }}
        />
      </div>
      <div className="tr-muted" style={{ marginTop: '0.6rem', fontSize: '0.9rem' }}>
        {typeof score === 'number' ? `Strength: ${score.toFixed(1)} / 100.` : 'Strength unavailable.'} {oneLiner}
      </div>
    </div>
  )
}
