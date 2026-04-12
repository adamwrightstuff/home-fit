'use client'

import { PILLAR_META, type PillarKey } from '@/lib/pillars'

const PURPLE = '#6B5CE7'
const CORAL = '#E76B5C'
const GRID = '#e8e8e8'

/** Padding around chart so axis labels are not clipped (min ~300×300 drawable). */
const PAD = 52

interface RadarChartProps {
  pillars: PillarKey[]
  queryScores: Record<PillarKey, number>
  twinScores: Record<PillarKey, number>
  /** Inner chart diameter; total SVG is larger due to PAD. */
  size?: number
}

function shortLabel(k: PillarKey): string {
  const n = PILLAR_META[k].name
  return n.length <= 11 ? n : `${n.slice(0, 9)}…`
}

export default function RadarChart({ pillars, queryScores, twinScores, size = 300 }: RadarChartProps) {
  const n = Math.max(3, pillars.length)
  const cx = PAD + size / 2
  const cy = PAD + size / 2
  const r = size * 0.36
  const labelR = r + 36

  const angle = (i: number) => (-Math.PI / 2 + (2 * Math.PI * i) / n) as number

  const point = (scores: Record<PillarKey, number>) => {
    return pillars.map((k, i) => {
      const v = Math.max(0, Math.min(100, scores[k] ?? 0)) / 100
      const a = angle(i)
      return [cx + r * v * Math.cos(a), cy + r * v * Math.sin(a)] as [number, number]
    })
  }

  const gridRings = [0.25, 0.5, 0.75, 1]
  const polyQ = point(queryScores)
  const polyT = point(twinScores)
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') + ' Z'

  const vb = size + PAD * 2

  return (
    <svg
      width="100%"
      height="auto"
      style={{ maxWidth: vb, minHeight: vb }}
      viewBox={`0 0 ${vb} ${vb}`}
      className="mx-auto block"
    >
      {gridRings.map((gr) => (
        <polygon
          key={gr}
          fill="none"
          stroke={GRID}
          strokeWidth={0.75}
          points={pillars
            .map((_, i) => {
              const a = angle(i)
              return `${cx + gr * r * Math.cos(a)},${cy + gr * r * Math.sin(a)}`
            })
            .join(' ')}
        />
      ))}
      {pillars.map((_, i) => {
        const a = angle(i)
        const x2 = cx + r * Math.cos(a)
        const y2 = cy + r * Math.sin(a)
        return <line key={i} x1={cx} y1={cy} x2={x2} y2={y2} stroke={GRID} strokeWidth={0.75} />
      })}
      <path d={path(polyQ)} fill={`${PURPLE}33`} stroke={PURPLE} strokeWidth={2} />
      <path d={path(polyT)} fill={`${CORAL}33`} stroke={CORAL} strokeWidth={2} />
      {pillars.map((k, i) => {
        const a = angle(i)
        const lx = cx + labelR * Math.cos(a)
        const ly = cy + labelR * Math.sin(a)
        const c = Math.cos(a)
        const s = Math.sin(a)
        let anchor: 'start' | 'middle' | 'end' = 'middle'
        if (c > 0.35) anchor = 'start'
        else if (c < -0.35) anchor = 'end'
        let dy = 0
        if (s > 0.5) dy = 3
        else if (s < -0.5) dy = -3
        const label = shortLabel(k)
        return (
          <text
            key={k}
            x={lx}
            y={ly + dy}
            textAnchor={anchor}
            dominantBaseline="middle"
            style={{ fontSize: 9, fontFamily: 'ui-monospace, SFMono-Regular, monospace', fill: '#444' }}
          >
            {label}
          </text>
        )
      })}
    </svg>
  )
}
