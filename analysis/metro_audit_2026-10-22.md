# Metro-level audit of the catalog (2026-10-22)

Read-only analysis of `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`
(21 metros, 1,476 places, 14 scored pillars; Seattle has 5 places and is excluded from
comparisons; Denver is included but not yet committed). Nothing was rescored or changed.

Method: for every pillar, each metro vs all other metros, matched on area type x income band
(<90k, 90-130k, 130-180k, 180k+), weighted by the metro's own cell counts. A pair is flagged when
the gap is >= 10 points and |z| >= 3. Full matrix: `metro_audit_matched_gaps_2026-10-22.csv`.

## A. Confirmed artifacts (the scores are wrong, not just surprising)

1. **Flood zone component does nothing.** 1,473 of 1,476 places get the maximum 30/30 flood points
   (the other 3 got the neutral 15 from a failed request). The configured FEMA endpoint
   (`data_sources/fema_flood.py`, ArcGIS FeatureServer 0) holds only 66 polygons around one small area, so
   every other point finds no polygon and is scored "minimal". Live check: Davis Islands (Tampa),
   Key Biscayne, the Galveston seawall and the Hoboken waterfront all return `in_flood_zone: False`.
   Effect: climate_risk is inflated by a constant for every metro, and flood-prone metros (Tampa, Miami,
   Houston, NYC waterfront) get no penalty. Tampa's +16.9 climate gap comes from heat and trend, not flood.
2. **Economic opportunity mixes two methods across metros.** The job-access (gravity) component exists
   only where the LODES job grid was built (NYC, LA, SF, Sacramento, Philadelphia); every other metro
   falls back to market quality alone. NYC's +19.4 gap is partly this: its job_access averages 94 against
   market quality 71. Boston and Las Vegas are partially covered, which is worse: job_access is 0.0 for
   36 of 81 Boston places and 27 of 30 Las Vegas places (mean 2.8 and 0.0), so final scores are 43.4 and
   19.1 against market quality alone of 65.9 and 37.3. Matched gaps: Boston -25.9, Las Vegas -47.3.
   The code intends to fall back to market quality when the grid does not cover a point
   (`pillars/economic_opportunity.py`, `data_sources/job_accessibility.py`); coverage detection is
   too loose at grid edges.

## B. Suspicious, not yet proven

3. **Tampa safety looks undercounted.** Suburban property crime 8.9 per 1,000 against Orlando 26.5 and
   Miami 18.0 (same state), equal to NYC and Boston suburbs. Possible partial NIBRS reporting. Needs the
   agency-level incident counts checked.
4. **Missing safety scores are not random.** Places with no safety score (state-aggregate withheld) are
   Las Vegas 23%, Charlotte 17%, Orlando 16%, Miami 15%, Atlanta 12%, Denver 10%. The scored remainder may
   be biased toward agencies that report well.
5. **Boston green-view index.** At the same tree canopy (20-45%), Boston's raw green-view index is 45.6
   against 61.5 (NYC), 62.2 (Philadelphia), 62.4 (Atlanta), 64.2 (Chicago). It is NYC's lead over Boston that
   looks odd (Boston low), not NYC high. Cause unknown (the index is NDVI-based, a 2022-2026 all-season
   Sentinel-2 median).

## C. Real or design effects (no action suggested)

- **NYC suburban safety (+12.2) and beauty.** Holds at matched income; source mix is consistent;
  Northeast suburbs (Boston, Chicago, Seattle 63-67) differ from Sun Belt (25-45).
- **Denver air travel (-14.6).** Denver International is 35 km from the places, so distance is the driver.
- **Heat-driven climate gaps** (Phoenix -14.7, Dallas -12.1, Austin -12.4): LST scores near 0 are real heat.
- **Housing value** (LA -11.9, SF -14.2, Chicago +11.7, Philadelphia +10.3): expected.
- **Houston neighborhood amenities (-14.2)** looks like sprawl; not examined further.

## D. Sample and coverage differences that limit comparison

- **Place mix.** Urban-core share: NYC 45%, Chicago 23%, Philadelphia 23%, Boston 20%, SF 13%, and 0-3%
  in Atlanta, Dallas, Houston, Charlotte, San Antonio, Orlando, Austin, Raleigh, Tampa. Median household
  income ranges from $66.8k (Tampa) to $159.5k (SF). Metro mean scores are not comparable; the matched
  gaps above are net of area type and income but cannot say anything about urban cores in most metros.
- **built_environment** is scored only for NYC (78% of places) and LA (94%).
- **Confidence differences:** public_transit_access 31-36 in Dallas, Houston, San Antonio; air_travel_access
  22 in Sacramento and 44 in San Antonio (63 default elsewhere); social_fabric 68 in Philadelphia.

## Suggested next steps (none done)

1. Replace the FEMA flood source with the national NFHL service and recompute climate_risk. This needs
   fresh API data (flood zone is not derivable from stored values).
2. Make job-access fall back to market quality for Boston and Las Vegas now (a coverage test), then either
   build the LODES grid for all states or document that the component is NYC/CA/PA only. Recompute
   offline from stored market_quality_score.
3. Check Tampa agency incident counts; decide whether withheld safety scores need a flag.
4. Re-measure a few Boston towns' green-view index with summer-only imagery (waiting on approval).
5. Add urban-core neighborhoods to the Sun Belt metros, or limit cross-metro conclusions to suburbs.

## Addendum: economic opportunity with a national job grid (offline, nothing applied)

Built LODES 2022 workplace jobs for all states into a scratch grid (794,259 H3 cells, 142.8M jobs) and
recomputed job access and the economic score for all 1,476 places from stored coordinates and
market_quality_score (score = 0.55 x job access + 0.45 x market quality). Consistency check: in NYC, LA,
SF and Sacramento the new job access matches the stored value (mean difference 0.00, max 1.5).

Matched economic gap vs the rest, before to after: Boston -25.9 to +1.1, Las Vegas -47.3 to -15.4, NYC
+19.4 to +9.9, LA +10.4 to +3.4, SF -1.6 to -9.2, Austin +9.7 to +2.8, Dallas +9.8 to +5.9. Philadelphia's
job access rose from 66.6 to 84.4 (the old grid had New Jersey but not Pennsylvania). Mean total score
moves: Boston +2.5, Las Vegas +2.9, Phoenix +0.9, Chicago +0.8, Philadelphia +0.7; NYC, LA, SF, Sacramento
unchanged. Rank changes: Chicago 4 to 3, SF 3 to 4, Miami 10 to 9, Charlotte 9 to 10, San Antonio 18 to 17,
Sacramento 17 to 18. Per-place values: `econ_national_grid_before_after_2026-10-22.csv`.

Still open: Las Vegas stays -15.4 because its market quality alone is low (37.3), and SF -9.2 because its
market quality is 52.2; both come from the BLS-based market components, not the job grid.

## Addendum: flood zone fix (offline, nothing applied)

The official FEMA NFHL service (hazards.fema.gov NFHL MapServer layer 28, flood hazard zones) works; the
configured ArcGIS Online copy holds 66 polygons. Queried all 1,476 catalog places (5 failed, 4 outside the
NFHL). Zones: 1,193 minimal hazard, 130 shaded 0.2% or levee-reduced X, 101 special flood hazard area,
12 floodway, 7 D. The existing classifier scores every FLD_ZONE "X" as moderate (55% of points); with working
data that would dock about 13 points from the 82% of places in unshaded minimal-hazard X, so the proposal
(rule B) uses ZONE_SUBTY: only 0.2% and levee-reduced X are moderate.

Mean climate_risk, now to rule B: Miami 70.3 to 56.8 (42% of places in a flood hazard area), Tampa 78.0 to 69.2
(32%), Houston 56.0 to 50.1, Phoenix 48.6 to 37.2, Sacramento 56.3 to 50.5, SF 62.9 to 59.0, NYC 67.1 to 64.6.
Total score change: Miami -1.0, Phoenix -0.9, Tampa -0.7, Houston -0.5, Sacramento -0.4, others -0.03 to -0.3.
Matched climate gap: Tampa +16.7 to +12.7, Miami +8.2 to -1.9, Phoenix -15.0 to -23.4.
Per place: `flood_fix_before_after_2026-10-22.csv`. Caveats: FEMA zones are regulatory maps, not forward-looking
coastal risk (Mid-Beach Miami Beach and Venice LA read minimal); the 30-point flood weight and tier
percentages (15/55/45/100) are unchanged and not research-grounded here.

## Addendum: Tampa safety (suspicious item 3) resolved: not an undercount

Tampa suburbs use county sheriff rates for 12 of 33 places (Hillsborough 8, Pasco 3, Pinellas 1). Pulled
Hillsborough County Sheriff's Office (ORI FL0290000) from the FBI CDE directly: all 12 months reported in
every year, property crime per 1,000 service population 7.7 (2022), 7.0 (2023), 5.5 (2024), 4.4 (2025);
stored value 4.32 matches 2025 (the pipeline uses current year minus one, 2025). So the low rate is real,
falling, and fully reported. Two side effects remain: (a) place rates use 2025 data while the national
percentile scale is built on 2024 data, which flatters places with fresh data relative to agencies that
lag and fall back to 2022-2024 (the code walks back up to three years); (b) `data_period` is not stored for
FBI-sourced places, so the year each place uses cannot be audited from the catalog. Orange County Sheriff
(Orlando) shows the NIBRS-transition pattern (data only from Dec 2024), so Florida agencies near that
switch deserve a year check.

## Addendum: places with no safety score (suspicious item 4)

55 of 1,456 places have no community_safety score; all are "no_data" because no police agency near them reports to
the FBI (crime rule C4, decision "gap"). By metro: Miami 10, Atlanta 9, Charlotte 7, Las Vegas 7, Orlando 7,
Philadelphia 6, the rest 1-2. All are exurban (27), suburban (15) or rural (13). Median household income is
similar to scored places ($91k against $96.5k). Totals are computed over the remaining pillars (weights are
renormalized, not zero-filled), and imputing each missing score with its metro and area-type median moves the
total by under 1.5 points for most metros (+2.5 to +5 where one or two places are missing), so the bias in totals is small.

Spot check of 16 against the FBI CDE: most are genuine non-reporting (Broward County agencies including Hollywood,
Deerfield Beach, Lauderhill, Parkland, Cooper City are non-NIBRS with no 2024 or 2025 data; Cumming and Jonesboro
GA PDs do not report; Buford, Peachtree Corners and Laughlin have no FBI agency). Three look mappable: College Park GA
(own PD, 12 months of NIBRS data) and Enterprise and Summerlin South NV (inside LVMPD's jurisdiction, which has data;
sibling places Paradise and Winchester already map to it). The list is in `missing_safety_places_2026-10-22.csv`;
`data/crime_agency_map.json` is being edited in another session, so these were not touched.

## Addendum: Las Vegas natural beauty (-23.8): partly a region-lookup bug

Natural beauty (V9) normalizes green-view index and tree canopy against a regional median. `_NB_REGION_BOXES`
(pillars/natural_beauty.py) is checked in order and the "california" box (lat 32-42.5, lon -125 to -114) comes
before "southwest_arid" (lon -114.5 to -103), so all 30 Las Vegas places (lon -115.1) get California baselines
(GVI 13, canopy 19) instead of southwest_arid (8, 9) and are normalized as 2x greener-expectation than a desert
city; Phoenix, 140 km east, correctly uses southwest_arid. Reproduced the stored scores to within 0.03 and
recomputed Las Vegas with southwest_arid: mean natural beauty 40.3 to 45.8 (Summerlin 53.7 to 73.6), matched gap
-23.7 to -18.7, total +0.42. The remaining gap is real desert (canopy 1.5%, water 10); Phoenix is -14.7.
Smaller effects: the NYC metro splits across two regions (182 places mid_atlantic, 11 east of lon -73.5 northeast;
using mid_atlantic would lift the 5 checkable places from 78.9 to 81.2). The same crude boxes can mis-assign
Reno, Mesquite, Laughlin and the Colorado River strip. The fix is a state-aware region lookup; the toolkit already
has rescore_natural_beauty_v9_offline.py for the recompute. Nothing changed.

## Addendum: Boston green-view index (suspicious item 5)

Boston's raw green-view index (NDVI-based, 47.9 at 20-45% canopy) is lower than NYC 62.3, Philadelphia 64.1,
Chicago 66.7, Atlanta 56.8. A regression of GVI on canopy, developed share, water share and latitude across all
1,237 places (R2 0.68) puts Boston's residual at only -4.7, in the middle of the range (Denver -19.5, Phoenix
-10.5, LA -10.3, Las Vegas -9.5, Chicago +13.5, Philadelphia +7.7), so Boston is not a measurement outlier and a
summer-only re-measure would not settle it. The larger driver is the regional baseline: V9 divides GVI and
canopy by a regional median (northeast 26/32, mid_atlantic 22/29, midwest 19/27) that came from street-view
(Treepedia-style) GVI and NLCD canopy literature, but it is applied to an NDVI-pixel GVI that runs two to three
times higher, so the baselines are on a different scale from the measurement. The choice moves natural beauty by
4-10 points: Boston 66.5 (northeast), 71.0 (mid_atlantic), 74.1 (midwest); Chicago 55.2 (midwest), 51.7, 47.1
(northeast). Cross-metro natural beauty gaps therefore partly reflect which baseline a place falls in.
Options: leave as is; derive regional medians from this pipeline's own GVI and canopy on a random national
sample (needs GEE for several hundred points per region); or an interim from catalog medians (selection-biased).
Nothing changed.

## Addendum: Place Pulse test of the natural beauty components (offline, nothing changed)

Downloaded MIT Place Pulse 2.0 (Figshare, CC BY 4.0, votes_clean.csv, 481 MB) to scratch: 220,604 "more beautiful"
pairwise votes over 110,781 street-view images from 56 cities; 10 of our 21 metros are in it (Atlanta, New York,
Chicago, Houston, Philadelphia, Denver, Seattle, Boston, Los Angeles, San Francisco). Note the file's `long_*`
columns hold latitude and `lat_*` hold longitude, and image ids are the `left`/`right` columns. Image score = win
rate (ties count half); 4,952 images in those metros have 6+ votes. Aggregated to catalog places (images within
1.5 km of a place pin, 8+ images): 103 places, 1,131 images, 10 metros, mostly humid or temperate regions (no desert).

Place-level correlation of mean perceived beauty (pooled, 90% bootstrap range): raw green view 0.64 (0.53-0.72), raw
canopy 0.57 (0.46-0.67), our natural beauty score 0.48, water -0.08, terrain -0.16, landcover 0.33. Jointly, green view
carries the effect (standardized 0.63) and canopy adds nothing (0.01); R2 0.40 for green view alone, 0.32 canopy alone.
Regional normalization did not help: green view 0.63 with a curve only, 0.56 with literature medians (what we do),
0.60 with our own medians; ranges overlap, so this is suggestive, not conclusive. Caveats: street-scene beauty includes
buildings and sky, images are 2007-2012, ratings are noisy (median 4 votes per image), and water and terrain cannot show
in street images, so this does not test them (USDA Natural Amenities Scale is the planned test for those).
