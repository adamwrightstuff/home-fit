'use client'

import { useEffect, useRef, useCallback } from 'react'
import type { PillarPriorities } from './SearchOptions'
import type { ClimatePreferences } from '@/lib/climatePreferences'

export interface QuizPayload {
  priorities: Partial<PillarPriorities>
  filterAoTypes: string[]
  filterNbTypes: string[]
  filterHousingType: string[]
  filterPoliticalLean: string[]
  filterTrajectory: string
  filterCommuteMax: string
  filterLocalScene: string
  climatePrefs: ClimatePreferences
  dealbreakers: Partial<Record<string, boolean>>
}

interface QuizModalProps {
  onApply: (payload: QuizPayload) => void
  onBack: () => void
}

export default function QuizModal({ onApply, onBack }: QuizModalProps) {
  const appliedRef = useRef(false)

  const handleMessage = useCallback(
    (e: MessageEvent) => {
      if (e.data?.type !== 'homefit-quiz-result') return
      if (appliedRef.current) return
      appliedRef.current = true
      onApply(e.data.payload as QuizPayload)
    },
    [onApply],
  )

  useEffect(() => {
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [handleMessage])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        background: '#0D1219',
      }}
    >
      <button
        onClick={onBack}
        style={{
          position: 'absolute',
          top: 16,
          right: 20,
          zIndex: 10000,
          background: 'none',
          border: 'none',
          color: '#7A8696',
          fontSize: 13,
          cursor: 'pointer',
          fontFamily: 'system-ui, sans-serif',
          padding: '4px 8px',
        }}
      >
        ✕ Close
      </button>
      <iframe
        src="/quiz.html"
        style={{ flex: 1, border: 'none', width: '100%' }}
        title="HomeFit Preferences Quiz"
      />
    </div>
  )
}
