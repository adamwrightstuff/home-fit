# Climate risk Level 2, second pass: criteria fixed before any result is read

Written 2026-11-08 on branch `climate-l2` (off origin/main 5f1ff51b). Nothing below has been run. No scoring change is proposed or made.

Disclosure: results from 2026-11-03 are already known to the author (heat at cap 93 places = 6.3%, air 7, trend 0; Galveston LST 29.5 C and score 60.2; MODIS pooled Spearman 0.761). Checks C1, S1 and H1 are therefore not blind. F1 and P1 are blind, because no NFIP value and no shifted MODIS value has been read. All thresholds are judgments, not sourced, except where a source is named.

## Flood source (needs an owner yes before any download)

| Source | Measures | Resolution | Coverage of our places | Size | Licence | Independent of our flood score |
|---|---|---|---|---|---|---|
| OpenFEMA NFIP redacted claims plus policies (v3; v2 is deprecated and frozen 2026-06-01) | Realized flood insurance claims and insured units, with a census tract field | Tract (location also rounded to 0.1 degree, so use the tract field only) | Any tract with policies; places with few policies are unchecked | v2 claims 2.72 M rows, Parquet 50 to 500 MB; v2 policies 73.6 M rows, 500 MB to 10 GB. v3 sizes not verified (page returned 503) | No licence named; OpenFEMA terms apply | Partly. Outcome, not map. But policies cluster in mapped zones because of the mandatory purchase rule |
| FEMA NFHL state geodatabases | The same flood zone polygons our score reads | Polygon | All | Multi-GB per region | Public | No. It would only test our code, not our measure |
| FEMA NRI tract table | Inland flood expected loss and exposure area per tract | Tract | All tracts | Not verified | Public | Unknown. The exposure area definition is unconfirmed |
| First Street flood model (via Headwaters Economics tract tool or First Street raw data) | Modeled share of properties at 100-year flood risk, includes unmapped flooding | Tract / property | All | Not verified | Raw data on AWS is noncommercial and needs an account, tool terms unverified | Yes in method, but licence blocks bulk use |

Can a county source validate place-level scores? No. Our 1,476 places fall in about 127 counties, so a county value takes 127 distinct values and cannot rank places inside a county, which is where most flood spread is. It can only test direction between counties. Both county checks (V1c, V1c-b) already failed and cannot say which side is wrong.

Recommendation: NFIP claims and policies at tract level, filtered to the 18 scored states. It is the only free source that is place scale and built from outcomes. Join each place to its tract through the free Census geocoder (1,476 calls, already used by the pipeline) or offline from stored tract fields if the catalog has them (it does not store a tract id today).

## Criteria

### C1 Component caps, rerun on the owner's exempted rule (offline, stored files)
Rule (owner, 2026-11-03): a flood component at its cap is not counted when the place has no flood hazard, defined here as `flood_zone_shares` having 100% minimal (no floodway, SFHA, shaded X or D share) and mapped fraction 1.0. Heat, air and trend caps are counted.
Pass: no more than 5% of places (73 of 1,476) have any counted component at cap.
Owner decision needed before the run: the same "no hazard" logic could exempt heat at cap where LST is 30 C or lower. I will run the rule as the owner stated it and report the heat-exempt variant beside it, labeled as a variant. The pass or fail is decided by the stated rule only.

### H1 Galveston heat reading (offline, MODIS files on disk)
Read the MODIS JJA mean (Terra and Aqua, same method as V1a-b) at the Galveston pin and at its 8 neighbouring pixels, and report the MODIS water or land character of the pin pixel from the files.
Pass: stored Landsat `local_lst_c` minus MODIS lies between the 5th and 95th percentile of that difference over all 1,454 places checked on 2026-11-03.
Fail means the Galveston heat reading is recorded as unreliable. Scoring is not changed by this check. The V4 Galveston vs Katy result stays a recorded fail unless a separate approved change moves the gap to 8 or more.

### S1 San Antonio leftover cool readings (offline)
List every San Antonio metro place with Landsat minus MODIS below -10 C and heat points above 0 (not screened). For each, give Landsat, MODIS, the stored TerraClimate JJA air normal, and heat points.
A place counts as explained by MODIS when MODIS is at or above the air normal while Landsat is more than 10 C below MODIS (the Landsat reading is the outlier). Report-only, no pass threshold. Any screen change (for example Landsat more than 10 C below MODIS) is proposed separately and needs approval; MODIS covers only the places in its tiles, so a live screen could not use it.

### F1 Flood against NFIP claims (blind, needs download approval)
Outside value (fixed now): claims per policy-year at the tract of each place, over 2010 to the latest full year, using tracts with at least 100 policy-years. Places in tracts below that are unchecked and listed. Exact field names to be confirmed from the v3 data dictionary before download, and any change to the definition is written here before reading a value.
Pass, all required:
1. Absolute Spearman of flood points vs claims rate at least 0.40, sign negative, n at least 500 places.
2. Within-metro (metro mean removed) absolute Spearman at least 0.25, sign negative.
3. Median claims rate of the lowest-flood-points decile at least 5 times the median of the highest decile.
4. Rerun 1 without the single largest loss year: absolute Spearman still at least 0.30.
Limit: policies concentrate in mapped zones, so agreement is partly expected by construction; a pass shows direction and rough scale, not that the point values are right. Places with no policies (likely no hazard) are untested.

F1 definitions confirmed and written 2026-11-08 before any NFIP value was read (v3 field names read from a one-row API sample): the tract field is `censusGeoid`, a 12-digit block group id, so tract = first 11 digits. Files: `NfipClaimsV3.parquet` (164 MB) and `NfipPoliciesV3.parquet` from the OpenFEMA bulk links, both refreshed 2026-09-09. Years 2010 to 2025. Claims = every claim row by `yearOfLoss` (paid-only is a sensitivity, not the decision). Policy-years = sum of `policyCount` by `policyEffectiveDate` year, times 3 where `policyTermIndicator` is 3. Places are joined to a tract by the Census geocoder at the stored coordinates, for both the 2020 and 2010 tract vintages; the vintage with more places found in the policy file is used for all places (the NFIP vintage is not documented in what I read). "Largest loss year" is the year with most claims in the places' tracts, dropped from both claims and policy-years in part 4. Deciles use 10th and 90th percentile of flood points with ties included. If the highest-points decile has a median claim rate of 0, the ratio in part 3 counts as met when the lowest-points decile median is above 0.

### P1 Heat pin-shift from MODIS (blind, offline)
Possible, with limits. MODIS pixels are 1 km; a 500 m shift reaches a new pixel only about half the time, and the stored heat reading is a 500 m Landsat buffer, so this understates 500 m sensitivity and cannot test the Landsat read itself. It is an independent lower bound for the heat part.
Test: the 60 places in `analysis/climate_pin_shift_2026-11-03/sample.json`, shifts north, east, south, west at 500 m and 1,000 m. Sample the MODIS JJA mean at each shifted point. Heat points at the shifted point = stored scoring formula applied to (Landsat at pin + (MODIS shifted minus MODIS at pin)). Other components held at stored values. Report the change in the climate pillar score.
Pass: median at most 2 at 500 m and at most 5 at 1,000 m; 95th percentile at most 10 at 500 m. Same limits as V3. Manhattan places are excluded (no valid MODIS).
What this does not cover: the flood disk shift (builder's pilot only), PM2.5 and trend shift, and any new random sample. The builder's 480 Landsat shifted reads already exist in `reads.jsonl` for the same 60 places. Owner options: accept P1 plus the builder's reads as the V3 evidence with the non-independence recorded, or waive V3 in writing.

## Level proposal rule (fixed now)
Level 2 may be proposed only if C1 passes (or the owner accepts the variant in writing), H1 or S1 findings are recorded with the open limit stated, F1 passes all four parts, and P1 passes or V3 is waived in writing. If F1 fails or is not run, the proposal is that Level 1 stands with the failure recorded.

## Results (2026-11-08, offline, owner approved the criteria above before the run)

Inputs: the 21 `data/*composites_recomputed.jsonl` files on origin/main (1,476 places) and the 260 MODIS files from `analysis/climate_level2_modis_2026-11-03/` (read from the archived worktree, unchanged). Method for MODIS is the V1a-b method (Terra and Aqua mean of valid composites, pin pixel, nearest valid pixel within 2 km). Script: scratchpad `pass2.py`, no network call. Python ran with -I.

| Check | Result | Verdict | n |
|---|---|---|---|
| C1 caps, owner's rule | 99 places (6.71%) have a counted component at cap; limit 73. Flood at cap 376, of which 369 have no flood hazard (exempt) and 7 are counted. Heat at cap 87, air 7, trend 0 | FAIL | 1,476 |
| C1 variant (heat also exempt when LST 30 C or lower) | 13 places (0.88%). All 87 heat-at-cap places have LST 30 C or lower | Variant would pass; not the decision rule | 1,476 |
| H1 Galveston | Landsat 29.48 C, MODIS 37.31 C, difference -7.83 C. Allowed range -6.05 to +7.67 (5th to 95th percentile of the 1,454 differences, median +3.06). Stored air normal 31.21 C | FAIL (Landsat reads cool) | 1 |
| S1 San Antonio leftovers | 13 places, Landsat 10.0 to 17.8 C below MODIS, heat points 21.6 to 25.0. All 13 have MODIS at or above the air normal | Report only | 13 |
| P1 heat pin-shift on MODIS, 500 m | median 0.21, 95th percentile 1.32, none over 10 | PASS (limit 2 / 10) | 231 shifts |
| P1, 1,000 m | median 0.49, 95th percentile 1.59 | PASS (limit 5) | 231 shifts |

Notes and limits:
- C1: heat at cap was 93 on 2026-11-03 and is 87 now. I did not check why (the 6 places the heat screen later removed would account for it, not verified). Flood-counted 7 places have a tiny non-minimal share in the disk. The "no hazard" test used non-minimal share 0.001 or less and mapped fraction 0.999 or more, which is my reading of "100% minimal" given four-decimal rounding.
- H1: the failure is modest (1.8 C outside the band) and the check does not say which side is wrong. MODIS 1 km pixels around Galveston include several with no valid composite (water or cloud, not verified), so the MODIS value may itself be mixed. Landsat 29.48 C is 1.7 C below the stored air normal, which is a surface temperature reading below air temperature in summer. Scoring unchanged; V4 Galveston vs Katy stays a recorded fail.
- S1: "explained" is a weak test, since surface temperature at or above air temperature is expected almost everywhere, so all 13 pass it. What the list does show is 13 San Antonio places 10 to 18 C cooler than MODIS and cooler than the air normal, and they hold 22 to 25 heat points. Catalog wide, 29 places with heat points are more than 10 C below MODIS: San Antonio 13, Tampa 4, Atlanta 3, NYC 3, Denver 2, Miami 2, Charlotte 1, Las Vegas 1. A screen of "Landsat more than 10 C below MODIS" would catch these 29 but needs MODIS for live requests, which is not available; a live-compatible rule is not proposed here.
- P1: MODIS is 1 km, so it understates shift sensitivity, as predicted. Calibration run after the fact (not a criterion): the builder's own Landsat shifted reads for the same 60 places, heat part only with other components at stored values, give median 0.73 and 95th percentile 2.63 at 500 m, and median 1.35 and 95th percentile 5.1 at 1,000 m (n 236 and 234). The Landsat 500 m figure is about 3 times the MODIS figure. The 1,000 m criterion covers the median only, and the Landsat median (1.35) is under 5; the Landsat 500 m 95th percentile (2.63) is under 10. Same 60-place sample as the builder's, not a new random sample. 8 shifts were excluded for Manhattan and Land O' Lakes (no MODIS or no heat). Flood disk, PM2.5 and trend shift are not covered here.
- Not run: F1 (flood against NFIP claims). It needs the download approval and the confirmed v3 field names.

Level rule applied: C1 fails on the stated rule, F1 not run. Proposed level: Level 1 stands, with these recorded: C1 fail (variant passes, owner to decide), H1 fail at Galveston, 13 San Antonio and 29 catalog-wide leftover cool readings, flood still unvalidated, heat pin-shift passes on MODIS and on the builder's Landsat reads (not independent, not a new sample).

## F1 result (2026-11-08): FAIL on all four parts

Data: OpenFEMA NFIP v3 claims (2,725,989 rows) and policies (74,739,461 rows), both refreshed 2026-09-09, bulk Parquet from the OpenFEMA links, 164 MB and 3.7 GB, in `/Users/adamwright/Dev/nfip_dl_2026-11-08/raw/` (outside the repo). Places joined to tracts by the Census geocoder (1,476 places, both vintages). The 2010 vintage matched more places in the policy file (1,453 against 1,430 for 2020), so it was used for all places, per the rule above. Policy-year weights: 74.65 M rows have term indicator 1, 69 k have 3, 19 k have 2, a few others (weight 1). Scripts in the scratchpad (`f1.py`, `tracts.py`), no scoring code touched.

| Part | Criterion | Result | Verdict |
|---|---|---|---|
| 1 pooled Spearman, flood points vs claims per policy-year | absolute 0.40 or more, negative, n 500 or more | +0.062 (wrong sign), n 995 | FAIL |
| 2 within-metro Spearman | absolute 0.25 or more, negative | -0.049 | FAIL |
| 3 median rate, lowest-points decile over highest-points decile | 5 or more | 0.00327 / 0.00835 = 0.39 (n 100 and 138) | FAIL |
| 4 pooled Spearman without the largest loss year (2017) | absolute 0.30 or more | +0.077, n 979 | FAIL |

481 of 1,476 places are unchecked (tract under 100 policy-years); half of them have full flood points, so the places with no hazard are mostly untested, as stated in the criteria.

Post hoc, not criteria, and not used for the verdict: raising the policy-year minimum to 500, 1,000 and 3,000 gives +0.143, +0.150 and +0.177 (n 513, 354, 191), still the wrong sign. Median claim rate by flood-points band: 0 to 5 points 0.0074 (n 16), 5 to 15 0.0021 (50), 15 to 25 0.0045 (256), 25 to 30 0.0069 (529), full 30 points 0.0083 (144). Galveston tract 78 claims on 14,793 policy-years (0.53%), Katy tract 118 on 33,741 (0.35%), Meyerland 1,000 on 13,312 (7.5%). Places with the highest claim rates but 18 to 29 flood points include Conshohocken, Ambler, Elkins Park, Norristown (PA), Bronxville and Rye (NY): creek and urban flooding near, but mostly outside, the mapped zones in a 800 m disk.

How to read it: the score does not agree with realized claims at tract level, in any variant I ran. What the check cannot say: the window is 2010 to 2025, so Ike (2008) and Katrina (2005) are out, and a few events (2012, 2017, 2024) carry most claims; a tract is much larger than the 800 m disk; claim counts per tract are small (about 28,000 claims over 995 tracts), so rates are noisy; claims need insurance, which follows the mapped zones, so an unmapped hazard is under-counted as well. Not shown: which side is wrong. Flood now has three independent failures (V1c, V1c-b, F1) and no pass.

Proposed level: **Level 1 stands.** Recorded gaps: flood unvalidated with three failed outside checks; cap rule fail (variant passes, owner to decide); Galveston heat fail; 29 leftover cool heat readings; heat pin-shift passes on MODIS and the builder's Landsat reads (not independent, not a new sample).
