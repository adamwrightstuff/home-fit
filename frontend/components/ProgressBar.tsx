'use client'

interface ProgressBarProps {
  progress: number
}

export default function ProgressBar({ progress }: ProgressBarProps) {
  const clamped_progress = Math.min(100, Math.max(0, progress))
  
  return (
    <div className="hf-panel" style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <span className="hf-label">Progress</span>
        <span className="hf-label" style={{ fontWeight: 800, color: 'var(--hf-text-primary)' }}>
          {clamped_progress.toFixed(0)}%
        </span>
      </div>
      <div style={{ width: '100%', background: '#f1f3f5', borderRadius: 999, height: 12, overflow: 'hidden' }}>
        <div
          style={{
            width: `${clamped_progress}%`,
            height: '100%',
            background: 'var(--hf-primary-gradient)',
            transition: 'all 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}
