'use client'

import { useRouter } from 'next/navigation'
import PlaceValuesGame from '@/components/PlaceValuesGame'
import type { PillarPriorities } from '@/components/SearchOptions'

export default function QuizPage() {
  const router = useRouter()

  function handleApplyPriorities(priorities: PillarPriorities, _nbPref?: string[], _jobCats?: string[], politicalVibe?: string | null) {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      const political_preference = politicalVibe === 'progressive' || politicalVibe === 'conservative' ? politicalVibe : null
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, ...priorities, political_preference }))
    } catch {
      // ignore
    }
    // No auto-navigation — user chooses "Search a place" or "See neighborhood picks"
  }

  function handleBack() {
    router.push('/catalog')
  }

  return (
    <PlaceValuesGame
      onApplyPriorities={handleApplyPriorities}
      onBack={handleBack}
    />
  )
}
