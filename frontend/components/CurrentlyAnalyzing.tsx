'use client'

interface PillarConfig {
  emoji: string
  name: string
  description: string
}

interface CurrentlyAnalyzingProps {
  pillar_key: string
  config: PillarConfig
}

export default function CurrentlyAnalyzing({ pillar_key, config }: CurrentlyAnalyzingProps) {
  return (
    <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <div style={{ fontSize: '2rem' }}>{config.emoji}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', marginBottom: '0.25rem' }}>Analyzing {config.name}</div>
          <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
            {config.description}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.35rem' }} aria-hidden="true">
          <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.7 }} />
          <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.45 }} />
          <div style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--hf-primary-1)', opacity: 0.25 }} />
        </div>
      </div>
    </div>
  )
}
