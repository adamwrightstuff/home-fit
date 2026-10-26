# Education pillar, DPv2 final status (2026-10-26)

Everything verified on origin/main (commit b4ff435, 1,476 places) unless noted. Earlier detail: `analysis/audit_education_v2_recheck_2026-10-26.md`, `analysis/education_spec_sheet_2026-10-26.md`, `analysis/education_p4_sources_2026-10-26.md`, `analysis/education_launch_pairs_2026-10-26.md`. Owner decisions of 2026-10-26 are tier 3.

## Principle by principle

| Principle | Status | Evidence |
|---|---|---|
| P1 reference frame | Meets (owner judgment) | Within-state percentile, stated in the doc as not comparable across states. Tier 2 support (price follows standardized test rank), owner decision. |
| P2 construct | Meets | One sentence in the doc. Level (not growth) is sourced: Imberman and Lovenheim 2016, prices follow test levels, not value-added (tier 2, one city, from a search summary). |
| P3 measurement area | Meets with recorded judgment | Assigned school by pin, district polygon and zone polygon. Base radii and caps act only where no zone map covers the point (364 places) and barely matter: see P4. |
| P4 sourced weights and ranges | Documented, not sourced | Sourced: elementary-to-middle-to-high radius ratio (NHTS 2017). Judgment with a recorded range: weight 7.69% (0 to 2 times, weight 0 moves totals a mean 1.6); level weights (doubling one level moves scores a mean 2.5, p95 7.3 to 7.9); radii and caps (below); choice pool average (no test). Early-education points are 0. |
| P5 double counting | Meets | No shared raw input: education uses SchoolDigger ratings only; housing value has no school input. Spearman rho with other pillars (1,472 places): community safety 0.48, natural beauty 0.44, diversity -0.42, social fabric 0.38, housing value 0.20, all others under 0.2 in absolute value. Within metro, housing value 0.26, safety 0.39, diversity -0.41. These reflect shared affluence, not shared inputs; no numeric threshold exists in DPv2, so none is applied. Education also enters the longevity and happiness indices, which are separate from the headline total. |
| P6 sensitivity | Measured and disclosed | 0.5 mile pin shift: median 5.8, p95 42.7; 387 places flagged above 15 points (cutoff is owner judgment). Weight, level-weight and radius sensitivity measured (P4). The swing itself is not reduced. |
| P7 independent validation | Meets, with stated limits | Two tests against EDFacts proficiency (Urban Institute API, free, 2018 data). (1) School ratings: Spearman by district 0.66 to 0.92 (2018); the newest API year (2020) is COVID-disrupted and does not improve on it. (2) Place level, run 2026-10-26: for 798 places (of 1,438 with named schools, in the 9 well-covered states) the place's education score vs the mean proficiency of the same schools, within state: CA 0.94 (n=243), IL 0.96 (97), NJ 0.95 (41), PA 0.96 (75), TX 0.90 (262), NY 0.89 (56); weighted mean 0.93 over 774 places. This is above the 0.7 that DPv2 uses as a bar for perceptual pillars (no bar is set for education). All-grades version (EDFacts grade 99, run 2026-10-26, 473 requests, same 798 places): CA 0.95, IL 0.96, NJ 0.96, PA 0.96, TX 0.92, NY 0.91, weighted mean 0.94 over 774 places, so the single-grade version was not hiding a problem. Limits: it tests the rating aggregation at the schools the place uses, not whether the right schools were chosen; ratings are 2025, proficiency 2018; only 56% of places matched (name and grade coverage), NY and CT, IN, WA are thin; largest rank disagreements are in Texas and California (Allen TX 79.8 rating vs 46% proficiency, New Braunfels, Sausalito, Venice), not diagnosed. |
| P8 all-places check | Meets | Every change run on all 1,476 places; `check_education.py` passes for all 21 metros. |
| P9 fail-loud | Meets | 0 zero scores; 4 no data (degraded); 32 places missing a level are degraded; 541 places without early-education data flagged `early_ed_missing`; live scorer no longer coerces a missing score to 0.0. |
| P10 launch check | Meets with one known limit | Spread gate passes (sd 26, 99 distinct values). Five of six approved pairs pass; the owner's mid-range pair Babylon vs Tarrytown fails (64.7 vs 49.4) because Babylon is scored from one level; owner decided to keep scoring from fewer levels, flagged, and record it as a known limit. |
| P11 data limits | Meets | Flagged on the place: 2015-16 zone maps (1,023), nearest-school levels (364), pin sensitivity (387), missing levels (32), missing early-education data (541). Vintage and sampling limits in the doc. |
| P12 re-validation | Meets as a written schedule | Rule (from DPv2): when a source changes or quarterly, whichever is first. Triggers: yearly SchoolDigger snapshot refresh; any district zone-map update (Austin first); new EDFacts release; any education code change. Each run: `rescore_education_offline.py --no-osm`, `enable_education_weight.py`, `recompute_catalog_composites.py --no-census`, `check_education.py`, then `compute_education_pin_sensitivity.py` and `flag_education_data_limits.py`, then the six launch pairs. Next dated check: 2027-01-26 (quarterly). |

## Radius and cap sensitivity (P4 range, 364 places that use nearest-school logic, offline, 2026-10-26)

| Change | Mean abs change | p95 | Max | Places changed more than 0.5 |
|---|---|---|---|---|
| base radius x0.5 | 0.21 | 0.0 | 25.1 | 4 |
| base radius x2 | 0.60 | 4.15 | 25.5 | 52 |
| cap 2 miles | 0.68 | 4.56 | 19.4 | 60 |
| cap 4 miles | 0.38 | 2.91 | 10.8 | 40 |
| cap 5 miles | 0.52 | 4.03 | 13.8 | 49 |

Reading: the radius barely matters because the rule picks the nearest 3 schools whichever radius reaches them; the cap matters only for places whose third school is far. Replay reproduced the stored scores exactly.

## Choice pool average sensitivity (P4 range, 126 places with a lottery-pool level, offline, 2026-10-26)

The rule is the enrollment-weighted mean of the rated district-run schools of the level. Alternatives on the same 126 places (replay of the stored scores was exact):

| Alternative | Mean abs change | p95 | Max | Places changed more than 2 | more than 5 |
|---|---|---|---|---|---|
| unweighted mean | 3.15 | 10.4 | 10.4 | 45 | 39 |
| median | 1.30 | 4.1 | 7.5 | 52 | 2 |
| enrollment-weighted median | 3.28 | 10.9 | 10.9 | 41 | 41 |

Reading: unlike the radii, this judgment moves scores. The choice of mean versus median and of weighting by enrollment changes these places by a mean 1.3 to 3.3 points (up to 10.9). It stays a recorded judgment (no source found); the range is now measured. Owner decision 2026-10-26: keep the enrollment-weighted mean (weights by students served; no evidence favors another method). These 126 places are 8.5% of the catalog.

## Place-level validation: the biggest disagreements, dug into (2026-10-26, from the cached API results, no new calls)

| Place | What the stored schools show | Likely cause |
|---|---|---|
| Allen TX, New Braunfels TX | High school rating 90.0 vs 12.0% proficiency (Allen High); 79.6 vs 11.0% (New Braunfels High) | The check compares a whole-school rating with grade-9 proficiency only. In Texas, grade-9 results look unrepresentative (likely because advanced students take Algebra I earlier; not verified here), as the earlier pooled high school figure of 0.39 also showed. A limit of the check. |
| Venice CA | Elementary 77.3 vs 37.0%, middle 80.5 vs 32.0% | The check uses one grade (4 or 8) and 2018 results as bin midpoints, against a whole-school 2026 rating. Plausible measurement gap, not shown to be a rating error. |
| San Marcos TX, EaDo TX | Elementary 82.5 vs 39.5%, 62.4 vs 32.0% | Same single-grade and year-gap explanation. |
| Sausalito CA | Martin Luther King Jr Academy: rating 70.7 vs 24.5% proficiency; it counts as both the elementary and middle level (K-8) | Unexplained. A 24.5% proficiency school at the 71st state percentile looks wrong at face value; it may have changed since 2018 or the rating may be off. Needs SchoolDigger or state data to resolve. |
| Anna TX | Joe K Bryant Elementary: rating 3.4 vs 59.5% | Unexplained. A fast-growing district; a large change since 2018 is possible. |
| Clarksburg CA | Walnut Grove Elementary 33.1 vs 69.5% (nearest school, small district) | Unexplained; very small schools. |

Rating year is 2026 and proficiency is 2018, so an eight-year gap is built into every row. Conclusion: most large disagreements come from limits of the check itself (a single grade or Texas grade-9 results standing in for a whole school, bin midpoints, the year gap), not from demonstrated errors in the ratings. Three cases (Sausalito, Anna, Clarksburg) are unexplained and are listed as open. No change to scoring is proposed. The all-grades rerun (473 requests) raised the weighted mean from 0.93 to 0.94 and Allen TX dropped out of the top disagreements, confirming the grade-9 artifact. Still large in the all-grades run: Sausalito CA (rating 78.8 vs 34.0%), New Braunfels TX (78.9 vs 41.7%), Anna TX (25.1 vs 52.2%), EaDo TX (49.9 vs 31.5%), Manvel TX, Montclair CA, Hollywood CA, Lancaster TX, Clarksburg CA. These stay open. Correction: the local SchoolDigger snapshot (`data/school_snapshot/`) was checked on 2026-10-26 and does not help: each school carries only its 2026 statewide percentile, stars, grades, enrollment and address, with no test scores and no earlier years (so Sausalito's King Academy is simply 70.74, 4 stars, K-8, 262 students). Resolving them needs state test results for a recent year (a download), not more SchoolDigger data.

## What is not met, plainly

1. P4 is documented, not sourced: no study gives the education weight, level weights, the cap or the pool average. DPv2 calls an unsourced number a TODO, so these stay TODOs with recorded ranges.
2. P7: no clean test year after 2018 in the source used (the 2020 year is COVID-disrupted); the place-level test covers 798 places and the biggest disagreements are not diagnosed.
3. Education launch pair Babylon vs Tarrytown fails (known limit).
4. Early-education data is missing for 541 places in states the private Overpass server does not cover; it is worth 0 points.

## Last open item

The validation script now takes `--year` (change is in a local worktree, `../home-fit-edu7`, uncommitted). Nothing else is open that can be closed with the data available. Remaining limits are the four listed under "What is not met", with P7 now limited by the source (no clean year after 2018), not by effort.
