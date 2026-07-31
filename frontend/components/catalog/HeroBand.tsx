'use client'

import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'

export default function HeroBand() {
  const { loading } = useAuth()

  if (loading) return null

  return (
    <div
      className="flex items-center justify-between border-b border-gray-100 bg-white px-4 py-3"
      style={{ gap: '1rem' }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <h2 style={{ fontSize: 17, fontWeight: 500, margin: 0, lineHeight: 1.3, color: '#1a1a2e' }}>
          Find neighborhoods that fit how you want to live.
        </h2>
        <p style={{ fontSize: 13, color: '#6b7280', margin: '4px 0 0' }}>
          Scores across 13 pillars — longevity, happiness, walkability, schools, and more.
        </p>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
        <Link
          href="/quiz"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '7px 16px',
            borderRadius: 999,
            background: 'var(--hf-primary-1)',
            color: '#fff',
            fontSize: 13,
            fontWeight: 600,
            textDecoration: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          Take the quiz →
        </Link>
      </div>
    </div>
  )
}
