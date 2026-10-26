# DPv2 check, education pillar (run 2026-10-26 after commit f53aecd)

Read-only. Stored values are from origin/main (1,476 places). Pin-shift numbers are the 2026-10-25 replay (zoning code unchanged). Decisions of 2026-10-26 are owner judgment (tier 3). Details of earlier findings: `analysis/audit_education_v2_recheck_2026-10-26.md`, spec sheet `analysis/education_spec_sheet_2026-10-26.md`.

## Result: 4 meet, 5 partly, 2 fail, 1 not tested

| Principle | Result | Evidence |
|---|---|---|
| P1 reference frame | Meets as owner judgment | Within-state percentile, stated in the doc as not comparable across states. Evidence tier 2 (capitalization studies, not re-verified here) plus an owner decision. Part 1 would default school proficiency to a fixed standard; the deviation is recorded. |
| P2 construct | Meets | One sentence now in `docs/PILLAR_QUALITY_EDUCATION.md`: quality of the assigned school (zoned, else nearest, lottery levels use the district pool), by statewide test percentile. Not checked: level versus growth in the research. |
| P3 measurement area | Partly | Pin plus district polygon plus zone polygon, reason given for the assigned-school choice. The 1.5 / 2 / 3 mile radii and nearest-3 are judgment with no source (only the elementary-to-middle ratio is sourced, NHTS 2017). |
| P4 sourced weights and ranges | Fails | Weight 7.69% (owner judgment, no source, no range), radii, nearest-3, 3 mile cap, 15 mile fallback, pool average, equal level weights: all TODO. Early-education points are 0 (not a parameter any more). |
| P5 double counting | Not tested | Feeds the longevity index (sourced to years of schooling, a different construct). Overlap with housing value (home prices capitalize schools) untested. |
| P6 sensitivity | Fails | 0.5 mile pin shift, largest of four directions, 1,472 places: median 5.8 points, p90 32.0, p95 42.9, max 80.9; 53% move more than 5 points. Agreed treatment is a confidence flag; not built. No in-pillar weight test (composite level: weight to 0 moves totals a mean 1.6, approximate). |
| P7 validation | Partly | Ratings vs EDFacts proficiency, Spearman 0.66 to 0.92 within districts, 2017-18 data. The place-level score and pool averages are not validated. |
| P8 all-places check | Meets for this work | Every change this week was run on all 1,476 places and compared with before; `check_education.py` passes for all 21 metros. |
| P9 fail-loud | Meets | 4 places are no data and degraded; none scored 0 (0 zeros in 1,476); early-education lookup failures and uncovered states are `early_ed_missing` (541), not zero; live scorer no longer turns a missing score into 0.0. Small gap: 3 places with only 1 or 2 levels scored ("thin") are not flagged degraded. |
| P10 launch check | Partly | The spread gate passes (sd 26.0, 99 distinct values, 0.1% at max, top value 2.8%, between-metro variance 7%). No should-differ and should-match pairs are written for education. 95 places score 95 or higher, so the top is crowded. |
| P11 data limits | Partly | Docs list thin districts and stale Austin zones. 1,023 places have at least one level from the 2015-16 zone survey (77.7% of zoned levels) and nothing flags it; 541 places have no early-education data (flagged). Lottery districts give every address nearly the same number (documented). |
| P12 re-validation | Partly | Yearly snapshot refresh is written down; no dated validation schedule. |

## Defects with stored evidence

1. P6: pin sensitivity above. Contradiction found: `analysis/launch_check_and_pin_shift_plan_2026-10-25.md` lists education as "not applicable, shift-proof by construction". The replay shows the opposite (median 5.8 points for 0.5 mile), so that line should be corrected before anyone relies on it.
2. P4: no source or range for weight, radii or pool rules.
3. P11: 2015-16 zone vintage (1,023 places) not surfaced; 3 thin places not flagged degraded; 366 places have at least one level from nearest-school logic (no zone map), also not surfaced as confidence.
4. P10: no launch pairs.

## Proposed fixes and expected score impact

| Fix | Catalog score change |
|---|---|
| Pin-sensitivity confidence flag | None; adds a flag (cutoff to agree) |
| Zone-vintage, thin-level and nearest-level flags in degraded or confidence | None; flags on about 1,000 places |
| Correct the "shift-proof" line in the plan file | None |
| Education launch pairs, run and recorded | None |
| Source or range for weight and radii | Unknown until found; test on all places first |
| Add GA, FL, AZ, CO, NV, MA, NC to the private server and re-query early-education access | None (0 points); fills 541 gaps |

## Sourced versus judgment

Sourced: SchoolDigger percentile rating (checked against EDFacts, old data); elementary-to-middle radius ratio (NHTS 2017); zone maps from district publications and the NCES 2015-16 survey (90% agreement with current maps in 143 checks). Judgment: weight, radii, nearest-3, caps, pool average, the frame and construct choices (owner, 2026-10-26).

## Decision for you

Education launch pairs: do you want to name them (3 places that should differ, 3 that should match), or have me propose candidates from stored data for you to approve?
