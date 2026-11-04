# Climate risk: Level 2 check brief (for an agent that did not build or convert the pillar)

Written 2026-11-03. Pass criteria below were fixed before any validation result exists. Read the disclosure under "Criteria" first.

## Rules for the checker
- Work in a git worktree off the branch `worktree-dpv2-climate-risk`. Do not edit scoring code, the catalog files, or the spec sheet values in `docs/PILLAR_CLIMATE_RISK.md`. Write results to a new file `analysis/climate_level2_results_<date>.md` and new data files only.
- Offline from stored catalog data first. Anything that needs a download, an API call, a GEE read or a FEMA query: stop and ask the owner with the exact file name or endpoint, source, and read count. Downloads go in their own empty folder; run Python that reads them with `-I`; keep scripts in a different directory.
- No em dashes. Say plainly what is verified and what is not.
- Files under test: `analysis/climate_dpv2_disk_2026-11-03/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (1,476 places, disk flood measure). Comparison only: `analysis/climate_dpv2_2026-11-03/` (single-pin flood, option B). Pillar key `score.livability_pillars.climate_risk`; fields `score`, `breakdown.heat_exposure_pts`, `breakdown.air_quality_pts`, `breakdown.flood_zone_pts`, `breakdown.climate_trend_pts`, `summary.flood_zone_shares`, `summary.flood_mapped_fraction`.
- Components and points: heat 25, air 20, flood 30, trend 25. Score is scaled over the components present; fewer than 3 present means no score.
- Pin-shift data already run by the builder: `analysis/climate_pin_shift_2026-11-03/` and `analysis/climate_flood_disk_pilot_2026-11-03/`. Rerun, do not trust.

## Criteria (fixed now)
Disclosure: the builder's pin-shift, disk pilot and diff numbers were seen before these thresholds were written, so V2, V3 and V4 are not blind. The thresholds for V1 were set before any comparison with an outside source was run. Thresholds are judgments, not sourced; the pin-shift limits follow the healthcare benchmark, and the 0.7 Spearman follows principle 7.

| # | Check | Pass criterion |
|---|---|---|
| V1a | Heat against NOAA summer (JJA) mean daily maximum temperature, 1991 to 2020 normals, for the nearest station within 25 miles of each place (or the PRISM 800 m normal at the place) | Spearman of heat points vs station value, all places with a heat reading: at least 0.60. Within-metro Spearman (metro mean removed): at least 0.30. Report the places that differ by more than 30 percentile points. Heat is satellite surface temperature, station air temperature is a different quantity, so the bar is moderate |
| V1b | Air against EPA monitor annual mean PM2.5 (2021 to 2022) of the nearest regulatory monitor within 15 miles | Spearman of air points vs monitor value, places with a monitor: at least 0.75. Median absolute difference between tract PM2.5 and monitor value at most 1.5 ug/m3 |
| V1c | Flood against the FEMA National Risk Index riverine plus coastal expected-annual-loss rating or the county share of land in the special flood hazard area, whichever the owner approves for download | Spearman of flood points (metro mean included) vs the outside value: at least 0.40 at county level. Flood is local and the outside source is coarse, so this tests direction only. State this limit in the write-up |
| V2 | All-places check, rerun from the files | No more than 5 percent of places with score at or below 5 or at or above 95; no more than 5 percent with any one component at its cap; stored score equals the scaled sum of present components within 0.15 for every place; places with fewer than 3 components have no score; the 5 places with no mapped polygon and the places with zone D only have flood as no data and are listed |
| V3 | Pin shift, rerun with 4 diagonal directions at 500 m and 1,000 m on a new random sample of 60 places (12 per area type) | Disk flood measure: median final-score change at most 2 at 500 m and at most 5 at 1,000 m; 95th percentile at most 10 at 500 m. Needs FEMA and GEE reads: ask first with the count |
| V4 | Launch pairs, stored scores | Should differ by 8 or more points: Phoenix vs Seattle; Las Vegas vs Boston; a Gulf coast floodplain place vs an inland place in the same metro (pick from the catalog and list them before looking at scores). Should be within 3 points: two adjacent tracts of one neighbourhood in one metro (pick before looking). Report every pair that fails; do not swap pairs after the fact |
| V5 | Overlap with other pillars | Absolute Spearman of the climate score with natural_beauty and with active_outdoors, all places and within metro, below 0.6 for both |
| V6 | Disk vs pin | Report, no pass threshold: the 20 largest movers between `climate_dpv2_2026-11-03` and `climate_dpv2_disk_2026-11-03`, each with the zone shares that explain the change |

## Steps and what each needs
1. V2, V5, V6 need only the files above. Do them first.
2. V4 needs the files above. Choose and write down the unnamed pairs first.
3. V1a, V1b, V1c each need an outside download (NOAA normals or PRISM, EPA AQS annual summary, NRI or county flood share). Confirm exact file names, vintages and sizes from the source pages, then ask the owner before downloading. Each also needs station or monitor coordinates joined to places, which is offline once downloaded.
4. V3 needs live FEMA and GEE reads: about 480 flood queries and 480 heat reads for 60 places, 8 shifts each. Ask first.
5. V1 independence caveat: tract PM2.5 and station or monitor PM2.5 share some monitor data (the CDC/EPA surface is fused from monitors and satellite), so V1b is independent in processing, not wholly in the underlying data. State this.

## Report format
One table: check, result, pass or fail against the criterion above, n. Then a list of places that failed or were not checked, and what was not verified. Do not change a criterion after seeing results; if one looks wrong, say so and propose the change separately.
