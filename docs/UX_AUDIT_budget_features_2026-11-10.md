# UX audit: monthly budget, bedroom picker, monthly cost line and Zillow link (2026-11-10)

Standard: `docs/UX_PRINCIPLES_DRAFT.md` (six owner rules plus Candidates A "say what a number means where it appears" and B "no silent gaps", both counted as rules since the owner confirmed 2026-11-05). Same method as `docs/UX_AUDIT.md`. This covers only the four features shipped 2026-11-10 (commits ad87d5bb, 0848ac56, 41255419, 21578741).

**Conclusion (first pass, 2026-11-10): Level 0 (not certified).** 9 FAILs, none fixed, none owner-accepted. Rule 6 passes.

**Re-audit 2026-11-11: Level 0 at the time, 1 open FAIL (G1) plus 3 findings. G1, the 375px wrap (G2), the silent last-chip tap (G3) and the cost missing from the map panels (G4) were fixed the same day; no FAIL or finding is open now except the compare views, and Level 1 still needs an independent re-check and the owner's sign-off. See the last section.**

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
- 2026-11-10, next commit: F1 fixed (the Zillow link moved off the rows into the expanded row, shown only for places inside the cap). F2 fixed (bedrooms and down payment live on the profile page, saved with the account profile and mirrored into the Explorer's local settings; the filter sheet now only shows "Using N bedrooms and $X down. Change in your profile" with a link). F3 and F4 fixed (no bedroom chips or down payment field in the filter sheet; the cost estimate turns on only after a bedroom count is set on the profile or a cap is set). F7 fixed (one-tap caps "Your current cost" and "30% of your income" appear when the profile has them). Checked in the desktop browser: profile to Explorer flow, 1,253 cost lines, zero Zillow links on rows, link present in the expanded Pelham row, 30% chip set the cap to $10,000 and cut results to 1,301. Not checked: signed-in save to the account profile, and the 375px layout.
- Still open: none from the nine listed above.
- 2026-11-10, follow-up commit: the per-row basis sentence from the F8 fix is gone (it repeated on every row and broke Rule 4); the basis now appears once in the explainer bar under the sort row, and rows keep only the exceptions (low California tax, no data, over budget). "Over budget" uses the Trovamo score-low color instead of stock amber. The max-per-month input is 40px tall (the touch control token) and uses the border, radius and text tokens.
- Not an owner decision (corrected): the owner said only that having to go to the profile to change bedrooms is a hassle, as an observation, not a choice. Claude then added bedroom chips to the filter sheet as well as the profile page, which departs from Rule 2 (one home per action) and is NOT owner-accepted; it stays an open FAIL until the owner decides. The value is still stored once: a change in the sheet is written to the profile (local settings, and the account profile when signed in), so both screens show the same number. Down payment is still edited only on the profile page. Signed-in write-through was not tested in a browser (no account available).
- 2026-11-10, owner decision (asked and answered "all in the sheet"): bedrooms, down payment and the monthly cap are now set together in the Explorer's filter sheet, which resolves the split across two screens (F2 closed as owner-decided). The profile page keeps income and current cost and shows the home budget as a read-only summary with a link to the Explorer. A change in the sheet is still written to the profile (local settings, and the account profile when signed in, debounced), so other screens read the same value. Checked in the desktop browser: sheet down-payment input formats with commas and is 40px tall, profile summary reads "3 bedrooms, $250,000 down". Not checked: signed-in account save, phone width.
- 2026-11-10, owner approved: in the expanded row, "View full breakdown" comes first as the primary action and the Zillow link follows as a quieter secondary link ("4+ bed homes on Zillow ↗", secondary text color, smaller), so the in-app action is the one obvious next step (Rule 1). Checked in the desktop browser on Glen Rock: link order and Zillow URL correct.
- 2026-11-11, owner request: bedrooms are now pick-one-or-more. With a monthly cap a place stays if any chosen size fits and its row shows the biggest chosen size that fits (a 5-bed for the price of a 4-bed wins); a place with no price for one of the chosen sizes is kept, so adding a size never removes a place. With no cap a row shows the range across the chosen sizes ("~$4,623 to $6,495/mo · 3 to 4 bed"). The last chip cannot be unselected; Clear all resets. Saved single counts still load. Checked in the desktop browser (4 bed 1,250; 4 or 5+ 1,273; 3, 4 or 5+ 1,370; 3 only 1,321 at a $8,000 cap). Not checked: signed-in save of a list of sizes, phone width. This audit's headline (Level 0) was never updated after the fixes above and no re-audit has been run.


---

## Re-audit 2026-11-11

Standard and method as above. Run in a headless browser against the current `main` (multi-select bedrooms included) on the dev server; desktop 1300px, phone 375px.

**Independence.** The multi-select bedroom change (commit 6f5d433) was built in this same session, so the rows it touches (Rule 3, Rule 5, G2, G3) are not graded independently. Level 1 needs a re-check of those rows by someone who did not build them, and the owner's sign-off on the owner-decided rows (Rule 2, Rule 3 chips in the sheet).

### What was checked and how

| View | Result | How |
|---|---|---|
| Catalog list, desktop, empty storage (fresh visitor) | 0 cost lines, 0 Zillow links, no explainer bar (1,476 rows) | Browser, DOM count |
| Filter sheet, desktop, before any choice | No bedroom chip selected; down payment field already reads 600,000; max per month empty; no suggested caps | Browser, DOM |
| List with bedrooms 3 and 4 chosen, no cap | 1,334 rows with a cost, 142 with a stated reason, 0 blank; explainer bar present; 241 California cards say tax likely low | Browser, DOM count |
| Same, cap $3,000 | 1,116 rows (360 removed); 973 with a cost, 142 with a reason; 0 "Over budget" tags (over-budget places are removed, not tagged) | Browser, DOM count |
| Expanded row, desktop (priced place, 3 bed, cap $7,000) | "View full breakdown" first, "3+ bed homes on Zillow" below it, quieter | Browser, element order |
| Filter sheet and list, 375px | No horizontal overflow; sheet and chips usable; cost line and no-data line wrap (see G2) | Browser, screenshots |
| Profile page, signed out | Shows "Not set yet" and says bedrooms, down payment and cap are set in the Explorer's filters, with a link | Browser, text |
| Map markers, mobile bottom sheet, detail panel, compare tray | No cost anywhere | Code only: budget identifiers appear only in the catalog page, list view, filter sheet, API route, profile page and types |
| Signed-in save of a list of sizes, other pages | Not checked | No account available |

### Per-rule results

| Rule | Result | Evidence |
|---|---|---|
| 1. One primary action per state | PASS | Expanded row: "View full breakdown" above the Zillow link, which is smaller and secondary; no Zillow link on any list row. |
| 2. One home per action | PASS (owner-decided) | Bedrooms, down payment and cap are set only in the filter sheet; profile shows a read-only summary and links back. Owner decision 2026-11-10 ("all in the sheet"). |
| 3. Controls follow selection | PASS (owner-decided) | Chips and fields are visible before a choice by owner decision; no chip is pre-selected and nothing is applied until a choice. See G1 for the pre-filled number. |
| 4. Quiet by default | PASS | Fresh visitor sees no cost line, Zillow link or explainer; the California caveat shows only on California cards; reasons show only after a choice. |
| 5. Start from a suggestion | FAIL (G1) | Suggested caps ("Your current cost", "30% of your income") only appear when a profile has income or a current cost. A fresh visitor faces an empty cap and a down payment already set to $600,000, the owner's own scenario, with no stated basis. |
| 6. Search finds, panels edit | PASS | Budget is edited only in the filter sheet. |
| A. Say what a number means | PASS | The basis (rate, down payment, tax, insurance, ZIP median, and the sizes chosen) shows once in the explainer bar when a budget is chosen; the sheet text repeats it. |
| B. No silent gaps | PASS | With 3 and 4 chosen every row shows a cost or a reason: 1,334 plus 142 equals 1,476. |

### Findings

| ID | Rule | Finding | Smallest fix |
|---|---|---|---|
| G1 | 5 (and 4) | Down payment is pre-filled with 600,000 and no cap suggestion exists for a visitor with no profile. | Leave the down payment empty until chosen, or label the default ("example") and offer a one-tap cap from the visitor's chosen bedrooms (for example the metro median monthly cost for that size). |
| G2 | none (layout) | At 375px the multi-size range ("~$4,623 to $6,495/mo · 3 to 4 bed") wraps to 3 lines and the no-data line ("No 3 or 4-bed cost: no price data for this ZIP") to 4, in the narrow place column. | Show "from ~$4,623/mo · 3 to 4 bed" (cheapest only) and shorten the no-data line to "No price data". |
| G3 | none (feedback) | Tapping the last selected bedroom chip does nothing and says nothing. | Keep it selected but show the helper line "Pick at least one" or let the last chip clear the choice back to the unchosen state. |
| G4 | A | The map, bottom sheet, detail panel and compare tray filter by the budget but never show the number (unchanged from the first audit's coverage gap). | Show the cost line in the bottom sheet and detail panel. |

### Level

Level 0 stands: G1 is an unfixed FAIL with no owner-accepted entry. All nine first-pass FAILs are closed and Rules 1, 2, 3, 4, 6, A and B pass. Closing G1, or an owner-accepted entry for it, would reach Level 1 for these features, subject to the independence note above.

### Verification statement

Rendered in the browser: fresh-visitor list and filter sheet (desktop), list with a budget chosen and with a cap (desktop), expanded priced row (desktop), filter sheet and list at 375px, profile page signed out. Code only: map, bottom sheet, detail panel, compare tray, other pages. Not checked: signed-in save, the account profile with a list of sizes, a real phone. Nothing was changed by this re-audit except this document.

### Fix log, 2026-11-11 (after the re-audit)

- G1 fixed. The down payment is no longer pre-filled with $600,000: it starts empty with the placeholder "20% of price", and until the visitor types an amount every place is priced at 20% down, which the explainer bar says ("after 20% down"). Clearing the field returns to 20%. A visitor with no profile now gets a starting cap: once a bedroom count is chosen, a "Typical place $4,100" chip sets the cap to the median cost across all places at the chosen sizes (a fresh visitor with nothing chosen still sees no suggestions or costs). Saved down payments that were never chosen are dropped; saved ones the visitor chose are kept; the account profile accepts a null down payment.
- G2 fixed. At 375px the multi-size line reads "from ~$7,293/mo · 3-4 bed" (2 lines, was 3; the full range is in the tooltip) and a place with no price reads "No cost · no ZIP price data" or "No cost · too few sales" (2 lines, was 4; the full reason is in the tooltip).
- Checked in the browser (desktop and 375px): fresh sheet empty and no chips; "Typical place $4,100" cap gives 808 of 1,476 places at 3 bed; typing $250,000 changes the explainer to "after $250,000 down" and clearing returns to "after 20% down".
- Still open (findings, not rule FAILs): G3 (last chip tap gives no feedback), G4 (map, bottom sheet, detail panel never show the cost). Not checked: signed-in save with a null down payment, a real phone.
- Independence: G1 and G2 were fixed by the same session that built the multi-select change, so Level 1 needs someone else to re-run the rows above.

### Fix log, 2026-11-12 (G3 and G4)

- G3 fixed. Tapping the last selected bedroom chip with nothing else set (no cap, no typed down payment) clears the budget back to the unchosen state: no cost on any row, no "Typical place" chip. With a cap or down payment set the chip stays selected and a line under the chips says "Keep at least one size while a cap or down payment is set. Clear them to turn the budget off."; choosing another size clears the line.
- G4 fixed for the places the budget filters on the map. One shared component (BudgetCostLine) now draws the cost line on list rows, the desktop detail panel and the mobile bottom sheet, with the same words, tooltip, over-budget tag and California note. Checked in the browser: desktop detail panel for Larchmont reads "~$10,976/mo · 3 bed"; the bottom sheet (tablet width 700px, tapping a bubble) shows "~$3,839/mo · 3 bed" under Chelsea, MA. Not shown before a budget is chosen.
- Still open: the compare tray and `/saved/compare` do not show the cost (they never filtered by budget). Not checked: the bottom sheet on a real phone (reached at 700px because the search box is hidden below that), signed-in save with a blank down payment.
- Independence: same session built and fixed these, so Level 1 needs someone else to re-run the rows.

### Correction and fix log, 2026-11-12 (compare views)

- Correction to the audit. The "Code only" row for the compare views said no cost appears there. That was wrong for `/saved/compare`: for two places in the same metro it already shows an estimated monthly cost for each (the InMetroPrice block), using the Explorer's budget. My search looked for four identifiers and that block imports the budget types without matching them. The compare tray in the Explorer did not show a cost.
- Compare tray. Each chip now ends with the place's cost ("Pelham · ~$9,005/mo", or "from ~$X/mo" for several sizes, or "no cost"), with the bedroom count and reason in the tooltip; shown only once a budget is chosen. A place hidden by the current search still shows its raw key without a cost (an existing quirk of the tray, not changed).
- Bug fixed on `/saved/compare`: after the down payment became optional the basis line would have read "$0 down" for a visitor on the default 20%; it now reads "20% down" (checked: "Basis: 7% mortgage, 20% down, ZIP average property tax ... and 0.4% insurance").
- Bug fixed: a compare context saved in a browser tab before multi-select stored one bedroom count; reading it would have thrown. It is now normalized on read (checked by injecting the old shape: the compare page renders and shows "$600,000 down" for a down payment the visitor had chosen).
- Checked in the browser: tray without a budget shows names only; with 3 bed chosen the Pelham chip shows its cost; the compare page for Larchmont and Pelham shows "Same metro: estimated monthly cost for a 3-bedroom home · Pelham is $1,971/mo lower". Not checked: pairs in different metros (they use the existing relocation estimate, not the budget), signed-in save, a real phone.
