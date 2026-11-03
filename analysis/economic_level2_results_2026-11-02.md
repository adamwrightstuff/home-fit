# Economic security Level 2 results (independent checker), 2026-11-02

Scope: V2, V3, V4, V5 from `docs/ECONOMIC_SECURITY_LEVEL2_BRIEF.md`, run from the stored catalog files (`data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, 1,476 places) and `data_sources/job_accessibility.py`. V1 was not run (needs a download; on hold). No network, no API calls, no existing files edited. Scripts are in `/private/tmp/claude-501/-Users-adamwright-Dev-home-fit/9841ed0f-a5a0-4ca5-b5d3-3542012c3299/scratchpad/l2/`.

## Results

| Check | Result | PASS / FAIL | n |
|---|---|---|---|
| V1 EPA SLD validation | Not run (on hold, needs download) | Not checked | 0 |
| V2a Final score at or below 5 or at or above 95 | 0 places (0.0%); limit is 5% | PASS | 1,476 |
| V2b Job access equal to 100 | 31 places (2.1%); limit is 5% | PASS | 1,476 |
| V2c Stored blend equals round(0.55 x job access + 0.45 x market quality, 1) within 0.15 | 0 places outside 0.15; max difference 0.10 | PASS | 1,476 |
| V3 Pin shift, 1 km, 4 diagonals: median change (limit 1.0) | 0.10 | PASS | 5,904 shifts (1,476 places x 4) |
| V3 Pin shift, 1 km: 95th percentile change (limit 3.0) | 0.20 (max 0.70, Moapa Town) | PASS | 5,904 |
| V3 Pin shift, 500 m (reported, no criterion): median / p95 | 0.0 / 0.10 (max 0.50) | Info | 5,904 |
| V4 Midtown vs Galt CA (should differ by 10 or more) | 83.7 vs 65.8, difference 17.9 | PASS | 2 |
| V4 Harlem vs Spring Branch, San Antonio (should differ by 10 or more) | 83.2 vs 57.8, difference 25.4 | PASS | 2 |
| V4 Downtown Las Vegas vs Mesquite NV (should differ by 10 or more) | 61.5 vs 37.4, difference 24.1 | PASS | 2 |
| V4 Harlem vs Park Slope (within 3) | 83.2 vs 83.2, difference 0.0 | PASS | 2 |
| V4 Park Slope vs Brooklyn Heights (within 3) | 83.2 vs 83.6, difference 0.4 | PASS | 2 |
| V4 Compton vs Beverly Hills (within 3) | 82.7 vs 83.1, difference 0.4 | PASS | 2 |
| V4 Palo Alto vs East Palo Alto (within 3; expected FAIL per brief) | 68.5 vs 76.1, difference 7.6 | FAIL (expected, open limit) | 2 |
| V5 Economic score vs status_signal, all places (|r| below 0.6) | Spearman 0.16 | PASS | 1,470 |
| V5 Economic score vs status_signal, within metro (|r| below 0.6) | Spearman 0.22 | PASS | 1,470 |
| V5 Economic score vs housing_value, all places (|r| below 0.6) | Spearman -0.48 | PASS | 1,469 |
| V5 Economic score vs housing_value, within metro (|r| below 0.6) | Spearman -0.50 | PASS | 1,469 |

## Places that failed

- Palo Alto (sf, suburban, final 68.5, job access 84.9, market quality 48.5) vs East Palo Alto (sf, suburban, final 76.1, job access 85.2, market quality 65.1): gap 7.6 points against a limit of 3. The brief expects this failure. The brief's note says "gap 1", which does not match the observed 7.6, so the note needs a check (see criteria concerns below).

No other place failed a criterion.

## Criteria concerns (not applied, proposed separately for the owner)

1. V4 Palo Alto note: the brief says "metro line, gap 1", but the stored gap is 7.6. Either the note refers to a different measure or it is out of date. Owner to confirm what "gap 1" means.
2. V3 thresholds are loose relative to what the job access function does. Observed 1 km median 0.1 and 95th percentile 0.2 are far below the 1.0 and 3.0 limits, so this check could not catch a place whose score is sensitive to position. It also cannot test a metro line, which needs a county boundary (not run). Owner may want a tighter limit or an added test.
3. V5 limit of 0.6 is wide; observed values (0.16, 0.22, -0.48, -0.50) sit well inside it. Not a defect, but it would not catch moderate overlap.
4. V4 names: the brief says "Midtown Manhattan", but the catalog entry in nyc is named "Midtown". I used "Midtown". Not a criterion problem, just a naming mismatch in the brief.

## What was not verified

- V1 not run (EPA Smart Location Database download and block-group lookup needed; held).
- The job access grid (`data/lodes_h8_jobs_national.parquet`) was used as in the repo. I did not check its vintage, provenance or coverage against the LODES source. The recomputed job access at each place's stored coordinates matches the stored value exactly (max difference 0.0 across all 1,476 places), which shows consistency with the stored values only, not validity.
- V3 shift interpretation: each place moved a total distance of 1 km (or 500 m) along the NE, NW, SE and SW bearings, so each axis moves about 0.71 km (or 0.35 km). I did not run the alternative (1 km per axis). The change is measured against the stored final score, so the rounding noise of the stored blend (up to 0.1) is included; the 500 m median of 0.0 shows this noise is the main source of small changes.
- V3 uses the stored market quality for each place (not recomputed), as the brief specifies.
- V5: 6 places lack a status_signal and 7 lack a housing_value; they are excluded from the matching correlation. Within-metro is computed by removing each metro's mean from both variables and then ranking the pooled values. Per-metro Spearman values are in `scratchpad/l2/results.json`; with fewer than 30 places in a metro, sample sizes are small.
- Spearman was computed with my own average-rank implementation; I did not cross-check it against a statistics library.
- V2 counts use the stored `score.livability_pillars.economic_opportunity.score` as the final score.
- I did not compare `catalog.lat/lon` with `score.coordinates`; the coordinates used are `score.coordinates`.
- These results are from the stored catalog files as they are in this worktree, not from the production Explorer or live API.
