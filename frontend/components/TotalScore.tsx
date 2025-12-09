import { OverallConfidence } from '@/types/api'

interface TotalScoreProps {
  score: number
  confidence: OverallConfidence
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600'
  if (score >= 60) return 'text-yellow-600'
  return 'text-red-600'
}

function getScoreBgColor(score: number): string {
  if (score >= 80) return 'bg-green-50 border-green-200'
  if (score >= 60) return 'bg-yellow-50 border-yellow-200'
  return 'bg-red-50 border-red-200'
}

export default function TotalScore({ score, confidence }: TotalScoreProps) {
  return (
    <div className={`bg-white rounded-lg shadow-lg p-8 border-2 ${getScoreBgColor(score)}`}>
      <div className="text-center">
        <p className="text-sm font-semibold text-gray-600 mb-2">TOTAL LIVABILITY SCORE</p>
        <div className={`text-6xl font-bold ${getScoreColor(score)} mb-2`}>
          {score.toFixed(1)}
        </div>
        <div className="text-2xl text-gray-400 mb-4">/ 100</div>
        
        <div className="mt-6 pt-6 border-t border-gray-200">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-600">Confidence</p>
              <p className="text-lg font-semibold text-gray-900">
                {confidence.average_confidence.toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-gray-600">Data Quality</p>
              <p className="text-lg font-semibold text-gray-900 capitalize">
                {confidence.overall_quality}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
