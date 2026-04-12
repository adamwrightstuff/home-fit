'use client'

import { signalStrengthFromCompositeScore } from '@/lib/statusSignalStrength'

function dotsFromLabel(label: string): number {
  const l = label.toLowerCase()
  if (l.includes('dominant')) return 4
  if (l.includes('strong')) return 3
  if (l.includes('moderate')) return 2
  if (l.includes('faint')) return 1
  return 1
}

/** dominant=4 … faint=1 */
export default function SignalStrengthDots({
  breakdown,
  statusSignalScore,
}: {
  breakdown?: {
    signal_strength?: string
    signal_strength_label?: string
    composite_score?: number
  } | null
  statusSignalScore?: number | null
}) {
  let n = 1
  const s = breakdown?.signal_strength
  if (s === 'dominant') n = 4
  else if (s === 'strong') n = 3
  else if (s === 'moderate') n = 2
  else if (s === 'faint') n = 1
  else if (breakdown?.signal_strength_label) {
    n = dotsFromLabel(breakdown.signal_strength_label)
  } else if (typeof statusSignalScore === 'number' && Number.isFinite(statusSignalScore)) {
    n = dotsFromLabel(signalStrengthFromCompositeScore(statusSignalScore).label)
  }

  return (
    <span className="inline-flex gap-0.5" aria-label={`Signal strength ${n} of 4`}>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: i < n ? '#D85A30' : 'var(--hf-border)' }}
        />
      ))}
    </span>
  )
}
