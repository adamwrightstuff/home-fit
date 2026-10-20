'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import type { CatalogMapPlace } from '@/lib/catalogMapTypes'
import { readLocalProfile } from '@/lib/userProfile'
import {
  fetchRelocation, findPlaceByKey, findPlaceByName, placeCtx,
  type PlaceCtx, type RelocationResult, type RelocationView,
} from '@/lib/relocation'

const usd = (n: number) => `$${Math.round(n / 100) * 100 >= 1000 ? Math.round(n / 1000) + 'k' : Math.round(n)}`
const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(0)}%`

function viewText(label: string, v: RelocationView | null): string | null {
  return v ? `${usd(v.equivalent_income_in_dest)} (${pct(v.change_pct)}) if ${label}` : null
}

interface Props {
  /** The place being priced. */
  dest: CatalogMapPlace
  /** Used as the starting point when the profile has no current home. */
  fallbackOrigin?: CatalogMapPlace
  className?: string
}

/**
 * "What would I need to earn here to keep the same money left over?" Reads income and current
 * home cost from the user's profile; asks for nothing. Metro-to-metro estimate.
 */
export default function RelocationEquivalent({ dest, fallbackOrigin, className }: Props) {
  const [state, setState] = useState<
    | { kind: 'loading' }
    | { kind: 'needs-income' }
    | { kind: 'same-metro'; originName: string }
    | { kind: 'ok'; originName: string; income: number; res: RelocationResult }
    | { kind: 'none' }
  >({ kind: 'loading' })

  const destCtx = placeCtx(dest)
  const destKey = `${destCtx.metro}|${destCtx.state}|${destCtx.city}`

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const profile = readLocalProfile()
      const income = profile.household_income ?? null
      if (!income) return !cancelled && setState({ kind: 'needs-income' })
      let origin: PlaceCtx | null = null
      let cost: number | null = null
      if (profile.current_home) {
        const home = await findPlaceByName(profile.current_home.name)
        if (home) {
          origin = placeCtx(home)
          cost = profile.current_home.monthly_cost
        }
      }
      if (!origin && fallbackOrigin) origin = placeCtx(fallbackOrigin)
      if (!origin) return !cancelled && setState({ kind: 'none' })
      if (origin.metro === destCtx.metro) return !cancelled && setState({ kind: 'same-metro', originName: origin.name })
      const res = await fetchRelocation(origin, destCtx, income, cost)
      if (cancelled) return
      setState(res && (res.rent || res.own) ? { kind: 'ok', originName: origin.name, income, res } : { kind: 'none' })
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [destKey, fallbackOrigin?.catalog.name])

  if (state.kind === 'loading' || state.kind === 'none') return null
  const box = `rounded-xl border border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] px-3 py-2 text-xs text-[var(--hf-text-secondary)] ${className ?? ''}`

  if (state.kind === 'needs-income') {
    return (
      <div className={box}>
        Add your household income in your <Link href="/profile" className="underline">profile</Link> to see what you would need to earn here.
      </div>
    )
  }
  if (state.kind === 'same-metro') {
    return <div className={box}>Same metro as {state.originName}, so there is no metro-level cost difference.</div>
  }
  const { res } = state
  const parts = [viewText('renting', res.rent), viewText('owning', res.own)].filter(Boolean)
  return (
    <div className={box} title={res.estimate_note}>
      <div className="font-semibold text-[var(--hf-text-primary)]">
        To keep the same money left over as at {state.originName} ({usd(state.income)}), you would need about {parts.join(' or ')}
      </div>
      <div className="mt-0.5 opacity-80">Estimate: state and some city income tax, metro prices, median housing costs.</div>
    </div>
  )
}

/** Same card for places known only by catalog key (the compare page). Catalog keys only. */
export function RelocationForKey({ placeKey, fallbackKey, className }: { placeKey: string; fallbackKey?: string; className?: string }) {
  const [places, setPlaces] = useState<{ dest: CatalogMapPlace; fallback?: CatalogMapPlace } | null>(null)
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const dest = await findPlaceByKey(placeKey)
      const fallback = fallbackKey ? await findPlaceByKey(fallbackKey) : null
      if (!cancelled && dest) setPlaces({ dest, fallback: fallback ?? undefined })
    })()
    return () => { cancelled = true }
  }, [placeKey, fallbackKey])
  if (!places) return null
  return <RelocationEquivalent dest={places.dest} fallbackOrigin={places.fallback} className={className} />
}
