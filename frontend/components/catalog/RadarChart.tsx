'use client'

import { PILLAR_META, type PillarKey } from '@/lib/pillars'

const PURPLE = '#6B5CE7'
const CORAL = '#E76B5C'
const GRID = '#e8e8e8'

interface RadarChartProps {
  pillars: PillarKey[]
  queryScores: Record<PillarKey, number>
  twinScores: Record<PillarKey, number>
  size?: number
}

export default function RadarChart({ pillars, queryScores, twinScores, size = 220 }: RadarChartProps) {
  const n = Math.max(3, pillars.length)
  const cx = size / 2
  const cy = size / 2
  const r = size * 0.36
  const labelR = r + 22

  const angle = (i: number) => (-Math.PI / 2 + (2 * Math.PI * i) / n) as number

  const point = (scores: Record<PillarKey, number>, scale: number) => {
    return pillars.map((k, i) => {
      const v = Math.max(0, Math.min(100, scores[k] ?? 0)) / 100
      const a = angle(i)
      return [cx + scale * r * v * Math.cos(a), cy + scale * r * v * Math.sin(a)] as [number, number]
    })
  }

  const gridRings = [0.25, 0.5, 0.75, 1]
  const polyQ = point(queryScores, 1)
  const polyT = point(twinScores, 1)
  const path = (pts: [number, number][]) => pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ') + ' Z'

  return (
    <svg width={size} height={size + 8} viewBox={`0 0 ${size} ${size + 8}`} className="mx-auto block">
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
        return (
          <line key={i} x1={cx} y1={cy} x2={x2} y2={y2} stroke={GRID} strokeWidth={0.75} />
        )
      })}
      <path d={path(polyQ)} fill={`${PURPLE}33`} stroke={PURPLE} strokeWidth={2} />
      <path d={path(polyT)} fill={`${CORAL}33`} stroke={CORAL} strokeWidth={2} />
      {pillars.map((k, i) => {
        const a = angle(i)
        const lx = cx + labelR * Math.cos(a)
        const ly = cy + labelR * Math.sin(a)
        return (
          <text
            key={k}
            x={lx}
            y={ly}
            textAnchor="middle"
            dominantBaseline="middle"
            style={{ fontSize: 9, fontFamily: 'ui-monospace, monospace', fill: '#444' }}
          >
            {PILLAR_META[k].name.length > 14 ? PILLAR_META[k].name.slice(0, 12) + '…' : PILLAR_META[k].name}
          </text>
        )
      })}
    </svg>
  )
}
