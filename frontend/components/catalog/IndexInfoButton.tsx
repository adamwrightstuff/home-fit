'use client'

import { useEffect, useRef, useState } from 'react'
import { Heart, Smile, MapPin, Users } from 'lucide-react'
import { LONGEVITY_INDEX_WEIGHTS } from '@/lib/pillars'

type IndexId = 'homefit' | 'longevity' | 'happiness' | 'status'

interface IndexInfoButtonProps {
  indexId: IndexId
}

const INDEX_NAMES: Record<IndexId, string> = {
  homefit: 'Trovamo Score',
  longevity: 'Longevity Index',
  happiness: 'Happiness Index',
  status: 'Archetype',
}

const LONGEVITY_ROWS = Object.entries(LONGEVITY_INDEX_WEIGHTS).sort((a, b) => b[1] - a[1])
const LONGEVITY_TOTAL = Object.values(LONGEVITY_INDEX_WEIGHTS).reduce((a, b) => a + b, 0)

function pillarDisplayName(key: string): string {
  const MAP: Record<string, string> = {
    social_fabric: 'Social Fabric',
    neighborhood_amenities: 'Neighborhood Amenities',
    active_outdoors: 'Active Outdoors',
    natural_beauty: 'Natural Beauty',
    climate_risk: 'Climate Risk',
    quality_education: 'Quality Education',
  }
  return MAP[key] ?? key
}

function ProgressBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 6, borderRadius: 3, background: '#f3f4f6', overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${Math.min(100, pct)}%`, background: color, borderRadius: 3 }} />
    </div>
  )
}

function PopoverContent({ indexId }: { indexId: IndexId }) {
  if (indexId === 'homefit') {
    return (
      <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <MapPin size={14} color="#6B5CF6" />
          <span style={{ fontWeight: 700, fontSize: 13 }}>Trovamo Score</span>
        </div>
        <p style={{ fontSize: 12, color: '#4b5563', margin: '0 0 8px', lineHeight: 1.5 }}>
          A composite of all 13 pillars, weighted equally by default. Adjust weights to personalize.
        </p>
        <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 6 }}>
          Use <em>Adjust weights</em> to match your priorities →
        </div>
      </>
    )
  }

  if (indexId === 'longevity') {
    return (
      <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <Heart size={14} color="#0d9488" />
          <span style={{ fontWeight: 700, fontSize: 13, color: '#0d9488' }}>Longevity Index</span>
        </div>
        <p style={{ fontSize: 12, color: '#4b5563', margin: '0 0 8px', lineHeight: 1.5 }}>
          Predicts long-term health outcomes based on Blue Zone–style research.
        </p>
        <div style={{ marginBottom: 8 }}>
          {LONGEVITY_ROWS.map(([key, w]) => {
            const pct = Math.round((w / LONGEVITY_TOTAL) * 100)
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 11, color: '#374151', width: 130, flexShrink: 0 }}>{pillarDisplayName(key)}</span>
                <ProgressBar pct={pct} color="#0d9488" />
                <span style={{ fontSize: 11, color: '#6b7280', width: 30, textAlign: 'right', flexShrink: 0 }}>{pct}%</span>
              </div>
            )
          })}
        </div>
        <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 6 }}>
          Same formula for everyone — ignores your Trovamo weights.
        </div>
      </>
    )
  }

  if (indexId === 'happiness') {
    const rows = [
      { label: 'Commute ease (Transit)', pct: 35 },
      { label: 'Social Fabric', pct: 30 },
      { label: 'Housing value for space', pct: 15 },
      { label: 'Natural beauty', pct: 15 },
      { label: 'Built beauty', pct: 5 },
    ]
    return (
      <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <Smile size={14} color="#7c3aed" />
          <span style={{ fontWeight: 700, fontSize: 13, color: '#7c3aed' }}>Happiness Index</span>
        </div>
        <p style={{ fontSize: 12, color: '#4b5563', margin: '0 0 8px', lineHeight: 1.5 }}>
          Captures day-to-day livability, weighted toward commute and social connection.
        </p>
        <div style={{ marginBottom: 8 }}>
          {rows.map(({ label, pct }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: '#374151', width: 130, flexShrink: 0 }}>{label}</span>
              <ProgressBar pct={pct} color="#7c3aed" />
              <span style={{ fontSize: 11, color: '#6b7280', width: 30, textAlign: 'right', flexShrink: 0 }}>{pct}%</span>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 6 }}>
          Sources: Census ACS, OpenStreetMap.
        </div>
      </>
    )
  }

  // status / archetype
  const archetypeRows = [
    { label: 'Established', desc: 'Old-money stability' },
    { label: 'Upper Middle Class', desc: 'Professional affluence' },
    { label: 'Middle Class', desc: 'Broad mainstream' },
    { label: 'Up-and-coming', desc: 'Rising, transitional' },
    { label: 'Immigrant Community', desc: 'Community-anchored' },
    { label: 'Working Class', desc: 'Blue-collar character' },
  ]
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <Users size={14} color="#d97706" />
        <span style={{ fontWeight: 700, fontSize: 13, color: '#d97706' }}>Archetype</span>
      </div>
      <p style={{ fontSize: 12, color: '#4b5563', margin: '0 0 8px', lineHeight: 1.5 }}>
        Every neighborhood has a social character. Archetype captures it — classifying places by how wealth and status are expressed, using income, education, occupation, and housing data.
      </p>
      <div style={{ marginBottom: 8 }}>
        {archetypeRows.map(({ label, desc }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#374151', flexShrink: 0 }}>{label}</span>
            <span style={{ fontSize: 11, color: '#9ca3af' }}>{desc}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 6 }}>
        Based on Census ACS + Status Signal model.
      </div>
    </>
  )
}

export default function IndexInfoButton({ indexId }: IndexInfoButtonProps) {
  const [open, setOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  function clearTimer() {
    if (timerRef.current) clearTimeout(timerRef.current)
  }

  useEffect(() => {
    if (!open) return
    function handleMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [open])

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}>
      <button
        type="button"
        aria-label={`Learn about ${INDEX_NAMES[indexId]}`}
        role="button"
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => {
          clearTimer()
          timerRef.current = setTimeout(() => setOpen(true), 200)
        }}
        onMouseLeave={() => {
          clearTimer()
          setOpen(false)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setOpen((v) => !v)
          }
        }}
        style={{
          width: 15,
          height: 15,
          borderRadius: '50%',
          border: '1px solid #e5e7eb',
          background: '#f9fafb',
          fontSize: 9,
          color: '#9ca3af',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          cursor: 'pointer',
          padding: 0,
        }}
      >
        ?
      </button>
      <div
        style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          zIndex: 50,
          width: 256,
          borderRadius: 12,
          border: '1px solid #e5e7eb',
          background: '#fff',
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          padding: 12,
          opacity: open ? 1 : 0,
          transform: open ? 'translateY(0)' : 'translateY(-4px)',
          transition: 'opacity 0.15s ease, transform 0.15s ease',
          pointerEvents: open ? 'auto' : 'none',
        }}
      >
        <PopoverContent indexId={indexId} />
      </div>
    </div>
  )
}
