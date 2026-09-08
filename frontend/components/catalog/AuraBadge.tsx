'use client'

export default function AuraBadge({
  itScore,
  compact = false,
  threshold = 75,
}: {
  itScore: number | null | undefined
  compact?: boolean
  threshold?: number
}) {
  if (typeof itScore !== 'number' || !Number.isFinite(itScore) || itScore < threshold) return null
  return (
    <span
      title={`Aura score ${itScore.toFixed(1)} — high status, vibrant scene, and strong livability all at once`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        height: compact ? 20 : 28,
        padding: compact ? '0 7px' : '0 10px',
        borderRadius: 99,
        fontSize: compact ? 11 : 13,
        fontWeight: 600,
        whiteSpace: 'nowrap',
        background: 'linear-gradient(135deg, #fdf4ff 0%, #ede9fe 100%)',
        color: '#6b21a8',
        border: '1px solid #e9d5ff',
        letterSpacing: '0.01em',
      }}
    >
      ✦ Aura
    </span>
  )
}
