# Education pillar, DPv2 re-audit (2026-10-26)

Read-only. Stored values come from origin/main (commit 0cb8333, 1,476 places), not the local working tree, which is stale. Pin-shift numbers are from the 2026-10-25 replay in `analysis/audit_education_2026-10-25.md`; the zoning and district code has not changed since, so I did not rerun it. Principles are in `docs/DESIGN_PRINCIPLES_V2_DRAFT.md`.

## Headline

Fail-loud (P9) now mostly meets for this pillar, and the early-education bonus is no longer an unsourced parameter (it carries 0 points). The pillar still does not meet P2, P4 and P6: it has no stated construct, its weight and radii have no source, and a half mile pin shift moves the score a median 5.8 points. P1 is waiting on your decision.

## What changed since 2026-10-25 (verified in origin/main)

- Early-education bonus: 0 points in all 1,476 places. Access is stored as data (facilities within 2 km and 800 m, nearest distance) for 935 places. 541 places in GA, FL, AZ, CO, NV, MA and NC are flagged `early_ed_missing`, not stored as zero.
- Four places that stored 0.0 now store no data: score empty, status no_data, degraded with a reason. Indian Springs (NV) and Rio Verde, Sun City and Sun City West (AZ).
- SF: all 113 places score (none empty or zero).
- 1,472 places have a score (min 1.6, median 61.5, max 99.4); 95 are at 95 or above and none sit at 100 (before, two did, through the bonus).
- Weights: 1,466 at 7.69, 7 at 8.33 (air travel is no data for them, so the weight is redistributed, which is the right behavior), 3 at 0 (the Phoenix places).

## Per principle

| Principle | Status | Evidence |
|---|---|---|
| P1 reference frame | Open, owner decision | The score is a statewide percentile of school test results (relative, tier 2 from Part 4). Part 1 says school proficiency should default to a fixed standard. A statewide percentile is not comparable across states. |
| P2 construct | Does not meet | No one-sentence construct. The code scores the test-score level of the zoned, nearest or district-pool schools, not growth, and the doc still describes it as "school quality near a location". Whether score level or growth is what residents pay for is not checked beyond the capitalization studies already cited. |
| P3 measurement area | Partly | Pin plus Census district polygon plus zone polygon; nearest 3 within 1.5, 2 or 3 miles by area type when no zone. The doc calls the radii "our own conservative choice". Only the elementary-to-middle ratio has a source (2017 NHTS). |
| P4 sourced weights and ranges | Does not meet | Still unsourced, no recorded range: the 7.69% weight, the radii, nearest-3, the 3 mile widening cap, the 15 mile district-far fallback, the district-average choice pool, equal weighting of the three levels. The early-education points are now 0, so that item is a TODO, not a parameter. |
| P5 double counting | Not tested | Education also feeds the longevity index (weight 3.0, sourced to years of schooling, a different construct). Overlap with housing value (prices capitalize schools) is not tested. |
| P6 sensitivity | Fails | Replay of 1,472 places, pin moved 0.5 mile in four directions, largest change: median 5.8, p90 32.0, p95 42.9, max 80.9; 53% move more than 5 points. Part of the tail is shifts landing in another district. No in-pillar weight test; composite level (approximate): weight to 0 moves totals a mean 1.6 (max 4.9). |
| P7 independent validation | Partly | Ratings checked against EDFacts proficiency, Spearman 0.66 to 0.92 within districts, 2017-18 data. Nothing validates the place-level score or the pool averages. |
| P8 all-places check | Partly | This session's changes were each run on all 1,476 places and compared with before. No standing all-places regression for the pillar beyond `check_education.py`, which passes for all 21 metros. |
| P9 fail-loud | Mostly meets | Missing early-education data is flagged, not zero; no-data places are null and degraded; the scorer returns no score instead of 0.0. Open: the live endpoint in `main.py` (lines 2361 and 4046) still turns a missing education score into 0.0. Three places have only 1 or 2 levels scored ("thin") and one has none; that shows in the summary but not in the degraded flag. |
| P10 launch pairs | Not defined | No pairs written down. Top is crowded: 95 places score 95 or higher. |
| P11 data limits | Partly | Docs list thin districts and stale Austin zones. 77.7% of zoned levels use 2015-16 boundaries and the place does not show that as a confidence or degraded reason. 541 places have no early-education data. |
| P12 re-validation | Partly | Yearly snapshot refresh is written in the doc; no dated validation schedule. |

## Defects still open

1. Live scorer coerces no data to 0.0 (`main.py` 2361, 4046). Effect on the catalog: none (the catalog is rescored offline). Effect on `/score` with education requested: the pillar shows 0 instead of no data. Education's default live weight is 0, so totals are unaffected unless a user raises it.
2. Doc drift: `docs/PILLAR_QUALITY_EDUCATION.md` (lines 58, 89 to 101) still describes the early-education bonus as scored points and the old radius formula as the scoring section.
3. Zone vintage is not surfaced (P11). About 1,020 places carry at least one level from the 2015-16 survey (count from the 2026-10-25 run; origin's current count may differ slightly).
4. Pin sensitivity (P6): no mitigation yet.
5. 541 places have no early-education data until the private server covers those states.
6. Weight, radii and pool rules have no source (P4).

## Expected impact of the proposed next fixes

| Fix | Catalog score change |
|---|---|
| Live scorer returns no data instead of 0.0 | None |
| Update the doc | None |
| Surface zone vintage and thin levels as degraded or confidence | No score change; flags on roughly 1,000 places |
| Add GA, FL, AZ, CO, NV, MA, NC to the private server and re-query | None (bonus is 0 points); fills 541 data gaps |
| Source or record a range for the weight and radii | Unknown until sources are found; each would be tested on all places first |
| Pin-shift mitigation (place or tract footprint) | Would change many scores (replay shows median 5.8); needs a design and an all-places run first |
| Reference frame change to a fixed standard | Not computable offline: needs a national comparison source |

## Sourced versus judgment

Sourced: SchoolDigger percentile as the rating (validated against EDFacts, old data); elementary-to-middle radius ratio (NHTS 2017); zone maps from district publications and the NCES 2015-16 survey (90% agreement with current maps in 143 checks); relative frame (capitalization studies in the Part 4 table, not re-verified).

Judgment, no source: everything listed under P4, and the choice to average lottery pools.

## Decision for you

Should education stay a within-state percentile (what it is now, comparable only inside a state) or move to a fixed national standard, which needs a national test-score source I have not found and would change cross-state ordering?
