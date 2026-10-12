'use client'

import InteractiveMap from '@/components/InteractiveMap'
import type { ScoreResponse } from '@/types/api'

export default function NeighborhoodMap({
  location,
  score,
}: {
  location: string
  score: ScoreResponse
}) {
  return (
    <div
      style={{
        width: '100%',
        height: '260px',
        borderRadius: 16,
        overflow: 'hidden',
        background: 'var(--hf-bg-subtle)',
      }}
    >
      <InteractiveMap
        location={location}
        coordinates={score.coordinates}
        completed_pillars={Object.keys(score.livability_pillars ?? {})}
      />
    </div>
  )
}
