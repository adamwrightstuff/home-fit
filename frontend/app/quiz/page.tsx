'use client'

import { useRouter } from 'next/navigation'
import QuizModal, { type QuizPayload } from '@/components/QuizModal'
import { DEFAULT_PRIORITIES } from '@/components/SearchOptions'
import type { PillarPriorities } from '@/components/SearchOptions'
import { DEFAULT_BUDGET } from '@/lib/budgetCost'
import { saveProfile } from '@/lib/userProfile'

export default function QuizPage() {
  const router = useRouter()

  function handleApply(payload: QuizPayload) {
    try {
      const merged = { ...DEFAULT_PRIORITIES, ...payload.priorities } as PillarPriorities
      const stored = localStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      localStorage.setItem('homefit_search_options', JSON.stringify({
        ...opts,
        quiz_override: true,
        priorities: merged,
        // Same fields the profile page writes, so the catalog reads them.
        ...(payload.commuteMode ? { commute_mode: payload.commuteMode } : {}),
        ...(payload.officeDays ? { office_days: payload.officeDays } : {}),
        filters: {
          ...(opts.filters ?? {}),
          filterAoTypes: payload.filterAoTypes,
          filterNbTypes: payload.filterNbTypes,
          filterHousingType: payload.filterHousingType,
          filterTenure: payload.filterTenure,
          ...(payload.workZoneId ? { workZoneId: payload.workZoneId } : {}),
          filterLocalScene: payload.filterLocalScene ?? [],
          filterPoliticalLean: payload.filterPoliticalLean,
          filterTrajectory: payload.filterTrajectory,
          filterCommuteMax: payload.filterCommuteMax,
          climatePrefs: payload.climatePrefs,
          ...(payload.homeBudget
            ? { filterBudget: { beds: [payload.homeBudget.beds], max: payload.homeBudget.max, down: opts.filters?.filterBudget?.down ?? DEFAULT_BUDGET.down, chosen: true } }
            : {}),
        },
        dealbreakers: payload.dealbreakers,
      }))
    } catch { /* ignore */ }
    // Signed in: keep the account profile in step so its saved bedrooms do not override the quiz answer.
    if (payload.homeBudget) {
      let down: number | null = DEFAULT_BUDGET.down
      try { down = JSON.parse(localStorage.getItem('homefit_search_options') ?? '{}')?.filters?.filterBudget?.down ?? down } catch { /* ignore */ }
      void saveProfile({ home_budget: { beds: [payload.homeBudget.beds], down } })
    }
    router.push('/catalog')
  }

  return (
    <QuizModal
      onApply={handleApply}
      onBack={() => router.push('/catalog')}
    />
  )
}
