# Climate risk Level 2: offline checks (V2, V4, V5, V6), 2026-11-03

Checker did not build the pillar. Criteria are those in docs/CLIMATE_RISK_LEVEL2_BRIEF.md, unchanged. Stored files only: no API, GEE, FEMA, Overpass or download calls. V1a, V1b, V1c and V3 were not run (they need owner approval, see the last section).

Files read: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (21 files, 1,476 places, all with a climate_risk object and a score). The `climate_risk` objects in these files are identical, place by place, to `analysis/climate_dpv2_disk_2026-11-03/` (the brief's named file under test); 6 of the 21 files differ byte-wise (chicago, la, las_vegas, nyc, sacramento, sf) but only outside climate_risk. Comparison for V6: `analysis/climate_dpv2_2026-11-03/` (same 1,476 places). Scripts: scratchpad only (load.py, v2.py, v456.py, extra.py).

## Results

| Check | Result | Pass or fail | n |
|---|---|---|---|
| V2 score at or below 5 or at or above 95 | 0 places (min 43.6 Meyerland TX, max 91.6 Lake Forest IL) | PASS | 1,476 |
| V2 any one component at its cap | 457 places (31.0%) have at least one component at cap. By component: flood 376 (25.5%), heat 93 (6.3%), air 7 (0.5%), trend 0 | FAIL (limit 5%), on either reading: any component, or flood and heat each singly | 1,476 |
| V2 stored score equals scaled sum of present components within 0.15 | 0 mismatches (scaled = sum of present points / sum of present maxima x 100) | PASS | 1,476 |
| V2 fewer than 3 components present means no score | 0 places with fewer than 3 present; none scored wrongly; all 1,476 have a score | PASS (rule never triggered, so untested in practice) | 1,476 |
| V2 no-mapped-polygon and zone-D-only places have flood as no data and are listed | 4 places have flood as no data: Chatham NJ, Morristown NJ, West Sacramento CA (mapped fraction 0), Rose Garden (San Jose) CA (zone D only, share 1.0). Their scores are present on the other three components. | PASS for the 4. Brief says 5 unmapped places; only 3 are now no data (see notes) | 4 |
| V4 Phoenix vs Seattle (Downtown Phoenix vs Ballard) | 60.4 vs 86.8, gap 26.4 (need 8 or more) | PASS | 1 pair |
| V4 Las Vegas vs Boston (Downtown Las Vegas vs Downtown Boston) | 67.5 vs 80.0, gap 12.5 (need 8 or more) | PASS | 1 pair |
| V4 Gulf coast floodplain vs inland, same metro (Galveston vs Katy, Houston metro) | 60.2 vs 61.6, gap 1.4 (need 8 or more) | FAIL | 1 pair |
| V4 adjacent places within 3 points (Willo vs Encanto, Phoenix) | 61.8 vs 60.9, gap 0.9 | PASS, with proxy caveat (see notes) | 1 pair |
| V5 natural_beauty, all places | Spearman 0.200 (limit absolute value below 0.6) | PASS | 1,475 |
| V5 natural_beauty, within metro (metro mean removed) | Spearman 0.242 | PASS | 1,475 |
| V5 active_outdoors, all places | Spearman 0.278 | PASS | 1,476 |
| V5 active_outdoors, within metro (metro mean removed) | Spearman 0.037 | PASS | 1,476 |
| V6 disk vs pin, 20 largest movers | Report only, table below. All 20 rose by 22.2 to 28.1 points | no threshold | 1,476 |

## V4 pairs, written down before any climate score was read

Chosen from catalog names and coordinates only. Seattle metro holds 5 places and none named Seattle, so Ballard is the Seattle city side; Phoenix, Las Vegas and Boston use their "Downtown" places. For the Gulf pair I chose Galveston (barrier island, Gulf coast) against Katy (inland, same Houston metro) before reading either score. For the adjacent pair, the catalog has no tract-level places, so I used the two nearest neighbourhood centres in one metro (Willo and Encanto, about 0.9 km apart). That is a proxy for "two adjacent tracts of one neighbourhood", and it is a weak test because it only shows the score is smooth, not that it separates anything. No pair was swapped after seeing results.

Pair detail (points: heat / air / flood / trend):
- Downtown Phoenix 8.0 / 17.4 / 24.9 / 10.1, LST 50.4 C. Ballard 18.6 / 18.3 / 30.0 / 19.9, LST 37.7 C.
- Downtown Las Vegas 4.7 / 18.6 / 30.0 / 14.3, LST 54.4 C. Downtown Boston 24.2 / 18.9 / 23.0 / 13.9, LST 30.9 C, 26.8% of the disk in the special flood hazard area.
- Galveston 25.0 / 18.1 / 4.5 / 12.7, LST 29.5 C, 99.97% of the disk in the special flood hazard area. Katy 12.2 / 17.1 / 21.9 / 10.4, LST 45.3 C.

Why the Galveston pair fails: flood points correctly separate the two (4.5 vs 21.9, a 17.4 point gap), but Galveston's heat reading is full marks (25.0, LST 29.5 C), which offsets almost all of it. Whether the Galveston LST is a water-pixel artefact is not verified here; land_pixel_fraction and the LST guard would need a look by the builder. Galveston is one of the 93 places at the heat cap (LST in the capped group ranges 16.5 to 29.9 C).

## V6: 20 largest movers, pin (option B) to 800 m disk

Whole catalog: 1,060 places changed flood points and nothing else changed (heat, air, trend identical). Final score moved by more than 0.05 for 1,030 places (132 up, 898 down); mean absolute change 2.71, median 0.9, 95th percentile 12.3, maximum 28.1. The 20 largest are all increases. In every case the single pin sat on a special flood hazard area polygon (zone A or AE) while the 800 m disk is mostly minimal-hazard, so flood points jump from 0 or 4.5 to 22 to 29. Shares are of the 800 m disk; "minimal" is zone X unshaded.

| Metro | Place | Pin score | Disk score | Change | Flood pts pin to disk | Pin zone | Disk shares |
|---|---|---|---|---|---|---|---|
| san_antonio | Lytle | 38.9 | 67.0 | +28.1 | 0 to 28.2 | AE | floodway 1.9%, sfha 4.6%, x_500yr 1.7%, minimal 91.8% |
| denver | Morrison | 51.9 | 79.2 | +27.3 | 0 to 27.3 | AE | floodway 4.6%, sfha 4.7%, x_500yr 2.5%, minimal 88.2% |
| sf | Fairfax | 50.0 | 77.3 | +27.3 | 0 to 27.2 | AE | floodway 2.6%, sfha 7.3%, x_500yr 2.7%, minimal 87.4% |
| chicago | Aurora | 52.0 | 78.5 | +26.5 | 0 to 26.5 | AE | floodway 10.7%, sfha 0.8%, x_500yr 1.8%, minimal 86.7% |
| denver | RiNo | 40.3 | 66.5 | +26.2 | 0 to 26.2 | AE | floodway 5.4%, x_500yr 43.7%, minimal 50.9% |
| raleigh | Brier Creek | 51.0 | 77.0 | +26.0 | 0 to 26.0 | AE | floodway 6.8%, sfha 7.8%, minimal 85.5% |
| atlanta | Snellville | 58.1 | 82.6 | +24.5 | 4.5 to 29.0 | A | sfha 4.0%, minimal 96.0% |
| sf | Ross | 52.8 | 77.1 | +24.3 | 0 to 24.3 | AE | floodway 6.7%, sfha 12.8%, x_500yr 9.0%, minimal 71.4% |
| austin | Bouldin Creek | 43.0 | 67.0 | +24.0 | 4.5 to 28.5 | AE | sfha 5.4%, x_500yr 1.7%, minimal 92.9% |
| charlotte | Statesville | 58.8 | 82.7 | +23.9 | 4.5 to 28.5 | AE | floodway 2.8%, sfha 2.5%, x_500yr 1.4%, minimal 93.3% |
| austin | Wells Branch | 44.6 | 68.5 | +23.9 | 4.5 to 28.4 | AE | sfha 5.8%, x_500yr 2.0%, minimal 92.2% |
| nyc | South Orange | 60.7 | 84.5 | +23.8 | 4.5 to 28.4 | AE | floodway 2.7%, sfha 3.2%, minimal 94.1% |
| nyc | Maplewood | 59.9 | 83.6 | +23.7 | 4.5 to 28.2 | AE | floodway 3.0%, sfha 3.2%, x_500yr 1.0%, minimal 92.7% |
| sf | Portola Valley | 54.6 | 78.3 | +23.7 | 4.5 to 28.3 | AE | sfha 6.1%, x_500yr 3.7%, minimal 90.2% |
| austin | Sunset Valley | 41.0 | 64.6 | +23.6 | 0 to 23.6 | AE | floodway 11.7%, sfha 9.9%, x_500yr 6.5%, minimal 71.8% |
| atlanta | Dallas | 59.5 | 82.6 | +23.1 | 4.5 to 27.7 | AE | floodway 3.9%, sfha 4.4%, x_500yr 1.5%, minimal 90.2% |
| boston | Lexington | 56.8 | 79.8 | +23.0 | 4.5 to 27.5 | A | sfha 9.9%, minimal 90.1% |
| nyc | Roslyn | 56.1 | 79.1 | +23.0 | 4.5 to 27.5 | A | sfha 9.4%, x_500yr 2.4%, minimal 88.2% |
| austin | Dripping Springs | 44.6 | 67.4 | +22.8 | 4.5 to 27.3 | AE | sfha 10.5%, x_500yr 1.3%, minimal 88.2% |
| nyc | SoHo | 55.2 | 77.4 | +22.2 | 4.5 to 26.7 | AE | sfha 11.6%, x_500yr 7.0%, minimal 69.7% |

Read: each mover is a place whose pin was on a creek or river polygon but whose 800 m neighbourhood is 70 to 96 percent minimal hazard. The disk gives a more representative flood score for these, but note two facts: a place with 5 to 11 percent floodway or special flood hazard area in its disk now gets about 85 to 98 percent of flood points, so the disk average is insensitive to a narrow channel through the middle of a town (a design property of the area-weighted mean, not an error). Whether those places "should" score near full flood points is a judgment this check cannot settle.

The largest decreases (not top-20 by magnitude, but listed for balance): Belle Isle FL -20.5, Venice (LA) -18.3, Tarpon Springs FL -18.1, Victoria Park FL -17.3, Land O' Lakes FL -16.2.

## Failed or unchecked places

- Failed V2 cap criterion: 457 places (the flood-at-cap group of 376 are the zone X minimal places that get all 30 flood points; the heat-at-cap group of 93 sit at a heat cap near LST 30 C or lower; air at cap 7). This is a ceiling effect by design (best case equals full marks), so the 5 percent limit may be the wrong shape for flood; I am not changing it, but I propose the owner decide whether the criterion should apply to "pinned at cap because the hazard is absent" components. Fail stands as written.
- Failed V4: Galveston vs Katy (1.4 points).
- Flood no data (4): Chatham NJ, Morristown NJ, West Sacramento CA, Rose Garden (San Jose) CA.
- Heat no data (9, score is scaled over the other three): Palm Beach FL, Clearwater Beach, Clearwater, Dunedin, Land O' Lakes, Oldsmar, Palm Harbor, Safety Harbor, Tarpon Springs (all Tampa metro except Palm Beach). Scoring on three components is within the rule, but two of them (Tarpon Springs -18.1, Land O' Lakes -16.2) are among the five largest pin-to-disk decreases, so the builder should check whether dropping heat is part of why they moved.
- Thin flood coverage but scored: Southport CT (mapped fraction 0.10, 8.4 flood points from a tenth of the disk), Belvedere CA (0.75), St. Pete Beach (0.70), Treasure Island (0.74), Marblehead MA (0.77). The brief and the spec sheet call Southport and Belvedere unmapped at the pin; the disk now gives them flood points, so the count of "no mapped polygon" no-data places is 3 now, not 5. Southport's flood points rest on 10 percent of its disk and should be treated as low confidence.
- 29 places have a zone D share in the disk (for example Porter Ranch CA 68%, Hidden Hills CA 30%). Zone D area inside a disk is treated as no information within the average; only Rose Garden is all D. I did not verify how the code weights the D share in the mapped fraction; mapped fraction for these is 1.0, so D appears to count as mapped.
- natural_beauty is missing for 1 place (V5 n = 1,475).

## What is not verified

- V1a, V1b, V1c: not run. No outside comparison of heat, air or flood exists yet; everything above is internal consistency and cross-pillar behaviour.
- V3: not run. The disk pin-shift for the live measure has not been re-tested on a new sample; the only pin-shift data is the builder's earlier single-pin run (analysis/climate_pin_shift_2026-11-03/summary.md: 95th percentile 22 to 24 points at 500 m and 1,000 m, which is a single-pin number, not the disk measure) and the 60-place disk pilot, neither rerun by me.
- V4 adjacent pair is a proxy (two neighbourhood centres 0.9 km apart), not two tracts.
- I did not check whether the Galveston LST (29.5 C) is a data artefact.
- I did not read any code. I inferred the scaled-sum rule and the component caps (25, 20, 30, 25) from the brief and confirmed the stored scores satisfy it for all 1,476 places; I did not confirm that the pillar code applies the same rule.
- Spearman computed by rank then Pearson (no scipy available); ties get average ranks. Within-metro uses metro mean removed, as the brief says, not per-metro Spearman; per-metro values range from -0.33 to 0.72 for natural_beauty (Denver 0.72, Sacramento 0.64, Charlotte 0.55) and -0.33 to 0.40 for active_outdoors. Denver natural_beauty at 0.72 is above 0.6 when taken metro by metro; the brief's criterion does not ask for per-metro values, so it is not a fail, but it is worth knowing.

## What V1a, V1b, V1c and V3 would need from the owner (not performed)

Sizes and vintages below are from my knowledge of the sources, not confirmed against the live pages (I made no web calls). Confirm on the source page before approving.

**V1a, heat vs summer maximum temperature.** Either source needs a download and then offline joins to the 1,476 place coordinates.
- Option 1: NOAA NCEI U.S. Climate Normals 1991-2020, monthly (product "normals-monthly", variable MLY-TMAX-NORMAL for June, July, August). Source: https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals. Per-station CSVs live under https://www.ncei.noaa.gov/data/normals-monthly/1991-2020/access/ (about 15 KB each, roughly 15,000 stations, so about 200 MB to 1 GB in total if fetched individually; a bulk archive of the same exists, size unconfirmed) plus the station inventory file in the same tree. Read count: 0 API calls; one bulk archive or inventory plus, if per-station, only the stations nearest each place (a few hundred distinct stations within 25 miles). The 25-mile rule means some rural places will have no station.
- Option 2: PRISM 800 m 1991-2020 normals, monthly tmax, files for months 06, 07, 08 (PRISM Climate Group, Oregon State, https://prism.oregonstate.edu/normals/; one zipped raster per month, expected tens of MB each, size unconfirmed). Read count: 3 downloads, 1,476 point samples offline, no live reads. This avoids the 25-mile station gap and is closer to the stored heat measure's resolution, so I would approve this one.

**V1b, air vs EPA monitor PM2.5.** EPA AirData pre-generated files: https://aqs.epa.gov/aqsweb/airdata/annual_conc_by_monitor_2021.zip and annual_conc_by_monitor_2022.zip (parameter code 88101, PM2.5 local conditions; each a few MB zipped, size unconfirmed) and https://aqs.epa.gov/aqsweb/airdata/aqs_monitors.zip (monitor coordinates, a few MB, unconfirmed). Vintages 2021 and 2022, matching the stored `pm25_years` [2021, 2022]. Read count: 3 downloads, 0 live calls; the join of 1,476 places to the nearest monitor within 15 miles is offline. Remember the independence caveat in the brief: the CDC/EPA tract surface was fused from these monitors.

**V1c, flood vs outside source (county level).** FEMA National Risk Index county table, CSV: https://hazards.fema.gov/nri/data-resources (file "NRI_Table_Counties", current release as of my knowledge is v1.20 of late 2025 or v1.19; vintage to be confirmed on the page; the zip is expected to be single-digit to low tens of MB, unconfirmed). Fields needed: RFLD_EALR (riverine flooding expected annual loss rating or its score RFLD_EALS), CFLD_EALR and CFLD_EALS (coastal flooding). Read count: 1 download, 0 live calls. The catalog stores county names and state abbreviations only, so the county join is by name and state (about 250 distinct counties, ambiguities to resolve by hand), or via a TIGER county file (Census cb_2022_us_county_500k, about 10 MB, an extra download) for point-in-polygon. The alternative named in the brief, county share of land in the special flood hazard area, would need the NFHL county-level S_FLD_HAZ_AR data (hundreds of MB to multiple GB nationally, per-county zips) and is much heavier; NRI is the lighter route.

**V3, pin shift for the disk measure.** New random sample of 60 places (12 per area type), 4 diagonal directions at 500 m and 1,000 m, so 8 shifted pins per place = 480 shifted pins. Reads: about 480 FEMA NFHL polygon queries (POST to https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query, one per shifted pin, up to 4 attempts each on failure, so up to roughly 1,900 worst case) and 480 GEE land surface temperature reads. Each shifted pin may also change the census tract used for PM2.5, which would need a tract lookup (Census geocoder, up to 480 calls) unless the builder's script holds tract fixed; I did not read the script, so I do not know which. The 60 unshifted baselines are the stored scores if the sample is drawn from the catalog. The earlier run of the same design on the single-pin measure made 480 reads and had 4 failed reads (summary.md).

## V1b: air points against EPA regulatory PM2.5 monitors (independent checker, offline)

**Result: PASS on both criteria.** n = 1,304 of 1,476 places have a monitor within 15 miles (172 have none and are excluded). Spearman of air points vs monitor value = -0.847 (absolute 0.847, criterion at least 0.75; the sign is negative as expected, higher PM2.5 gives lower points). Median absolute difference between stored tract PM2.5 (summary.pm25_ugm3) and monitor value = 0.56 ug/m3 (criterion at most 1.5). Criteria were not changed.

Method. Files: annual_conc_by_monitor_2021.zip and _2022.zip from analysis/climate_level2_epa_airdata_2026-11-03/, unzipped into analysis/climate_level2_v1b_unzipped_2026-11-03/. Parameter code 88101 (PM2.5 FRM/FEM, local conditions), field "Arithmetic Mean", rows with Pollutant Standard "PM25 Annual 2012" (one row per monitor-year-event type, which avoids duplicates), Completeness Indicator = Y only (the valid-year criterion in the file), Event Type "Events Included" where present, else "No Events" (all-data basis, no exceptional-event exclusion). Several POCs at one site are averaged, then 2021 and 2022 are averaged where both exist (745 of 947 sites have both; 1,040 of the 1,304 matched places use a two-year monitor mean, the rest use the single valid year). Monitor coordinates come from the same annual files (aqs_monitors.zip was not needed). Nearest valid monitor by great-circle distance, 15 miles; median distance 5.0 miles; 184 distinct monitors. Places and stored values from the 21 data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl files (breakdown.air_quality_pts, summary.pm25_ugm3). Spearman by rank then Pearson with average ranks. Script: /private/tmp/claude-501/-Users-adamwright-Dev-home-fit/d4d1c066-399c-489a-ab49-94319960c0a2/scratchpad/v1b.py. No network calls.

Supporting numbers. Tract PM2.5 vs monitor Spearman 0.847. Mean signed difference (tract minus monitor) +0.28 ug/m3; 90th percentile absolute difference 1.22. Monitor values 4.19 to 12.77, tract values 4.67 to 12.76.

Ten largest differences (tract minus monitor, ug/m3):
1. Elk Grove CA (Sacramento): tract 9.56, monitor 5.65, +3.91, monitor 10.9 mi away
2. Vineyard CA (Sacramento): 9.34 vs 5.65, +3.69, 6.3 mi
3. Rancho Palos Verdes CA (LA): 9.91 vs 12.57, -2.66, 12.6 mi
4. Maricopa AZ (Phoenix): 8.39 vs 11.05, -2.66, 12.0 mi
5. Rancho Murieta CA (Sacramento): 8.31 vs 5.65, +2.66, 6.3 mi
6. Whitney NV (Las Vegas): 6.70 vs 9.07, -2.37, 3.6 mi
7. Downtown Las Vegas NV: 7.10 vs 9.45, -2.35, 1.5 mi
8. Almaden Valley CA (SF): 7.50 vs 9.84, -2.34, 8.1 mi
9. Cherry Hills Village CO (Denver): 7.39 vs 5.12, +2.27, 4.5 mi
10. Saratoga CA (SF): 7.20 vs 9.40, -2.20, 9.2 mi

Most of the large differences are at 6 to 13 miles from the monitor, where one monitor is standing in for a different airshed (three Sacramento places share one low monitor at 5.65). Only 2 of the 1,304 places differ by more than 3 ug/m3 (both Sacramento area); the median is small.

Independence caveat (from the brief). The stored tract PM2.5 is the CDC/EPA downscaler surface, which is fused from these same regulatory monitors plus satellite and model data. V1b is therefore independent in processing but not wholly in the underlying data, and agreement is partly expected by construction. It checks that the join, units and scoring direction are right and that the surface has not drifted from the monitors; it does not prove the surface is right where there is no monitor. The 172 places with no monitor within 15 miles (mostly rural or exurban) are untested by this check. Not verified: choice of the 2012 annual-standard rows over other standards (values are the same measurement; I did not compare), and whether any monitor is a special-purpose or near-road site.

## V1c: flood points against FEMA National Risk Index county flood loss (independent checker)

Outside value, fixed before any correlation was computed: outside = max(IFLD_EALS, CFLD_EALS) for the place's county, the national expected-annual-loss score for the worse of inland (riverine) or coastal flooding. Counties with neither score present count as 0 (the number is reported below). Note on field names: the layer has no RFLD_* fields; NRI names riverine flooding "IFLD" (inland flooding), so IFLD_EALS is used in place of RFLD_EALS. This is a naming substitution only, same hazard. Criterion from the brief, not changed: absolute Spearman of breakdown.flood_zone_pts vs the outside value at least 0.40 at county level, over places with a flood score; expected sign negative (higher points = safer).

Source and read. One public read, FEMA NRI Counties FeatureServer layer 0, returnGeometry=false, paged at 1,000 rows (4 pages, 3,232 county rows), saved raw in analysis/climate_level2_nri_2026-11-03/ (page0.json, page1000.json, page2000.json, page3000.json). The first request with a named outFields list was rejected by the service (400, no data returned), so the same query was repeated once with outFields=*; the layer was not read again after that. No other network use.

Place to county join. The catalog stores no tract GEOID (the only geoid is a 7 digit place code), only county name (catalog.county_borough) and state abbreviation, so the join is by county name and state, done offline against the saved NRI file.
Join results. Of 1,476 places, 4 have no flood score (excluded, per the criterion), 13 Fairfield County CT places cannot be joined (NRI's Connecticut rows are the 9 planning regions, not counties, and the catalog has no town to region key; excluded, listed as unchecked), and 1,459 are joined. Manhattan, Brooklyn and Staten Island were mapped to New York, Kings and Richmond counties NY. Six NRI names appear twice (a county and an independent city: Baltimore MD, St. Louis MO, Fairfax, Franklin, Richmond and Roanoke VA); no catalog place uses any of them, so the first row was used without effect. Every joined county had at least one of the two flood scores, so the number of counties counted as 0 is 0.

**Result: FAIL.** n = 1,459 places in 127 distinct counties. Spearman of stored flood points vs max(IFLD_EALS, CFLD_EALS) = +0.103 (absolute 0.103, criterion at least 0.40; sign is positive, expected negative, so the direction is also wrong). Check with one value per county (county mean of place flood points, 127 counties): Spearman = -0.054, also far below 0.40. Criterion not changed. The outside value takes only 127 distinct values (one per county), ranging 46.0 to 100, and most catalog counties are large metro counties with scores in the 90s; flood points take 604 distinct values from 4.05 to 30.0.

Limit stated in the brief. The outside source is county level and flood is local, so this tests direction only, and here it does not show agreement in direction. A likely reason (not tested): NRI expected annual loss scores are national percentiles of dollar loss, which rise with how much property and population a county holds, so nearly every large metro county scores in the 90s regardless of how much of its land is in a flood zone. That makes the outside value a weak proxy for hazard share in this catalog, but I did not test it, and this test cannot tell whether the flood points or the outside value is the problem.

Ten places where flood points and the county rating disagree most (rank gap as a share of all 1,459 places, risk rank from low flood points vs risk rank from the outside value; the outside value is compressed near 100 so its ranks are mostly ties in a narrow band, which inflates gaps for high-risk places):
1. Knights Landing CA (Yolo): flood pts 4.5, county inland 90.7, outside 90.7, gap 94 percentile points
2. Clarksburg CA (Yolo): 4.5, 90.7, gap 94
3. Bandera TX (Bandera): 17.39, outside 71.0, gap 93
4. Smithfield NC (Johnston): 14.95, outside 88.0, gap 92
5. Bastrop TX (Bastrop): 18.4, outside 86.2, gap 90
6. Galveston TX (Galveston): 4.5, outside 93.7 (coastal 91.2), gap 89
7. Dickinson TX (Galveston): 5.12, outside 93.7, gap 89
8. Elkton MD (Cecil): 21.73, outside 67.2, gap 88
9. Tottenville NY (Richmond): 18.22, outside 90.3, gap 88
10. Castroville TX (Medina): 21.99, outside 71.7, gap 87
Several of these (Galveston, Dickinson, Knights Landing, Clarksburg) have the lowest possible flood points and high county ratings, so they agree in direction; the gap is a rank artifact of the compressed outside value. Reading the list as disagreement is therefore misleading for those four; the real disagreements are the places with middling points in high-rated counties, such as Smithfield, Bandera and Bastrop.

Not verified: whether flood points are right (this check cannot say); a hazard-share outside source (county share of land in the special flood hazard area, the brief's alternative) was not read and would be a better test of direction. Script: /private/tmp/claude-501/-Users-adamwright-Dev-home-fit/d4d1c066-399c-489a-ab49-94319960c0a2/scratchpad/v1c.py. Network use: the one NRI read above only.

## V1c-b: flood points against NRI flood-exposed share of county (added after V1c failed)

This test was added after V1c failed. It does not replace V1c, whose FAIL stands unchanged. Exposure-area definition unconfirmed (alias only; FEMA documentation not read). Because of that, a result here cannot count as a clean pass.

Outside value, fixed before any correlation was computed: flood-exposed share of county = min(1, (IFLD_EXP_AREA + CFLD_EXP_AREA) / AREA), from the same saved NRI file (analysis/climate_level2_nri_2026-11-03/). Missing values count as 0. Units: all three fields are square miles (aliases "Inland Flooding - Exposure - Impacted Area (sq mi)", "Coastal Flooding - Exposure - Impacted Area (sq mi)", "Area (sq mi)"). What the file shows: for other hazards the exposure area equals the full county area, while inland flood is a partial subset; no county has inland plus coastal above county area; median share across 3,232 counties is 0.054. What it does not show: that the impacted area is the flood hazard zone (no description saved). Double-count caveat: 538 counties have both inland and coastal area above 0 and the two may overlap, so the sum can overstate the share (the cap at 1 is not reached by any county). Same places and joins as V1c. Criterion unchanged: absolute Spearman at least 0.40, expected sign negative. County-level exposure is still coarse for a local measure, so this tests direction only.

**V1c-b result: FAIL.** n = 1,459 places in 127 distinct counties (same set as V1c). Spearman of stored flood points vs flood-exposed share = +0.104 (absolute 0.104, criterion at least 0.40; sign positive, expected negative, so direction is also wrong). One value per county (county mean of place flood points, 127 counties): Spearman = +0.033. The outside value takes 127 distinct values, range 0.012 to 0.630. Criterion not changed. This repeats the V1c outcome on a different outside value, but the exposure-area definition is unconfirmed, the source is county level and flood is local, so it tests direction only and does not show which side is wrong.

Five largest disagreements (rank gap in percentile points, risk rank from low points vs risk rank from high exposed share): Bandera TX (Bandera): points 17.39, share 0.025, gap 94; Belvedere CA (Marin): 15.15, 0.074, gap 91; Lake Las Vegas NV (Clark): 19.08, 0.035, gap 91; Sausalito CA (Marin): 18.81, 0.074, gap 88; DC Ranch AZ (Maricopa): 13.18, 0.094, gap 88. Script: /private/tmp/claude-501/-Users-adamwright-Dev-home-fit/d4d1c066-399c-489a-ab49-94319960c0a2/scratchpad/v1cb.py. Network use: none.

## V1a: heat points against PRISM 1991-2020 summer maximum temperature (independent checker)

Outside value, fixed before any correlation was computed: PRISM JJA mean = average of the June, July and August 1991-2020 normals of monthly mean daily maximum temperature (30 arc-second grid, about 800 m, degrees C), sampled at the place's stored coordinates (score.coordinates lat/lon). Where the cell is nodata (-9999) in any of the three months, the nearest cell valid in all three within 2 km is used; otherwise the place is listed as unchecked. Places with no heat reading (breakdown.heat_exposure_pts missing or null) are unchecked and listed. Criteria from the brief, not changed: Spearman of heat points vs the PRISM value, absolute value at least 0.60 over all places with a heat reading; within-metro Spearman (metro mean removed from both variables; metro = the catalog file) at least 0.30. Expected sign is negative (higher heat points = cooler = safer). Places differing by more than 30 percentile points are reported.

Limit from the brief: heat is satellite surface temperature (Landsat JJA 2022), PRISM is 30-year air temperature. These are different quantities over different periods, so the bar is moderate. Offline only; no network use.

**V1a result: FAIL on both criteria.** n = 1,467 places with a heat reading and a PRISM value (1,476 total; 9 unchecked, listed below). Every sampled cell was valid, so the 2 km nearest-cell fallback was never used. Spearman of heat points vs PRISM JJA mean = -0.433 (absolute 0.433, criterion at least 0.60; sign negative as expected). Within-metro Spearman (metro mean removed from both variables, metro = catalog file, 21 metros) = -0.206 (absolute 0.206, criterion at least 0.30). Criteria not changed.

Places more than 30 percentile points apart (heat risk rank from low points vs PRISM risk rank from high temperature, over the 1,467): 465 (31.7 percent), split 234 where heat points say riskier than PRISM and 231 the reverse. By metro the most are in LA (77), SF (64), Atlanta (50), San Antonio (34), Tampa (31).

Ten largest disagreements:
1. Von Ormy TX (san_antonio): heat pts 25.0, PRISM JJA 35.4 C, gap 90 percentile points
2. Elmendorf TX (san_antonio): heat pts 25.0, PRISM JJA 35.3 C, gap 90 percentile points
3. Sandy Oaks TX (san_antonio): heat pts 25.0, PRISM JJA 35.2 C, gap 90 percentile points
4. La Vernia TX (san_antonio): heat pts 25.0, PRISM JJA 35.1 C, gap 90 percentile points
5. Dignowity Hill TX (san_antonio): heat pts 25.0, PRISM JJA 34.8 C, gap 86 percentile points
6. Olmos Park TX (san_antonio): heat pts 25.0, PRISM JJA 34.8 C, gap 86 percentile points
7. Kirby TX (san_antonio): heat pts 25.0, PRISM JJA 34.8 C, gap 86 percentile points
8. Southtown TX (san_antonio): heat pts 24.61, PRISM JJA 35.1 C, gap 85 percentile points
9. Converse TX (san_antonio): heat pts 25.0, PRISM JJA 34.8 C, gap 85 percentile points
10. Alamo Heights TX (san_antonio): heat pts 25.0, PRISM JJA 34.7 C, gap 84 percentile points
All ten have heat points at 25.0 or just under, which is the top of the heat score, while PRISM puts them among the hottest air in the catalog (about 35 C). So the heat measure rates these San Antonio places as the coolest.

Observations (descriptive, not new criteria). Heat points reach a ceiling of 25.0 for 93 places (heat points range 1.42 to 25.0, 942 distinct values), and those places are not cool by PRISM (mean 28.8 C vs 30.4 C for all places); 14 in SF, 13 in Atlanta, 13 in San Antonio, 12 in Tampa, 10 in NYC. Dropping them raises the pooled value only to -0.470 on 1,374 places, still below 0.60. Within-metro Spearman by metro is mixed: strongly negative (agreeing) in SF -0.72, Philadelphia -0.67, Denver -0.65, LA -0.64, Las Vegas -0.51, Phoenix -0.35, Sacramento -0.32, and wrong sign (positive) in NYC +0.34, Austin +0.36, San Antonio +0.30, Seattle +0.30 (n=5), Atlanta +0.23, Miami +0.22, Boston +0.18; near zero in Charlotte, Orlando, Tampa. I did not test why. A plausible cause given the brief's limit is that Landsat surface temperature within a metro tracks local land cover (pavement vs vegetation) while PRISM at 800 m is smooth, but that is untested, so this check cannot say whether the heat points or the comparison is the problem.

Unchecked (9, no heat reading, so no heat points to test): Palm Beach FL, Clearwater Beach FL, Clearwater FL, Dunedin FL, Land O' Lakes FL, Oldsmar FL, Palm Harbor FL, Safety Harbor FL, Tarpon Springs FL. These are all Tampa or Palm Beach area places and may be the roughly 9 nonpositive or implausible LST places the earlier heat check flagged, but the catalog does not say why the reading is missing, so I could not confirm the match. No place with lst_score at or below 0 appears among the 1,467 checked.

Limit stated in the brief: heat is satellite surface temperature (Landsat JJA 2022), PRISM is 30-year air temperature, different quantities and periods, so the bar is moderate; both criteria still fail. Script: /private/tmp/claude-501/-Users-adamwright-Dev-home-fit/d4d1c066-399c-489a-ab49-94319960c0a2/scratchpad/v1a.py. Network use: none.

## V1a-b: Landsat surface temperature against MODIS land-surface temperature, same season (independent checker)

Added after V1a failed. It does not replace V1a, whose result (FAIL, -0.433 pooled, -0.206 within-metro) stands unchanged; V1a compared satellite surface temperature with 30-year air temperature, a quantity mismatch, and this is a better-matched test.

Outside value, fixed before any correlation was computed: for each place, the mean over all valid composites (value greater than 0) of the MOD11A2 (Terra) and MYD11A2 (Aqua) LST_Day_1km pixel containing the stored coordinates (score.coordinates lat/lon), Terra and Aqua averaged together, converted to Celsius as value x 0.02 - 273.15. Coordinates are reprojected from EPSG:4326 to the raster CRS (MODIS sinusoidal). If the pin's pixel has no valid composite, the nearest pixel with valid data within 2 km is used; otherwise the place is listed as unchecked. Source: analysis/climate_level2_modis_2026-11-03/*.tif, all files used as downloaded.

Stored values compared: score.livability_pillars.climate_risk summary.local_lst_c (Landsat surface temperature, C; same quantity as MODIS, the primary comparison) and breakdown.heat_exposure_pts (continuity with V1a). Places with no heat reading (9 Florida places) and the 6 places screened out by the heat plausibility screen (heat points now none) are listed separately; local_lst_c is used for them where present, and results are reported with and without them.

Criteria fixed before results (judgments, not sourced; same quantity so higher than the PRISM bars): Spearman of Landsat local_lst_c vs MODIS value at least 0.70 over all checked places; within-metro Spearman (metro mean removed from both variables; metro = catalog file) at least 0.50.

Limits: MODIS is 1 km against a 500 m Landsat buffer; Terra overpasses about 10:30 and Aqua about 13:30 local time, Landsat about 10:30; 8-day composites are cloud-screened differently. The test checks whether the Landsat readings are sound, not whether the 30 to 60 C scoring scale is right.

**File count.** 260 files on disk, not 270. The grid is complete with no duplicates: 10 tiles (h08v05, h09v04, h09v05, h09v06, h10v05, h10v06, h11v04, h11v05, h12v04, h12v05) x 13 eight-day composites (year-days 145, 153, ..., 241) x 2 satellites (MOD11A2 and MYD11A2) = 260, and every tile has exactly 26 files. Nothing is missing within that grid, so I cannot say what the extra 10 in the downloader's 270 count were; the files on disk are all that was used. Composite start days 145 to 241 are 25 May to 29 Aug (the last composite runs into early September), slightly wider than June to August; all were used as downloaded.

**Coverage.** 1,476 places. 1,430 sampled at the pin's pixel, 33 by the nearest valid pixel within 2 km (nearest valid pixel 0.5 to 1.9 km away), 13 unchecked: Chinatown, East Village, Flatiron, Gramercy Park, Greenwich Village, Little Italy, Midtown East, Midtown, Murray Hill, NoHo, Nolita, SoHo and Turtle Bay (all Manhattan, NY). The MODIS tile has fill (no valid composite) in every composite for the pixels within about 2 km of those pins. Of the 1,463 with a MODIS value, 9 Florida places have no local_lst_c (listed in V1a) and 6 places have local_lst_c but no heat points (the heat plausibility screen: Clermont FL, New Port Richey FL, Alamo Heights TX, La Vernia TX, Terrell Hills TX, Von Ormy TX).

**Result: PASS on both criteria.**

| Comparison | n | Pooled Spearman | Within-metro Spearman |
|---|---|---|---|
| Landsat local_lst_c vs MODIS, all places with both (includes the 6 screened) | 1,454 | 0.761 | 0.567 |
| Landsat local_lst_c vs MODIS, without the 6 screened places | 1,448 | 0.770 | 0.569 |
| Heat points vs MODIS (V1a continuity; absolute values, sign negative as expected) | 1,448 | -0.770 | -0.574 |

Criteria (not changed): pooled at least 0.70 (0.761 passes; 0.770 without the screened places), within-metro at least 0.50 (0.567 passes; 0.569). Heat points track local_lst_c almost exactly, so the heat score keeps what the Landsat reading says, which the same-quantity test supports as sound at the rank level.

Within-metro Spearman by metro (n above 3): LA 0.94, SF 0.91, Sacramento 0.77, Boston 0.75, Philadelphia 0.75, Denver 0.74, Las Vegas 0.73, Chicago 0.70, Raleigh 0.66, Orlando 0.57, Charlotte 0.55, Houston 0.54, NYC 0.43, Tampa 0.42, Phoenix 0.38, Dallas 0.35, Austin 0.34, Miami 0.19, Atlanta 0.07, San Antonio -0.06. The metro-level agreement is weak in the humid Southeast and in San Antonio; I did not test why. Seattle has 5 places and is not meaningful.

**Disagreements of more than 10 C.** Difference = Landsat minus MODIS over the 1,454 places: mean +2.3 C, median +3.1 C (Landsat is typically a little warmer, as expected for a 500 m reading near 10:30 against a Terra and Aqua mean at 1 km). Landsat reads more than 10 C below MODIS at 33 places and more than 10 C above at 13. The 15 largest differences (Landsat, MODIS, difference in C; stored heat points):

1. Von Ormy, TX: 21.6, 42.9, -21.4 (screened, no heat points)
2. La Vernia, TX: 22.4, 43.7, -21.3 (screened)
3. Alamo Heights, TX: 20.7, 40.0, -19.2 (screened)
4. New Port Richey, FL: 16.5, 35.5, -19.0 (screened)
5. Kirby, TX: 26.1, 43.8, -17.8 (heat 25.0)
6. Elmendorf, TX: 27.1, 43.8, -16.7 (heat 25.0)
7. Terrell Hills, TX: 24.6, 40.8, -16.1 (screened)
8. Olmos Park, TX: 25.0, 40.9, -16.0 (heat 25.0)
9. Dignowity Hill, TX: 28.4, 44.3, -16.0 (heat 25.0)
10. Edgewater, NJ: 19.9, 35.7, -15.8 (heat 25.0)
11. Downtown St. Petersburg, FL: 22.0, 37.7, -15.7 (heat 25.0)
12. Indian Springs, NV: 33.8, 48.5, -14.7 (heat 21.84)
13. Kirkwood, GA: 21.1, 35.5, -14.4 (heat 25.0)
14. Ballard, WA: 37.7, 23.9, +13.8 (heat 18.58)
15. Selma, TX: 29.2, 43.0, -13.8 (heat 25.0)

The sign convention: difference = Landsat minus MODIS, so negative means Landsat is cooler than MODIS. Almost all large gaps are Landsat too cool (14 of the 15; 9 are in the San Antonio metro), and 5 of the 15 are places the plausibility screen already removed. The other cases (San Antonio, Tampa, NYC and Atlanta) sit at the heat-points ceiling of 25.0, which means they score as the coolest end. This suggests Landsat cool readings (20 to 28 C where MODIS shows 35 to 44 C) may be partly unscreened bad readings of the kind V1a-era checking found in San Antonio (see the earlier LST finding); I have not inspected the Landsat scenes, so that is a pointer, not a finding. Ballard, WA is the largest warm case (Landsat 37.7 vs MODIS 23.9), a single-scene or industrial-surface reading is a possibility I did not test.

Limits (as stated above): different footprint (500 m vs 1 km), different overpass times (Terra and Aqua averaged, Aqua about 3 hours after Landsat), different cloud screening and compositing, so a rank agreement of 0.76 is a soundness check of the Landsat readings and does not validate the 30 to 60 C scoring scale. Script: /private/tmp/claude-501/-Users-adamwright-Dev-home-fit/d4d1c066-399c-489a-ab49-94319960c0a2/scratchpad/v1ab_extract.py (sampling) and v1ab_stats.py (statistics) in the same folder. Network use: none. Not committed.
