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

function get_score_color(score: number): string {
  if (score >= 80) return 'bg-green-50 border-green-200 text-green-700'
  if (score >= 60) return 'bg-yellow-50 border-yellow-200 text-yellow-700'
  return 'bg-red-50 border-red-200 text-red-700'
}

export default function CompletedPillars({ completed_pillars, pillar_config }: CompletedPillarsProps) {
  if (completed_pillars.size === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
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
    <div className="space-y-3 max-h-96 overflow-y-auto">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Completed Pillars</h3>
      {pillars_array.map(({ key, score, details, config }) => (
        <div
          key={key}
          className={`p-4 rounded-lg border-2 transition-all duration-300 ${get_score_color(score)}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{config.emoji}</span>
              <div>
                <h4 className="font-semibold text-sm">{config.name}</h4>
                <p className="text-xs opacity-75">{config.description}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold">{score.toFixed(1)}</div>
              <div className="text-xs opacity-75">/ 100</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
