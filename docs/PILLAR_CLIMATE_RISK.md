# Pillar Deep-Dive: Climate Risk

How `pillars/climate_risk.py` scores a location.

## What it measures
Forward-looking environmental risk, as a 0–100 score where **higher = safer** (lower risk),
built from four sub-scores:

| sub-score | signal | source |
|---|---|---|
| `lst_score` | heat exposure / urban heat island (land surface temp) | satellite LST |
| `aqi_score` | air quality: annual mean PM2.5 for the census tract | CDC Tracking Network tract PM2.5 (EPA Downscaler), `data/pm25_tract_annual.json` |
| `flood_score` | flood risk | FEMA flood data |
| `trend_score` | forward climate trend | trend model |

Each is a capped point bucket (`heat_pts/HEAT_MAX_PTS`, etc.) converted to 0–100, then
combined.

## Air quality (changed 2026-10-24)
The old component was a Sentinel-5P aerosol index scaled to a fake "PM2.5 proxy"; it tracked desert dust and
smoke (rank correlation about -0.14 with measured PM2.5) and gave 86% of places full points. It is replaced by
measured annual PM2.5 per census tract (2021 to 2022 mean, extended as CDC adds years), built by
`scripts/baselines/build_pm25_tract_table.py`. Points: 20 at 5 ug/m3 (WHO 2021 annual guideline) falling
linearly to 0 at 35 (WHO interim target 1). The 5 end is evidence-based; the 35 end is a judgment that only
sets the slope (no US place is near 35), so treat the air weight as an unvalidated choice (tracker D13). A tract
with no value means no data for this component (the climate score uses the other three, flagged degraded).
Wildfire smoke is part of PM2.5 and is kept.

## Heat and warming-trend scales (changed 2026-10-25, judgments)
Heat is linear in the June to August Landsat land-surface temperature: 25 points at 30 C down to 0 at 60 C. Warming trend is linear in the
30-year tmax trend: 25 points at no warming down to 0 at 0.8 C per decade. Both anchors are judgments, not sourced thresholds: surface
temperature runs well above the air temperature health evidence uses, and the old zero points (42 C and 0.5) sat inside the observed
ranges and flattened 36% of places on heat and 10% on trend. Sensitivity (analysis/launch_check_findings_2026-10-25.md): a pure rescale
(rank agreement 0.97 for the climate score), Phoenix and Las Vegas stay about 12 points below Seattle and Boston, urban cores stay below
exurbs in the same metro, the climate score rises about 16 points (about +1.25 on totals, +1.2 on longevity). A scale relative to the metro
background was rejected because it erases real differences between metros. Surface temperatures outside 15 to 75 C are no data.

## Fail loud (changed 2026-10-24)
A component that cannot be measured is no data, not a neutral value; the score is built from the rest and marked
degraded, and fewer than three of four components means the pillar fails.

## Reading the score
- It's **regional** in character — places in the same metro share similar climate, so within-
  metro variance is modest (and legitimate). Coastal places correctly carry higher flood risk
  (Marina del Rey / Manhattan Beach score lower on flood — real, not a bug).
- A coastal high-flood signal is the main intra-metro differentiator.

## Gotcha
- Low within-metro spread is expected (shared climate); don't mistake it for a coarse-geo bug.
- Higher score = lower risk (safer) — note the polarity when interpreting.

---

## DPv2 spec sheet and audit (2026-11-02, audit only, nothing changed)

Level: 1 (Converted), accepted by the owner 2026-11-05. Level 2 not reached (see "Level 2 status" near the end). Option B was approved 2026-11-03 and implemented (see "Change record" at the end).
Everything below was computed offline from the 1,476 stored catalog rows (`data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`) and `data/fema_flood_zones_catalog.json`. No API, GEE or FEMA call was made for the numbers. Sources I did not open this session are marked "cited in code, not re-read".

```
Pillar: climate_risk
Construct (one sentence): Exposure at the pin to physical environmental hazards: summer surface heat, fine particulate air
  pollution, FEMA-mapped flood zone, and the recent rate of warming. Exposure, not resident outcomes and not price response.
Reference frame: fixed standard (absolute hazard) for all four components. No peer norm, no area-type baseline.
  Evidence for the frame (tier 1 published study | tier 2 revealed-preference proxy | tier 3 survey):
    air: tier 1. Mortality rises about linearly with PM2.5 (Di et al. 2017 NEJM, cited in code, not re-read); the WHO 2021
      annual guideline of 5 ug/m3 is a fixed health standard (cited in code, not re-read).
    heat: tier 1 for "absolute level matters" (heat and mental-health emergency visits, JAMA Psychiatry, listed in
      HAPPINESS_EVIDENCE_NOTES, not re-read). Nothing found that maps satellite surface temperature to harm.
    flood: tier 2. Price discounts for flood risk are small and depend on disclosure (DPv2 Part 4, from search summaries), so
      the frame is physical probability, not price. FEMA's 1% and 0.2% annual-chance zones are a regulatory standard, not a study.
    trend: none. No source found that treats the past rate of warming as a hazard level (see G6).
Measurement area: pin + circle, different per component (heat 500 m; PM2.5 the pin's census tract; flood the single pin point;
  trend a 5 km circle read at 4 km pixels).
  Reason: heat 500 m has no stated reason; tract is the PM2.5 table's native unit; the flood point lookup is a convenience, not a
  lived-experience area (principle 3 not met, see G4); trend is regional by construction.
Place context inputs used (fields) and remaining area-type uses (with reason):
  Reads area_type and density from the context only to feed assess_pillar_data_quality (confidence metadata). No score value keys
  on the area type. It does not read census_tract from the context: get_pm25 calls the Census geocoder again (G3).
Inputs and data sources (with vintage):
  Heat: Landsat 8/9 Collection 2 Level 2 surface temperature, June to August 2022 only (one summer), cloud under 30%, water masked.
  Air: CDC Tracking Network tract PM2.5 (EPA Downscaler), 2021 and 2022 mean, 83,776 tracts, table built 2026-10-25.
  Flood: FEMA NFHL service layer 28, live at fetch; catalog snapshot 2026-10-23. Effective date of each county's underlying map
    is not recorded (unknown).
  Trend: TerraClimate monthly tmax, 1990 to 2020 linear fit.
Parameters:
  name | value | source | plausible range | sensitivity result
  component caps heat/air/flood/trend | 25/20/30/25 | unsourced | unknown | not run
  heat best / worst LST | 30 C / 60 C | judgment (2026-10-25) | zero point 42 to 60 tested earlier | rank agreement 0.97 (launch_check_findings_2026-10-25)
  heat land fraction minimum | 0.3 | judgment | unknown | not run
  LST plausible bounds | 15 to 75 C | judgment | unknown | rejects 9 places, see G2
  PM2.5 best | 5 ug/m3 | WHO 2021 guideline | fixed | n/a
  PM2.5 worst | 35 ug/m3 | judgment (WHO interim target 1) | 15 to 50 | air points sd 1.27 at 25, 0.85 at 35, 0.56 at 50 (offline, this audit)
  PM2.5 nearest-tract match | 5 km | judgment | unknown | 13 places use it (Connecticut)
  flood multipliers floodway/SFHA/shaded X/D/minimal | 0 / 0.15 / 0.83 / no data / 1.0 (changed 2026-11-03; was 0.55 and 0.45 for X and D) | floodway 0 and SFHA 0.15 judgments; shaded X derived from FEMA annual chances (1% and 0.2%) assuming loss proportional to chance | unknown | not run
  trend zero point | 0.8 C per decade | judgment (2026-10-25) | unknown | not run
  minimum components | 3 of 4 | design | n/a | n/a
Shared inputs with other pillars: none read directly (grep of pillars, data_sources, main.py, scripts). Downstream only: the
  climate score feeds the happiness and longevity composites. Heat and trend correlate weakly (Spearman 0.27 across the catalog,
  0.16 within metro), so they do not double count much. Natural beauty doc records no overlap with climate.
Pin-shift sensitivity (shift distance, median and p95 score change): RUN 2026-11-03 by the owner with
  `scripts/catalog/climate_pin_shift.py` (60 places, 12 per area type, seed 20261103; north, east, south, west at 500 m and 1,000 m;
  fresh FEMA flood and GEE heat reads, 480 points; PM2.5 and trend NOT re-read, so their shift sensitivity is unmeasured).
  4 flood reads failed (all Boca Raton) and are excluded; 476 scored. Output: `analysis/climate_pin_shift_2026-11-03/`.
  500 m: median change 0.8, 95th percentile 24.2, 10.9% of shifts move the score by more than 10.
  1,000 m: median 1.6, 95th percentile 22.5, 12.2% over 10.
  By area type (median / 95th, 500 m): urban core 0.6 / 24.4; urban residential 0.6 / 2.6; suburban 0.8 / 23.5; exurban 1.1 / 26.7;
  rural 1.0 / 24.7. At 1,000 m the urban residential 95th percentile is 30.6.
  Cause (computed from the reads): flood. When the flood tier at the shifted point equals the tier at the pin (401 of 476 shifts),
  the median change is 0.8, the 95th percentile 3.9 and no shift exceeds 10 (this isolates heat plus the unchanged parts). When the
  tier differs (75 shifts), the median change is 20.6 and 73% exceed 10. 27 of the 60 places have at least one of their eight
  shifted points in a different flood tier from the pin. Stored tier to shifted tier, most common changes: minimal to SFHA 19,
  SFHA to minimal 12, shaded X to minimal 10, shaded X to SFHA 8.
  Criteria fixed in advance (healthcare benchmark): median 2 or less at 500 m (PASS, 0.8), median 5 or less at 1,000 m (PASS, 1.6),
  95th percentile 10 or less at 500 m (FAIL, 24.2). Level 2 pin-shift is therefore not met until the flood measurement changes.
  Not claimed: that the unchanged-tier result covers PM2.5 and trend, which were held at their stored values.
Independent validation source and result: NOT RUN. Candidates for the brief: PM2.5 against EPA monitor annual means (open
  data), heat against NOAA station summer maximum temperature, flood against FEMA county flood-zone area share. Pass criteria
  to be fixed before any result is seen.
All-places check (date, n, summary): 2026-11-02, n=1,476, stored values before any change. Mean 74.2, median 77.1, 10th to 90th
  percentile 58.7 to 84.5, min 34.8, max 93.6. Median by area type: urban core 79.8, urban residential 78.1, suburban 76.2,
  exurban 76.0, rural 76.4. 42% of variance is between metros. No place at 0 or 100.
  Component clumping: flood 83.2% of places at the 30-point maximum; heat 6.3% at 25; air 0.5%; trend 0.1%.
Fail-loud conditions: a component that cannot be measured is no data and the score scales over the rest, flagged degraded;
  fewer than 3 of 4 raises. Implausible LST is no data. G1 and G11 are places where this does not hold today.
Launch check pairs: NOT RUN for this spec. The 2026-10-25 check kept Phoenix and Las Vegas about 12 points below Seattle and
  Boston and urban cores below exurbs in the same metro. Pairs for Level 2 to be fixed in the validation brief.
Known data limits: only four hazards are scored. Not covered: wildfire exposure (smoke only, through PM2.5), hurricane wind and
  surge beyond FEMA coastal zones, tornado and hail, earthquake, drought, extreme cold. PM2.5 for 2021 and 2022 includes the
  2021 western smoke season. NFHL is the regulatory map, not a model of future flood risk. Heat is one summer.
Last re-validated: never under DPv2.
```

### Audit gap table

Impacts are on the climate pillar score (0 to 100). Climate carries about 8 percent of the composite, so 1 pillar point is roughly 0.08 on the total.

| # | Gap | Evidence (stored data) | Recommended fix | Expected impact | Needs |
|---|---|---|---|---|---|
| G1 | La Porte, TX carries a neutral flood value from a failed FEMA read, not flagged (principles 9, 16). | Flood snapshot holds null for 29.6658,-95.0194; stored flood points 15.0 (50%), tier None, degraded false, score 56.2. | Set flood to no data, flag degraded, recompute from the other three offline. A real value needs one FEMA call. | One place: 56.2 to about 58.9 on the other three components. | Offline now; 1 FEMA call to restore |
| G2 | Nine places lose heat because the Landsat composite returned an impossible temperature (-21 C to 14 C): eight Tampa area places and Palm Beach. Land fraction is 1.0, so it is not a water-mask effect. | Dunedin -21.5 C, Clearwater Beach -10.2 C, Oldsmar 10.1 C, others 7.7 to 14.7 C. Scores 52.5 to 87.7 on three components. | Keep fail-loud (correct today). Cause not verified; a one-summer window with few clear images is a candidate. Widening to 2021 to 2023 summers would test it and fix G7. | Nine places regain heat; Gulf places likely score lower, size unknown until reread. | GEE reads, 9 places plus whatever G7 needs |
| G3 | The pillar ignores the shared tract and calls the Census geocoder again for PM2.5 (principles 13, 15). | get_pm25 calls get_census_tract; PlaceContext.census_tract exists and main.py fills it. | Read the tract from the context when present, fall back only for catalog callers. Add a test. | None expected (same tract). One fewer network call per live request. | Code and test only |
| G4 | Flood is one point-in-polygon lookup at the place center, so a small move can flip 30 points (principles 3, 6). | 83.2% of places at the maximum; 111 places (7.5%) in SFHA or floodway average 54.5 against 75.8 for the rest; flood is the largest source of within-metro spread (sd 7.6 points against 5.0 for heat). Pin-shift not measured. | Measure first: pin-shift at 500 m and 1,000 m on 60 places (15 per area type, 4 directions). Then decide whether to score the share of an 800 m disk in each zone. | Unknown until measured. | About 480 FEMA point reads for the test (60 x 4 x 2); disk share would need about 1,500 geometry queries. Free public service, ask first |
| G5 | Flood tier multipliers are unsourced. The 0.2% zone keeps 55% of points and the 1% zone keeps 15%: a 5x gap in annual chance becomes a 1.9x gap in points lost (45 against 85). Zone D (undetermined) gets 45%, an invented number. | FEMA defines the zones by annual chance. 129 places are shaded X (Phoenix 49 of 64, Sacramento 15, SF 19, Miami 13, Houston 10); 7 are zone D. | Make loss proportional to annual chance: keep SFHA at 15% retained, set shaded X to 83% retained (0.2 of the SFHA loss). Zone D becomes no data. Floodway stays 0 (judgment, listed). Proportional-to-probability is itself an assumption, recorded as such. | Simulated offline on stored tiers: +8.4 for shaded X places; mean +0.7 over the catalog; 140 places move more than 1 point; Phoenix mean +6.3 (median 52.5 to 60.6), Sacramento +2.0, Miami +1.6, Houston +1.2; rank correlation with today 0.986; catalog sd 9.98 to 9.05. This simulation also applies G11. | Offline recompute only |
| G6 | Warming trend is a past rate, not a hazard level, with no source as a harm measure. It is 25% of the pillar and costs places 11.9 points on average (minimum 4.8). Regional: 308 distinct values over 1,476 places. | Trend range 0.15 to 0.58 C per decade against a 0.8 zero point; Spearman with heat 0.27. | Record as a TODO with range unknown. Replace with a forward-looking hazard source (G8) or cut its weight. Both change composites, so this is a separate decision. | Not estimated. | Decision |
| G7 | Vintages are thin: heat one summer (2022); PM2.5 two years; NFHL map dates not recorded. | Date filter in code; table meta. | Recorded in the spec above. Widen heat with G2. Extend PM2.5 years when CDC adds them. | Heat changes by weather noise; size unknown until reread. | GEE reads (with G2) |
| G8 | Hazard coverage is narrow (listed under known data limits). A place can read as low climate risk with a large uncovered hazard. FEMA flood and air quality are already scored and are not gaps. | Code review. | Option C: add FEMA's National Risk Index tract layer (per-hazard annual expected loss). Not downloaded, not read, not verified as suitable. | Large and unknown; would reorder metros. | Download (permission, own empty folder, python -I) and a weights decision |
| G9 | Air has almost no effect: the 35 ug/m3 zero point means 12 ug/m3 loses only 4.7 of 20 points. | Air points mean loss 2.3, p95 3.7, sd 0.85. 403 places exceed the 2024 US annual standard of 9.0 and 123 exceed 10. | Do not change now. The zero point has no evidence (range 15 to 50) and no common unit exists to compare ug/m3 with a flood zone. Level 3 TODO. | None | Decision at Level 3 |
| G10 | WITHDRAWN 2026-11-03. I reported 36 stored pins missing from the flood snapshot. That came from matching on the catalog list coordinates; the scored coordinates (what the recompute uses) match the snapshot for all 1,476 places. | Recompute: 0 places left as stored. | None. | None. | None |
| G11 | Five places with no FEMA polygon at the pin are scored as minimal risk, full flood points (principle 16). | Chatham NJ, Morristown NJ, Southport CT, West Sacramento CA, Belvedere CA. West Sacramento is a known levee-protected city. | Treat "no mapped polygon" as no data for flood. | CORRECTION: I wrote "under 2 points" for the other four. Measured: all five fall 6.0 to 12.5 points (Chatham 78.6 to 69.4, Morristown 77.1 to 67.3, Southport 85.2 to 78.8, West Sacramento 70.7 to 58.2, Belvedere 86.2 to 80.2), because dropping a full-marks component scales the score over three weaker ones. | Offline for the rule; reads to restore |

Verified this session: stored heat, air and trend points match the current formulas for every place, and the stored score equals the weighted parts for every place; stored flood points match the snapshot for every pin once matched on the scored coordinates (an earlier 36-pin gap, G10, was my matching error and is withdrawn). Not verified: any cited paper, what a missing NFHL polygon means, why Landsat returned negative temperatures, and whether the National Risk Index fits. One side effect to note: a first script imported the pillar module, which initialized the Earth Engine client (an authentication call, no data read); the rerun used inline formulas.

### Options

- **A. Spec only.** Record the spec sheet and fix G1, G3, G11 (flags and code; six places change). Reaches Level 1. Leaves the flood tier numbers and pin problem open.
- **B. A plus the flood tier rescale and zone D as no data (G5).** Offline recompute, no API. Then run the pin-shift (G4) with approved FEMA reads and decide on the disk-share measure from the result.
- **C. B plus a new hazard layer (G8, G6).** Largest change, needs a download and a weights decision. Do after B is signed off.

Recommendation: **B**. It fixes the one number we can derive from a published definition (FEMA annual chance) using data we already hold, and it produces the evidence for the bigger flood and coverage decisions.

### Decisions needed (original, before approval)

1. Approve B (or A)? Approved 2026-11-03.
2. Permission for later reads: FEMA (G1, G4) and GEE (G2). I will state exact counts and the output folder before running.
3. Whether G8 (National Risk Index download) deserves its own pass.

### Change record, option B (2026-11-03, uncommitted, for your review)

Code: `data_sources/fema_flood.py` (shaded X keeps 83% of flood points, derived as 1 minus 0.85 x 0.2; zone D and an unmapped point return no data; cache key bumped to v3), `pillars/climate_risk.py` (flood tier and zone are kept when points are None; degraded reasons `flood_zone_d_undetermined` and `flood_no_mapped_polygon`; the tract comes from the place context), `data_sources/air_quality_pm25.py` (`get_pm25` takes the context tract and only looks it up when none is supplied), `scripts/catalog/recompute_flood_offline.py` (rewritten: new files only, no-data flood handling, carries total score and longevity; a null snapshot entry is a failed FEMA read and becomes no data, G1).
Tests: `tests/test_fema_flood.py` (updated), `tests/test_climate_risk_dpv2.py` (new). Full suite: 794 passed, 1 failed, 1 skipped. The failure is `tests/test_metro_agent_state.py` (Colorado election file registered or not); it does not touch these modules, and I did not run it on the unchanged code to confirm it fails there too.
Recompute: `analysis/climate_dpv2_2026-11-03/` (21 metro files plus `diff.csv`; `data/` untouched). Offline, no data call. The happiness index was recomputed on the new files with `recompute_happiness_only.py`; the total score and longevity follow the climate change. Verified: exactly 142 places differ from the stored files, and in those places only the climate pillar, total score, longevity and happiness changed.
Results (142 of 1,476 places changed):
  shaded X, 129 places: +8.3 to +11.2 (mean +8.4). Zone D, 7 places: +1.9 to +6.8. La Porte, TX: failed read now no data, 56.2 to 58.9. Unmapped, 5 places: -6.0 to -12.5 (G11 correction above).
  Climate score mean change +0.73 over the catalog; total score mean +0.06 (min -1.04, max +0.93). Metro mean climate change: Phoenix +6.5, Sacramento +2.0, Miami +1.6, SF +1.5, Houston +1.2, San Antonio +0.9, others under 0.5.
  All-places after change: mean 74.9, median 77.2, 10th to 90th percentile 61.8 to 84.5, min 34.8, max 93.6. Median by area type: urban core 79.8, urban residential 78.1, exurban 76.5, suburban 76.4, rural 76.4. Flood at the 30-point maximum 82.9% (13 places with no flood component).
  One side effect: importing the composite code initializes the Earth Engine client (authentication only, no data read), so the recompute script prints the same GEE message.

Open for your decision: the five unmapped places lose 6 to 12.5 points because "no data" removes their best component. That is principle 9 working as written, but it penalizes a place for a missing map. Options: keep (current), or re-read a point 100 m away first (needs FEMA reads, ask first).

Re-read of the five unmapped pins (2026-11-03, 20 FEMA point reads: 100 m north, east, south, west of each, plus 1 control read at a known zone AE pin): all 20 returned an empty answer (no request failed), and the control returned zone AE as stored, so the service was answering normally. The five are not pin-edge gaps; there is no mapped polygon within 100 m in any direction. Not known: whether NFHL leaves areas with no identified flood hazard unpolygoned (so "no polygon" could mean minimal hazard) or whether these areas are not digitized. That is a hypothesis I have not checked. West Sacramento is levee-protected, where "minimal" would be wrong. Scoring was not changed by the re-read; the five stay no data pending your decision.

Re-read at 1 km (2026-11-03, 20 more FEMA point reads, north, east, south, west of each pin): Chatham NJ, Morristown NJ and West Sacramento CA are empty in all four directions at 1 km, so the gap is larger than a pin edge (a block of the county with no polygon). Southport CT and Belvedere CA are mixed: Southport has zone VE to the north, minimal hazard to the west, empty east and south; Belvedere has minimal hazard north and west, zone VE south, empty east. Those two sit at a patchy coastal edge, where the empty cells are likely water or unpolygoned shore (not checked). Scoring unchanged; the five stay no data. Recommendation: keep no data, since neither class supports "minimal" and the nearby coastal polygons include high-hazard VE.

Flood disk pilot (2026-11-03, `scripts/catalog/climate_flood_disk_pilot.py`, output `analysis/climate_flood_disk_pilot_2026-11-03/`): the flood component scored as the average flood points over an 800 m disk around the pin (area-weighted by zone, mapped part only) instead of the single pin. One FEMA polygon query per place (60 places, 1,800 m radius, saved), then everything computed locally, including the eight shifted centres of the pin-shift test (shifted heat reads reused, air and trend as stored). A few extra requests were made because the service returned transient 500 errors on one place (Weddington NC); I retried and lowered the page size and generalized vertices by about 2 m for the last 43 queries. The first 17 were fetched without generalization.
  500 m shift: median change 1.0, 95th percentile 5.4, 0.4% of shifts over 10 (pin measure: 0.8, 24.2, 10.9%). PASSES the fixed criteria (median 2 or less, 95th percentile 10 or less).
  1,000 m shift: median 1.8, 95th percentile 9.7, 3.4% over 10 (pin measure: 1.6, 22.5, 12.2%). Urban core 95th percentile 11.2 at 1,000 m, the only group over 10.
  At the pin, the disk score differs from the stored pin score by a median 0.5 and a 95th percentile 11.2; 14 of the 60 places differ by more than 5. No place lost its flood component and every disk was fully covered by mapped polygons (the sample holds no unmapped place, so the five unmapped places are untested).
  The 800 m radius is a borrowed convention (not a flood-specific source). Radius sensitivity from the saved polygons, flood points at the pin: 400 m against 800 m differs by a median 0.3 and a 95th percentile 3.8 points (3 of 60 places over 5); 1,200 m against 800 m differs by a median 0.3 and a 95th percentile 2.8 (none over 5). Plausible range for the radius: unknown, tested 400 to 1,200.
  Not yet shown: the result on the full catalog (the 60 places are a sample), independent validation of the flood measure, and the pin-shift of PM2.5 and trend. Nothing in scoring or the catalog has been changed by the pilot.

## Level 2 status (2026-11-03): NOT reached

Done: catalog on the 800 m disk flood measure (pushed, a0495673 on main); live lookup has the disk measure behind HOMEFIT_FLOOD_DISK (default off, latency on Railway not measured); brief written with criteria fixed first (docs/CLIMATE_RISK_LEVEL2_BRIEF.md); offline checks and the air check run by independent agents, full tables in analysis/climate_level2_results_2026-11-03.md.

Passed: V2 score range, scaled-sum rule and no-data list; V4 Phoenix vs Seattle and Las Vegas vs Boston; V5 overlap (0.20 and 0.28 across places); V1b air against EPA monitors (n 1,304, Spearman 0.85, median difference 0.56 ug/m3; independent in processing, not wholly in data; 172 places have no monitor in range).

Failed or open:
- V2 component caps: 457 places (31%) at a cap, against a 5% limit. Owner decision 2026-11-03: the rule does not apply to a place with no flood hazard (full flood points are correct there). Heat and air caps stay counted. The criterion was not edited by the checker; this is the owner's recorded exemption, and the rerun against the exempted rule is not done.
- V4 Galveston vs Katy: 60.2 vs 61.6, should differ by 8 or more. Flood separates them (4.5 vs 21.9); Galveston's heat reading (29.5 C) cancels it. The reading was not checked. Open limit.
- Correction: the spec sheet's "5 places with no mapped polygon" is now 3 no-data places under the disk measure; Southport CT and Belvedere CA get flood points from the disk (Southport's rest on 10% of the disk).

FAILED, V1c flood against FEMA National Risk Index county data (independent agent, read from the public NRI county service, one query of 3,232 county rows, saved in analysis/climate_level2_nri_2026-11-03/): n 1,459 places in 127 counties. Against the county expected-annual-loss score, Spearman +0.103 (county-level -0.054; criterion absolute value at least 0.40, expected sign negative). Re-test added after that fail, against the county flood-exposed share from the NRI exposure-area fields: +0.104 (county-level +0.033), also a fail; the exposure-area definition is unconfirmed (field alias only, FEMA documentation not read), so even a pass could not have counted as clean. Limits: county-level data is coarse for a local measure, and the loss score is a national percentile of dollars that puts most large metro counties in the 90s. The county-level result is flat too, so this is not shown to be only an artifact. 13 Fairfield County CT places are unchecked (NRI lists Connecticut by planning region). Flood has no independent support.

FAILED, V1a heat against PRISM 1991-2020 June to August mean daily maximum temperature (independent agent, 800 m grid, files in analysis/climate_level2_prism_2026-11-03/, read offline in a throwaway Python environment): n 1,467 places (9 Florida places have no heat reading). Pooled Spearman -0.433 (needs absolute value at least 0.60), within-metro -0.206 (needs at least 0.30); 465 places (31.7%) differ by more than 30 percentile points, mostly LA, SF, Atlanta, San Antonio and Tampa. The ten largest disagreements are all San Antonio metro, with the best possible heat points and some of the hottest PRISM values in the catalog. Builder follow-up, offline, stored values only: the stored satellite temperature (local_lst_c) has a San Antonio median of 36.3 C against 43.4 C for both Austin and Houston, while PRISM puts San Antonio about as hot as those two; 14 San Antonio places score 24.5 or more heat points. Cause not found and not verified (a bad scene or cloud contamination are untested guesses); finding it needs Earth Engine re-reads, which the owner ruled out on 2026-11-03. Landsat surface temperature (2022) against 30-year air temperature is a different quantity and period, so the bar is moderate, and the check cannot say which side is wrong; within-metro agreement is good in SF (-0.72), Philadelphia (-0.67), Denver (-0.65) and LA (-0.64) and has the wrong sign in NYC, Austin and San Antonio.

Change after V1a (owner approved 2026-11-03): heat plausibility screen (data_sources/heat_screen.py). A land-surface temperature more than 10 C below the normal June to August air temperature is a bad reading, so heat is no data and the score rescales over the other components. The 10 C margin is a judgment and its sensitivity is not tested (nearest place that passes, Olmos Park TX, is 9.8 C below). Catalog: 6 places screened out (Alamo Heights, La Vernia, Terrell Hills, Von Ormy TX; Clermont FL; New Port Richey FL), climate score down 5.0 to 7.4, total down 0.4 to 0.6; no other place changed (checked against the previous files). Live pillar: same function, reference is the TerraClimate 4 km June to August normal (new function get_jja_tmax_normal_terraclimate), not PRISM 800 m, so a place near the margin can differ between catalog and live. The live reference read is covered by mocked tests only; it has not been run against Earth Engine. The check against PRISM that found the problem is not independent of this fix, so a rerun of V1a after it would be a check of the fix, not a fresh test.

PASSED, V1a-b heat against MODIS land surface temperature (independent agent, run after the PRISM fail; criteria fixed before the run in the brief, but the check was chosen because the PRISM comparison used a mismatched quantity, so it is a second attempt and not a first test). Source: MODIS MOD11A2 and MYD11A2 LST_Day_1km, June to August 2022, free from Microsoft Planetary Computer, 260 files (10 tiles x 13 composites x 2 satellites) in analysis/climate_level2_modis_2026-11-03/. n 1,454 places. Pooled Spearman 0.761 (needs 0.70), within-metro 0.567 (needs 0.50); heat points against MODIS: -0.770 pooled, -0.574 within-metro. Without the 6 screened places: 0.770 and 0.569. 1,430 places read at the pin pixel, 33 by nearest valid pixel within 2 km; 13 Manhattan places are unchecked (no valid composite within 2 km). Limits: MODIS is 1 km against Landsat 500 m, and Terra (about 10:30) and Aqua (about 13:30) overpass at different times from Landsat, with different cloud screening. A pass shows the Landsat readings rank places soundly; it does not show the 30 to 60 C scale is right. Weak within-metro agreement remains in Atlanta (0.07), San Antonio (-0.06) and Miami (0.19), and Austin, Dallas and Phoenix are 0.35 to 0.38; LA and SF are about 0.9. Leftover bad readings: 33 places read more than 10 C below MODIS (13 read above); 14 of the 15 largest gaps are Landsat too cool, 9 in San Antonio, 5 already screened. The others (for example Kirby, Elmendorf, Olmos Park, Dignowity Hill and Selma TX) still get full 25.0 heat points, so the 10 C air-temperature margin is too loose to catch them. Not investigated at scene level, and the margin has not been changed. Heat now has one independent pass (MODIS) and one fail (PRISM, mismatched quantity).

Not run: V3 disk pin-shift rerun (needs Earth Engine heat reads). Owner decision 2026-11-03: no Google spending, so the pin-shift rerun is not run. The pilot pin-shift on 60 places (disk measure passes) is the builder's, not independent; it shows the measure is steady, not that it is right.

Proposed level: below Level 2. Level 1 plus the independent air check and the MODIS heat check. Flood is unvalidated (two independent fails), heat passes MODIS but has leftover bad cool readings in San Antonio that the screen misses, and the pin-shift rerun is not run. Level 2 needs a flood result that passes (or a better outside source, for example county share of land in the special flood hazard area, not tried), and V3 or an owner waiver.

### Level 2 second pass, offline part (2026-11-08)

Criteria fixed first and results in `docs/CLIMATE_RISK_LEVEL2_PASS2_CRITERIA.md`. Cap rule as exempted by the owner: FAIL (99 places, 6.71%, limit 5%; heat at cap 87 places, all at LST 30 C or lower). Galveston heat vs MODIS: FAIL (Landsat 7.8 C below MODIS, outside the 5th to 95th percentile band). San Antonio: 13 leftover cool readings listed, 29 catalog wide. Heat pin-shift on MODIS: passes (500 m median 0.21, p95 1.32; 1,000 m median 0.49), understates by about 3x against the builder's Landsat reads. Flood against NFIP claims (tract, 2010 to 2025): FAIL on all four parts (pooled Spearman +0.062, needs -0.40 or stronger; wrong sign). Third independent flood fail. Proposed level: Level 1 stands.

### Level 1 accepted by the owner (2026-11-05)

Climate risk stays at Level 1 (Converted). Accepted gaps: flood is unvalidated (two independent checks failed, V1c and V1c-b);
heat passes the MODIS check but San Antonio has leftover bad cool readings the plausibility screen misses; the disk pin-shift
rerun was not run (owner decision 2026-11-03, no Google spending), and the pilot pin-shift on 60 places is the builder's own;
the air zero point (35 ug/m3) and hazard weights are unsourced. Level 2 would need a flood result that passes or a better
outside source (for example county share of land in the special flood hazard area, not tried), plus V3 or an owner waiver.

### Level 1 stands, signed off by the owner (2026-11-08)

Level 2 second pass (`docs/CLIMATE_RISK_LEVEL2_PASS2_CRITERIA.md`) did not reach Level 2. Climate risk stays at Level 1 (Converted). Accepted gaps: flood unvalidated (V1c, V1c-b and the NFIP claims check F1 all failed); cap rule fails on the owner's exempted rule (99 places, 6.71%; the heat-exempt variant, 13 places, was not adopted); Galveston heat reads 7.8 C below MODIS; 29 leftover cool Landsat readings catalog wide (13 in San Antonio); the heat pin-shift passes on MODIS and on the builder's Landsat reads, which are not independent and not a new sample; air zero point and hazard weights remain unsourced.
