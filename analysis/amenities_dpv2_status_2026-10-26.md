# Neighborhood amenities: DPv2 status (2026-10-26)

Branch: `amenities-v2-on-origin` (built on origin/main, not pushed). Evidence per principle; "judgment" means a number with no source, recorded as a TODO with its measured range.

| Principle | Status | Evidence |
|---|---|---|
| P1 frame | Partial | Fixed walk-time access; tier 1 evidence for the construct only (young graduates). Location term still uses area-type divisors that change scores by under 4 points |
| P2 construct | Met (stated) | Walk-time access plus access to a nearby business center; spec sheet in the pillar doc. The center measure is still the old one |
| P3 measurement area | Partial | 800 m window and 1,200 m reach are judgment. 43 inconsistent pins found: 36 re-read at the stored pin, 6 held as no data, Ridgewood left; the pin-consistency check now reports 1 place. Stored pins themselves can be off (Tiburon) |
| P4 sourced weights | Open (judgment, ranges recorded) | 60/40, 50/25/25, tier weights, decay shape: all judgment. Grocery rule has a policy definition (USDA) |
| P5 double counting | Open | Location and home score correlate 0.86 on one business list |
| P6 sensitivity | Met (measured) | Window, anchor, split, weights, pin shift (200 m moves about 400 places by over 5) in the audit; pin range reported live |
| P7 validation | Open | Walk Score pull not done (needs permission; not independent). Price check: median within-metro Spearman 0.03 vs home value, -0.21 vs income, a null result |
| P8 all-places check | Met | Every change run on all 1,476 places; impacts in the audit and estimate files |
| P9 fail loud | Met | 0 amenities no-data rows. 49 verified empties score 0.0 with a warning; control query on the same endpoint; failed Places fallback marks degraded |
| P10 launch check | Met | Launch check PASS (gap +48.2 vs 20 required). Eight owner-approved pairs all pass (analysis/amenities_launch_pairs_2026-10-26.md); they were looked up before writing, so a check not a blind test |
| P11 disclose limits | Met | Live response and every catalog row carry data_source, source_counts, limits and pin_sensitivity (NYC pin range median 6.0, p95 24.1 points) |
| P12 re-validate | Met | One version tag live and catalog, stamped on all rows; health check updated; quarterly schedule and three checks documented (launch check, health check, pin consistency); live-vs-catalog comparison still manual |

## Tried and not adopted: cluster-based location quality
Densest 400 m cluster within 1,200 m of the pin, reach by decay, uniform divisor. Result on all 1,476 places: mean -2.65, 404 places drop over 5, up to -37.8; Brookline falls 75.1 to 66.3 while Darien rises 81.3 to 86.3, the opposite of the intended direction. Cause: it picks the densest cluster even when a decent one is much nearer the pin (Brookline: 55-business cluster 953 m away, businesses 22 m from the pin). A version that trades size against distance needs a new unsourced weight. Reverted; no code or catalog change.

## 43 places with inconsistent pins (known item, deferred 2026-10-14; now handled)
For 43 of 1,360 places with a business list, the stored distances disagree with the stored coordinates by more than 100 m (median). Worst: Highland Village (Dallas) 401 km, Almaden Valley (SF) 2,952 m, Windsor Square (LA) 1,557 m, Evergreen (SF) 1,507 m, Tiburon 1,394 m. SF has 21. Their amenities scores are suspect; the fix is a re-read at the right pin (private Overpass server needed). Not done.

## Catalog state
No amenities no-data rows. 32 re-read places (28 empty at 0.0, 4 with data) and 18 earlier ones are written; totals for the 32 dropped 3.3 to 6.0 points (mean -4.9). Several zero places are in large neighborhoods whose pin sits 1.5 km or more from the commercial center (for example Coconut Grove, Pinecrest, Pine Hills, Snell Isle); they are real zeros at the pin and a pin-quality question.

## Still needs the owner
Permission to pull Walk Score values; decision on the 43 inconsistent pins; sign-off; merge and push (main also holds two local natural beauty commits that are not part of this branch).

## Pin batch result (2026-10-26)
36 re-read at the stored pin and written (for example Reading 25.4 to 80.7, Chamblee 15.9 to 61.0, Lynn 56.0 to 83.5, Almaden Valley 82.3 to 72.3, Windsor Square 63.2 to 53.0, Loomis 64.5 to 31.9). 6 held as no data because the re-read found no business and the stored pin may be wrong. Totals for the 42 moved +0.7 on average (-2.7 to +4.4).
