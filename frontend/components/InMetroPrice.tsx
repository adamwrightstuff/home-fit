'use client'

import { bedLabel, bestCost, costGapReason, DEFAULT_BUDGET, downLabel, type Beds, type BudgetFilter, type HousingCost } from '@/lib/budgetCost'

export interface PriceRow {
  name: string
  metro: string
  cost: HousingCost | null
}

const usd = (n: number) => `$${Math.round(n).toLocaleString('en-US')}`
/** A ZIP-median estimate, so it is shown to the nearest $100 (no false precision). */
const usd100 = (n: number) => usd(Math.round(n / 100) * 100)
const bedName = (n: number) => `${bedLabel(n)}-bedroom`

/** Metros whose places are in California, where the tax figure runs low (the state reassesses a home when it sells). */
const CALIFORNIA_METROS = new Set(['la', 'sf', 'sacramento'])

/**
 * Housing price for two places in the SAME metro, where the metro-to-metro estimate has nothing to say.
 * With a home budget chosen in the Explorer: the monthly cost of the SAME bedroom size in both places (the smallest size you picked
 * that both have a price for), one rounded number each, with the other sizes and the basis one tap away. Without one: ZIP median
 * home values only, since a monthly cost needs a down payment the visitor has not given.
 */
export default function InMetroPrice({ a, b, budget, income }: { a: PriceRow; b: PriceRow; budget: BudgetFilter | null; income: number | null }) {
  const chosen = budget?.chosen ? budget : null
  const box = 'rounded-xl border border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] px-3 py-2 text-xs text-[var(--hf-text-secondary)]'
  const grid = { display: 'grid', gap: '0.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginTop: 6 } as const

  if (!chosen) {
    const cell = (r: PriceRow) => {
      const have = ([3, 4] as const).map((n) => ({ n, v: r.cost?.v[n - 1] ?? null })).filter((x) => x.v != null)
      return have.length === 0
        ? { main: 'No price', sub: costGapReason(r.cost, DEFAULT_BUDGET), n: null as number | null }
        : { main: have.map((x) => `${usd(x.v as number)} (${x.n}-bed)`).join(' · '), sub: 'ZIP median home value', n: have[0].v as number }
    }
    const ca = cell(a)
    const cb = cell(b)
    const diff = ca.n != null && cb.n != null && ca.n !== cb.n ? Math.abs(ca.n - cb.n) : null
    const cheaper = diff != null ? (ca.n! < cb.n! ? a.name : b.name) : null
    return (
      <section aria-label="Housing price within the metro" className={box} style={{ marginTop: '0.75rem' }}>
        <div className="font-semibold text-[var(--hf-text-primary)]">
          Same metro: ZIP median home value{cheaper && diff != null && <> · {cheaper} is {usd(diff)} lower</>}
        </div>
        <div style={grid}>
          {[{ r: a, c: ca }, { r: b, c: cb }].map(({ r, c }) => (
            <div key={r.name}>
              <div className="font-semibold">{r.name}</div>
              <div className="text-[var(--hf-text-primary)]">{c.main}</div>
              <div className="opacity-80">{c.sub}</div>
            </div>
          ))}
        </div>
        <div className="mt-1 opacity-80">Set bedrooms and a down payment in the Explorer to see a monthly cost here. Zillow ZIP values, single-family and condos combined.</div>
      </section>
    )
  }

  // The monthly cost of one bedroom size in one place, or null when that size has no price there.
  const costAt = (r: PriceRow, n: Beds) => bestCost(r.cost, { ...chosen, beds: [n], max: null })
  const sizes = chosen.beds
  const common = sizes.find((n) => costAt(a, n) && costAt(b, n)) ?? null
  const ca = common != null ? costAt(a, common)! : null
  const cb = common != null ? costAt(b, common)! : null
  const diff = ca && cb ? Math.round(Math.abs(ca.cost.total - cb.cost.total) / 100) * 100 : null
  const cheaper = ca && cb ? (ca.cost.total < cb.cost.total ? { lo: a, hi: b } : { lo: b, hi: a }) : null
  const californiaNote = CALIFORNIA_METROS.has(a.metro)

  const headline = common == null
    ? 'No bedroom size you picked has a price in both places'
    : diff === 0 || !cheaper
      ? `About the same monthly cost for a ${bedName(common)} home`
      : `${cheaper.lo.name} is about ${usd(diff!)}/mo less than ${cheaper.hi.name} for a ${bedName(common)} home`

  const side = (r: PriceRow, c: ReturnType<typeof costAt>) => (
    <div key={r.name}>
      <div className="font-semibold">{r.name}</div>
      {c ? (
        <>
          <div className="text-sm font-semibold text-[var(--hf-text-primary)]">~{usd100(c.cost.total)}/mo</div>
          {income ? <div>{Math.round((c.cost.total * 12 / income) * 100)}% of your income</div> : null}
          {chosen.max != null && c.cost.total > chosen.max && (
            <div className="font-semibold text-trovamo-score-low">Over your {usd(chosen.max)} cap</div>
          )}
        </>
      ) : (
        <div className="opacity-80">No {bedName(common ?? sizes[0])} price: {costGapReason(r.cost, chosen)}</div>
      )}
    </div>
  )

  return (
    <section aria-label="Housing price within the metro" className={box} style={{ marginTop: '0.75rem' }}>
      <div className="font-semibold text-[var(--hf-text-primary)]">{headline}</div>
      <div style={grid}>
        {side(a, ca)}
        {side(b, cb)}
      </div>
      <details className="mt-1.5">
        <summary className="cursor-pointer opacity-80">Other sizes and how this is estimated</summary>
        <div className="mt-1.5 grid gap-x-3 gap-y-0.5" style={{ gridTemplateColumns: 'auto 1fr 1fr' }}>
          <span />
          <span className="font-semibold">{a.name}</span>
          <span className="font-semibold">{b.name}</span>
          {sizes.map((n) => {
            const x = costAt(a, n)
            const y = costAt(b, n)
            return [
              <span key={`l${n}`}>{bedLabel(n)} bed</span>,
              <span key={`a${n}`}>{x ? `~${usd100(x.cost.total)}/mo` : 'no price'}</span>,
              <span key={`b${n}`}>{y ? `~${usd100(y.cost.total)}/mo` : 'no price'}</span>,
            ]
          })}
        </div>
        <p className="m-0 mt-1.5 opacity-80">
          7% mortgage over 30 years, {downLabel(chosen.down)}, the ZIP&apos;s average property tax and 0.4% insurance, on Zillow&apos;s ZIP median home value for the size (single-family and condos combined).
          {californiaNote ? ' Property tax runs low in California, where a home is reassessed when it sells.' : ''}
        </p>
      </details>
    </section>
  )
}
