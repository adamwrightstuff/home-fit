# UX audit: monthly budget, bedroom picker, monthly cost line and Zillow link (2026-11-10)

Standard: `docs/UX_PRINCIPLES_DRAFT.md` (six owner rules plus Candidates A "say what a number means where it appears" and B "no silent gaps", both counted as rules since the owner confirmed 2026-11-05). Same method as `docs/UX_AUDIT.md`. This covers only the four features shipped 2026-11-10 (commits ad87d5bb, 0848ac56, 41255419, 21578741).

**Conclusion: Level 0 (not certified).** 9 FAILs, none fixed, none owner-accepted. Rule 6 passes.

## What was checked and how

| View | Result | How |
|---|---|---|
| Catalog list, desktop, empty storage (fresh visitor) | Cost line and Zillow link on 1,253 of 1,476 rows | Browser, DOM count |
| Catalog list, 375px, empty storage | Same line wraps to 3 lines under the place name | Browser, screenshot |
| Filter sheet, 375px | Monthly Budget section present | Browser, screenshot |
| Catalog map and mobile bottom sheet | Budget filter changes which places show; no cost shown | Browser plus grep |
| Expanded row and detail panel | No cost, no Zillow link (cost count stayed 1,253 after opening a row) | Browser plus grep |
| Twin finder, compare tray, `/saved/compare`, `/search`, `/results`, `/p/[id]`, `/saved/[id]`, `/neighborhoods/[slug]` | No cost anywhere | Code only: `filterBudget`, `budgetCost` and `housing_cost` appear in just the catalog page, list view, filter sheet, API route and types |
| `/profile`, quiz | Neither reads or sets the budget, bedrooms or down payment | Code only |
| Vacation screens | Not applicable (not a residential decision) | |

## Per-rule results

| Rule | Result | Evidence |
|---|---|---|
| 1. One primary action per state | FAIL (F1) | Every list row now carries an underlined external link ("See 4+ bed homes on Zillow") beside the row's real action, opening a place. At 375px it wraps to three lines and pushes the profile chips down. 1,253 rows leave the app. |
| 2. One home per action | FAIL (F2, F3) | Bedrooms and down payment are personal settings edited only in the filter sheet, while income and current monthly cost live on the profile. "What can I afford" now has two homes (profile income, filter max per month). "Clear all" resets the max but leaves bedrooms and down payment. |
| 3. Controls follow selection | FAIL (F4) | The bedroom chips show "4 bed" selected and the down payment shows 600000 before the visitor chose anything, and both change cards on screen even with no max set. |
| 4. Quiet by default | FAIL (F5, F6) | F5: a fresh visitor with empty storage sees the cost line and Zillow link on 1,253 rows, driven by defaults of 4 bedrooms and $600,000 down. Those defaults are the owner's own scenario, not an evidence-backed default for most people. F6: the California tax caveat appears only in the filter sheet, not on the California cards it affects. |
| 5. Start from a suggestion | FAIL (F7) | Max per month is empty ("No limit") and down payment is a bare number. The profile already holds income and current monthly cost ($11,700 for the owner) that could seed a suggested cap; nothing does. |
| 6. Search finds, panels edit | PASS | The budget is edited only in the filter sheet. Search results show the cost line read-only. |
| A. Say what a number means where it appears | FAIL (F8) | A card says "~$6,495/mo · 4 bed" and the basis (principal and interest, tax, insurance, Zillow ZIP median for single-family and condo combined) is only in a hover tooltip, which touch screens never show, and in a seven-line paragraph in the filter sheet. |
| B. No silent gaps | FAIL (F9) | 223 rows show nothing where a cost would be (for example Ridgewood), and the sheet's note that such places are not filtered out is the only trace. A card should say "no 4-bed price data" with the reason. |

## Coverage gap (counted under A and 2)

The budget filter removes places from the map and the list, but the map, the mobile bottom sheet, the detail panel and the compare views never show the number being filtered on. A visitor filtering on the map cannot see why a place disappeared. This is recorded inside F8 and F2, not as a separate FAIL.

## Gap table

| ID | Rule | Fix, smallest first |
|---|---|---|
| F5 | 4 | Show the cost line and Zillow link only when the visitor has chosen a budget or bedroom count; default state shows none. Remove the owner's 4 bed and $600,000 as silent defaults. |
| F9 | B | Put "no 4-bed price data" on rows with no cost. |
| F8 | A | Put the basis on the card in words, not a tooltip ("P&I at 7%, tax, insurance; ZIP median"). |
| F1 | 1 | Move the Zillow link to the expanded row or detail panel, and show it only for places inside the budget. |
| F6 | 4 | Show "tax likely low (CA)" on the affected cards. |
| F7 | 5 | Offer "your current cost" and "your income x 30%" as one-tap caps when the profile has them. |
| F2 | 2 | Make the profile the one home for income, down payment and bedrooms; the filter sheet shows them and links back. Make "Clear all" reset bedrooms and down payment too. |
| F3, F4 | 2, 3 | Show bedrooms and down payment only after the visitor turns the budget on. |

## Verification statement

Rendered in the browser: desktop list and 375px list with empty storage, the 375px filter sheet, and the DOM count of cost lines and Zillow links. Everything under "Code only" is from searching the frontend for the three identifiers above; no screen was rendered for it. The Zillow link was checked only for its URL (Pelham matches the tested pattern in the ticket); it was not opened. Nothing was changed by this audit.

## Fix log

- 2026-11-10, c06c16c5: F5 fixed (cost line and Zillow link only after the visitor chooses a bedroom count, cap or down payment; no chip is pre-selected; Clear all resets bedrooms and down payment). Also resolves part of F4 and the Clear all half of F2.
- 2026-11-10, next commit: F8 fixed (the card states its basis in words: mortgage rate, down payment, tax and insurance, ZIP median price). F9 fixed (rows with no cost say why: no price data for the ZIP, too few Zillow sales of that size, or no property tax data). F6 fixed (California cards say tax likely low). Checked in the desktop browser: 223 rows now show a reason instead of a blank.
- Still open: F1 (Zillow link on every row), F2 (profile is not the one home for down payment and bedrooms), F3 and the rest of F4 (controls before selection), F7 (no suggested cap).
