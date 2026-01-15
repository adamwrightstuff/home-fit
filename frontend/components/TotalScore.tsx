import { OverallConfidence } from '@/types/api'

interface TotalScoreProps {
  score: number
  confidence: OverallConfidence
}

export default function TotalScore({ score, confidence }: TotalScoreProps) {
  return (
    <div className="hf-panel">
      <div className="hf-score-hero">
        <div className="hf-score-hero__value">{score.toFixed(1)}</div>
        <div className="hf-score-hero__label">Overall HomeFit Score (0–100)</div>
      </div>

      <div
        style={{
          marginTop: '1.5rem',
          paddingTop: '1.5rem',
          borderTop: '1px solid var(--hf-border)',
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: '1rem',
        }}
      >
        <div>
          <div className="hf-label">Confidence</div>
          <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)' }}>
            {confidence.average_confidence.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="hf-label">Data quality</div>
          <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)', textTransform: 'capitalize' }}>
            {confidence.overall_quality}
          </div>
        </div>
      </div>
    </div>
  )
}
