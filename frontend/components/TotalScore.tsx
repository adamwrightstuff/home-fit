import { OverallConfidence } from '@/types/api'
import { HOMEFIT_COPY } from '@/lib/pillars'
import HomeFitInfo from './HomeFitInfo'

interface TotalScoreProps {
  score: number
  confidence: OverallConfidence
  /** When true, render skeleton placeholders (avoid misleading mid-load score). */
  loading?: boolean
}

export default function TotalScore({ score, confidence, loading }: TotalScoreProps) {
  const isLoading = Boolean(loading)
  return (
    <div className="hf-panel">
      <div className="hf-score-hero">
        <div className="hf-score-hero__value" aria-busy={isLoading}>
          {isLoading ? '—' : score.toFixed(1)}
        </div>
        <div className="hf-score-hero__label" style={{ display: 'inline-flex', alignItems: 'center' }}>
          Overall HomeFit Score (0–100)
          <HomeFitInfo />
        </div>
      </div>
      <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.9rem' }}>
        {HOMEFIT_COPY.subtitle}
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
            {isLoading ? '—' : `${confidence.average_confidence.toFixed(1)}%`}
          </div>
        </div>
        <div>
          <div className="hf-label">Data quality</div>
          <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)', textTransform: 'capitalize' }}>
            {isLoading ? '—' : confidence.overall_quality}
          </div>
        </div>
      </div>
    </div>
  )
}
