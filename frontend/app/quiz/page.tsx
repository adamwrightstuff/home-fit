'use client'

import { useRouter } from 'next/navigation'
import QuizModal, { type QuizPayload } from '@/components/QuizModal'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { PillarPriorities } from '@/components/SearchOptions'

export default function QuizPage() {
  const router = useRouter()

  function handleApply(payload: QuizPayload) {
    try {
      const merged = { ...DEFAULT_PRIORITIES, ...payload.priorities } as PillarPriorities
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({
        ...opts,
        quiz_override: true,
        priorities: merged,
        filters: {
          ...(opts.filters ?? {}),
          filterAoTypes: payload.filterAoTypes,
          filterNbTypes: payload.filterNbTypes,
          filterHousingType: payload.filterHousingType,
          filterPoliticalLean: payload.filterPoliticalLean,
          filterTrajectory: payload.filterTrajectory,
          filterCommuteMax: payload.filterCommuteMax,
          climatePrefs: payload.climatePrefs,
        },
        dealbreakers: payload.dealbreakers,
      }))
    } catch { /* ignore */ }
    router.push('/catalog')
  }

  return (
    <QuizModal
      onApply={handleApply}
      onBack={() => router.push('/catalog')}
    />
  )
}
