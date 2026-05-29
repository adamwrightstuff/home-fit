'use client'

import { useRouter } from 'next/navigation'
import PlaceValuesGame from '@/components/PlaceValuesGame'
import type { PillarPriorities } from '@/components/SearchOptions'

export default function QuizPage() {
  const router = useRouter()

  function handleApplyPriorities(priorities: PillarPriorities) {
    try {
      const stored = sessionStorage.getItem('homefit_search_options')
      const opts = stored ? JSON.parse(stored) : {}
      sessionStorage.setItem('homefit_search_options', JSON.stringify({ ...opts, ...priorities }))
    } catch {
      // ignore
    }
    router.push('/catalog')
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
