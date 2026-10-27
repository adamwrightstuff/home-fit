# Natural beauty: v2 design principles audit (2026-10-25)

Read-only and offline. No code, tests, tracker or catalog files changed. Nothing committed or pushed. Scratch scripts are in the session scratchpad, not the repo. One side effect to know about: importing the pillar module initialises the Google Earth Engine client (authentication only, no data requests).

## Bottom line

The two-part construct is the best-evidenced version of this pillar so far, and the stored scores reproduce exactly from stored components (0 mismatches in 1,476). But it fails the v2 fail-loud rule in a way that moves real scores: 192 places (13%) carry a made-up water score of 5.0 because water data is missing, and the stored Active Outdoors data shows water within 3 km for 135 of them. Regional normalization still has no source and moves Phoenix about 20 points. Neither the live scorer nor the catalog tells you when GEE or Overpass failed.

## Git state (checked first)

- The two-part work is committed locally as 429486e (2026-10-24, "Natural beauty: two-part score ..."). It is NOT pushed: `origin/main` does not contain it, and main is 17 commits ahead of origin.
- The memory note `project_natural_beauty_two_part` says "uncommitted". That is stale. It should say committed, unpushed.
- `pillars/natural_beauty.py` and `data/natural_beauty_two_part_scale.json` have no uncommitted changes against HEAD.
- Still untracked: `analysis/natural_beauty_two_part_proposal_2026-10-24.md` and `data/neighborhood_beauty_wip/`. The 21 metro `*.composites_recomputed.jsonl` files are modified in the working tree for other reasons (the tree was already dirty at session start), so I cannot say from status alone that the committed rewrite is what is on disk. I did verify the on-disk scores reproduce from the on-disk components.

## P1 to P12

| # | Principle | Verdict | Evidence |
|---|---|---|---|
| P1 | Reference frame | Partial | Part 4 of the draft says beauty uses a shared absolute scale validated by human ratings. The code does the opposite for streets: green view and canopy are divided by a regional median (peer norm). Terrain and water are absolute. Mixed frame, undeclared. The Place Pulse test in the proposal found regional normalization neither helps nor hurts (+0.005), so there is no tier 1 to 3 evidence for the peer norm. |
| P2 | Construct in one sentence | Meets, not written down | Implied: "how beautiful the surroundings look, from street greenery and from landscape setting". Not stated in code or docs in one sentence. Landcover and biodiversity are computed and stored but no longer scored (fine, documented). |
| P3 | Measurement area | Partial | Pin plus radius: canopy 400/1000/2000 m weighted 0.5/0.35/0.15, green view up to 1200 m, terrain and water have their own radii. Beauty is perceptual, so a viewing radius is defensible, but no reason is recorded for these radii. |
| P4 | Every weight/threshold/curve sourced with a range | Does not meet | See the parameter table below. Almost everything is judgment. |
| P5 | No double counting | Partial | Green view and canopy are both built from satellite canopy/NDVI and share inputs (the green view fallback is literally built from canopy). Within the streets part this is handled by the 0.7/0.3 pairing, not tested. Overlap with Active Outdoors: both read water and parks (the proposal argues they measure different things; no test). Overlap with Climate Risk: none found. |
| P6 | Sensitivity | Partial | Done below offline. Weights and regional normalization move scores a lot. True pin shifts could not be run offline. |
| P7 | Independent validation, Spearman 0.7+ on 15+ places | Not met | The proposal reports Pearson r of 0.37 (streets vs Place Pulse), 0.41 (terrain vs ScenicOrNot Britain), 0.66 and 0.30 (USDA Natural Amenities Scale, terrain and water). None reaches 0.7, none validates the final blended score, none covers deserts. The final 50/50 blend has no validation at all. The tracker's own row lists validation as a gap. |
| P8 | Test across all places | Meets for the construct change | The proposal and the offline recompute ran on all 1,476 places with per-metro deltas reported. Regional baselines and the water default were never tested this way. |
| P9 | Fail loudly | Does not meet | See defects D1 to D4. |
| P10 | Launch check | Partial | Spread is fine after the rescale (mean 64.6, SD 18.9, 17 places at 95 or above, 1 at 99+, 4 at or below 10; no floor/ceiling clump). But that spread is forced by construction (see D6). I did not see a pre-registered pairs check for beauty in the QA files. |
| P11 | Disclose data limits | Partial | Proposal lists instrument mismatch, 2007 to 2012 photos, Britain-only ScenicOrNot, deprecated GEE canopy sources. None of it reaches the API response as confidence. 239 places (la 89, nyc 150) store `confidence: None` and 2 nyc places store 0 in the pillar. |
| P12 | Re-validate on a schedule | Not met | No schedule. The live scorer and catalog diverge by design (see docs/LIVE_SCORER_VS_EXPLORER.md); the TS mirror exists but I did not diff it. |

## Parameter source table (P4)

| Parameter | Value | Source on file | Status |
|---|---|---|---|
| Within-part weights | 0.7 stronger, 0.3 weaker | None (carried over from the old OWA idea) | Judgment. Moving to 0.6 or 0.8 changes scores by 4 points on average (p95 7 to 8, max 10); 0.5 or 1.0 by 8.5 to 10.4 (max 20 to 21) |
| Streets vs scenery blend | 0.5 / 0.5 | None. Proposal says so | Judgment. 0.4 or 0.6 moves 5 points on average (p95 9 to 10, max 13); 0.3 or 0.7 moves 9 to 10 (p95 16 to 20, max 22 to 25). Rank correlation 0.89 to 0.98 |
| Preference tilt | 0.75 streets for canopy, 0.25 for scenery picks | None | Judgment |
| Water mismatch penalty | water x 0.25 | None | Judgment |
| Green view curve | breakpoints 5/15/25/40/50%, plateau at 50 | None cited | TODO. 34% of places (505) score 95 or above on green view, so the curve plateaus for a third of the catalog |
| Canopy curve | breakpoints 5/15/25/40/60% | None cited | TODO |
| Terrain curve | breakpoints 2/5/10 on a raw relief score | None cited; terrain does test against USDA (0.66) and ScenicOrNot (0.41) | Curve shape is TODO; the input choice has evidence |
| Water curve | ocean max 100 decay 0.20/km; lake 70 / 0.30; river 40 / 0.35 | Comment cites "blue-space wellbeing literature", no citation | TODO. Also the proposal found water is the weakest measure (USDA 0.30) |
| Water missing | 5.0 | None | Invented value, see D1 |
| Regional baselines | 12 regional gvi/canopy medians | Comment says "Treepedia, NLCD, urban greenery literature"; commit 776e778 cites none | TODO (tracker D12). No per-number source |
| Global reference | gvi 20%, canopy 24% | "national urban median", no citation | TODO |
| Street-tree boost | log1p(count/500) x 8, cap 20 pct points | None | Judgment, adds up to 20 points of green view in 94 places |
| Visible-green-fraction floor | 0.85 x vgf when more than 2x gvi | None | Judgment; fires in 379 places (26%) |
| Canopy proxy | gvi = 0.7 x canopy when gvi under 2% | None | Judgment; 60 places |
| Percentile scale | 101-point quantile table, maps blend to old V9 distribution | Calibration, not evidence (stated in the table's own note) | Self-referential, see D6 |

## Defect list with stored-data evidence

**D1. Missing water is scored as 5.0, a made-up value (P9, high).** `_v9_score_water` returns 5.0 when distance or type is None. 192 places store `water_type: null` and `water_score: 5.0` (Philadelphia 74, SF 50, NYC 37, LA 30, Seattle 1). The same places' Active Outdoors summary reports water features for all 192 and a nearest water within 3 km for 135 (within 1 km for 34). Examples: Astoria (nearest 0.5 km), Greenpoint (0.5 km), Canarsie (1.4), Flushing (1.7), Emeryville (1.3), Daly City (2.4). So this is mostly a missing read, not an absence of water. Nothing flags it: no degraded reason, no data warning. Score impact if the real water were used instead of 5.0 (using Active Outdoors' stored distance, water type unknown, so shown as bounds): river type mean +3.1 (max +11.5, 44 places move more than 5), lake mean +7.8 (max +25.7, 103 places), ocean mean +15.3 (max +39.0, 163 places). Dropping the water term instead of defaulting it gives mean +5.2, max +15.4.

**D2. A GEE or Overpass failure cannot reach the score as "no data" (P9, high).** In `get_natural_beauty_score` a total failure of all sub-fetches only logs a warning and continues. In `_apply_v9_formula`, missing green view and canopy become 0.0 through `or 0.0`, and the "streets missing" check tests `green_view_index is not None`. Because the green view code always writes a number (including a composite fallback built from canopy, street trees and parks), the check can never trigger live. The only fail-loud path that exists is the stored-data version (both exact zeros), and it fired for 1 place (San Fernando). A live GEE outage therefore produces a streets score from zeros, not a degraded flag. I read the code path but did not execute a failure, because the task is offline.

**D3. Fallback green view is labeled "measured" (P9/P11, medium).** `gvi_source` is "measured" whenever green view is at least 2%, including when the composite fallback produced it. The stored catalog is clean on this point (1,236 semantic, 1 enhanced NDVI, 0 composite), so no stored score is affected today, but the label cannot be trusted going forward. Separately, the stored `gvi_source` field reads "unknown" for 1,237 places and `gvi_available` is False for the same 1,237 while the data clearly exists. Those two metadata fields are broken, which also makes any audit of GEE failures from stored data impossible.

**D4. San Fernando and the scenery-only rule (P9, medium).** San Fernando (LA) scores 3.1: no greenery measurement, terrain 0, water default 5.0. The streets part is dropped and `low_confidence` is set, which matches the policy for a missing optional piece. But the score is still weighted at full pillar weight in the composite. Under P9, missing required data should show no data and drop out of the headline. The score is also itself built on the D1 default (water 5.0) and a terrain of exactly 0.

**D5. Stale breakdowns on 121 places (provenance, medium).** Arcadia, Belmont Shore, Burbank and 118 others (la 10, nyc 40, sf 71) carry the new two-part score but a `v9_breakdown` from the old six-component OWA (keys `owa_components`, `owa_score`, `weights`; no `method`, no `streets_score`). `score_before_two_part` is stored, so the change is traceable, but anyone reading the breakdown sees the old method. Scores themselves reproduce from the components, so this is a labeling defect, not a number defect.

**D6. The percentile scale fixes mean and SD by construction (P1/P7/P10, medium).** The quantile table is built from these 1,476 places and maps the new blend onto the old score distribution. The catalog mean (64.6) and SD (18.9) are therefore identical to the old score by design, and "launch check spread looks fine" is guaranteed rather than tested. A new place is scored against this catalog's distribution, which is dominated by 21 metros. Calibration to the old score is also the same anchoring complaint as D12, one layer up. The table note itself says "Calibration, not evidence".

**D7. Regional normalization (tracker D12, high).**
- No source for any of the 12 baselines or the two global references.
- The baselines do not match what this pipeline measures. Catalog medians of the pipeline's own canopy are 2 to 3 times lower than the baselines in most regions: California 6.3 vs baseline 19, Mid-Atlantic 13.1 vs 29, Midwest 9.9 vs 27, Texas 10.0 vs 22, Southeast 18.8 vs 33. Northeast and Southwest are the near matches (34.2 vs 32; 1.0 vs 9 canopy, 10.6 vs 8 green view). The proposal notes stored green view runs 2 to 3 times above street-view literature, so the instrument is different from the one the baselines came from. "Average for the region" is therefore not average in this data.
- Effect if dropped (rescored through the same scale table): mean absolute change 5.9 points, p95 17, max 34.7; Spearman with the current score 0.906. Mean change by region: southwest_arid -17.3, mountain_west -10.0, california -8.3, texas -3.5, midwest -0.3, mid_atlantic +2.4, northeast +5.5, southeast +6.2, pacific_northwest +14.0 (5 places). By metro: Phoenix -19.9 (51.2 to 31.3), Denver -10.0, Las Vegas -11.7 (44.0 to 32.3), LA -9.8, Seattle +14.0, Orlando +7.5.
- Without normalization the two desert metros fall to about 31 to 32. With it they sit at 44 to 51. That 12 to 20 point swing rests entirely on an unsourced constant and on the absence of any human rating of desert places.

**D8. Water leads scenery in 769 of 1,476 places (P4, medium).** Because the lead rule is "stronger component counts 0.7", and the water curve is the weakest-evidenced part (USDA r 0.30), it decides the scenic part for half the catalog. The curve maxima (100/70/40 by water type) are unsourced.

**D9. Confidence metadata (P11, low).** Pillar `confidence` is None for 239 places and 0 for 2 NYC places, `degraded` is False for all 1,476, and `per_pillar_degraded` is empty. The fail-loud flags never show up in stored data.

## Desert gap (from the memory note, now quantified)

- 94 places are in the southwest_arid region (Phoenix 64, Las Vegas 30). Their mean streets part is 39.6, scenery 30.8, final score 48.9, against a catalog mean of 64.6.
- Their stored canopy averages 1.6% and green view 11.7%. Normalization lifts these (gvi 11.7 to 29.0 on the scoring scale) so the score is not at the floor.
- No human beauty rating covers this terrain: Place Pulse and ScenicOrNot do not include deserts and the USDA test had 3 desert counties. So nobody can say whether 49 is right, 31 is right, or either. The decision that matters (keep normalization, drop it, or hold) has no data under it. The memory note's plan (in-product photo rating) is the only route to evidence; the owner said no paid rating panels.
- Also unvalidated: arid places with water (Lake Mead area, Phoenix canals) and mountains at desert edges are handled by the absolute terrain/water terms, which is the correct direction, but untested.

## Sensitivity summary (P6)

- Pin shift: could not be tested offline. Two proxies instead.
  - Canopy radius swap (use only the 400, 1,000 or 2,000 m canopy in place of the weighted blend, 1,237 places with stored multi-radius values): mean change 1.0 / 0.8 / 1.6 points, p95 3.3 / 2.5 / 4.9, max 7.3 / 5.3 / 14.2. Canopy radius is a minor driver.
  - Neighbouring catalog places (pairs within the same metro): median score gap 5.4 points within 0.5 mi (n=50), 6.5 within 1 mi (n=331), 8.7 within 1.5 mi (n=795), p95 26 to 39. This is an upper bound on pin sensitivity because real neighbourhood differences are included (largest gaps: Borough Park vs Sunset Park 59, Davis Islands vs Harbour Island 53, Cow Hollow vs Nob Hill 51). It does show that terrain and water, which are step-like in distance, can swing a score by tens of points between nearby pins. A true shift test (same place, pin moved 250 m and 500 m) needs a live run and is not done.
- Weights and normalization: see parameter table and D7. Rank order is fairly stable to the within-part and blend weights (Spearman 0.89 to 0.99) but absolute scores move 4 to 10 points on average.

## Proposed fixes (in priority order) with expected impact

None of these has been made. Per the scoring rule, each needs your approval, and none needs a new API call to start.

1. **Stop scoring missing water as 5.0.** Treat missing water as no data: score scenery from terrain alone, mark the place degraded with reason "water read missing", and queue it for a water re-read. Impact if dropped from the scenery part: 192 places, mean +5.2, max +15.4. If the re-read later returns real water, expected changes are in D1 (river +3, lake +8, ocean +15 on average). A re-read is justified because the missing input is water proximity, which is not stored; Active Outdoors holds a distance but not the type.
2. **Make the live path fail loud.** Replace `or 0.0` and the always-true "measured" test with explicit flags: GEE canopy unavailable, GEE green view unavailable (composite fallback used), Overpass water unavailable. Score from the rest, mark degraded with the reason, and drop the pillar when both streets inputs are missing. Impact on stored scores: San Fernando only (3.1 would become no data); the live path gets protection against future outages.
3. **Fix the stored metadata**: repair `gvi_source` and `gvi_available` (1,237 places say "unknown"/False), set `confidence`, and add the `degraded` flag from item 1. Offline, from stored fields. Also rewrite the 121 stale breakdowns so the method label is correct. No score changes.
4. **Regional normalization: decide, don't tune.** Options are keep (status quo, 94 desert places 12 to 20 points higher), drop (the numbers in D7), or keep but state it as a judgment in the methodology. Dropping has the better evidence profile for P4 (a number with no source is a TODO) but loses on the one thing nothing can check, deserts. I recommend keeping it for now, disclosing it as unsourced, and starting the desert rating collection before changing it.
5. **Source or label the curves.** Green view, canopy, terrain and water curve breakpoints each need a citation or an explicit judgment label with a range. The cheapest next step is a documentation task, not a recompute.
6. **Validation:** the current evidence is Pearson on pieces. Per P7 report Spearman for the blended score on a matched set (Place Pulse photos for streets, ScenicOrNot for scenery) and state plainly that the blend itself and deserts are unvalidated.
7. **Push state:** the two-part commit and 16 other commits are local only. Once D1 is resolved, the resulting score changes should go out in one reviewed push.

## What is sourced and what is judgment

Sourced (tier 1, correlation evidence from the proposal): streets inputs vs Place Pulse (r about 0.37), terrain vs ScenicOrNot (0.41) and USDA (0.66), water vs USDA (0.30, weak), old V9 vs ScenicOrNot (-0.06), CDC PLACES health test null. Judgment, no source: the 50/50 blend, 0.7/0.3 pairing, preference tilt, water mismatch factor, all curve breakpoints, water maxima, regional baselines and global references, street-tree boost, visible-green floor, canopy proxy, the percentile scale, and the water default of 5.0.

## Decision for you

Should missing water (192 places) become "no data, degraded, re-read queued" now, accepting that those places' scores rise by about 5 points on average until the re-read lands?
