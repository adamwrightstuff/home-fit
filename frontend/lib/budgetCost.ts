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

export interface BudgetFilter {
  beds: 1 | 2 | 3 | 4 | 5
  /** Maximum all-in monthly cost; null means no budget filter. */
  max: number | null
  /** Cash down payment. */
  down: number
}

export const DEFAULT_BUDGET: BudgetFilter = { beds: 4, max: null, down: 600000 }
export const MORTGAGE_RATE = 0.07
export const INSURANCE_RATE = 0.004

export interface MonthlyCost {
  value: number
  principalInterest: number
  tax: number
  insurance: number
  total: number
}

export function monthlyCost(hc: HousingCost | null | undefined, budget: BudgetFilter): MonthlyCost | null {
  if (!hc || hc.tax == null) return null
  const value = hc.v[budget.beds - 1]
  if (value == null) return null
  const loan = Math.max(value - budget.down, 0)
  const r = MORTGAGE_RATE / 12
  const n = 360
  const principalInterest = loan > 0 ? (loan * r) / (1 - Math.pow(1 + r, -n)) : 0
  const tax = hc.tax / 12
  const insurance = (value * INSURANCE_RATE) / 12
  return { value, principalInterest, tax, insurance, total: principalInterest + tax + insurance }
}

/**
 * Zillow for-sale search for a place with N or more bedrooms, no API:
 * https://www.zillow.com/homes/for_sale/Pelham,-NY/4-_beds/ (Zillow's filter is N or more, not exactly N).
 */
export function zillowSearchUrl(name: string, stateAbbr: string, beds: number): string {
  const city = name.trim().replace(/\s+/g, '-')
  return `https://www.zillow.com/homes/for_sale/${encodeURIComponent(city)},-${encodeURIComponent(stateAbbr)}/${beds}-_beds/`
}

/** True when the place has a cost and it is over the budget cap. Places with no data are not excluded. */
export function overBudget(hc: HousingCost | null | undefined, budget: BudgetFilter): boolean {
  if (budget.max == null) return false
  const c = monthlyCost(hc, budget)
  return c != null && c.total > budget.max
}
