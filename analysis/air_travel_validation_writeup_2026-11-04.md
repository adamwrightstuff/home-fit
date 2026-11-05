# Air travel access: independent validation write-up (2026-11-04)

Validator: an agent that did not build the pillar. Pass criteria are quoted from `docs/AIR_TRAVEL_VALIDATION_BRIEF.md` and were not changed after results. No existing file was edited, nothing was committed or pushed, no scoring changed. Random seed 42 for every draw. Scripts and raw outputs are in the scratchpad `/private/tmp/claude-501/-Users-adamwright-Dev-home-fit/48e098fe-7a59-4c3f-99f8-92253430d6a3/scratchpad/validator/` (sample.py, route.py, v1_routed.json, v2sample.py, v2calc.py, v3sample.py, v3check.py).

## Verdicts

| Check | Verdict |
|---|---|
| V1 drive minutes vs second router | FAIL (routed group passes, estimated group fails both tests) |
| V2 served destination counts vs published route lists | PASS on the numbers, with a major sourcing caveat (current pages, not 2023) |
| V3 pair spot check | NOT DONE as specified (no 2023 schedule source reachable); partial cross-check only |
| V4 construct sanity | NOT SCORED (lists proposed, owner confirmation required first) |

## V1. Drive minutes against Valhalla

Router: Valhalla public demo (valhalla1.openstreetmap.de), car ("auto") costing, no key. Requests: 62 in total (60 sample pairs, 1 connectivity test, 1 water-crossing pair), one at a time with 1.5 s pause, no retries needed, all 60 returned a route. Valhalla time is its own free-flow style car time; it is a different router from the OSRM used for the stored "routed" minutes, so the routed group is a router-to-router comparison, not a truth test.

Sample: 30 pairs with stored source `estimated_from_distance` (airports added 2026-11-04) and 30 with source `routed` (older airports). Pairs were drawn from the `nearest_airports` lists of all 20 final catalog files (7,380 place-airport pairs in total). Restrictions: straight-line distance 5 to 250 km, and the 14 + 11 pairs whose place has area type "unknown" were excluded. Stratified 6 pairs per area type (urban_core, urban_residential, suburban, exurban, rural) in each group, at most one pair per place. Stored minutes taken from the record's `drive_minutes`.

| Group | n | Median abs % error | Median abs error (min) | Mean signed (stored minus Valhalla) | Pairs off by more than 30 min |
|---|---|---|---|---|---|
| estimated (added airports) | 30 | 22.6% | 11.6 | +17.8 min | 9 |
| routed (older airports) | 30 | 13.5% | 5.4 | +1.5 min | 1 |

Criteria: median absolute percentage error <= 20% for both groups, and for the 30 estimated pairs median absolute error <= 10 minutes.
- Routed group: 13.5% passes.
- Estimated group: 22.6% fails the 20% limit and 11.6 minutes fails the 10 minute limit.
- Verdict: FAIL.

Where the estimate errs (descriptive only, not a change to criteria): the fitted line (10 + 0.95 x km) overestimates, and the overestimate grows with distance. Estimated group by straight-line distance: under 60 km (n=14) median error 3.5 min (17.0%); 60 to 120 km (n=7) median 12.8 min, all over; 120 km and more (n=9) median 42.8 min over (37.7%). By area type, median absolute error (min): urban_residential 3.2, urban_core 4.6, exurban 11.1, suburban 27.5, rural 36.1. The sample draws many far airports for suburban and rural places because the added airports are often the only remote candidates in the stored lists; the pillar's credit decays with drive time, so the effect on scores is bounded by that decay (not measured here).

Pairs off by more than 30 minutes (stored vs Valhalla, minutes), estimated group, all stored too high:
- Wendell NC to EWN 145.4 vs 114.4
- Gulfport FL to PGD 120.3 vs 89.3
- Washington Park (Denver) to CYS 164.1 vs 111.5
- Austell GA to CHA 147.4 vs 112.8
- Midlothian TX to TYR 152.1 vs 110.9
- Lewisville TX to TYR 169.3 vs 113.8
- Sloans Lake (Denver) to CYS 159.4 vs 105.1
- Lithonia GA to CSG 156.3 vs 113.5
- Castroville TX to LRD 209.0 vs 148.6

Routed group: Buford GA to TYS 246.0 vs 214.5 (stored too high). Also note two routed pairs where stored is lower than Valhalla by 15 to 20 minutes (Fayetteville GA to ATL 28.0 vs 46.5; Sandy Springs GA to ATL 36.1 vs 49.5), which reflects router differences in Atlanta traffic-free speeds, not a defect proven either way.

Water-crossing pair (not in the random draw, run as the brief asks): Bainbridge Island (47.6262, -122.523) to PAE. Stored 44.2 min (estimated). Valhalla 70.1 min (route uses the Seattle-Bainbridge ferry, 54.6 km). The stored value is 26 minutes low, so the estimate understates a water-crossing case here, the opposite sign from the long-distance overestimate. The random sample contained no other water-crossing pair, so this is the one known case.

Not done: no second routing service was tried; the public Valhalla demo's speeds are free-flow style defaults and were not tuned.

## V2. Served destination counts against published route lists

Sample: 40 airports with a nonempty served set (20 added 2026-11-04, source `ourairports`; 20 older), 5 from each quartile of 2023 boardings within each group, random within quartile (seed 42). Ours = size of our served set for that origin.

Published count source: the Wikipedia "Airlines and destinations" table for each airport, read through the fetch tool (page text converted to markdown and summarised by a small model, so counts are a summary-level read of the table, not a hand count of every row). Published count = unique nonstop destinations inside the United States (50 states plus the Washington DC airports, territories excluded), de-duplicated across airlines, seasonal included.

Major caveat: these pages were last edited in late 2026 and show routes through 2027 start dates. The brief asks for 2023 or early 2024 published lists. I did not find a way to read a 2023/early-2024 route map or timetable for 40 airports within the rules. So this check compares our 2023 served sets to current published lists. Expect current lists to be larger than 2023 for some airports (growth) and counts to include seasonal and very thin routes that our 52-departure rule excludes. Additional limits: for MCO, LGA, IAH the page was too long for one read, so I read two chunks and merged the names by hand (the last ~10 to 30 thousand characters of each page were not read); the other large pages were read for their first 100,000 characters only. Tiny Alaska and bush airports (OME, CDB, WRG) list air-taxi routes that are outside the FAA commercial file, so a mismatch there is partly a definition difference. HDN's page marked only one route year-round and many seasonal, and HYS's page listed one destination (our set has two).

Results (n=40): Spearman correlation 0.970; median absolute relative difference 22.3%.
- Added airports (n=20): Spearman 0.906, median abs relative difference 24.9%.
- Older airports (n=20): Spearman 0.983, median 17.5%.
- Sensitivity: year-round-only published counts where the page gave them (n=26): Spearman 0.910, median 13.3%. Dropping the four definition-mismatch airports (OME, CDB, WRG, HDN), n=36: Spearman 0.988, median 17.5%.

Criteria: Spearman >= 0.85 and median absolute relative difference <= 30%. Both met. Verdict: PASS on the numbers, subject to the sourcing caveat above. A caution on the correlation: about a third of the sample are airports with 1 to 3 destinations, which ties and pulls the rank correlation up; the median difference is the more informative number.

Airports with a difference above 50% (our count vs published):
- OME (added): 2 vs 16 (-88%), bush air-taxi routes, partly definitional
- HDN (added): 6 vs 18 (-67%), mostly seasonal winter routes on the page
- CDB (added): 3 vs 7 (-57%), air-taxi routes
- HYS (added): 2 vs 1 (+100%), page lists only DEN (a small count)
Next largest undercounts, between 38% and 47%: FCA 9 vs 17 (-47%), JAC 10 vs 17 (-41%), RSW 47 vs 78 (-40%), TRI 5 vs 8 (-38%), ECP 13 vs 21 (-38%). RSW is worth a look by the builder: a large airport undercounted by 31 destinations, though the page includes many 2026 additions and starts.

Per-airport table (ours / published): GRR 29/37, MCI 46/54, CID 13/17, GSO 14/15, LIT 14/19, AEX 4/3, HDN 6/18, OME 2/16, TRI 5/8, CLL 1/1, ART 1/1, SJT 1/1, ACT 1/1, ROW 2/2, LNY 3/2, HYS 2/1, BKW 2/3, CDB 3/7, WRG 2/3, SOW 1/1; MCO 97/117, SAN 59/77, SLC 82/97, LGA 76/81, IAH 109/122, STL 54/55, RSW 47/78, CMH 36/48, RDU 55/75, TPA 74/82, RNO 21/24, ECP 13/21, PVD 25/35, SAV 32/39, KOA 15/18, RDM 9/10, JAC 10/17, FCA 9/17, SBP 8/8, SBA 10/13.

Read check I could not close: two of the fetched pages looked internally odd (the RDU summary shared several rare carrier destinations with the MCO summary; the SBA page's map caption refers to another airport), which fits the summary-level read. Treat single-airport counts as approximate.

## V3. Pair spot check against an independent schedule source

NOT DONE as specified. I found no independent source I may read that gives scheduled nonstop service by city pair for 2023 (airline timetable archives and schedule databases need downloads or paid access; web search returned only news items for individual routes). What I did instead is partial and is not a 2023 test.

Sampling (done as specified): top 50 airports by 2023 boardings (includes SJU, which is not an origin, so it is used only as a destination). Ordered pairs (origin with a served set, destination any other top-50 airport): 2,401 pairs, 1,921 served by our sets and 480 not. Drew 100 served and 100 not-served pairs with seed 42 (list in `v3_sample.json` in the scratchpad).

Partial cross-check: for 11 airports I had already read a current Wikipedia destination list (MCO, SAN, SLC, LGA, IAH, STL, RDU, TPA, MCI, RSW, CMH). A pair is verifiable if either end is one of those. That covered 38 of the 100 served pairs and 40 of the 100 not-served pairs. Results against 2026 pages:
- Served pairs: 36 of 38 listed. The two not listed: RSW to MIA (not on the RSW page; unresolved) and TPA to SJU (San Juan excluded from my name lists as a territory, so a read artifact). So 37 of 38 effectively.
- Not-served pairs: 16 of 40 appear on a current page (SLC to CLE, RDU to MCI, SAN to DCA, SAN to CMH, SLC to CMH, RSW to LAX, RDU to SAT, SFO to RSW, MCI to SMF, CMH to MCI, SLC to PIT, SLC to IND, RDU to SAN, CMH to SNA, plus two reversed duplicates of these). This cannot be read as failures because the pages are 2026, not 2023.
- Spot confirmation of three of those 16 against dated sources: SAN to DCA began in 2024 (Alaska; DOT slot award October 2024), so correctly not served in 2023. SLC to PIT and SLC to CLE: Delta started them in 2018, they lapsed, and the relaunch was announced for 23 November 2024; so not served in 2023 is consistent. These came from web search result summaries, not full pages. The other 13 are unresolved. SLC to CMH and SLC to IND I could not date.

Criteria (at least 95 of 100 served confirmed in 2023; at most 5 of 100 not-served found with weekly nonstop in 2023): not evaluated. The partial numbers are encouraging for the served side and show the not-served side needs a dated schedule source (a BTS-independent one) to adjudicate the remaining 13.

Also noted while sampling: the served sets are not symmetric. 4 of the 100 sampled served pairs have no reverse-direction entry, and for the top 50 there are 35 asymmetric unordered pairs, of which most involve SJU (not an origin) and a few are real asymmetries (BWI with EWR, LGA and PHL; DCA with IAD; JFK with LGA; SFO with SJC; FLL, MIA with RSW). The pillar uses the origin's own set, so asymmetries matter only if a pair is missing in the direction a place uses.

## V4. Construct sanity (no pass gate)

Not scored. The brief says the agent proposes the places and the owner confirms before scoring, so I only checked that the proposed names exist in the final catalog files (names and states only, no air travel scores were read).

Proposed air-travel-rich (10), all in big hub metros: Park Slope (nyc), Midtown (nyc), Hoboken (nyc), Brookline (boston), Cambridge (boston), Palo Alto (sf), Evanston (chicago), Wicker Park (chicago), Capitol Hill (denver), Decatur (atlanta).

Proposed air-travel-poor (10), far from a hub or with a water barrier: Esparto (sacramento), Winters (sacramento), Galt (sacramento), Bainbridge Island (seattle), Castroville (san_antonio), Floresville (san_antonio), Boerne (san_antonio), Gold Canyon (phoenix), Wendell (raleigh), Midlothian (dallas).

Note: some of these (Boerne, Midlothian, Galt, Wendell) are within 30 to 60 minutes of a hub, so the owner may prefer to swap them for more remote catalog places; the catalog covers 20 large metros, so true remote places are few. Awaiting the owner's confirmation or edits before any score is read.

## What could not be done
- V1: only one second router (Valhalla demo), as permitted; no traffic or toll variation tested; the sample has one water-crossing pair (Bainbridge Island).
- V2: no 2023 or early-2024 published lists were obtained; used current Wikipedia tables via a fetch-and-summarise tool; MCO/LGA/IAH merged from two chunks with some of each page unread; no airport official pages used.
- V3: the 2023 schedule confirmation was not possible; only a partial cross-check on 78 of 200 pairs against current lists, with three dated spot confirmations.
- V4: owner confirmation pending, nothing scored.

## V1 rerun after refit

Requested by the coordinator after commit 56e18e88 (piecewise refit of estimated drive minutes, catalog recomputed into new files). Same 60 sampled pairs (seed 42), same criteria, no criteria changed. No new Valhalla requests: saved results from the first run were reused. Stored minutes were re-read from the new files under analysis/air_travel_dpv2_recompute_2026-11-04/final/. All 60 pairs are still present and no source label changed (30 estimated_from_distance, 30 routed), so no replacements were needed. The 30 routed values are unchanged; 29 of 30 estimated values changed.

| Group | n | Median abs % error | Median abs error (min) | Mean signed (stored minus Valhalla) | Pairs off by more than 30 min |
|---|---|---|---|---|---|
| estimated (added airports) | 30 | 17.0% | 7.3 | +12.9 min | 6 |
| routed (older airports) | 30 | 13.5% | 5.4 | +1.5 min | 1 |

Criteria: median absolute percentage error <= 20% for both groups, and median absolute error <= 10 minutes for the 30 estimated pairs. Estimated group 17.0% and 7.3 min, routed group 13.5%. Verdict: PASS.

Pairs off by more than 30 minutes (stored vs Valhalla, minutes), all stored too high:
- Estimated: Washington Park (Denver) to CYS 155.2 vs 111.5; Midlothian TX to TYR 143.7 vs 110.9; Lewisville TX to TYR 160.3 vs 113.8; Sloans Lake (Denver) to CYS 150.7 vs 105.1; Lithonia GA to CSG 147.7 vs 113.5; Castroville TX to LRD 198.6 vs 148.6. (Before the refit there were 9; Wendell, Gulfport and Austell dropped under 30.)
- Routed: Buford GA to TYS 246.0 vs 214.5 (unchanged).

Remaining pattern: the refit fixed the 60 to 120 km band (median error 12.8 min before, 5.6 now) but pairs of 120 km and more (n=9) are still about 34 min high on median (was 43). Under 60 km (n=14) is 3.1 min. Bainbridge Island to PAE was not re-evaluated (the water-crossing case sits outside the random sample and its Valhalla time of 70.1 min is from the first run; the new stored value was not re-read).

Independence note: the refit coefficients came from stored OSRM times, not from Valhalla, so this comparison against Valhalla is still independent. The sample was drawn before the refit and the refit was made after seeing the first V1 result, so the passing margin on the estimated group (17.0% against 20%, 7.3 against 10 min) is a post-hoc fit on the same pairs only in the sense that the builder knew the failure; the Valhalla times were not used in the fit.

## Rerun after FAA-to-IATA fix

Requested by the coordinator after commit d651e680 (35 FAA location IDs mapped to IATA codes, 30 airports added as origins, served sets rebuilt, catalog recomputed into the same final/ folder). Criteria unchanged. No new Valhalla requests and no new web reads: saved Valhalla results and saved published counts were reused.

### V1 (same 60 pairs, stored minutes re-read from the new files)

One pair is gone: Gold Canyon (Phoenix metro) to FLG. Gold Canyon's five nearest airports are now AZA (newly an origin, 27.9 min, estimated), PHX, TUS, SOW, PRC, so FLG dropped out of the stored list. Its routed Valhalla time was therefore not compared. I did not replace it, because a replacement needs a new Valhalla request, which is not allowed on this rerun. Routed group is n=29. No source labels changed on the 59 remaining pairs. The 30 estimated values are the same as in the "V1 rerun after refit" section (29 changed in the earlier refit, none now); routed values unchanged.

| Group | n | Median abs % error | Median abs error (min) | Mean signed (stored minus Valhalla) | Pairs off by more than 30 min |
|---|---|---|---|---|---|
| estimated (added airports) | 30 | 17.0% | 7.3 | +12.9 min | 6 |
| routed (older airports) | 29 | 13.6% | 5.3 | +1.2 min | 1 |

Pairs off by more than 30 minutes (all stored too high): estimated, Washington Park to CYS 155.2 vs 111.5; Midlothian to TYR 143.7 vs 110.9; Lewisville to TYR 160.3 vs 113.8; Sloans Lake to CYS 150.7 vs 105.1; Lithonia to CSG 147.7 vs 113.5; Castroville to LRD 198.6 vs 148.6. Routed, Buford to TYS 246.0 vs 214.5.

Criteria unchanged (median abs % error <= 20% for both groups; estimated group median abs error <= 10 min). Verdict: PASS (estimated 17.0% and 7.3 min; routed 13.6%).

### V2 (same 40 airports, served-set sizes recomputed from airport_nonstop_served_2023.json)

All 40 airport codes are still present in the served file and none changed code. Served-set size changed for 7 airports: GRR 29 to 30, CID 13 to 14, AEX 4 to 5, SAN 59 to 60, SLC 82 to 83, LGA 76 to 78, FCA 9 to 10. Published counts are the saved ones (current Wikipedia tables, with the same caveats as in the V2 section above).

- All 40: Spearman 0.970; median absolute relative difference 18.4% (was 22.3%).
- Added airports (n=20): Spearman 0.905, median 22.6%. Older airports (n=20): Spearman 0.987, median 17.5%.
- Airports with a difference above 50%: HDN 6 vs 18, OME 2 vs 16, CDB 3 vs 7, HYS 2 vs 1, and AEX 5 vs 3 (was +33%, now +67%, a small count).

Criteria unchanged (Spearman >= 0.85 and median abs relative difference <= 30%). Verdict: PASS, with the same sourcing caveat as before (current published lists, not 2023).

## V4 scored

Findings only, no pass gate. The owner confirmed the 20 proposed places ("all"), so the list is unchanged. Scores read from the served files data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl, key score.livability_pillars.air_travel_access.score. All 20 places were found.

Rich (score, nearest airports with drive minutes): Evanston 94.5 (ORD 44.5, MDW 43.4); Wicker Park 93.9 (MDW 20.4, ORD 38.0); Capitol Hill 93.4 (DEN 39.8); Decatur 91.1 (ATL 26.6); Hoboken 88.8; Midtown 88.8; Park Slope 88.7 (all three NYC airports within 41 min); Brookline 85.7; Cambridge 85.7 (BOS 19.2 and 15.5 min, but BOS carries 83.4% coverage and no second big airport inside an hour); Palo Alto 84.7 (SFO 30.3, SJC 31.6, OAK 40.1).

Poor: Midlothian 93.5; Gold Canyon 88.4; Wendell 80.5; Floresville 75.9; Boerne 74.9; Castroville 74.8; Winters 71.8; Esparto 67.9; Galt 67.5; Bainbridge Island 34.5.

Separation: Mann-Whitney U = 89 of 100 rich-over-poor pairs (a rank-sum probability of 0.89 that a random rich place outscores a random poor one). Normal-approximation z about 2.95, two-sided p about 0.003 (approximation, no exact tables used). Rich median 89.4 (range 84.7 to 94.5); poor median 74.9 (range 34.5 to 93.5). Lowest rich: Palo Alto 84.7. Highest poor: Midlothian 93.5.

Places on the wrong side, with the reason from the airport breakdown:
- Midlothian (Dallas metro), poor 93.5, above every rich place. It sits 43.1 min from DAL and 48.8 min from DFW (91.1% coverage). It is a drive-time hub place, not remote. This is my selection error (I had flagged it as within 30 to 60 minutes of a hub), not a scoring defect: with DFW inside the 60 minute plateau the score is correctly high.
- Gold Canyon (Phoenix metro), poor 88.4, above Palo Alto, Brookline and Cambridge. PHX is 49.2 min away (87.1% coverage), inside the plateau, and AZA is 27.9 min. Same reading: my label was wrong given a 49 minute drive to a major hub; the pillar measures reach to nonstop service, and this place has it.

Excluding those two mislabelled places, every remaining rich place (84.7 and up) outscores every remaining poor place (80.5 and below), a gap of 4.2 points between Palo Alto and Wendell, and the poor tail (Winters, Esparto, Galt, Bainbridge Island) is separated by distance to a hub or by a ferry. Bainbridge Island at 34.5 is the one case driven by the known water-crossing limit (PAE is credited 43.6 min by an estimate, SEA 118.2 min routed). Caveat: the poor group was chosen from the few remote places a 20-metro catalog contains, and several are only 40 to 60 minutes from a large hub, so a compressed gap is expected for an adequacy pillar.
