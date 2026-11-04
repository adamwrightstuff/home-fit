# Brief: independent validation of the quality_education pillar (DPv2 Level 2)

For an agent that did not build or convert this pillar. Written 2026-11-03 with the pass criteria below fixed before any new result is seen. The criteria are judgment (no source), set after the earlier EDFacts numbers were known (0.66 to 0.92 for ratings, 0.93 to 0.94 weighted for places), so they are not blind; the point of this run is a full-catalog, committed, repeatable version with fixed bars. Do not edit the criteria after seeing results. If one is wrong, report the result against the original and propose a change separately.

## What is being tested

The pillar scores the assigned school (zoned, else nearest rated schools of the home district, else the district pool average for lottery levels) by SchoolDigger statewide percentile, averaged over elementary, middle and high. Stored in `data/*_place_catalog_scores_merged.composites_recomputed.jsonl` under `livability_pillars.quality_education` (`score`, `breakdown.levels`, `breakdown.rated_schools`). 1,476 places, 1,472 scored.

## Rules

1. Do not call SchoolDigger. Read scores only from the stored catalog and `data/school_snapshot/`.
2. Any download or live API call (Urban Institute Education Data API, state report-card files) needs the owner's yes first, stating the file or endpoint, source and size. Put each download in its own new empty folder, keep scripts elsewhere, run Python with `-I`, pass paths as arguments.
3. Commit the script and the per-place output table (CSV) so the run can be repeated offline. Work in a new worktree off origin/main. Do not push to main without the owner's explicit yes. No em dashes.
4. Report in the order: pass or fail per test, then coverage, then the exceptions. Say plainly what was and was not verified.

## Preferred source

A recent-year state test results file (2023-24 or 2024-25 school-level proficiency, from each state's report-card download) beats EDFacts 2018, because the ratings are 2025 and the 2018 gap is the main known confound. EDFacts 2018 (Urban Institute API, `read_test_pct_prof_midpt` and `math_test_pct_prof_midpt`, grade 99 for all grades) is the fallback. 2020 is COVID-disrupted, do not use it. Name the source and year in the result. Independence caveat to state in the write-up: SchoolDigger percentiles are built from the same state tests, so these tests check aggregation and school matching, not an independent view of school quality.

## Tests and pass criteria (fixed)

**Test A, ratings vs proficiency, school level.** For each state with at least 30 matched rated schools per level: Spearman rank correlation between the SchoolDigger percentile in the snapshot and the school's proficiency, within state and level. Pass: at least 0.70 in each state-level cell, and at least 80% of cells pass, and no cell below 0.50. Cells with fewer than 30 schools are reported as inconclusive, not pass.

**Test B, place score vs proficiency of the same schools.** For every scored catalog place, compute the mean proficiency of the schools that fed its score (same level averaging as the pillar), then Spearman within state against the stored `score`. Pass: at least 0.70 in every state with at least 30 matched places, and the weighted mean over states at least 0.80. Coverage rule: report matched places over scored places per state; a state matched on fewer than 80% of its places is reported inconclusive, not pass. "Validated" copy is allowed only if every state is conclusive and passing, which is the full-catalog standard in `docs/DPV2_ADOPTION_DRAFT.md`.

**Test C, assigned school vs the district's own finder (sample).** Draw 40 catalog places with seed 2026, stratified: 20 whose elementary level came from a current zone map, 10 from the 2015-16 survey fallback, 10 from nearest-school logic. For each, read the pin's assigned elementary school from the district's published school finder or map (a manual read, no scraping beyond the owner's approval). Pass: at least 85% match for zone-map levels, at least 85% for 2015-16 levels (the earlier internal comparison found 90%), and report the nearest-school match rate with no bar (those places have no assigned school by construction; the test shows how far nearest-3 is from the real assignment). Places in lottery districts are excluded and listed.

**Test D, open disagreements.** Explain or mark unexplained, with a recent-year source, the large disagreements already known: Sausalito CA (King Academy), Anna TX, Clarksburg CA, New Braunfels TX, EaDo TX. No numeric bar; each must end as explained, or a rating error to report to the owner, or still unexplained.

## What to hand back

A results table per test against the bars above; coverage per state; the list of failing cells or places with the likely cause; the committed script and CSV; one line saying Level 2 independent validation is passed, failed or inconclusive. Do not change scoring. A failure goes to the owner as a finding, not as a fix.

## Where results go

Record them in the "Independent validation source and result" line of the spec sheet in `docs/PILLAR_QUALITY_EDUCATION.md`, with the date, the source and year used, and the bars. The owner then signs off the level.
