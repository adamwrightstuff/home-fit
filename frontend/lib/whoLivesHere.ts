/**
 * "Who lives here": plain facts about the people in a place. No score, no weight, not counted in any total
 * (docs/WHO_LIVES_HERE.md). Missing data is shown as unavailable, never as zero.
 */

export const ACS_INCOME_TOPCODE = 250001
export const ACS_HOME_VALUE_TOPCODE = 2000001

export type WhoLivesHereRow = { label: string; value: string }
export type WhoLivesHereGroup = { title: string; rows: WhoLivesHereRow[] }

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function money(v: number | null, topcode: number): string {
  if (v === null || v <= 0) return 'n/a'
  if (v >= topcode) return `$${(topcode - 1).toLocaleString('en-US')}+`
  return `$${Math.round(v).toLocaleString('en-US')}`
}

function pct(v: number | null, scale: 'percent' | 'fraction'): string {
  if (v === null || v < 0) return 'n/a'
  const p = scale === 'fraction' ? v * 100 : v
  return `${Math.round(Math.min(100, p))}%`
}

/** Largest-remainder rounding so the three age shares always add to 100. */
export function ageMixWholePercents(age: { under_18?: number; age_18_64?: number; age_65_plus?: number } | null | undefined): number[] | null {
  if (!age || typeof age.under_18 !== 'number') return null
  const raw = [age.under_18, age.age_18_64, age.age_65_plus].map((v) => (typeof v === 'number' ? v : 0))
  const total = raw.reduce((a, b) => a + b, 0)
  if (!(total > 0)) return null
  const scaled = raw.map((v) => (v / total) * 100)
  const floors = scaled.map(Math.floor)
  let left = 100 - floors.reduce((a, b) => a + b, 0)
  const order = scaled.map((v, i) => [v - Math.floor(v), i] as const).sort((a, b) => b[0] - a[0])
  for (const [, i] of order) {
    if (left <= 0) break
    floors[i] += 1
    left -= 1
  }
  return floors
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function buildWhoLivesHere(pillars: any): { groups: WhoLivesHereGroup[]; geography: string | null } {
  const hv = pillars?.housing_value
  const sm = (hv && typeof hv.summary === 'object' && hv.summary) || hv || {}
  const div = pillars?.diversity || {}
  const edu = div.education_attainment || null
  const groups: WhoLivesHereGroup[] = []

  const income: WhoLivesHereRow[] = [
    { label: 'Median household income', value: money(num(sm.median_household_income), ACS_INCOME_TOPCODE) },
    { label: 'Mean household income', value: money(num(sm.mean_household_income), Infinity) },
    { label: 'Median home value', value: money(num(sm.median_home_value), ACS_HOME_VALUE_TOPCODE) },
  ]
  if (income.some((r) => r.value !== 'n/a')) groups.push({ title: 'Income and wealth', rows: income })

  if (edu && (num(edu.bachelor_pct) !== null || num(edu.grad_pct) !== null)) {
    groups.push({
      title: 'Education (adults 25 and over)',
      rows: [
        { label: "Bachelor's degree or higher", value: pct(num(edu.bachelor_pct), 'percent') },
        { label: 'Graduate degree', value: pct(num(edu.grad_pct), 'percent') },
      ],
    })
  }

  const renter = num(sm.renter_pct)
  if (renter !== null) {
    groups.push({
      title: 'Households',
      rows: [
        { label: 'Renters', value: pct(renter, 'fraction') },
        { label: 'Homeowners', value: pct(1 - renter, 'fraction') },
      ],
    })
  }

  const ages = ageMixWholePercents(div.raw_shares?.age)
  if (ages) {
    groups.push({
      title: 'Age',
      rows: [
        { label: 'Under 18', value: `${ages[0]}%` },
        { label: '18 to 64', value: `${ages[1]}%` },
        { label: '65 and over', value: `${ages[2]}%` },
      ],
    })
  }

  const geo = typeof sm.geo_level === 'string' ? sm.geo_level : null
  const geography =
    geo === 'tract' ? 'the surrounding Census tracts' : geo === 'incorporated_place' ? 'the whole city or town' : geo ? 'the surrounding area' : null
  return { groups, geography }
}
