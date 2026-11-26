'use client'

import { useEffect, useState } from 'react'
import SurroundingsCard from '@/components/catalog/SurroundingsCard'
import type { Surroundings } from '@/lib/surroundings'
import type { ScoreResponse } from '@/types/api'

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/**
 * "Around here" for a scored result: the API compares this place's income, home value and safety with the catalog
 * places near it (catalog_api /catalog/surroundings, docs/SURROUNDINGS.md). Display only. Renders nothing while
 * loading, on error, or when too few catalog places are nearby.
 */
export default function ResultsSurroundings({ score }: { score: ScoreResponse | null }) {
  const [surroundings, setSurroundings] = useState<Surroundings | null>(null)
  const lat = num(score?.coordinates?.lat)
  const lon = num(score?.coordinates?.lon)
  const pillars = (score?.livability_pillars ?? {}) as Record<string, any>
  const hv = pillars.housing_value?.summary ?? {}
  const cs = pillars.community_safety ?? {}
  const income = num(hv.median_household_income)
  const home = num(hv.median_home_value)
  const safety = num(cs.score)
  const source = typeof cs.breakdown?.source === 'string' ? cs.breakdown.source : ''
  const agency = typeof cs.breakdown?.agency_name === 'string' ? cs.breakdown.agency_name : ''
  const name = (score?.input ?? '').split(',')[0].trim()

  useEffect(() => {
    if (lat == null || lon == null) return
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) })
    if (name) params.set('name', name)
    if (income != null) params.set('income', String(income))
    if (home != null) params.set('home_value', String(home))
    if (safety != null) params.set('safety', String(safety))
    if (source) params.set('safety_source', source)
    if (agency) params.set('agency_name', agency)
    const ac = new AbortController()
    fetch(`/api/surroundings?${params}`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { surroundings?: Surroundings | null } | null) => setSurroundings(j?.surroundings ?? null))
      .catch(() => setSurroundings(null))
    return () => ac.abort()
  }, [lat, lon, name, income, home, safety, source, agency])

  if (!surroundings) return null
  return (
    <section className="mt-6" aria-label="Around here">
      <SurroundingsCard surroundings={surroundings} size="page" />
    </section>
  )
}
