'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'

interface PillarCardProps {
  name: string
  description: string
  pillar: LivabilityPillar
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 bg-green-50'
  if (score >= 60) return 'text-yellow-600 bg-yellow-50'
  return 'text-red-600 bg-red-50'
}

export default function PillarCard({ name, description, pillar }: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-white rounded-lg shadow-md p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900 text-lg">{name}</h3>
          <p className="text-sm text-gray-600 mt-1">{description}</p>
        </div>
        <div className={`ml-4 px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(pillar.score)}`}>
          {pillar.score.toFixed(1)}
        </div>
      </div>

      <div className="mt-3 text-xs text-gray-500 space-y-1">
        <div className="flex justify-between">
          <span>Weight:</span>
          <span className="font-medium">{pillar.weight.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between">
          <span>Contribution:</span>
          <span className="font-medium">{pillar.contribution.toFixed(1)}</span>
        </div>
        <div className="flex justify-between">
          <span>Confidence:</span>
          <span className="font-medium">{pillar.confidence.toFixed(0)}%</span>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 text-sm text-blue-600 hover:text-blue-800 font-medium"
      >
        {expanded ? 'Hide' : 'Show'} Details
      </button>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-gray-200 space-y-2 text-xs">
          {pillar.summary && Object.keys(pillar.summary).length > 0 && (
            <div>
              <p className="font-semibold text-gray-700 mb-1">Summary:</p>
              <div className="text-gray-600 space-y-1">
                {Object.entries(pillar.summary).slice(0, 5).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="capitalize">{key.replace(/_/g, ' ')}:</span>
                    <span className="font-medium">
                      {typeof value === 'number' ? value.toFixed(2) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div>
            <p className="font-semibold text-gray-700 mb-1">Data Quality:</p>
            <p className="text-gray-600 capitalize">
              {pillar.data_quality.quality_tier || 'Unknown'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
