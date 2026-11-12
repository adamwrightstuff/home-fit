'use client'

import { bedLabel, bedsLabel, bestCost, costGapReason, DEFAULT_BUDGET, downLabel, type BudgetFilter, type HousingCost } from '@/lib/budgetCost'

export interface PriceRow {
  name: string
  metro: string
  cost: HousingCost | null
}

const usd = (n: number) => `$${Math.round(n).toLocaleString('en-US')}`

/**
 * Housing price for two places in the SAME metro, where the metro-to-metro estimate has nothing to say.
 * With a home budget chosen in the Explorer: estimated monthly cost (P&I after the down payment, ZIP property
 * tax, insurance). Without one: ZIP median home values only, since a monthly cost needs a down payment the
 * visitor has not given.
 */
export default function InMetroPrice({ a, b, budget, income }: { a: PriceRow; b: PriceRow; budget: BudgetFilter | null; income: number | null }) {
  const chosen = budget?.chosen ? budget : null
  const box = 'rounded-xl border border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] px-3 py-2 text-xs text-[var(--hf-text-secondary)]'

  const cell = (r: PriceRow): { main: string; sub: string; n: number | null } => {
    if (chosen) {
      const bc = bestCost(r.cost, chosen)
      if (!bc) return { main: 'No price', sub: costGapReason(r.cost, chosen), n: null }
      const main = chosen.max == null && bc.low !== bc.high ? `${usd(bc.low)} to ${usd(bc.high)}/mo` : `${usd(bc.cost.total)}/mo`
      const share = income ? ` · ${Math.round((bc.cost.total * 12 / income) * 100)}% of income` : ''
      return {
        main,
        sub: `${bedLabel(bc.beds)}-bed, ZIP median ${usd(bc.cost.value)}${share}${bc.unknownSize ? ' · some chosen sizes have no price here' : ''}${chosen.max != null && !bc.fits ? ' · over your cap' : ''}`,
        n: bc.cost.total,
      }
    }
    const have = ([3, 4] as const).map((n) => ({ n, v: r.cost?.v[n - 1] ?? null })).filter((x) => x.v != null)
    if (have.length === 0) return { main: 'No price', sub: costGapReason(r.cost, DEFAULT_BUDGET), n: null }
    return { main: have.map((x) => `${usd(x.v as number)} (${x.n}-bed)`).join(' · '), sub: 'ZIP median home value', n: have[0].v }
  }

  const ca = cell(a)
  const cb = cell(b)
  const diff = ca.n != null && cb.n != null && ca.n !== cb.n ? Math.abs(ca.n - cb.n) : null
  const cheaper = diff != null ? (ca.n! < cb.n! ? a.name : b.name) : null

  return (
    <section aria-label="Housing price within the metro" className={box} style={{ marginTop: '0.75rem' }}>
      <div className="font-semibold text-[var(--hf-text-primary)]">
        Same metro: {chosen ? `estimated monthly cost for a ${bedsLabel(chosen.beds)}-bedroom home` : 'ZIP median home value'}
        {cheaper && diff != null && <> · {cheaper} is {chosen ? `${usd(diff)}/mo` : usd(diff)} lower</>}
      </div>
      <div style={{ display: 'grid', gap: '0.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginTop: 6 }}>
        {[{ r: a, c: ca }, { r: b, c: cb }].map(({ r, c }) => (
          <div key={r.name}>
            <div className="font-semibold">{r.name}</div>
            <div className="text-[var(--hf-text-primary)]">{c.main}</div>
            <div className="opacity-80">{c.sub}</div>
          </div>
        ))}
      </div>
      <div className="mt-1 opacity-80">
        {chosen
          ? `Basis: 7% mortgage, ${downLabel(chosen.down)}, ZIP average property tax (IRS itemizers; low in California) and 0.4% insurance, on Zillow's ZIP median for the size. Single-family and condos combined.`
          : 'Set bedrooms and a down payment in the Explorer to see a monthly cost here. Zillow ZIP values, single-family and condos combined.'}
      </div>
    </section>
  )
}
