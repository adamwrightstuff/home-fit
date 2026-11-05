# Launch check, 2026-10-28

1476 places, metros: atlanta, austin, boston, charlotte, chicago, dallas, denver, houston, la, las_vegas, miami, nyc, orlando, philadelphia, phoenix, raleigh, sacramento, san_antonio, seattle, sf, tampa.
Gates: FAIL at 25% of places at the max or the min; WARN above 15% in one rounded score or sd below 5. A failure means investigate the data or logic, never tune a parameter until it passes.

## 1. Spread and clumping

| Pillar | n | mean | sd | at max | at min | top value | distinct | between-metro variance | no data | degraded | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| quality_education | 1472 | 59.4 | 25.9 | 0.1% | 0.1% | 2.9% (at 61) | 98 | 7% | 0.3% | 2.4% | pass |
| neighborhood_amenities | 1476 | 60.9 | 25.8 | 1.2% | 3.3% | 3.3% (at 0) | 97 | 26% | 0.0% | 0.0% | pass |
| economic_opportunity | 1476 | 73.6 | 6.2 | 0.1% | 0.1% | 10.7% (at 76) | 36 | 74% | 0.0% | 0.0% | pass |
| climate_risk | 1476 | 74.2 | 10.0 | 0.1% | 0.1% | 6.8% (at 81) | 55 | 42% | 0.0% | 0.6% | pass |
| active_outdoors | 1476 | 65.8 | 14.7 | 0.1% | 0.1% | 3.9% (at 62) | 75 | 43% | 0.0% | 0.0% | pass |
| natural_beauty | 1475 | 65.3 | 18.9 | 0.1% | 0.1% | 3.3% (at 78) | 88 | 18% | 0.1% | 13.0% | pass |
| social_fabric | 1476 | 47.9 | 9.2 | 0.1% | 0.1% | 5.0% (at 48) | 53 | 25% | 0.0% | 38.2% | pass |
| healthcare_access | 1462 | 87.6 | 19.0 | 33.0% | 0.7% | 35.0% (at 100) | 84 | 17% | 0.9% | 0.9% | FAIL |
| public_transit_access | 1476 | 39.2 | 27.9 | 0.9% | 14.8% | 14.8% (at 0) | 100 | 41% | 0.0% | 0.0% | pass |
| air_travel_access | 1476 | 85.3 | 7.1 | 0.1% | 0.1% | 19.0% (at 87) | 47 | 60% | 0.0% | 0.0% | WARN |
| housing_value | 1469 | 57.1 | 13.7 | 0.1% | 0.1% | 4.7% (at 54) | 74 | 33% | 0.5% | 0.5% | pass |
| community_safety | 1420 | 54.5 | 28.7 | 1.7% | 0.3% | 3.0% (at 100) | 101 | 9% | 3.8% | 5.8% | pass |

Findings:
- FAIL: healthcare_access: 33% of places are at the maximum (100.0)
- WARN: air_travel_access: 19% of places share the score 87

## 2. Pre-registered contrasts

| Pillar | Result | A mean | B mean | Gap | Expected | Min gap | n A / n B | Reason |
|---|---|---|---|---|---|---|---|---|
| healthcare_access | PASS | 98.8 | 53.6 | +45.2 | a_higher | 15 | 98 / 132 | Rural areas are sparse and far from major hospitals and hospital networks (owner, very sure).  |
| public_transit_access | PASS | 79.3 | 20.8 | +58.6 | a_higher | 20 | 98 / 373 | There is almost no public transit in exurban areas (owner, very sure).  |
| neighborhood_amenities | PASS | 88.2 | 39.9 | +48.2 | a_higher | 20 | 98 / 143 | Rural areas have very small towns with limited options, or places are spread out (owner, very sure).  |
| air_travel_access | WARN | 87.3 | 79.6 | +7.7 | a_higher | 10 | 98 / 143 | Airports are built near cities, even when some sit far out, like Denver (owner, sure). right direction but the gap is below the minimum 10 |
| economic_opportunity | PASS | 82.8 | 66.6 | +16.1 | a_higher | 5 | 98 / 143 | Most jobs are in cities, and rural workers commute into cities (owner, very sure). Small gap because the pillar has little spread.  |
| housing_value | PASS | 65.1 | 39.3 | +25.8 | a_higher | 10 | 143 / 95 | Homes are cheaper relative to income in rural areas than in expensive metros; some metros and some rural areas are exceptions (owner, very sure).  |
| natural_beauty | PASS | 72.4 | 59.8 | +12.5 | a_higher | 5 | 143 / 98 | More concrete in cities; some cities invest in trees, parks and waterfronts, so the gap is small (owner, sure).  |
| natural_beauty | PASS | 69.4 | 59.8 | +9.5 | a_higher | 5 | 373 / 98 | Same statement for exurban areas (owner, sure).  |
| active_outdoors | PASS | 76.5 | 52.0 | +24.5 | a_higher | 10 | 62 / 74 | Denver sits next to the Rockies (trails, skiing, mountain parks); Houston is flat and hot and humid with far fewer trail and ski options (drafted by Claude at the owner's request; owner to confirm).  |

## 3. Degenerate metros (a sub-metric where 90% or more of a metro's places share one value while the rest of the catalog does not)

| Pillar | Sub-metric | Metros (shared value, share of places) |
|---|---|---|
| air_travel_access | summary.airport_count | dallas (2, 96%) |
| economic_opportunity | breakdown.density.score | atlanta (65.8953, 100%), austin (69.8086, 100%), boston (82.6745, 99%), charlotte (63.1913, 100%), chicago (67.7404, 99%), dallas (65.3701, 99%), denver (85.7437, 100%), houston (53.3812, 100%), la (73.9475, 99%), las_vegas (39.3451, 100%), miami (68.4484, 100%), nyc (75.6643, 93%), orlando (58.9276, 100%), philadelphia (61.587, 100%), phoenix (54.1674, 100%), raleigh (61.1425, 100%), sacramento (50.1059, 100%), san_antonio (37.8313, 100%), tampa (52.7898, 100%) |
| economic_opportunity | breakdown.ecosystem.score | atlanta (76.6499, 100%), austin (71.8683, 100%), boston (29.8333, 99%), charlotte (79.5861, 100%), chicago (61.4632, 99%), dallas (73.5441, 99%), denver (83.9378, 100%), houston (68.7148, 100%), la (83.1387, 99%), las_vegas (31.4111, 100%), miami (84.615, 100%), nyc (41.9123, 93%), orlando (71.2003, 100%), philadelphia (32.9256, 100%), phoenix (64.401, 100%), raleigh (59.8745, 100%), sacramento (62.7021, 100%), san_antonio (54.8925, 100%), tampa (67.0552, 100%) |
| economic_opportunity | breakdown.mobility.score | atlanta (59.502, 100%), austin (84.3389, 100%), boston (64.2543, 99%), charlotte (73.6357, 100%), chicago (41.8771, 99%), dallas (63.3928, 99%), denver (58.2048, 100%), houston (64.3105, 100%), la (63.3751, 99%), las_vegas (74.9312, 100%), miami (62.8832, 100%), nyc (78.6384, 93%), orlando (58.6994, 100%), philadelphia (55.9781, 100%), phoenix (60.6617, 100%), raleigh (68.7099, 100%), sacramento (62.6989, 100%), san_antonio (49.5794, 100%), tampa (63.9649, 100%) |
| economic_opportunity | breakdown.resilience.score | atlanta (65.3953, 100%), austin (62.2069, 100%), boston (39.6809, 99%), charlotte (58.1466, 100%), chicago (54.2799, 99%), dallas (60.7902, 99%), denver (67.3495, 100%), houston (59.6531, 100%), la (61.1946, 99%), las_vegas (19.0057, 100%), miami (64.7727, 100%), nyc (53.0351, 93%), orlando (48.5674, 100%), philadelphia (49.6705, 100%), phoenix (63.035, 100%), raleigh (52.976, 100%), sacramento (79.177, 100%), san_antonio (64.0364, 100%), tampa (59.5326, 100%) |
| economic_opportunity | summary.anchored_balance | atlanta (-0.003, 100%), austin (0.018, 100%), boston (0.088, 99%), charlotte (-0.053, 100%), chicago (0.002, 99%), dallas (-0.035, 100%), denver (0.013, 100%), houston (-0.041, 100%), la (-0.016, 99%), las_vegas (-0.151, 100%), miami (0.011, 100%), nyc (0.118, 93%), orlando (-0.047, 100%), philadelphia (0.102, 100%), phoenix (-0.001, 100%), raleigh (0.015, 100%), sacramento (0.096, 100%), san_antonio (0.025, 100%), tampa (0.026, 100%) |
| economic_opportunity | summary.employment_to_population_pct | atlanta (63.8, 100%), austin (68, 100%), boston (65.4, 99%), charlotte (64, 100%), chicago (62.5, 99%), dallas (65.9, 100%), denver (68.4, 100%), houston (62.4, 100%), la (60.6, 99%), las_vegas (58.4, 100%), miami (60.1, 100%), nyc (60.5, 93%), orlando (61.3, 100%), philadelphia (61.6, 100%), phoenix (60.6, 100%), raleigh (65.9, 100%), sacramento (58.6, 100%), san_antonio (60.5, 100%), tampa (57.3, 100%) |
| economic_opportunity | summary.estabs_per_1k | atlanta (23.07, 100%), austin (24.54, 100%), boston (24.56, 99%), charlotte (23.57, 100%), chicago (22.73, 99%), dallas (21.53, 99%), denver (26.85, 100%), houston (19.89, 100%), la (26.51, 99%), las_vegas (20.47, 100%), miami (30.6, 100%), nyc (24.83, 93%), orlando (24.97, 100%), philadelphia (22.34, 100%), phoenix (19.96, 100%), raleigh (23.81, 100%), sacramento (20.45, 100%), san_antonio (18, 100%), tampa (24.67, 100%) |
| economic_opportunity | summary.industry_diversity_hhi | atlanta (0.111, 100%), austin (0.1168, 100%), boston (0.14, 99%), charlotte (0.1098, 100%), chicago (0.1196, 99%), dallas (0.1097, 100%), denver (0.1123, 100%), houston (0.1099, 100%), la (0.1124, 99%), las_vegas (0.131, 100%), miami (0.114, 100%), nyc (0.1321, 93%), orlando (0.1178, 100%), philadelphia (0.1332, 100%), phoenix (0.1134, 100%), raleigh (0.1219, 100%), sacramento (0.1153, 100%), san_antonio (0.1166, 100%), tampa (0.1195, 100%) |
| economic_opportunity | summary.market_quality_score | atlanta (67, 100%), austin (70.5, 100%), boston (58.6, 99%), charlotte (66.8, 100%), chicago (59.2, 99%), dallas (65.6, 99%), denver (76.7, 100%), houston (59.7, 100%), la (71, 99%), las_vegas (38, 100%), miami (69.9, 100%), nyc (63.7, 93%), orlando (58.8, 100%), philadelphia (52, 100%), phoenix (59.4, 100%), raleigh (60, 100%), sacramento (61.8, 100%), san_antonio (49.6, 100%), tampa (59, 100%) |
| economic_opportunity | summary.median_earnings | atlanta (45128, 100%), austin (49624, 100%), boston (56419, 99%), charlotte (43712, 100%), chicago (46819, 99%), dallas (45358, 100%), denver (52179, 100%), houston (42784, 100%), la (42463, 99%), las_vegas (39294, 100%), miami (37974, 100%), nyc (51762, 93%), orlando (37051, 100%), philadelphia (48344, 100%), phoenix (43713, 100%), raleigh (49056, 100%), sacramento (46404, 100%), san_antonio (38358, 100%), tampa (40868, 100%) |
| economic_opportunity | summary.net_estab_entry_per_1k | atlanta (0.42, 100%), austin (1.15, 100%), boston (0.57, 99%), charlotte (0.79, 100%), chicago (0.35, 99%), dallas (0.57, 99%), denver (0.37, 100%), houston (0.57, 100%), la (1.18, 99%), las_vegas (0.98, 100%), miami (0.68, 100%), nyc (0.73, 93%), orlando (0.93, 100%), philadelphia (0.46, 100%), phoenix (0.6, 100%), raleigh (0.68, 100%), sacramento (0.74, 100%), san_antonio (0.54, 100%), tampa (0.62, 100%) |
| economic_opportunity | summary.qcew_employment_growth_pct | atlanta (4.89, 100%), austin (5.72, 100%), boston (3.17, 100%), charlotte (5.13, 100%), chicago (2.65, 100%), dallas (4.51, 100%), denver (3.67, 100%), houston (4.87, 100%), la (1.99, 99%), las_vegas (6.26, 100%), miami (4.04, 100%), nyc (4.3, 93%), orlando (3.35, 100%), philadelphia (3.9, 100%), phoenix (4.1, 100%), raleigh (4.65, 100%), sacramento (1.95, 100%), san_antonio (3.6, 100%), tampa (4.66, 100%) |
| economic_opportunity | summary.qcew_employment_per_1k | atlanta (421.19, 100%), austin (429.21, 100%), boston (529.1, 100%), charlotte (441.59, 100%), chicago (436.45, 100%), dallas (448.23, 100%), denver (462.77, 100%), houston (382.23, 100%), la (416.42, 99%), las_vegas (404.78, 100%), miami (381.12, 100%), nyc (412.2, 93%), orlando (445.24, 100%), philadelphia (443.76, 100%), phoenix (410.83, 100%), raleigh (415.3, 100%), sacramento (338.14, 100%), san_antonio (368.08, 100%), tampa (385.34, 100%) |
| economic_opportunity | summary.unemployment_rate_pct | atlanta (5, 100%), austin (4.3, 100%), boston (5, 99%), charlotte (4.7, 100%), chicago (6.2, 99%), dallas (4.6, 100%), denver (4.3, 100%), houston (6, 100%), la (6.6, 99%), las_vegas (7.7, 100%), miami (5.2, 100%), nyc (6.5, 93%), orlando (5.3, 100%), philadelphia (6.1, 100%), phoenix (4.9, 100%), raleigh (4.2, 100%), sacramento (5.7, 100%), san_antonio (5.2, 100%), tampa (4.9, 100%) |
| economic_opportunity | summary.wage_p25_annual | atlanta (36210, 100%), austin (36920, 100%), boston (45010, 100%), charlotte (36310, 100%), chicago (37640, 100%), dallas (36020, 100%), denver (43910, 100%), houston (34860, 100%), la (38120, 99%), las_vegas (34330, 100%), miami (35800, 100%), nyc (40340, 93%), orlando (34850, 100%), philadelphia (36890, 100%), phoenix (37950, 100%), raleigh (35940, 100%), sacramento (39950, 100%), san_antonio (33490, 100%), tampa (35830, 100%) |
| economic_opportunity | summary.wage_p75_annual | atlanta (80090, 100%), austin (82910, 100%), boston (103210, 100%), charlotte (78020, 100%), chicago (83660, 100%), dallas (79750, 100%), denver (97210, 100%), houston (77670, 100%), la (90360, 99%), las_vegas (65570, 100%), miami (76990, 100%), nyc (101370, 93%), orlando (66560, 100%), philadelphia (82350, 100%), phoenix (77790, 100%), raleigh (79940, 100%), sacramento (93770, 100%), san_antonio (69290, 100%), tampa (75550, 100%) |
| public_transit_access | summary.nearest_heavy_rail.route_type | atlanta (1, 100%) |
