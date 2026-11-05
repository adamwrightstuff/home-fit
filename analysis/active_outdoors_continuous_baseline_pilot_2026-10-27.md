# Pilot: density-based baseline for active outdoors (2026-10-27)

Status: PILOT, offline, proposal only. No code or catalog file was changed. Computed from stored catalog data (`data/*composites_recomputed.jsonl`, 1,468 places with a clean local park count) and the area-type diff in `analysis/area_type_principal_city_diff_2026-10-27.csv`.

## Question
If the area type is mostly a lookup key for each pillar's expected values, can the density factors that feed it be used directly as a continuous baseline instead?

## What was piloted
Only the part of Daily Urban Outdoors (0 to 35) that uses the type table: the park count term (0 to 22) and the playground term (0 to 5). Not piloted: the proximity and facilities terms (kept at their stored values), the trail term (0 to 50) and the water term (0 to 25). The score form is unchanged: `22 * (1 - exp(-parks / expected))`.

Check that the recompute is valid: the stored daily score minus the park and playground terms (recomputed from the stored counts and the stored type's table) falls in the 0 to 11 range left for the proximity and facilities terms for 1,432 of 1,468 places (98%).

## Finding 1: the type table does not match the catalog
Parks per square kilometer (stored count divided by the area of the radius used), by people plus jobs per acre:

| Activity per acre | Places | Median parks per km2 |
|---|---|---|
| 0 to 3 | 131 | 0.4 |
| 3 to 6 | 184 | 1.4 |
| 6 to 10 | 226 | 2.1 |
| 10 to 15 | 247 | 2.7 |
| 15 to 25 | 263 | 4.0 |
| 25 to 45 | 192 | 7.1 |
| 45 to 100 | 128 | 9.3 |
| 100 and up | 97 | 18.8 |

The curve is smooth, with no step at a type line. The current table's expected values, converted to parks per km2 at the radius each type uses:

| Type | Expected parks | Radius | Per km2 |
|---|---|---|---|
| Exurban | 1 | 2,000 m | 0.08 |
| Suburban | 64 | 1,500 m | 9.05 |
| Urban residential | 90 | 1,000 m | 28.65 |

Exurban sits far below the catalog medians (0.4 to 2.1 per km2 where exurban places live), and urban residential sits about 2 to 5 times above them (medians 4 to 19 across the activity range where urban residential places live). The urban residential values are marked in the code as estimates ("Est. P50 at 1000m radius").

## Finding 2: the cliffs at the type lines
Mean gap in the daily outdoors score between places of nearly equal density (within 10%) that land in different types, scored with the final types:

| Pair | Type table | Continuous baseline |
|---|---|---|
| Exurban versus suburban (n=169) | +18.2 | -0.4 |
| Suburban versus urban residential (n=256) | +6.0 | -1.7 |

Under the type table an exurban place scores 18 points higher than a suburban place of the same density on this component, because one park is enough to satisfy an exurban bar.

## Finding 3: effect on the 441 places whose type changes
Daily outdoors score (0 to 35), change from the stored value:

| Method | Mean change | Mean absolute change | Share moving more than 5 points |
|---|---|---|---|
| New type table | -8.8 | 10.5 | 80% |
| Continuous baseline | -2.3 | 6.5 | 49% |

Whole active outdoors score (0 to 100): type table mean -8.9, mean absolute 10.6; continuous mean -2.5, mean absolute 6.5. Largest drops under the type table: Coronado AZ (83.5 to 58.8), Biltmore AZ (89.8 to 65.3), Berkeley Place TX (91.4 to 67.1), West 7th TX (92.3 to 68.3), Addison TX (91.3 to 67.5), all exurban to urban residential.

## Cost: the continuous baseline recenters everyone
Over all 1,468 places, the whole active outdoors score changes by a mean of -0.8 (10th percentile -13.7, 90th percentile +8.5) and the rank correlation with the stored scores is 0.817. The type table changes only the places whose type changes (rank correlation 0.889, median change 0). So moving to a continuous baseline is a recalibration of the whole pillar, not only a fix at the boundaries.

## Fitted baseline (median parks per km2, made monotone)
| Activity per acre | Per km2 | Within 1,000 m | Within 1,500 m | Within 2,000 m |
|---|---|---|---|---|
| 2 | 0.64 | 2.0 | 4.5 | 8.0 |
| 5 | 1.59 | 5.0 | 11.2 | 20.0 |
| 10 | 2.51 | 7.9 | 17.7 | 31.5 |
| 25 | 5.23 | 16.4 | 37.0 | 65.8 |
| 45 | 8.70 | 27.3 | 61.5 | 109.3 |
| 100 | 14.89 | 46.8 | 105.3 | 187.1 |

## Caveats
- Only 27 of the pillar's 100 points were modeled. The trail term (50 points) uses per-type expected values and maximum points (12, 25 or 30) and a 2.6 times fragmentation discount for urban residential places, all of which would also need a continuous version.
- The baseline is the median of this catalog, which holds neighborhoods and close-in suburbs, so it is not a national sample. Fewer than 130 places sit below 3 activity units per acre.
- The expected value is fitted to the same places it then scores. The existing tables are also medians from small samples (n=10 to 19), so the construct is the same, but a continuous version needs an external check (for example against a national park dataset).
- Counts were gathered at each type's own radius. The "type table" column rescales counts by area to the new radius; a real rescore would re-query.
- This is an offline estimate, not a rescore.

## Options
A. Keep the type tables and recalibrate their values from the catalog medians (fixes the level, keeps the cliffs).
B. Replace the park and playground expected values with the continuous baseline, keep the other terms (fixes the cliffs for 27 points; mixed design until the trail and water terms follow).
C. Do B for every term of the pillar, then repeat for transit and healthcare.

## Open questions
1. Is recentering all active outdoors scores acceptable (rank correlation 0.817 with stored)?
2. What external dataset should check the fitted park baseline?
3. Should the trail and water terms be piloted next?

---

# Part 2: trails (wild adventure) and water (added 2026-10-27)

Status: PILOT, offline, proposal only. Same data and caveats as part 1. Result: a density baseline works for the park terms but is the wrong tool for trails, and the water term does not need one.

## Water term (0 to 25): no baseline to replace
The water score has no expected-value table. Its only dependence on the area type is a multiplier on the winning feature: 0.75 for urban core (not for beaches), 0.9 or 0.95 for suburban and urban residential (lakes 0.95, beaches and bays 1.0), and 1.0 for exurban and rural. For the 367 places whose type changes and that have a water feature, the effect is a mean of -0.18 points, a worst case of -1.80, and only 1% of places move by more than 1 point. Nothing to fix here beyond deciding whether to keep the multipliers; they carry no source in the code.

## Trails term (0 to 50): the type constants are the cliff
Expected trails within 15 km in the table: urban residential 10, suburban 109, exurban 1, rural 1. The maximum points, the near-trail expectation and a 2.6 times discount (urban residential only) also change with the type. Wild adventure score for the same raw counts under each type (camping within 20 km, no mountain-town flag):

| Trails within 15 km / within 5 km | Urban residential | Suburban | Exurban |
|---|---|---|---|
| 5 / 0 | 14.4 | 11.1 | 39.8 |
| 15 / 2 | 22.4 | 16.6 | 41.9 |
| 30 / 6 | 30.9 | 23.6 | 44.9 |
| 60 / 10 | 38.2 | 30.3 | 47.3 |
| 120 / 20 | 43.4 | 38.3 | 50.0 |

An exurban place with 5 trails and none nearby scores 39.8 of 50; the same counts in a suburban place score 11.1. That 28-point gap sits on the exurban versus suburban line. The suburban bar of 109 trails is also well above what suburban places have (stored medians are 22 to 72 within 15 km), so a typical suburban place scores about 24 of 50.

## Why density is the wrong baseline for trails
Stored median trails within 15 km by activity per acre: 22 (under 3), 43, 58, 71, 66, 72, then 30 for 45 and up. The count rises with density and then falls in dense cores, so it is not a monotone function of density the way the park count is. Trail access depends on where the metro sits relative to open land, not on how dense the pin's block is. A fit on local density would mostly learn which metros have foothills.

## A limit on any offline trails recompute (SUPERSEDED by part 3: the mismatch was my omission of the mountain-town rule)
Recomputing the stored wild adventure score from the stored trail counts, the stored camping distance and the current code reproduces it within 1.5 points for only 402 of 1,476 places (27%); on the mismatches the stored value is higher by a mean of 6.2. No single expected-trails value fixes it (best 18% for suburban places). So the stored summary counts are not the scoring inputs, or the stored scores came from an earlier version of the table or filters. Until that is explained, a trails baseline cannot be refit or tested from the catalog; it needs a rescore that records the exact scoring inputs.

## Revised options for the pillar
- Parks and playgrounds: use the density baseline (part 1).
- Trails: do not use local density. Consider scoring trail access on an absolute scale shared by all places, as the amenities pillar now does, or against a metro-level expectation. Needs a design decision.
- Water: drop or keep the small multipliers; no calibration needed.
- The question of why the stored wild adventure scores did not reproduce is answered in part 3.

---

# Part 3: why the stored wild adventure scores did not reproduce (added 2026-10-27)

Status: investigation, offline, report only.

## Answer
The 27% match in part 2 was my mistake: I scored every place as if the pillar's "mountain town" flag were off. With the flag applied as the code applies it, the stored scores reproduce for 94% of places (within 1.5 points, from the stored counts, canopy and camping distance, under the current formula or the previous one). The stored catalog is mostly consistent with the current code.

| Stored wild adventure score (n=1,474) | Places |
|---|---|
| Matches the current formula only | 650 (44%) |
| Matches both the current and the previous formula | 610 (41%) |
| Matches only the previous formula (still has the tree canopy term removed on 2026-09-27, `6cc625a`) | 125 (8%) |
| Matches neither | 89 (6%) |

The 125 stale places can be brought up to date offline: the canopy term is a function of the stored canopy percentage, so it can be subtracted. The 89 unexplained places (6%) were not investigated further.

## The mountain-town rule is the default, not a special case
`_detect_special_contexts` flags a place as a "mountain town" for non-dense areas when it has 40 or more trails within 15 km, or 30 or more with 8% canopy, or 20 or more with 10% canopy, or 5 or more within 5 km with 8% canopy. Applied to the stored counts and canopy, it flags 1,135 of 1,474 places (77%), including 695 of 764 suburban places (91%). Its branch uses a near-trail expectation of 15 and larger point budgets (35 and 20), so for most suburban places the "suburban" trail constants in the table are not the ones used.

## A second area type hides inside the pillar
For dense places (urban core or urban residential) the same flag switches the scoring type to exurban (`effective_area_type = "exurban"`), and that type feeds the park expectation too (one park). Applied to the stored data it affects 59 of the 197 places stored as dense (30%). So the pillar already overrides the shared area type for almost a third of the dense places, using only OSM trail counts and canopy.

## Consequences for the redesign
- Any baseline fit on the stored trail counts must model the flag, or it will fit the wrong expectation.
- The cliffs between types for the trail term are bigger than the type table alone shows, because the flag moves places between branches too.
- A shared, simpler trail scale (absolute, or metro-level) would remove both the type cliffs and the flag.
- The flag's thresholds are not sourced beyond three example cities in the comments (Denver, Boulder, Times Square).
