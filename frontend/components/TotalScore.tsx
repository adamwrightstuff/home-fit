import { OverallConfidence } from '@/types/api'

interface TotalScoreProps {
  score: number
  confidence: OverallConfidence
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-homefit-score-high'
  if (score >= 60) return 'text-homefit-score-mid'
  return 'text-homefit-score-low'
}

function getScoreBgColor(score: number): string {
  if (score >= 80) return 'bg-homefit-score-high/10 border-homefit-score-high/30'
  if (score >= 60) return 'bg-homefit-score-mid/10 border-homefit-score-mid/30'
  return 'bg-homefit-score-low/10 border-homefit-score-low/30'
}

export default function TotalScore({ score, confidence }: TotalScoreProps) {
  return (
    <div className={`bg-white rounded-lg shadow-lg p-8 border-2 ${getScoreBgColor(score)}`}>
      <div className="text-center">
        <p className="text-sm font-semibold text-homefit-text-secondary mb-2">TOTAL LIVABILITY SCORE</p>
        <div className={`text-6xl font-bold ${getScoreColor(score)} mb-2`}>
          {score.toFixed(1)}
        </div>
        <div className="text-2xl text-homefit-text-secondary opacity-50 mb-4">/ 100</div>
        
        <div className="mt-6 pt-6 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-homefit-text-secondary">Confidence</p>
              <p className="text-lg font-semibold text-homefit-text-primary">
                {confidence.average_confidence.toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-homefit-text-secondary">Data Quality</p>
              <p className="text-lg font-semibold text-homefit-text-primary capitalize">
                {confidence.overall_quality}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
