'use client'

import { bedLabel, bedsLabel, bestCost, costGapReason, costGapShort, downLabel, type BudgetFilter, type HousingCost } from '@/lib/budgetCost'

/**
 * The monthly cost estimate for a place under the visitor's budget settings: the same line on the list row, the map bottom sheet
 * and the desktop detail panel. Only render it when a budget has been chosen (nothing is shown before that).
 */
export default function BudgetCostLine({
  housingCost,
  stateAbbr,
  budget,
  large = false,
}: {
  housingCost: HousingCost | null | undefined
  stateAbbr: string | null | undefined
  budget: BudgetFilter
  /** Larger text for the detail panel and bottom sheet; the list row uses the small size. */
  large?: boolean
}) {
  const size = large ? 'text-xs' : 'text-[0.65rem]'
  const bc = bestCost(housingCost, budget)
  if (!bc) {
    return (
      <div
        className={`${size} text-[var(--hf-text-tertiary)]`}
        title={`No ${bedsLabel(budget.beds)}-bed cost: ${costGapReason(housingCost, budget)}`}
      >
        No cost · {costGapShort(housingCost, budget)}
      </div>
    )
  }
  const mc = bc.cost
  const showRange = budget.max == null && bc.minBeds !== bc.maxBeds
  const across = showRange ? ` Across your sizes it runs about $${Math.round(bc.low).toLocaleString('en-US')} to $${Math.round(bc.high).toLocaleString('en-US')}.` : ''
  return (
    <div
      className={`${size} font-medium tabular-nums text-[var(--hf-text-secondary)]`}
      title={`Estimate for a ${bedLabel(bc.beds)}-bedroom home at the ZIP median value of $${Math.round(mc.value).toLocaleString('en-US')}: principal and interest after ${downLabel(budget.down)}, plus average property tax and insurance.${across}`}
    >
      {showRange
        ? `from ~$${Math.round(bc.low).toLocaleString('en-US')}/mo · ${bedLabel(bc.minBeds)}-${bedLabel(bc.maxBeds)} bed`
        : `~$${Math.round(mc.total).toLocaleString('en-US')}/mo · ${bedLabel(bc.beds)} bed`}
      {!bc.fits && !bc.unknownSize && (
        <>
          {' · '}
          <span className="font-semibold text-trovamo-score-low">Over budget</span>
        </>
      )}
      {stateAbbr === 'CA' && <div className="font-normal text-[var(--hf-text-tertiary)]">Tax likely low (California)</div>}
    </div>
  )
}
