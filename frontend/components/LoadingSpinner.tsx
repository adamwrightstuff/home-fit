'use client'

import { useEffect, useState } from 'react'

interface LoadingSpinnerProps {
  startTime?: number
  message?: string
}

export default function LoadingSpinner({ startTime, message = 'Calculating livability score...' }: LoadingSpinnerProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useEffect(() => {
    if (!startTime) return

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      setElapsedSeconds(elapsed)
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime])

  const getTimeMessage = () => {
    if (elapsedSeconds === 0) {
      return 'This typically takes 20–90 seconds; some pillars take longer.'
    } else if (elapsedSeconds < 30) {
      return `Calculating... (${elapsedSeconds}s)`
    } else if (elapsedSeconds < 90) {
      return `Still calculating... (${elapsedSeconds}s)`
    } else {
      return `Taking longer than usual... (${elapsedSeconds}s)`
    }
  }

  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
      <p className="text-gray-600">{message}</p>
      <p className="text-sm text-gray-500 mt-2">{getTimeMessage()}</p>
    </div>
  )
}
