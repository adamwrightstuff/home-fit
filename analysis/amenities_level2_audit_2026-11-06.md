# Amenities Level 2 audit (2026-11-06), proposals only

Offline, from the stored composites_recomputed files (1,432 places with a stored business list). No download, no live call, no scoring change, nothing pushed. Scripts: scratchpad `loc_audit.py`, `pin2.py` (not in repo). Worktree branch `amenities-l2-v2` off origin/main b962da48.

## 1. Independent source candidates (ranked, none fetched)

Web facts below come from search summaries only, not from the files. Sizes marked "not found" were not in the results.

| Rank | Source | Measures | Coverage of our places | Size | Licence | Needs |
|---|---|---|---|---|---|---|
| 1 | Census LEHD LODES8 WAC, retail (NAICS 44-45) and food services (72) jobs by census block, years to 2022 | Where jobs in daily-life businesses sit, from state unemployment-insurance records, not OSM | All US blocks, 18 scored states are enough; I did not confirm 2022 is the newest year | not found (one file per state and segment) | Census public data; terms not confirmed in search | Download, free |
| 2 | EPA Smart Location Database 3.0 (block group), employment and household mix (D2A_EPHHM), retail and entertainment jobs fields (third-party listing, 3.0 names unconfirmed) | Land-use mix and jobs by sector per block group, 2018-19 vintage | 220,653 block groups, national | not found | EPA public data | Download, free |
| 3 | Overture Maps Places (Jan 2026 release) | Point businesses from sources other than OSM | Global, 72.4 M records; US count not found | 7.2 GB for the whole world (8 Parquet files) | CDLA Permissive 2.0 and Apache 2.0, no OSM data | Download or bounded cloud read, free |
| 4 | Foursquare OS Places | Point businesses | Global, about 104 M | about 10.6 GB | Apache 2.0, gated on Hugging Face (contact form) | Download, free |
| 5 | Census ZIP Code Business Patterns (via the CBP API) | Establishment counts by NAICS per ZIP | National | small | Census public data | API, free. Too coarse: a ZIP is bigger than an 800 m circle |
| 6 | Google Places | Point businesses | National | per call | Paid terms | Paid call. Already our fallback, so not independent for 83 places |

Recommendation: LODES WAC first. It is the only candidate that is independent of how we built the pillar (administrative records, not a map), it is free, and it can be tallied inside 800 m of each pin from block coordinates. Limits I can already state: it counts jobs, not shops, so a big-box store outweighs a cafe; multi-site firms can be coded to a head office; it cannot see variety. So it validates density and rank order, not the variety or location terms. Overture is the second choice if you want a point-count cross-check (variety too), at the cost of a multi-GB read and its own coverage bias toward chains.

## 2. Location-quality term: stored numbers and the proposal

Stored today (n 1,432): location adds a mean 30.7 of the 100 points (median 33.1, 23% of places at the 40 cap). Every place gets about 30 points from it regardless of home access: 292 places with a home score of 30 or less still get 10 or more location points, 63 get 25 or more. Correlation between 0.6 x home and location is 0.86 (exurban), 0.84 (suburban), 0.65 (urban residential). The stored value reproduces from the stored list, pin and area type for 1,368 of 1,432.

Why it measures the wrong thing: the center is the median latitude and median longitude taken separately, within 400 m of the pin for 634 places.

Proposal (not applied): replace that center with the densest 250 m cluster of businesses in the list, and keep every existing step and point value. The only new number is the 250 m cluster radius (sweep 150 / 250 / 400 gives a mean score change of -1.4 / -1.1 / -0.7; unsourced, record as a TODO). Impact on stored scores at 250 m:

| Measure | Value |
|---|---|
| Mean score change | -1.1 |
| Places moving more than 5 / more than 10 | 189 / 43 |
| Rank correlation with current | 0.984 |
| By area type, mean change | urban residential -2.9, urban core -2.5, suburban -1.2, exurban -0.5, rural 0.0 |
| Biggest losers | Canoga Park 85.4 to 64.6, Crescent Lake FL 71.1 to 53.4, Temescal 89.3 to 74.3, Downtown Dallas 85.4 to 70.4, DUMBO 94.1 to 79.1 |
| Biggest gainers | Lake Zurich IL 49.7 to 73.4, Belmont NC 32.8 to 55.0, Pasadena TX 19.4 to 34.4, Great Kills 67.6 to 80.4 |
| Car-dependent towns | Darien, Scarsdale, Plano, Bronxville unchanged; Brookline 75.1 to 70.1 |

Honest reading: it fixes what the term claims to measure but does not fix the audit's concern. It still lifts places with no home access, it still double counts the same list, and dense neighborhoods lose points because their densest cluster is elsewhere in the 1.2 km list. It is not a clear improvement, so I do not recommend adopting it before the 60/40 decision is revisited. The weight (40) and reach stay unsourced either way.

## 3. Pin-shift gap

Metric note: the recorded "median 2.2, p95 about 12, 405 over 5" is change per single 200 m shift. Recomputed from stored lists with the shipped function: per-shift median 1.5, p95 11.2, about 387 places over 5 per direction, 956 places move more than 5 in at least one of four directions. The stored `pin_sensitivity` range reproduces exactly (100% within 1 point), so this is deterministic geometry on the stored list, not sampling noise.

Finding: it is a scoring-design property, not noise. Evidence from stored data only:
- Places whose densest cluster is within 400 m of the pin: median 4-shift range 3.4, 41% over 5. Cluster more than 400 m away: median 10.3, 91% over 5. Stored geometry explains about half the variance in the range (R2 0.50).
- Base score 10 to 70 moves most (median range about 10); base 90 and up is stable (5.6).
- Home and location parts contribute equally (home range larger in 51% of movers).
- Asymmetry: a shift gains more than 5 for 470 places and loses more than 5 for 662. A shift loses more because the stored list is cut at the query radius, so some of the loss is an artifact.

What can reduce it (computed on stored lists, exploratory, constants are judgment):

| Variant | Per-shift p95 | Places moving more than 5 in any shift | Mean score vs current |
|---|---|---|---|
| Current | 11.2 | 956 | 62.6 |
| A: densest-cluster center | 11.1 | 924 | -1.1 |
| B: A plus continuous ramp for the 5-point location steps | 10.4 | 682 | -0.65 |
| C: B plus soft 500 to 1,100 m home window | 8.2 | 644 | +0.9 (329 places move more than 5) |

Conclusion: smoothing cuts the count by a third but cannot remove it. A 200 m shift is a quarter of an 800 m radius, so any count-in-a-circle score moves when the shop strip sits near the edge. This is a documented limit with a fix that costs new unsourced constants. Not verified: whether real pin errors are 200 m (only 43 of 1,476 pins were found inconsistent, so the shift size is a stress test, not an observed error).

## 4. Launch pairs (proposed from names only, before any score look-up for these)

Caveat: I saw stored scores for Plano, Darien, Scarsdale, Brookline, Bronxville and Highland Village while auditing, so none of those are used. The 2026-10-26 pairs were chosen after looking up scores; these replace them.

Should differ by 20 or more:
1. Cobble Hill NY vs Short Hills NJ
2. Wicker Park IL vs Barrington IL
3. Hoboken NJ vs Fountain Hills AZ

Should be within 10:
4. Wicker Park IL vs Bucktown IL
5. Cobble Hill NY vs Brooklyn Heights NY
6. Capitol Hill CO vs LoDo CO

## 5. Validation brief (pass criteria fixed now, before any result is read)

Source: LODES8 WAC, jobs in NAICS 44-45 plus 72 inside 800 m of each pin (block internal points), latest year. Compare with the stored home score (density, variety, proximity), not the location term, using log of jobs.
- Coverage: at least 95% of 1,476 places have a LODES value.
- Pass: Spearman at least 0.70 across all scored places, and median within-metro Spearman at least 0.60 with no metro below 0.45.
- Written reason a lower result may still be acceptable: LODES counts jobs not shops, so big-box retail inflates car-dependent places; a fail is reported with the 20 largest rank disagreements and does not trigger a formula change.
- A fail means Level 1 stands with the gap recorded.

## 6. Proposed level

Level 1 stands for now. Level 2 needs one decision from you: permission to download LODES WAC (own empty folder, Python -I). Everything else in the Level 2 list is done or documented: pin-shift reported, all-places spread known, pairs proposed, unsourced parameters listed. If validation passes and you accept the pin-shift and location-term gaps, Level 2 is reachable; otherwise it is not.

## 7. Results (owner approved the LODES download and the six pairs, 2026-11-08)

Download: LODES8 WAC (all jobs, JT00, 2023) and block crosswalk for the 18 scored states, 110 MB, from lehd.ces.census.gov into an empty folder, read with `python -I`. Method: retail (CNS07) plus accommodation and food (CNS18) jobs within 800 m of each stored pin, from 2020 block internal points. Script: `analysis/amenities_lodes_validation.py`. Criteria are the ones in section 5, written before any result was read.

| Criterion | Required | Result | Verdict |
|---|---|---|---|
| Coverage | 95% of 1,476 | 1,476 (56 places have zero jobs, kept as zero) | Pass |
| Spearman, home score vs jobs within 800 m | 0.70 or more | 0.819 | Pass |
| Median within-metro Spearman | 0.60 or more | 0.791 | Pass |
| Lowest metro | 0.45 or more | 0.600 (Seattle, n = 5); next lowest Los Angeles 0.692 | Pass, thin sample |

Not in the criteria, descriptive: the location term alone correlates 0.696 with jobs, lower than home (0.819), so the 40-point term is the weaker part. Largest rank disagreements: home too low against jobs for Silverado Ranch NV, Rancho Palos Verdes, Bal Harbour, Gainey Ranch, Highland Park TX, Peachtree Corners GA (big-box and office-park jobs, the expected LODES bias); home too high for Highland Village TX (the owner-kept 82.0 score), Sleepy Hollow, Irvington, Woodmere, Chappaqua NY (small village centers with few jobs). Limits: jobs not shops, so it validates density and rank order, not variety; the correlation is partly the urban-to-rural gradient, which is why the within-metro figure matters.

Launch pairs (stored scores, pass rule fixed in section 4):

| Pair | Scores | Gap | Result |
|---|---|---|---|
| Cobble Hill vs Short Hills | 100.0, 71.7 | 28.3 | Pass |
| Wicker Park vs Barrington | 95.3, 77.9 | 17.4 | Fail (needs 20) |
| Hoboken vs Fountain Hills | 97.3, 53.9 | 43.4 | Pass |
| Wicker Park vs Bucktown | 95.3, 83.2 | 12.1 | Fail (needs 10 or less) |
| Cobble Hill vs Brooklyn Heights | 100.0, 92.2 | 7.8 | Pass |
| Capitol Hill vs LoDo | 92.3, 98.8 | 6.5 | Pass |

Both failures match known gaps: Barrington is lifted by the location term (the audit's D4 and D5), and the Wicker Park and Bucktown gap is within the pin-shift range for adjacent places. Reported as failures, not explained away.

## 8. Proposed level for sign-off

Level 2 with recorded gaps. Independent validation passed all four fixed criteria on all 1,476 places. Launch pairs pass 4 of 6, the two misses traced to the location term and pin sensitivity. Accepted gaps to list: pin-shift (956 places move more than 5 in some 200 m shift; smoothing cuts it by about a third at the cost of new constants), location term unsourced and the weaker validated part (0.696), 800 m window and every weight unsourced, 49 places at zero because no business lies within 1,500 m, validation covers density and rank, not variety. Decision for you: sign Level 2 with these gaps, or hold Level 1 until the location term is redesigned. Spec sheet not edited and level line not changed until you sign.
