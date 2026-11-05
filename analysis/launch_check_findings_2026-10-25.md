# Launch check findings: causes and proposals (2026-10-25)

Status: investigation and proposals only. No code, data or catalog changed. Four findings from `scripts/qa/launch_check.py`.

## 1. Healthcare ceiling (39% of places at exactly 100)
- Cause: the five components add to 100 (hospital access 35, primary care 25, specialized care 15, pharmacies 15, emergency 10) and
  most saturate: primary care is at its maximum for 87% of places, emergency services 75%, pharmacies 52%, specialized care 24%; hospital
  access is almost never at its maximum (0.1%). Scoring is facility counts within a radius against an area-type expectation, capped at
  about 3x the expectation. A median suburban place has 14 hospitals, 27 clinics and 15 urgent-care sites within the radius.
  Share at 100 by area type: urban core 81%, urban residential 85%, suburban 40%, exurban 26%, rural 5%.
- Reading: this is saturation by design of a count-versus-expectation curve, not a bug. It also uses a peer norm (area-type
  expectations from a sample of 19) where the approved frame says a fixed standard with distance decay.
- Options: (a) accept healthcare as an adequacy pillar (a ceiling is correct) and say so in the docs and the launch-check config;
  (b) replace saturating counts with absolute standards that do not saturate in metros: drive time to the nearest ER and
  primary-care physicians per 1,000 residents against the HRSA shortage threshold (1 per 3,500); (c) keep counts but score on a log scale.
- Recommendation: (a) now, because the contrast test (city core 99 vs rural 53) shows it separates what matters, with (b) as a
  research item. Do not widen the launch-check gate to make it pass.

## 2. Climate heat and trend floors
- Heat: scored on June to August 2022 Landsat land-surface temperature, 25 points at 30 C down to 0 at 42 C. The catalog median is
  39.8 C and 36% of places are at 42 C or above: Las Vegas 97%, Phoenix 98%, Dallas 98%, LA 82%, Sacramento 79%, Austin 74%, Houston 62%,
  Denver 60% score 0, so heat cannot separate places inside those metros. Surface temperature runs far above air temperature and the
  42 C zero point is unsourced. The frontend text says "extra summer heat vs the region" but the code is absolute (changed in commit
  28a27d6).
- Invalid values: 13 places have a June to August surface temperature below 20 C (Dunedin -21.5, Clearwater Beach -10.2, Clearwater -1.2,
  Palm Beach 7.7, Land O'Lakes 14.2, ...), with a land fraction of 1.0, so the guard misses them. Cloud or water contamination gives
  these places full heat points (25 of 25). This breaks "reject impossible values".
- Trend: 30-year TerraClimate tmax trend, 25 points at 0 C per decade down to 0 at 0.5. The catalog range is 0.15 to 0.58 and the median
  0.38, so 10% of places are at the floor: San Antonio 100% and Austin 97% (median 0.53), Phoenix 39%, Denver 18%.
- Proposal: (1) reject surface temperatures outside a plausible summer range (for example below 20 C or above 70 C) as no data, which
  needs only a code guard and a recompute of 13 places; (2) heat: decide between a relative measure (surface temperature minus the
  regional non-urban background, the urban heat island, matching the docs) or an absolute measure with a sourced scale such as hot days
  per year; (3) trend: re-anchor the zero point above the observed range with a source (the scale is a judgment, tracker P4).
  Items 2 and 3 change scores and need owner approval.

## 3. Community safety zero worker counts (Austin 33, Chicago 47, Philadelphia 39 places)
- Cause: only the neighborhood-circle places (open incident data cities) use the commuter adjustment: ambient population =
  residents + 45/168 x (workplace jobs - resident workers). The LODES grid `data/lodes_h8_commuter.parquet` has no cells for
  Illinois, Georgia, Colorado, Florida, Arizona or Washington, and only an edge of Pennsylvania. `jobs_in_disk` returns (0, 0) when
  a cell is missing, so out-of-grid places store zeros that look like real zeros and no adjustment is applied. No flag is set.
- Austin is stale, not missing: Texas was added to the grid later; today all 33 zero places have worker data (median ambient/residents
  ratio 1.02, 90th percentile 1.17, maximum 2.79; 15% change by more than 10%). The stored incident counts allow an offline recompute.
- Chicago (47) and Philadelphia (37 of 39) have no cells at all: a real coverage gap. Philadelphia old-city and downtown scores (e.g. Old
  City 5.2) are the places where the adjustment matters most.
- Proposal: (1) fail loudly: `jobs_in_disk` returns None when no cell exists in the disk and the pillar records
  `commuter_adjustment: unavailable` and marks degraded; (2) recompute the 33 Austin places offline from stored incident counts; (3) add
  Illinois and Pennsylvania (free LEHD files; the builder script exists) and recompute Chicago and Philadelphia; (4) other states only
  when a metro there gets incident-level data.

## 4. Boston "wild adventure" at exactly 50
- Cause: not a default or fill. 50 is the component's maximum budget, and 90% of Boston places hit it (trail and camping counts in the
  regional radius exceed the expectation: Blue Hills, Middlesex Fells). Same saturation elsewhere: Boston 73 places, NYC 52, Chicago 44,
  Philadelphia 35, Denver 32, SF 26.
- Related design flaw: the three point budgets sum to 110 (35 + 50 + 25) but the total is capped at 100, so 15% of places reach exactly 100
  by construction (launch check WARN) and the cap hides differences among the best places.
- Options: (a) accept, since regional trail abundance is real; (b) scale the budgets to sum to 100 so the cap never binds; (c) score
  trails on a log or distance-decayed measure that does not saturate. (b) is arithmetic only; (a)/(c) are design choices.

## Suggested order
1. Fail-loud guard for impossible LST and for missing LODES cells (no score change except 13 climate places and flags).
2. Recompute Austin safety offline (33 places).
3. Owner decisions on healthcare (adequacy pillar?), heat scale (relative or absolute), trend anchor, and active outdoors budgets.
4. Build the Illinois and Pennsylvania LODES grid and recompute Chicago and Philadelphia.

## Applied 2026-10-25 (code committed locally; catalog files not committed)
- Climate: LST outside 15 to 75 C is no data. 9 places rejected (Tampa area 8, Palm Beach 1): climate score mean -8.2 (range -13.7 to -4.7), total score mean -0.63.
  The other four places below 20 C (14.7 to 19.0 C) are above the 15 C bound and still score.
- Safety: jobs_in_disk returns None when the state is not in the built-state list (CA, CT, MA, NJ, NY, TX); Austin 33 places rescaled to the new ambient
  population (score mean +5.1, up to +23.4, 27 of 33 changed; total mean +0.48), Chicago 47 and Philadelphia 39 flagged commuter_adjustment unavailable and degraded
  with scores unchanged. Backups: data/backups_lst_guard_2026-10-25/ and data/backups_safety_commuter_2026-10-25/.

## Offline comparison of heat and warming-trend scales (2026-10-25, stored values only, nothing applied)
Heat (25 points; climate score mean, sd, rank agreement with the current score, within-metro sd in brackets):
| Scale | Heat sd | At zero | Phoenix at zero | Urban minus exurban within metro | Phoenix+LV minus Seattle+Boston | Climate score (with trend T1) |
|---|---|---|---|---|---|---|
| H0 current (30 C full, 42 C zero) | 8.15 | 36% | 98% | -4.99 | -12.84 | 58.0 (T0) |
| H1 absolute re-anchored (30 C full, 60 C zero) | 4.97 | 0% | 0% | -2.46 | -12.40 | 74.2, sd 10.0, ranks 0.97, within-metro 7.6 |
| H2 relative to metro background (0 C above metro 10th percentile full, 12 C zero) | 8.03 | 11% | 9% | -5.01 | -0.76 | 70.9, sd 11.4, ranks 0.71, within-metro 9.7 |
| H3 half H1 and half H2 | 5.62 | 0% | | -3.74 | -6.58 | 72.6, sd 10.1, ranks 0.88, within-metro 8.5 |
Trend (25 points): T0 current (zero at 0.5 C/decade) sd 3.87, 9.6% at zero (Austin 97%, San Antonio 100%, Phoenix 39%); T1 (zero at 0.8) sd 2.58, 0% at zero.
Trend is regional (a metro's places share a value), so a metro-relative trend scale is meaningless.
Level shift: any of these raises the climate score by about 13 to 16 points because the zero points move up, about +1.1 to +1.25 on total scores (climate weight 7.69%).
Every anchor is a judgment: the thresholds are surface temperatures, while health evidence is in air temperature and heat index.

## Applied 2026-10-25 (code and tests committed locally; catalog files not)
Heat 30 to 60 C and trend zero at 0.8 C per decade. 1,476 rows rescored: heat points at zero 36.3% to 0.0%, trend points at zero 9.6% to 0.0%;
climate score +16.2 on average (range +3.2 to +24.2); total score +1.26 (range +0.25 to +2.04); happiness +0.99; longevity +1.18 (up to +2.33).
Metro climate means: Phoenix 38 to 54, Austin 46 to 67, LA 58 to 74, NYC 63 to 78, Seattle 78 to 88 (order preserved). Backups: data/backups_climate_scales_2026-10-25/.


## Active outdoors: investigation (2026-10-25, offline, nothing applied)
- Failed reads scored as zero: 49 places (SF 32 of 113, NYC 8, LA 4, Philadelphia 3, Seattle 1, Las Vegas 1) have an Overpass error or empty read
  (45 trail reads, 4 local-park reads), were scored as having no trails or parks, and none is flagged degraded. Affected SF places score a median 51 vs 80 for
  the rest of SF. Rescoring from the components that did read moves them +14 on average (range -6 to +31): SF metro median 72.0 to 76.7, LA 64.6 to 66.4.
  The real fix is a retry of the query (the public Overpass blocks scripts; the private server is billed hourly).
- Budget arithmetic (35 + 50 + 25 = 110, capped at 100): scaling by 100/110 takes places at 100 from 15.2% to 0.5%, the most common value from 16.5% to 6.2%,
  keeps rank agreement at 0.997, and lowers the mean 78.5 to 71.8 (about -0.5 on totals).
- Measurement bias: median trail features within range: Boston 657, Seattle 89, Denver 135, Chicago 136, NYC 64, LA 64, Phoenix 65, Dallas 56, SF 46. A 10x gap between
  Boston and LA is more likely OSM mapping intensity than real trail supply, and 82% of the places at 100 max out the wild-adventure part. An independent measure
  (USGS PAD-US protected land within 15 km; hosted ArcGIS services exist but fields and query syntax are unverified) needs a pilot before it can replace or check the OSM counts.
