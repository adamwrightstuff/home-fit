# Audit: community safety property-crime weight (2026-10-25)

Read-only and offline. No code, tests, catalog or tracker file was changed. Nothing committed.

## Finding

The 0.35 was chosen, not fitted, and never had a source. It first appears in the pillar's first commit (491aaf1, 2026-05-13) as "violent (65%) + property (35%)", with no citation, no fit script and no document behind it. The commit that added the 0.15 retail-hub override (9d49be4, same day) is also unsourced. A search of docs/, analysis/ and git history finds no derivation for either number.

A derivation has since landed, but not in this checkout. Commit 1b6df81 (2026-10-24) is on origin/main and replaces 0.35 and 0.15 with a single weight of 0.098. Local main is 17 commits ahead and 9 behind origin/main and does not contain it. That is why the tracker (D9) and the 2026-10-24 audit say the weight is not derived "in this checkout". The 0.098 is the property share of total harm: national offense rates (BJS NIBRS, 2023) times cost per offense (McCollister, French and Fang 2010, Table 5), written by `scripts/baselines/derive_community_safety_weight.py` into `data/community_safety_harm_weights.json`. I read these with `git show` only. I did not check the inputs against the original papers (offline), so the rates and costs are as recorded in that commit, not independently confirmed.

## Sourced versus judgment

| Item | Status |
|---|---|
| 0.35 property, 0.65 violent | Judgment, undocumented. Not fitted. |
| 0.15 retail-hub weight and the 8x ratio and violent under 8 per 1,000 gate | Judgment, undocumented. |
| 0.098 (total social cost incl. murder) | Sourced formula, published inputs (as recorded in 1b6df81, unverified here). The choice to use total social cost rather than direct victim cost is a judgment, stated in that commit's docs. |
| Range 0.197 to 0.519 | Sensitivity of the same formula to how murder and suffering are valued. Computed from the recorded inputs. I re-ran the arithmetic: 0.098, 0.197, 0.299, 0.519 reproduce exactly. |

## Plausible range from published work

- Total cost, murder included: 0.098.
- Total cost, murder excluded: 0.197.
- Direct victim cost only (no pain and suffering): 0.299. This is the only view near the old 0.35.
- Direct victim cost, murder excluded: 0.519.
- Crime severity indexes (Cambridge Crime Harm Index, Statistics Canada Crime Severity Index) weight by sentencing seriousness and rank violent far above theft. The existing doc cites them. I did not see their weights offline, so I give no number from them. This is a TODO, not a parameter.
- Revealed preference (tier 2): the v2 design doc cites Gibbons 2004 (London), where criminal damage lowered prices and burglary showed no measurable price effect. That points toward a low property weight but does not give a number, and I did not retrieve the paper.

My proposed recorded range is 0.10 to 0.30, central 0.098. The 0.52 case is an outer bound, not a candidate: it requires dropping murder and all non-victim cost at once.

Caveat on the derivation itself, from the commit's own docs: harm share is computed on offense rates in dollars, but the pillar blends percentile slots, not rates. A harm share is therefore an approximation of the right weight on slots, not an exact one. The violent slot also counts offenses, so murder is 1.5% of violent offenses by count but 56% of violent harm (I re-computed 55.9%), meaning the violent slot under-represents murder.

## Score movement across the range (1,420 scored places, computed from stored slots)

Baseline is each place's stored score in this checkout (903 places at 0.35, 517 retail-hub places at 0.15; all 1,420 reproduce exactly from stored slots under that rule). The other 56 places have no community safety score and are excluded. Trend delta is kept. Slots are stored to 0.1, so figures are good to about 0.1 point.

| Weight tested | Mean change | Mean absolute change | 95th percentile | Max | Places over 5 pts | Over 10 pts | Spearman vs stored |
|---|---|---|---|---|---|---|---|
| 0.098 | -0.12 | 2.16 | 6.0 | 15.5 | 129 | 9 | 0.995 |
| 0.197 | -0.85 | 1.47 | 3.8 | 9.4 | 27 | 0 | 0.998 |
| 0.299 | -1.61 | 1.81 | 6.8 | 13.2 | 146 | 11 | 0.997 |
| 0.35 (no hub rule) | -1.99 | 2.00 | 9.1 | 17.7 | 255 | 52 | 0.994 |
| 0.519 | -3.24 | 4.77 | 16.7 | 32.7 | 467 | 225 | 0.974 |

Swing within the proposed range, per place, 0.098 to 0.299: mean 3.3 points, median 2.6, 95th percentile 9.2, max 17.9; 312 places move over 5 and 55 over 10. Across the narrower 0.098 to 0.197: mean 1.6, max 8.8, none over 10.

Effect on total score (pillar weight about 7.7 of 100): at 0.098 versus stored, mean -0.01 points, max 1.19 for any place. At 0.299, max 1.02. Across the proposed range no place's total moves more than about 1.2 points.

Who moves and why. The movers are places where the two slots are far apart (mean gap 16.5, 95th percentile 45.7, max 88.9): high-property, low-violence places or the reverse. Biggest drops at 0.098 are low-violence-score, high-property-score places such as Von Ormy TX (stored 30.4, 14.9 at 0.098), Kirby TX (24.2, 12.5), Coney Island NY (23.1, 12.5), Chelsea MA (24.4, 14.0), Franklinton NC (10.9, 0.7). Biggest rises are very safe, high-property places such as Southside Place TX and West University Place TX (89.7, 100 at 0.098). The 517 retail-hub places barely move (mean +1.4, max 4.7) because 0.15 was already close to 0.098. Rank order is stable (Spearman 0.995), 128 of the 142 bottom-decile places and 130 of the top-decile places stay in their decile. This matches the 1b6df81 message (mean 2.2, about 10 places over 10); my count is 9 over 10 strictly.

## Per design principle (this weight only)

| Principle | Status | Evidence |
|---|---|---|
| P1 reference frame | Meets (provisional) | National percentile; v2 doc marks fixed standard as tier 2, norm-based proxy noted. Not specific to the weight. |
| P2 construct | Does not meet in the weight's wording | Docs say the score measures how safe a place is compared with the nation; the weight derivation measures cost to society, which is a different quantity from residents' perceived or priced safety. |
| P3 measurement area | Not assessed here | Out of scope for the weight. |
| P4 source and recorded range | 0.35 does not meet. 0.098 on origin/main meets the source half; the range exists only as sensitivity, not as a recorded plausible range in the spec. | No source for 0.35 in git history; harm weights file records four sensitivity cases. |
| P5 double counting | Not assessed | Property theft share also enters no other pillar as far as this audit read. |
| P6 sensitivity | Meets now for this weight | Table above. Not tested here: pin shift or radius. |
| P7 independent validation | Does not meet for the weight | Validation covers the circle, not the weight. The 1b6df81 note says radius floors did not agree better with third-party ratings; nothing validates the violent/property blend against residents' choices or ratings. |
| P8 test across all places | Meets for this analysis | 1,420 of 1,476, 56 have no score. |
| P9 fail loud | Not affected | Pillar already returns None with no data. |
| P10 launch check | Not assessed | |
| P11 disclose limits | Partial | Costs are 2008 dollars from one study, rates one year (the doc says so). |
| P12 re-validate | Does not meet | Rebuild command exists but no schedule. |

## Defect list

1. D-A: 0.35 and 0.15 undocumented. Evidence: first commit, no source anywhere in repo. Stored data: 903 places scored at 0.35 and 517 at 0.15 in this checkout, all reproduce exactly from stored slots.
2. D-B: Local main lacks 1b6df81 and later composite refreshes (36a7cac, 541f491), so local catalog files in this checkout still hold 0.35/0.15 scores (and have uncommitted edits on top). Tracker D9 is stale as a result.
3. D-C: Harm share is computed on rates but applied to percentile slots, and murder is a tiny share of violent counts yet most of violent harm. The 0.098 is defensible as an anchor, not as an exact value.
4. D-D: The 0.098 formula uses 2008-dollar cost from one study and one year of rates, with no recorded plausible range in the spec sheet.

## Proposed fix and expected impact

1. Sync this checkout with origin/main before any further safety work (needs your go-ahead; I did not do it).
2. Record the weight in the pillar's spec sheet as a judgment with a range: central 0.098 (total social cost, McCollister et al. 2010 with BJS 2023 rates), plausible range 0.10 to 0.30, outer bound 0.52, with the reason for choosing total cost over victim cost.
3. Keep 0.098 as the live value. Expected impact versus the old stored scores: mean absolute 2.2 points, 129 places move over 5, 9 over 10, rank order essentially unchanged; total score moves at most about 1.2 points.
4. TODOs to close the evidence gap, none invented here: get the Cambridge Crime Harm Index and Crime Severity Index weights (tier 1), and a hedonic estimate for property versus violent crime (tier 2) to check 0.098 to 0.30 against what residents pay.
5. If the percentile-slot mismatch matters, test a rate-based blend before adopting anything; not computed here.

## Decision for you

Do you want the weight recorded as 0.098 with a plausible range of 0.10 to 0.30 (my recommendation), and this checkout synced to origin/main so the derivation and recomputed catalogs are the ones in front of us?

## Update 2026-10-26: re-run in a worktree cut from origin/main (087fc26)

The tables above used the shared checkout's old catalogs (stored at 0.35 and 0.15). The catalogs on origin/main already store the 0.098 weight, so this section re-runs the sensitivity with 0.098 as the stored baseline. All 1,420 scored places reproduce exactly from stored slots at 0.098 (231 reproduce at 0.15 and 57 at 0.35, so the old rule is fully gone). 56 places have no score, as before. Slot, source, trend, precision and clumping figures in the v2 audit are unchanged (same 369 / 893 / 158 split, 114 at 95 or higher, 24 at 100, 4 at 0, 37 violent slots at 100).

Change in score versus the stored 0.098 score:

| Weight tested | Mean change | Mean absolute | 95th percentile | Max | Over 5 pts | Over 10 pts | Spearman | Max change in total |
|---|---|---|---|---|---|---|---|---|
| 0.0 (violent only) | +0.74 | 1.62 | 4.5 | 8.7 | 47 | 0 | 0.997 | 0.67 |
| 0.197 | -0.76 | 1.66 | 4.6 | 8.8 | 51 | 0 | 0.997 | 0.68 |
| 0.299 | -1.55 | 3.37 | 9.4 | 17.9 | 330 | 60 | 0.989 | 1.38 |
| 0.35 (old, no hub rule) | -1.95 | 4.23 | 11.8 | 22.4 | 485 | 119 | 0.983 | 1.72 |
| 0.519 | -3.26 | 7.07 | 19.7 | 37.4 | 762 | 352 | 0.952 | 2.88 |

Reading it: across 0.098 to 0.197 the average place moves 1.7 points and none move over 10. Across the proposed range of 0.098 to 0.299, the average place moves 3.4 points, 325 move over 5 and 59 over 10, and no place's total score moves more than about 1.4 points. The stored score is inside the proposed range, so the earlier recommendation (record 0.098, range 0.10 to 0.30) stands. Note the code and crime-data files on origin/main also changed since the first audit (Denver, Charlotte and Las Vegas incident feeds; commuter-grid flag), which does not affect these slot-based numbers.
