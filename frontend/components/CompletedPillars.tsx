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
  if (score >= 80) return 'bg-homefit-score-high/10 border-homefit-score-high/30 text-homefit-score-high'
  if (score >= 60) return 'bg-homefit-score-mid/10 border-homefit-score-mid/30 text-homefit-score-mid'
  return 'bg-homefit-score-low/10 border-homefit-score-low/30 text-homefit-score-low'
}

export default function CompletedPillars({ completed_pillars, pillar_config }: CompletedPillarsProps) {
  if (completed_pillars.size === 0) {
    return (
      <div className="text-center py-8 text-homefit-text-secondary">
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
      <h3 className="text-sm font-semibold text-homefit-text-primary mb-3">Completed Pillars</h3>
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
