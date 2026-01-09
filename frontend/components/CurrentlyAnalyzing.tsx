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
    <div className="mb-6 p-6 bg-homefit-info/10 border-2 border-homefit-info/30 rounded-lg">
      <div className="flex items-center space-x-4">
        <div className="text-4xl animate-bounce">{config.emoji}</div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-homefit-text-primary mb-1">
            Analyzing {config.name}
          </h3>
          <p className="text-sm text-homefit-text-secondary">{config.description}</p>
        </div>
        <div className="flex space-x-2">
          <div className="w-2 h-2 bg-homefit-info rounded-full animate-pulse"></div>
          <div className="w-2 h-2 bg-homefit-info rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
          <div className="w-2 h-2 bg-homefit-info rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
        </div>
      </div>
    </div>
  )
}
