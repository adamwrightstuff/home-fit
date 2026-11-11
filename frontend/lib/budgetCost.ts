/**
 * Monthly cost of an N-bedroom home in a catalog place: principal and interest on the Zillow ZIP value
 * for that bedroom count, plus the ZIP's average real estate tax (IRS SOI, itemizers) and insurance.
 * Built from data/catalog_housing_costs.json by scripts/baselines/build_catalog_housing_costs.py.
 */
export interface HousingCost {
  zip: string
  /** Zillow ZIP value for 1, 2, 3, 4 and 5+ bedrooms; null when Zillow has no value for that size. */
  v: (number | null)[]
  /** Average real estate tax per year (IRS itemizers in the ZIP); null when too few returns. */
  tax: number | null
}

export type Beds = 1 | 2 | 3 | 4 | 5
export const ALL_BEDS: Beds[] = [1, 2, 3, 4, 5]

export interface BudgetFilter {
  /** Bedroom counts the visitor would take, ascending (5 means 5 or more). With a cap, a place passes if any of them fits. */
  beds: Beds[]
  /** Maximum all-in monthly cost; null means no budget filter. */
  max: number | null
  /** Cash down payment. */
  down: number
  /** True once the visitor has picked a bedroom count, a cap or a down payment. Until then no cost is shown anywhere. */
  chosen: boolean
}

export const DEFAULT_BUDGET: BudgetFilter = { beds: [4], max: null, down: 600000, chosen: false }
export const MORTGAGE_RATE = 0.07
export const INSURANCE_RATE = 0.004

export interface MonthlyCost {
  value: number
  principalInterest: number
  tax: number
  insurance: number
  total: number
}

/** Reads a saved bedroom value: a list of counts, or a single count saved before multi-select. */
export function normalizeBeds(v: unknown): Beds[] {
  const raw = Array.isArray(v) ? v : [v]
  const out = ALL_BEDS.filter(b => raw.some(x => Number(x) === b))
  return out.length ? out : DEFAULT_BUDGET.beds
}

export const bedLabel = (n: number): string => (n >= 5 ? '5+' : String(n))

/** "4", "3 or 4", "3, 4 or 5+" */
export function bedsLabel(beds: Beds[]): string {
  const l = beds.map(bedLabel)
  return l.length <= 1 ? (l[0] ?? '') : `${l.slice(0, -1).join(', ')} or ${l[l.length - 1]}`
}

/** Taps a bedroom chip: the first tap chooses it, later taps add or remove it, and the last one cannot be removed. */
export function toggleBed(budget: BudgetFilter, b: Beds): BudgetFilter {
  if (!budget.chosen) return { ...budget, beds: [b], chosen: true }
  if (budget.beds.includes(b)) return budget.beds.length > 1 ? { ...budget, beds: budget.beds.filter(x => x !== b) } : budget
  return { ...budget, beds: ALL_BEDS.filter(x => x === b || budget.beds.includes(x)) }
}

function costForBeds(hc: HousingCost | null | undefined, down: number, beds: Beds): MonthlyCost | null {
  if (!hc || hc.tax == null) return null
  const value = hc.v[beds - 1]
  if (value == null) return null
  const loan = Math.max(value - down, 0)
  const r = MORTGAGE_RATE / 12
  const n = 360
  const principalInterest = loan > 0 ? (loan * r) / (1 - Math.pow(1 + r, -n)) : 0
  const tax = hc.tax / 12
  const insurance = (value * INSURANCE_RATE) / 12
  return { value, principalInterest, tax, insurance, total: principalInterest + tax + insurance }
}

export interface BestCost {
  /** The bedroom count this place is shown at. */
  beds: Beds
  cost: MonthlyCost
  /** False when a cap is set and none of the chosen sizes that have a price fits under it. */
  fits: boolean
  /** True when at least one chosen size has no price here, so a size we cannot price might still fit. */
  unknownSize: boolean
  /** Lowest and highest total across the chosen sizes that have data, and the smallest and largest of those sizes. */
  low: number
  high: number
  minBeds: Beds
  maxBeds: Beds
}

/**
 * Cost of a place across the chosen bedroom counts. With a cap, the biggest chosen size that fits under it (so a 5-bed for the
 * price of a 4-bed wins); if none fits, the cheapest. With no cap, the smallest chosen size, and low to high shows the range.
 * Null when no chosen size has a price (or the ZIP has no tax figure).
 */
export function bestCost(hc: HousingCost | null | undefined, budget: BudgetFilter): BestCost | null {
  const options = budget.beds.map(n => ({ n, c: costForBeds(hc, budget.down, n) })).filter((o): o is { n: Beds; c: MonthlyCost } => o.c != null)
  if (options.length === 0) return null
  const totals = options.map(o => o.c.total)
  const low = Math.min(...totals)
  const high = Math.max(...totals)
  const minBeds = options[0].n
  const maxBeds = options[options.length - 1].n
  let pick = options[0]
  let fits = true
  if (budget.max != null) {
    const fitting = options.filter(o => o.c.total <= budget.max!)
    if (fitting.length > 0) pick = fitting[fitting.length - 1]
    else {
      pick = options.reduce((a, b) => (b.c.total < a.c.total ? b : a))
      fits = false
    }
  }
  return { beds: pick.n, cost: pick.c, fits, unknownSize: options.length < budget.beds.length, low, high, minBeds, maxBeds }
}

/**
 * Zillow for-sale search for a place with N or more bedrooms, no API:
 * https://www.zillow.com/homes/for_sale/Pelham,-NY/4-_beds/ (Zillow's filter is N or more, not exactly N).
 */
export function zillowSearchUrl(name: string, stateAbbr: string, beds: number): string {
  const city = name.trim().replace(/\s+/g, '-')
  return `https://www.zillow.com/homes/for_sale/${encodeURIComponent(city)},-${encodeURIComponent(stateAbbr)}/${beds}-_beds/`
}

/** Why bestCost is null, in words for the card (so a missing number is never a blank). */
export function costGapReason(hc: HousingCost | null | undefined, budget: BudgetFilter): string {
  if (!hc) return 'no price data for this ZIP'
  if (budget.beds.every(b => hc.v[b - 1] == null)) return 'Zillow has too few sales of this size in the ZIP'
  return 'no property tax data for this ZIP'
}

/**
 * True only when every chosen size has a price and none is under the cap. A place with no price for one of the chosen sizes is kept
 * (that size might fit), so adding a bedroom count never removes a place.
 */
export function overBudget(hc: HousingCost | null | undefined, budget: BudgetFilter): boolean {
  if (budget.max == null) return false
  const c = bestCost(hc, budget)
  return c != null && !c.fits && !c.unknownSize
}
