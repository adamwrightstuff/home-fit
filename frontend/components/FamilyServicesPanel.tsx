'use client'

import { useEffect, useState } from 'react'

interface ServiceItem {
  name: string
  rating: number | null
  reviews: number
  url: string
  type: string
}

interface FamilyServicesData {
  childcare: ServiceItem[]
  activities: ServiceItem[]
}

const TYPE_LABELS: Record<string, string> = {
  child_care_agency: 'Childcare',
  preschool: 'Preschool',
  kindergarten: 'Kindergarten',
  ice_skating_rink: 'Ice Skating',
  dance_studio: 'Dance',
  martial_arts_school: 'Martial Arts',
  sports_club: 'Sports',
  gym: 'Fitness',
  swimming_pool: 'Swimming',
}

const TYPE_ICONS: Record<string, string> = {
  child_care_agency: '🧒',
  preschool: '🎒',
  kindergarten: '✏️',
  ice_skating_rink: '⛸️',
  dance_studio: '🩰',
  martial_arts_school: '🥋',
  sports_club: '⚽',
  gym: '🏃',
  swimming_pool: '🏊',
}

function StarRating({ rating, reviews }: { rating: number | null; reviews: number }) {
  if (rating == null || reviews < 5) {
    return <span style={{ fontSize: '0.75rem', color: 'var(--tr-muted, #888)' }}>No rating</span>
  }
  return (
    <span style={{ fontSize: '0.78rem', color: 'var(--tr-muted, #888)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
      <span style={{ color: '#f59e0b' }}>★</span>
      <span style={{ color: 'var(--tr-fg, inherit)', fontWeight: 600 }}>{rating.toFixed(1)}</span>
      <span>({reviews})</span>
    </span>
  )
}

function ServiceCard({ item }: { item: ServiceItem }) {
  const icon = TYPE_ICONS[item.type] ?? '📍'
  const label = TYPE_LABELS[item.type] ?? item.type

  return (
    <a
      href={item.url || undefined}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.3rem',
        padding: '0.75rem',
        borderRadius: '0.5rem',
        border: '1px solid var(--hf-border, #e5e7eb)',
        background: 'var(--hf-card-bg, #f9fafb)',
        textDecoration: 'none',
        color: 'inherit',
        cursor: item.url ? 'pointer' : 'default',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={(e) => {
        if (item.url) (e.currentTarget as HTMLElement).style.borderColor = 'var(--c-purple-400, #a78bfa)'
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--hf-border, #e5e7eb)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: 999, background: 'var(--hf-border, #e5e7eb)', color: 'var(--tr-muted, #888)', fontWeight: 600, letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>
          {icon} {label}
        </span>
      </div>
      <div style={{ fontSize: '0.85rem', fontWeight: 600, lineHeight: 1.3, color: 'var(--tr-fg, inherit)' }}>
        {item.name}
      </div>
      <StarRating rating={item.rating} reviews={item.reviews} />
    </a>
  )
}

function Section({ title, items, emptyMsg }: { title: string; items: ServiceItem[]; emptyMsg: string }) {
  if (items.length === 0) {
    return (
      <div>
        <div style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--tr-muted, #888)', marginBottom: '0.5rem' }}>{title}</div>
        <div style={{ fontSize: '0.82rem', color: 'var(--tr-muted, #888)', fontStyle: 'italic' }}>{emptyMsg}</div>
      </div>
    )
  }
  return (
    <div>
      <div style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--tr-muted, #888)', marginBottom: '0.6rem' }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem' }}>
        {items.map((item) => <ServiceCard key={item.name} item={item} />)}
      </div>
    </div>
  )
}

export default function FamilyServicesPanel({ lat, lon }: { lat: number; lon: number }) {
  const [data, setData] = useState<FamilyServicesData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/family-services?lat=${lat}&lon=${lon}`)
      .then((r) => r.json())
      .then((d) => {
        if (d && Array.isArray(d.childcare) && Array.isArray(d.activities)) {
          setData(d)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [lat, lon])

  return (
    <div className="tr-panel" style={{ marginBottom: '1rem', padding: '1rem 1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
        <span style={{ fontSize: '1.1rem' }}>👨‍👩‍👧‍👦</span>
        <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Family Services</span>
      </div>

      {loading ? (
        <div style={{ fontSize: '0.85rem', color: 'var(--tr-muted, #888)' }}>Loading nearby services…</div>
      ) : !data ? (
        <div style={{ fontSize: '0.85rem', color: 'var(--tr-muted, #888)', fontStyle: 'italic' }}>Could not load services for this location.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Section title="Childcare & Preschools" items={data.childcare} emptyMsg="No childcare listings found nearby." />
          <Section title="Kids Activities" items={data.activities} emptyMsg="No kids activities found nearby." />
        </div>
      )}
    </div>
  )
}
