'use client'

import { useEffect, useState, useRef } from 'react'

interface LoadingQuotesProps {
  is_loading: boolean
}

const QUOTES = [
  "Finding where you belong starts with understanding where you are.",
  "Analyzing thousands of data points to find your ideal fit...",
  "Your next chapter is waiting to be discovered.",
  "Measuring what matters most to your lifestyle...",
  "Making one of life's biggest decisions a little easier.",
  "Turning complex data into simple answers..."
]

const FADE_DURATION = 300 // 300ms fade transition
const QUOTE_DURATION = 3500 // 3.5 seconds per quote (between 3-4 seconds)

export default function LoadingQuotes({ is_loading }: LoadingQuotesProps) {
  const [current_index, set_current_index] = useState(0)
  const [quote_opacity, set_quote_opacity] = useState(1)
  const interval_ref = useRef<NodeJS.Timeout | null>(null)
  const fade_timeout_ref = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // Clear any existing timeouts/intervals
    if (interval_ref.current) clearInterval(interval_ref.current)
    if (fade_timeout_ref.current) clearTimeout(fade_timeout_ref.current)

    if (!is_loading) {
      // Fade out gracefully when loading completes
      set_quote_opacity(0)
      return
    }

    // Reset when loading starts
    set_quote_opacity(1)
    set_current_index(0)

    // Function to rotate to next quote with fade
    const rotate_quote = () => {
      // Fade out current quote
      set_quote_opacity(0)
      
      // After fade out, change quote and fade in
      fade_timeout_ref.current = setTimeout(() => {
        set_current_index((prev) => (prev + 1) % QUOTES.length)
        set_quote_opacity(1)
      }, FADE_DURATION)
    }

    // Start rotating quotes at regular intervals
    interval_ref.current = setInterval(rotate_quote, QUOTE_DURATION)

    return () => {
      if (interval_ref.current) clearInterval(interval_ref.current)
      if (fade_timeout_ref.current) clearTimeout(fade_timeout_ref.current)
    }
  }, [is_loading])

  // Always render when loading, even if opacity is 0 (for layout)
  if (!is_loading) {
    return null
  }

  return (
    <div 
      className="text-center"
      style={{
        minHeight: '2.5rem',
        paddingTop: '0.75rem',
        paddingBottom: '0.75rem',
        marginTop: '0.5rem',
        marginBottom: '1.5rem',
      }}
    >
      <p 
        className="italic"
        style={{
          fontSize: '17px',
          fontWeight: 400,
          lineHeight: '1.6',
          opacity: quote_opacity,
          transition: `opacity ${FADE_DURATION}ms ease-in-out`,
          color: '#6C7A89',
          margin: 0,
          display: 'block',
        }}
      >
        {QUOTES[current_index]}
      </p>
    </div>
  )
}
