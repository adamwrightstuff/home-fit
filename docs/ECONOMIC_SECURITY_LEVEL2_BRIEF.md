# Economic security: Level 2 check brief (for an agent that did not build or convert the pillar)

Written 2026-11-02. Pass criteria below were fixed before any validation result exists. Read the disclosure under "Criteria" first.

## Rules for the checker
- Work in a git worktree off origin/main. Do not edit scoring code, the catalog files in `data/`, or the pillar doc's spec sheet values. Write results to a new file `analysis/economic_level2_results_<date>.md` and new data files only.
- Offline from stored catalog data first. Anything that needs a download, an API call or an Overpass read: stop and ask the owner with the exact file name, source and size. Downloads go in their own empty folder; run Python that reads them with `-I`; keep scripts in a different directory.
- No em dashes. Say plainly what is verified and what is not.
- Catalog files: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (1,476 places). Pillar key `livability_pillars.economic_opportunity`; fields `score`, `summary.job_access_score`, `summary.market_quality_score`.
- Job grid: `data/lodes_h8_jobs_national.parquet`; code `data_sources/job_accessibility.py`.

## Criteria (fixed now)
Disclosure: the launch pairs and the builder's pin-shift and all-places numbers were seen before these thresholds were written, so those checks are not blind. The thresholds for validation V1 were set before any comparison with the outside source was run. Thresholds are judgments, not sourced; they follow the 0.7 Spearman used in principle 7 for perceptual pillars, raised to 0.8 because both measures count the same kind of jobs.

| # | Check | Pass criterion |
|---|---|---|
| V1 | Independent validation of job access against the EPA Smart Location Database employment-accessibility field (auto travel time) for the block group of each place | Spearman of log10(SLD value + 1) vs log10(gravity + 1), all 1,476 places: at least 0.80. Within-metro Spearman (metro mean removed from both): at least 0.60. Median of per-metro Spearman for metros with 30 or more places: at least 0.60. At most 5 percent of places differ by more than 30 percentile points. Report every place that does. |
| V2 | All-places check, rerun from the files | No more than 5 percent of places with final score at or below 5 or at or above 95; no more than 5 percent with job access of 100; stored blend equals round(0.55 x job access + 0.45 x market quality, 1) within 0.15 for every place |
| V3 | Pin shift, rerun with 4 diagonal directions at 500 m and 1 km | Median final-score change at most 1.0 and 95th percentile at most 3.0 at 1 km |
| V4 | Launch pairs, stored scores | Should differ by 10 or more points: Midtown Manhattan vs Galt CA; Harlem vs Spring Branch (San Antonio); Downtown Las Vegas vs Mesquite NV. Should be within 3 points: Harlem vs Park Slope; Park Slope vs Brooklyn Heights; Compton vs Beverly Hills; Palo Alto vs East Palo Alto. The Palo Alto pair is expected to FAIL (metro line, gap 1); report it as an open limit, not a surprise |
| V5 | Overlap with other pillars | Spearman of the economic score with status_signal and with housing_value, all places and within metro. Pass: absolute value below 0.6 for both (builder run on 2026-11-02 found 0.16 and -0.48; rerun independently) |

## Steps and what each needs
1. V2, V3, V4, V5 need only the files above. Do them first.
2. V1 needs a download of the EPA Smart Location Database (national block-group file). I have not verified the exact field name, the vintage or the file size, so confirm them from the source page, then ask the owner before downloading. It also needs each place's block group: ask before using the Census geocoder or any other API, or ask for a block-group boundary file.
3. V1 independence caveat: the Smart Location Database is also built from LODES jobs, so it is independent in travel-time method and processing, not in the jobs data itself. State this in the write-up.
4. Optional, each needs an owner decision on a download: (a) LODES origin-destination files to fit the commute-decay constant (pass for a fitted exponential constant between 15 and 30 km; this would source the parameter); (b) county boundaries to test a pin shift across a metro line (report only, no pass threshold, because the failure is already known).

## Report format
One table: check, result, pass or fail against the criterion above, n. Then a list of places that failed or were not checked, and what was not verified. Do not change a criterion after seeing results; if one looks wrong, say so and propose the change separately.
