'use client'

interface CompletedPillar {
  score: number
  details?: any
}

interface PillarConfig {
  emoji: string
  name: string
  description: string
}

interface CompletedPillarsProps {
  completed_pillars: Map<string, CompletedPillar>
  pillar_config: Record<string, PillarConfig>
}

export default function CompletedPillars({ completed_pillars, pillar_config }: CompletedPillarsProps) {
  if (completed_pillars.size === 0) {
    return (
      <div className="hf-muted" style={{ textAlign: 'center', padding: '2rem 0' }}>
        <p>Waiting for pillar results...</p>
      </div>
    )
  }

  const pillars_array = Array.from(completed_pillars.entries())
    .map(([key, value]) => ({
      key,
      ...value,
      config: pillar_config[key] || { emoji: '❓', name: key, description: '' }
    }))
    .sort((a, b) => b.score - a.score) // Sort by score descending

  return (
    <div style={{ display: 'grid', gap: '0.75rem', maxHeight: 420, overflowY: 'auto' }}>
      <div className="hf-label" style={{ marginBottom: '0.25rem' }}>
        Completed pillars
      </div>
      {pillars_array.map(({ key, score, details, config }) => (
        <div
          key={key}
          className="hf-panel"
          style={{ padding: '1rem' }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{config.emoji}</span>
              <div>
                <h4 style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>{config.name}</h4>
                <p className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.15rem' }}>
                  {config.description}
                </p>
              </div>
            </div>
            <div className="text-right">
              <div style={{ fontWeight: 900, fontSize: '1.6rem', background: 'var(--hf-primary-gradient)', WebkitBackgroundClip: 'text', color: 'transparent' }}>
                {score.toFixed(1)}
              </div>
              <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
                / 100
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
