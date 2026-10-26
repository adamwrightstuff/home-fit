# v2 audit: neighborhood amenities (2026-10-25)

Read-only and offline. No code, tests or catalog files were changed, nothing was rescored, nothing was committed. Statistics come from the 21 `*_merged.composites_recomputed.jsonl` files (1,476 places), recomputed from each place's stored `business_list`. Helper scripts are in the session scratchpad, not in the repo.

## Headline

The pillar does not fail loudly. 49 places have no amenities score and no reason recorded, and a failed or empty Overpass read can still produce a believable low score. Separately, the one tuning comment you flagged (D10) sits on thresholds that change no score by more than 3.6 points, so they can be deleted rather than sourced. The 60/40 split and the 800 m window are unsourced and do move scores.

## Sourced versus judgment

| Item | Value | Status |
|---|---|---|
| Walk window | 800 m (`min(walkable, 800)`) | Judgment. The repo cites no study. v2 Part 4 only says 800 m is a common benchmark and "not a validated cutoff" |
| Query radius | 1,200 m (neighborhood scope) or 1,500 m, 3,000 m in vacation mode | Judgment. Only feeds location quality and data-quality counts |
| Density curve | log(1+n)/log(401), 50 points | Judgment. The 400 anchor has no source. Moving it 200 to 800 changes scores by 3.5 points at most (see Sensitivity) |
| Home split | 50 density / 25 variety / 25 proximity | Judgment, but low leverage (see Sensitivity) |
| Variety tier points | 10 / 7 / 5 / 3 | Judgment |
| Proximity weights | grocery 0.45, cafe or bakery 0.30, restaurant or bar 0.25 | Judgment |
| Proximity steps | 150 / 300 / 500 / 800 m give 1.0 / 0.85 / 0.60 / 0.35 | Judgment. Part 4 says a decay curve beats a cutoff and cites observed 85th percentile walks of about 524 m for bus, but that is a transit finding and I did not see it applied to shops |
| Home 0.6 plus location 0-40 | `min(100, 0.6 * home + location)` | Judgment, added 2026-09-06 (0e2096e) because the earlier formula "zeroed car-dependent places" |
| Location steps | 400 / 800 / 1,200 / 1,600 m, variety points, density divisors 12.5 / 10 / 7.5 / 3.75 | Judgment. Commit 24490af says "Based on Perplexity research recommendations"; no citation is on file |
| Area-type "expectations" | thresholds 100 / 80 / 60 / 30 | Judgment, and inert (see D3) |
| Places fallback trigger | completeness below 0.6, or fewer than max(12, 45% of the area-type business floor) | Judgment. The floors (50 / 25 / 15 / 5) come from `get_expected_minimums` and are also unsourced |
| Evidence that supports the construct | Couture and Handbury: walking-time restaurant and nightlife density explains young college graduates' location choices (tier 1, from v2 Part 4b, summaries only) | Supports "walk-time access, valuing variety". It says nothing about any number above |
| Validation against Walk Score | "Pearson 0.90 vs old 0.80" in commit e701eb5 | Not reproducible here: no file in the repo holds the Walk Score values. It describes the v3 formula without location quality, so it no longer describes today's formula. Walk Score is also built from the same kind of amenity counts, so it is not independent |

## Findings per principle

**P1 reference frame.** Mostly meets. The home part is an absolute count with no area-type input, which matches the v2 provisional frame (fixed walk-time access). The location part still uses area-type thresholds. The pillar doc never states the frame. Evidence tier for the frame: 1 (Couture and Handbury), but for young graduates only.

**P2 construct.** Does not meet. Module docstring says "walkability and variety", the doc says "walkable local life", and the code adds a "town center" term that is really the distance from the pin to the median coordinate of all businesses within 1,200 to 1,500 m. That measures how centered the pin is in the sample, not whether a town center exists. The v3 commit message and the in-code comment both say the town-center signal "NO LONGER inflates the score"; since 0e2096e it adds up to 40 points.

**P3 measurement area.** Partly meets. A pin plus an 800 m circle is a walk-time standard, which is the right kind. The reason for 800 m is not stated and no pin QA exists beyond case fixes (Cold Spring Harbor was 2 km off).

**P4 sourced weights with ranges.** Does not meet. Every number in the table above except the construct is a judgment with no recorded range. Sensitivity below gives the observed ranges.

**P5 no double counting.** Does not meet within the pillar. Home and location are both computed from the same business list. Correlation between 0.6 x home and location across 1,427 scored places is 0.86. The `business_list` is also a shared input to Status Signal (luxury presence) and happiness; not tested here.

**P6 sensitivity.** Run offline, see below. The pillar is pin-sensitive.

**P7 independent validation.** Does not meet. No independent source on file (see Walk Score row).

**P8 all-places check.** Meets for the 2026-06 v3 rewrite (recomputed on the catalog) but not for 0e2096e: the commit says "All 180 other NYC NA scores updated"; the other metros were reproduced from the same formula, as this audit confirms (0 of 1,427 totals fail to reproduce from stored home and location parts).

**P9 fail loudly.** Does not meet. See defects D1, D2, D6.

**P10 launch check.** Partly meets. Dense places separate well from low-density ones. Floor and ceiling clumping exists (D7). Several known car-dependent towns are scored well above where the v3 commit said they should sit (D5).

**P11 disclose limits.** Does not meet. The OSM and Places mix, chain inclusion (the doc says "mostly independent" but chains are included by default, e.g. Starbucks and Walmart in the stored lists), and OSM sparsity in non-urban areas are not surfaced. 83 places use Google Places records (3,863 records); the stored pillar does not keep the fallback metadata.

**P12 re-validate.** Does not meet. Live code and catalog differ: the catalog stores `businesses_within_walk` (written by `scripts/apply_amenities_rescore.py`), the live pillar writes `businesses_within_1km`, and the live breakdown version string is `neighborhood_amenities_v2_places_fallback` while the doc says `amenities_v3_walkable_density`. 85 of 1,426 stored location values do not reproduce from the stored list and stored area type (cause not established; reclassification after scoring is a guess).

## Defect list

**D1. 49 places have a null score with no reason (P9).** All 49 have `score: null`, `status: success`, `failure_reason: null`, no data warnings, not degraded, and `contribution: 0.0` (weights are redistributed, so totals are right). The stored shape cannot tell a failed read from a real empty area. Evidence that most are failed reads: density of the 49 ranges 1 to 9,022 per sq mi with 10 above 2,500, while among 354 scored places in the 2,500 to 5,000 band the 5th percentile business count is 3 and the median 29. Coconut Grove, Pinecrest, Weston, Preston Hollow, Tampa Palms, Ahwatukee, Granite Bay and Green Valley cannot plausibly have zero cafes, restaurants and shops within 1.5 km. These are the old "empty means None" behavior from before 27e656f. Spread: 22 exurban, 17 rural, 9 suburban, 1 unknown; Miami, Orlando, Sacramento 5 each.

**Correction (2026-10-26): most of the 49 are real empties, not failed reads.** The private Overpass server (OSM base 2026-10-17) was queried for the 18 of the 50 places in its 11 covered states. 16 of the 18 have zero tracked businesses within 1,500 m of the pin, and for all 16 the nearest cafe, restaurant or grocery is 1.5 to 4.3 km away (Preston Hollow 1,520 m, Granite Bay 1,749 m, Cameron Park 2,048 m, Sienna 4,301 m; Clarksburg and Rancho Murieta have none within 5 km). Only La Crescenta (31 businesses, score 30.3) and Parkway (11 businesses, 15.8) had real data the first time was missed. The inference above from density bands (Coconut Grove, Pinecrest and others) was a guess and is unverified; those places are in states the server does not cover. The two-endpoint confirmation I first built also failed true empties whenever the second endpoint was the blocked public one, so it was replaced by a control query on the same endpoint (does the server show any map data in the circle?).

**D2. Today's live code would score a silent empty read as a low number (P9).** Commit 27e656f made "Overpass answered with zero businesses" a scored result (about 0 to 5, confidence capped at 40, a text warning, `degraded` false). A 200 response with zero elements is exactly what an overloaded public Overpass can return, and the code itself treats it as suspect (it sets `_cache_skip` and the warning `empty_businesses_result_not_cached`) but the pillar still scores it. The remark-error check in `_retry_overpass` catches server-side runtime errors, not empty bodies. The test `test_empty_walkable_area_gets_a_low_score_not_none` locks this in. D1 shows how often it matters: a plausible-looking 0 to 5 for a place that has a coffee shop.

**D3. The D10 area-type thresholds are inert (tracker D10).** The comment "make it harder to max out location_quality" (line 553) belongs to `_score_location_quality`. Within it, `vibrant_threshold` (100 / 80 / 60 / 30) is assigned and never used. Only `density_divisor` is used, and it feeds a term capped at 8 points. Replacing all four area-type variants with the suburban one changes the stored scores of the 1,426 reproducible places by a mean of -0.28, median 0.0, p95 1.9, maximum 3.6, and no place by more than 5. By area type the mean shift is exurban -0.89, rural -0.79, urban residential +0.12, suburban 0. So the unsourced "expectation by area type" is a tuning artifact that does almost nothing. The dead functions `_score_density`, `_score_variety`, `_score_proximity`, `_empty_breakdown` and `_empty_breakdown_with_fallback` (about 270 lines, no callers outside the file) carry more of the same unsourced "Research: 50+ excellent" text and the old imputed-fallback path.

**D4. Location quality is unsourced, double counts, and contradicts the construct (P2, P4, P5).** Weight 40 of 100, measured against the median of businesses. 325 of 1,427 scored places (23%) sit at the 40-point cap. 70 places with home walkability of 30 or less still get 25 or more location points (mean 27.7). Example: Plano has 0 businesses inside 800 m, home score 0.0, and scores 30.0 purely from location. Share of score variance: home part 47%, location 12%.

**D5. Location quality re-inflates car-dependent towns the v3 rewrite was meant to fix (P10).** Stored scores: Scarsdale 65.6 (home 51.0, location 35.0), Darien 75.9 (home 68.1, location 35.0), Cold Spring Harbor 58.0, Bronxville 88.9. The v3 commit named Scarsdale and Darien as car-dependent (Walk Score 28 to 40, from the commit text; I could not check). Darien at 75.9 now outscores Brookline at 72.5.

**D6. A fallback value is still stored for one place, La Crescenta (P9).** Status `fallback`, score 15.0 from `fallback_used: true`, zero businesses. This is the "imputed score" path that 27e656f removed from live code. Rancho Palos Verdes is not a failure (13 businesses, score 17.2, confidence 76). Southport (NYC) is null with density 0 and area type unknown.

**D7. Floor and ceiling clumping (P10).** 13 places score 100 (12 of 197 urban residential, 1 of 2 urban core) and 44 score 95 or higher. Four places score exactly 0.0 (Union City GA, Dickinson TX, Seven Hills NV, Timberwood Park TX), each with a single business about 1.5 km away. Whether OSM is that sparse or the read was partial cannot be told from the stored data. 248 scored places have confidence under 50 and 62 have 20 or less, yet `degraded` is false for all 1,476.

**D8. Convenience stores count as groceries for the milk-run (P2).** Gas-station and convenience records map to type `grocery` (Speedway, "Canyon Golf Market (Valero)"). Of 1,071 scored places with a walkable grocery-type record, 330 (31%) have no supermarket among them. Grocery carries 45% of the 25 proximity points. Stored `shop` tags in grocery records: convenience 8,282, supermarket 4,029, greengrocer 483, untagged 472.

**D9. Dead guard in location quality.** `avg_cluster_distance > 1500` returns 0, but it averages the first 10 list entries (list order, not nearest) and the query radius is at most 1,500 m outside vacation mode, so it almost never fires. Minor.

**D10. Places fallback failure is not surfaced (P9, P11).** If the Places request fails, the metadata records `error: places_request_failed` and scoring proceeds on thin OSM data with no degraded flag. The fallback metadata is not stored in the catalog, so the rate of this cannot be measured offline. The trigger thresholds are unsourced (see table).

## The 3 LA places with amenities of 0 (memory note)

The note is stale. Its three places were Southport CT, La Crescenta CA and Rancho Palos Verdes CA, and only La Crescenta and Rancho Palos Verdes are in the LA file. Today: La Crescenta 15.0 with the old imputed fallback (D6), Rancho Palos Verdes 17.2 from 13 real businesses, Southport is in the NYC file with a null score (D1). No LA place has an amenities score of 0 now. The four exact zeros are in Atlanta, Houston, Las Vegas and San Antonio (D7). I recommend updating the memory note; I did not edit it.

## Sensitivity (stored values recomputed offline, change in final score)

Base case reproduces the stored home score for all 1,426 places. n = 1,426. Spearman is rank agreement with the base.

| Perturbation | Mean | Median abs | p95 abs | Max abs | Places over 5 | Spearman |
|---|---|---|---|---|---|---|
| Walk window 400 m | -9.0 | 6.9 | 28.1 | 42.1 | 862 | 0.953 |
| Walk window 600 m | -3.9 | 2.0 | 14.9 | 33.3 | 407 | 0.983 |
| Walk window 1,000 m | +2.5 | 1.4 | 9.1 | 25.0 | 226 | 0.993 |
| Walk window 1,200 m | +4.3 | 2.8 | 14.1 | 28.8 | 450 | 0.985 |
| Density anchor 200 to 800 | +1.7 to -1.4 | 0.7 to 1.9 | at most 3.1 | at most 3.5 | 0 | 1.000 |
| Home split 40/30/30, 60/20/20, 34/33/33 | +0.5 / -0.8 / +0.8 | 0.6 to 0.9 | at most 2.9 | at most 4.6 | 0 | at least 0.999 |
| Variety points 7/7/7/4 or 12/6/4/3 | -0.4 / +0.2 | at most 0.4 | at most 1.2 | at most 1.8 | 0 | 1.000 |
| Proximity weights .34/.33/.33 or .6/.2/.2 | +0.2 / -0.2 | at most 0.3 | at most 1.6 | at most 2.2 | 0 | at least 0.999 |
| Home multiplier 0.5 / 0.7 / 1.0 (location unchanged) | -5.1 / +4.8 / +14.3 | 5.3 to 15.6 | up to 24.9 | up to 30.7 | 802 / 758 / 1,203 | 1.000 / 1.000 / 0.971 |
| Location removed (home only, 0 to 100) | -10.0 | 10.5 | 19.8 | 40.0 | 1,186 | 0.980 |
| Area-type thresholds made uniform (D3) | -0.3 | 0.0 | 1.9 | 3.6 | 0 | not computed |
| Convenience stores not counted as grocery (D8) | -1.3 | 0.0 | 5.7 | 6.8 | 125 | not computed |
| Pin shifted 200 m (four directions) | -0.8 to -1.2 | 2.1 to 2.3 | 12.0 to 13.5 | 46 to 69 | 379 to 416 | 0.970 to 0.973 |

Reading it: the window radius, the 60/40 split and the pin position move scores; the within-home weights and the density anchor barely matter. Pin shift caveat: the stored list stops at the original query radius, so a 200 m shift loses some edge businesses; this affects the location part (median 0.0, p95 5.0) far less than the home part (median 1.5, p95 8.7). Where the pin sits relative to the commercial strip decides most of the movement.

## Proposed fixes and expected impact

None applied. Each is computed from stored values unless noted.

**F1 (D1, D2, D6, D10): fail loudly.** (a) Store the 49 null places with `status: no_data`, a failure reason and `degraded: true`. No score or total changes (all already have contribution 0.0). (b) Remove La Crescenta's imputed 15.0 and treat it as no data: its total moves from 69.05 to 73.55 (+4.5); nothing else changes. (c) In the live path, require a second endpoint to confirm an empty read before scoring it as an empty area; otherwise return no data with a reason. Retry the 49 and La Crescenta from a private Overpass server when it is up. Their new scores cannot be estimated offline, and I will not guess them. (d) Mark `degraded` when the Places fallback was needed and failed. Expected score impact on the 1,476: 0 changes now; up to 50 places gain a real score after retry.

**F2 (D3, D9): delete the inert area-type thresholds and the dead functions.** Expected impact if you instead keep location quality and just make the divisor uniform: mean -0.3, max 3.6, no place over 5. Deleting dead code changes no score.

**F3 (D8): count only supermarkets and large groceries for the milk-run, or make convenience a lesser category.** The 0.45 grocery weight and any lesser credit would be new unsourced numbers, so the clean version is supermarket only: mean -1.3, 125 places lose more than 5 points. I did not retrieve a source for the category definition (USDA food-access work uses supermarket-type stores, from memory, unverified). Flag as judgment.

**F4 (D4, D5, P2, P5): decide what location quality is.** Options with stored-data impact: (i) keep as is and document honestly as a judgment (no change; the construct statement must say it rewards a centered pin); (ii) remove it so the pillar is the home score (0 to 100): mean -10.0, 768 places move more than 10, rank order nearly unchanged (Spearman 0.98); car-dependent towns with no walkable business go to 0, which is what v2 P2 "access" implies and what the 2026-09-06 change reversed; (iii) change the 0.6 multiplier: every 0.1 of multiplier moves the mean about 5 points. Nothing in the evidence on file selects among these.

**F5 (P3, P6): record the 800 m window and pin tolerance as a documented limit** and add pin QA for the 405 or so places whose score moves more than 5 points under a 200 m shift. No new numbers needed for the QA list.

**F6 (docs):** rewrite `docs/PILLAR_NEIGHBORHOOD_AMENITIES.md` with the v2 spec sheet, correct the version string, correct the "no longer inflates" comments, and update the pillar-coverage-gaps memory note.

## Decision for you

Should location quality (0 to 40, unsourced, 0.86 correlated with the home score) stay in the amenities score, or come out so the pillar is pure walk-time access? Everything else above (F1 to F3, F5, F6) I would do as written, but F4 changes the level of 1,186 places and needs your call.
