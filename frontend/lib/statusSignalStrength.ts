/** Bands match pillars/status_signal._signal_strength_band (composite 0-100). */

export type SignalStrengthKey = 'faint' | 'moderate' | 'strong' | 'dominant'

export function signalStrengthFromCompositeScore(score: number): {
  key: SignalStrengthKey
  label: string
} {
  const s = Math.max(0, Math.min(100, score))
  if (s < 25) return { key: 'faint', label: 'Faint signal' }
  if (s < 50) return { key: 'moderate', label: 'Moderate signal' }
  if (s < 75) return { key: 'strong', label: 'Strong signal' }
  return { key: 'dominant', label: 'Dominant signal' }
}
