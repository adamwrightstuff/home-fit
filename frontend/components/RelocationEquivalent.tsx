'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { readLocalProfile } from '@/lib/userProfile'
import {
  ctxFromSpec, fetchRelocation, findPlaceByName, placeCtx,
  type PlaceCtx, type PlaceSpec, type RelocationResult, type RelocationView,
} from '@/lib/relocation'

const usd = (n: number) => `$${Math.round(n / 100) * 100 >= 1000 ? Math.round(n / 1000) + 'k' : Math.round(n)}`
const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(0)}%`

function viewText(label: string, v: RelocationView | null): string | null {
  return v ? `${usd(v.equivalent_income_in_dest)} (${pct(v.change_pct)}) if ${label}` : null
}

interface Props {
  /** The place being priced. */
  dest: PlaceSpec
  /** Starting point when the profile has no current home (e.g. the other place in a compare). */
  fallbackOrigin?: PlaceSpec
  className?: string
}

type State =
  | { kind: 'loading' }
  | { kind: 'needs-income' }
  | { kind: 'same-metro'; originName: string }
  | { kind: 'ok'; originName: string; income: number; res: RelocationResult }
  | { kind: 'none' }

const specKey = (s?: PlaceSpec): string =>
  !s ? '' : 'place' in s ? `p:${s.place.catalog.name}:${s.place.catalog.state_abbr}` : 'key' in s ? `k:${s.key}` : `s:${s.saved.lat},${s.saved.lon}`

/**
 * "What would I need to earn here to keep the same money left over?" Reads income and current
 * home cost from the user's profile; asks for nothing. Metro-to-metro estimate.
 */
export default function RelocationEquivalent({ dest, fallbackOrigin, className }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    const set = (s: State) => { if (!cancelled) setState(s) }
    ;(async () => {
      const profile = readLocalProfile()
      const income = profile.household_income ?? null
      if (!income) return set({ kind: 'needs-income' })
      const destCtx = await ctxFromSpec(dest)
      if (!destCtx) return set({ kind: 'none' })
      let origin: PlaceCtx | null = null
      let cost: number | null = null
      if (profile.current_home) {
        const home = await findPlaceByName(profile.current_home.name)
        if (home) {
          origin = placeCtx(home)
          cost = profile.current_home.monthly_cost
        }
      }
      if (!origin && fallbackOrigin) origin = await ctxFromSpec(fallbackOrigin)
      if (!origin) return set({ kind: 'none' })
      if (origin.metro === destCtx.metro) return set({ kind: 'same-metro', originName: origin.name })
      const res = await fetchRelocation(origin, destCtx, income, cost)
      set(res && (res.rent || res.own) ? { kind: 'ok', originName: origin.name, income, res } : { kind: 'none' })
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specKey(dest), specKey(fallbackOrigin)])

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
      <div className="mt-0.5 opacity-80">
        Estimate: federal, payroll, state and some city income tax, metro prices, median housing costs.
        {res.own?.housing_scale_source === 'Zillow Home Value Index' && (
          <>
            {' '}Owner values: <a href="https://www.zillow.com/research/data/" target="_blank" rel="noopener noreferrer" className="underline">Zillow Research</a> (ZHVI).
          </>
        )}
      </div>
    </div>
  )
}
