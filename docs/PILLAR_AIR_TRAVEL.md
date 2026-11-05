# Pillar Deep-Dive: Air Travel Access

How `pillars/air_travel_access.py` scores a location. Rebuilt 2026-10-25 to meet design principles v2 (replaces the
drive-time band model, which was a five-step function with unsourced speeds and hand-set service levels).

## What it measures
How much of where Americans fly you can reach nonstop from the airports within reach of a place. It is an
**adequacy measure on a fixed national standard** (P1), not a peer comparison.

Score (0 to 100) = share of national domestic passenger boardings (FAA CY2023) whose airport is served nonstop by at
least one airport you can reach. Each reachable airport counts with a **time credit**: 1.0 up to 60 minutes of driving,
then the share of people still willing to travel that long, relative to the share at 60 minutes. For each destination
the best credit among the airports serving it is used, so a destination reachable from two airports is not counted
twice. The ceiling is about 96, not 100, because you cannot fly to the airport you are standing in.

## Parameters (P4: source, tier and plausible range)
| Parameter | Value | Source (tier) | Plausible range / note |
|---|---|---|---|
| Nonstop service | 52+ departures in 2023 and 5+ passengers per departure | BTS T-100 Segment, all carriers, 2023 (tier 2, revealed) | The weekly and load cut-offs are definitions, not fitted; they remove charters and cargo (Memphis falls from 60 to 29 destinations) |
| Destination weights | CY2023 boardings per airport | FAA final CY2023 enplanements (tier 2) | Includes connecting passengers at hubs |
| Plateau | 60 minutes of full credit | Median maximum acceptable travel time, Ipsos survey for Airlines for America, Jan 2018, n=5,046 (tier 3) | **Judgment**. Range 30 to 90 minutes; catalog mean 76 to 87, spread 13 to 5 |
| Decay beyond the plateau | Survey distribution of maximum acceptable time (33% at 30 min, 60% at 60, 78% at 90, 90% at 120, 94% at 180) | Same survey | The question was about travel for a cheaper flight, so beyond the plateau this is a stretch |
| Drive minutes, live and for airports without routed time | Piecewise line: 8.0 + 1.04 x km, slope changes -0.313 beyond 30 km, +0.198 beyond 60, -0.008 beyond 120, -0.333 beyond 250 (refit 2026-11-04; replaces 10 + 0.95 x km, which ran long beyond 60 km) | Least-absolute-deviation fit to 8,504 stored OSRM pin-to-airport routes (tier 2 proxy) | Split-half: intercept 7.6 to 8.5, first slope 1.02 to 1.06; held-out median error within 0.7 min in every distance band |
| Drive minutes, catalog | Routed time to the 6 nearest served airports | OSRM public server, car profile, free-flow | Not validated against a second source; see limits |

Evidence that did not hold: a published decay rate (none found in a search of the airport-choice literature), and a fit of
the decay to boardings (not identifiable, error about a factor of 3). The survey exponential was tried first and
rejected because the survey measures willingness to travel farther than necessary for a cheaper flight, not the
quality of the nearest airport.

## Fail-loud (P9)
If the airport file or the coverage file is missing or empty the scorer raises and the pillar shows as no data (weight
redistributed by the existing mechanism). A place with no served airport within 400 km scores 0, which is a real
result. Pins whose routed trip is slower than 45 km/h (road-adjusted) carry `routed_drive_time_unusually_slow`, and
live-estimated minutes are marked `drive_minutes_source: estimated_from_distance` in the summary.

## Results on the 1,476 catalog places
- Mean 80.3 to 85.3, spread 15.7 to 7.1, distinct values 18 to 47, maximum 100 to 96.
- Metro means from Chicago and Dallas (92) down to Seattle (72) and Sacramento (65). Urban 87, rural 80.
- Pin shift of 500 m: median 0, maximum 0.6 points (the old step score jumped up to 16).
- Launch check: WARN. 19% of places share the score 87 (the plateau), and the urban-over-rural contrast gap is 7.7
  against a minimum of 10. The pillar separates places who live near a major hub from those who do not, and little
  beyond that; this is an adequacy result like healthcare.

## Known limits
- Domestic destinations only; international nonstops (JFK, MIA, ORD) add nothing.
- Routed times are free-flow with no traffic, and the public server sometimes starts a trip on a slow service road
  (Summerlin to Harry Reid shows 58 minutes). Ferry crossings are not modelled (Bainbridge Island scores 23).
- The plateau is a judgment; the table above shows how much it matters.
- Coverage counts destinations by how busy they are, so a small airport that serves the busiest 20 destinations
  scores well. Frequency and fares are not measured.

## Data and rebuild
`data_sources/static/airport_nonstop_served_2023.json` is built by `scripts/baselines/build_airport_nonstop_served.py`
from the BTS and FAA files named in its docstring. Catalog drive minutes are in `data/airport_drive_minutes_catalog.json`.
Catalog rescore: `scripts/catalog/recompute_air_travel_coverage_offline.py` (offline), then
`recompute_catalog_composites.py --no-census` for the total, happiness and longevity composites.

---

## DPv2 spec sheet and audit (2026-11-04, DRAFT for owner review; no scoring changed)

Level: 1 (Converted). Signed off by the owner 2026-11-04 with TODOs (a) to (h) below accepted. Not pushed to main; new catalog files not yet swapped in. Level 2 not reached: independent validation not yet run, and one pre-registered all-places criterion failed (see Level 2 results).

### Evidence search (one standard search per topic, read from summaries only; full papers not read)
- Airport choice in multi-airport regions (Los Angeles, Bay Area, Washington/Baltimore, Sao Paulo; Hess 2014 review): access time and flight frequency both significantly drive choice. Frequency shapes which airports are considered; access time dominates the final pick. Nonstop availability is a standard mixed-logit variable. Tier 1 for "service level and access time both matter". Source examples: https://eprints.whiterose.ac.uk/43626, https://www.economics.uci.edu/files/docs/colloqpapers/f06/VanDender.pdf
- Accessibility measure literature: gravity (decay) versus cumulative-opportunities within a threshold; a Turkish airport study used a 2 h catchment gravity measure. No published decay rate for drive time to an airport found. https://findingspress.org/article/32444
- Residential price evidence: only noise and proximity hedonics with conflicting signs (Atlanta 2008: farther sells for less after noise; New Zealand 2025: sign differs by city). Nothing pricing nonstop destinations or frequency. No migration study found. So tier 2 is empty.
- Conclusion: direction (service reachable within a drive-time decay) is supported at tier 1 for the construct. The decay shape and the 60 minute plateau have no tier 1 or 2 source; they rest on a tier 3 survey (Ipsos/A4A 2018). Value of time cited at about $68 per hour (Warburg et al. 2006, via a review; unverified).

### Spec sheet
```
Pillar: air_travel_access
Construct (one sentence): Access to nonstop service: the share of national domestic boardings at destinations served nonstop from airports reachable by driving, discounted by drive time.
Reference frame: fixed standard (adequacy on a national scale).
  Evidence for the frame: construct tier 1 (airport-choice studies, summaries only); decay and plateau tier 3 (Ipsos/A4A survey); tier 2 none found.
Measurement area: drive-time reach to airports up to 400 km straight line, credit decays after 60 min.
  Reason: access pillar; airport choice studies use access time; the cutoff is a judgment (range 30 to 90 min).
Place context inputs used (fields) and remaining area-type uses (with reason): pin coordinates only. Area type and density are read from the context for response metadata only; no scoring value keys on them. Live path still calls the Census density lookup when no context is passed, only to fill metadata (TODO: skip it).
Inputs and data sources (with vintage): BTS T-100 segment 2023; FAA CY2023 enplanements; airports.json (99 hand-listed airports); OSRM free-flow routed minutes (catalog, built 2026-10-25); piecewise fitted line (live and new airports; see Parameters).
Parameters: see table above. Unsourced: plateau (judgment), 52 departures and 5 passengers cut-offs (definitions), 400 km candidate radius (credit below 6%).
Shared inputs with other pillars: none.
Pin-shift sensitivity: 500 m, median 0, max 0.6 (recorded 2026-10-25, fitted-line path); not rerun on routed times.
Independent validation source and result: none yet. Candidate: BTS T-100 nonstop counts from the airports themselves cannot validate themselves; needs an outside source (see brief, step 5).
All-places check (2026-11-04, stored values, n=1,476): mean 85.3, median 86.8; 280 places (19%) at 87; 7 at 95 or more; 1 at 20 or less; none at 0. By area type mean: urban_residential 86.8, suburban 85.8, exurban 85.4, rural 80.0.
Fail-loud conditions: missing airport or coverage file raises (no data); no served airport within 400 km scores 0 (real); slow routed trips flagged (79 places).
Launch check pairs: not rerun. Earlier result WARN (plateau clumping, urban over rural gap 5.2 to 7.7 against minimum 10).
Known data limits: origin set is 99 airports, 30 of the top 100 by boardings are missing as origins (see audit). Domestic only. Frequency and fares not measured. Free-flow drive times. Ferries not modelled. Vacation catalog records (49) are on the old model.
Last re-validated: never under DPv2.
```

### Audit gap table (stored data only; no API or download used)
| # | Gap | Evidence | Recommended fix | Expected impact |
|---|---|---|---|---|
| 1 | Origin airport set is 99 hand-listed airports. 30 of the top 100 by boardings are missing: EWR, DCA, SJC, OAK, MCI, PIT, JAX, BDL, HPN, PSP, PIE, SFB and others. The origin set holds 84.2% of boardings. | `airports.json` vs boardings in `airport_nonstop_served_2023.json` | Add every commercial airport with coordinates and rebuild the served sets (needs BTS and FAA files, and OSRM times for new pairs) | Largest. Catalog places within 45 km straight line of a missing airport (my approximate coordinates, unverified): EWR 150 and HPN 121 (NYC), OAK 103 and SJC 35 (SF), PIE 44 (Tampa), SFB 31 (Orlando). Most already reach JFK, SFO or a similar hub, so likely a few points up, but not measurable offline |
| 2 | Vacation catalog (49 records) is on the old model; Newport lists MVY, BOS, ACK and no PVD | stored record has no method field | Not a data gap: current code finds PVD for Newport (36.7 min, offline score 59.7 against stored 74). Recompute vacation records with current code | Newport 74 to about 59.7; Vail 65 to about 50.2 (my approximate pins) |
| 3 | Plateau 60 min and decay are survey-based, not tier 1 or 2 | no published decay found | Keep, record range 30 to 90, report sensitivity (catalog mean 76 to 87) | None now |
| 4 | Plateau clumping: 19% of places at 87 | stored scores | Accept as adequacy ceiling (like healthcare) or lower the plateau; owner decision | Spread only |
| 5 | Live path calls the Census density lookup only for metadata | code | Skip it when no scoring use (principle 13) | None on score |
| 6 | No independent validation, pin-shift on routed times not run | none | Level 2 brief | None |
| 7 | Frequency not measured (literature says frequency shapes choice sets) | T-100 has departures | Optional second input; needs rebuild of the served file with departure weights | Unknown |

### Level 2 pass criteria (written 2026-11-04 before any Level 2 result was computed)
Origin set now 412 airports (served sets from BTS T-100 2023, rebuilt 2026-11-04). The builder ran checks 1 to 4; check 5 is for another agent (brief in `docs/AIR_TRAVEL_VALIDATION_BRIEF.md`).
1. Pin shift (all 1,476 places, shifts N/E/S/W, fitted-line minutes for every airport so only geometry moves). PASS: 500 m median change <= 1.0 and 95th percentile <= 3.0; 1,000 m median <= 2.0 and 95th <= 6.0.
2. Fitted line versus routed (stored catalog minutes). PASS: median absolute score difference <= 3 and 95th percentile <= 10. This bounds the error on the 313 new airports, which use the line.
3. All-places (new catalog). PASS: no single rounded score above 15% of places; at least 40 distinct rounded scores; at most 2% of places at 99.5 or above; urban residential mean minus rural mean >= 10 (the earlier launch criterion; failing it is reported, not hidden).
4. Launch pairs. Should differ by >= 15 points: Park Slope (nyc) vs Esparto (sacramento); Midtown (nyc) vs Galt (sacramento); Palo Alto (sf) vs Bainbridge Island (seattle). Should be within 4 points: Park Slope vs Brooklyn Heights (nyc); Cambridge vs Brookline (boston); Mountain View vs Sunnyvale (sf).

### Level 2 results (2026-11-04, run by the builder; independent validation still open)
Catalog: 1,476 places on the 412-origin model (new files, not yet the served catalog).
1. Pin shift, all 1,476 places, 4 directions, fitted-line minutes: 500 m median 0.0, 95th percentile 0.2, max 0.7; 1,000 m median 0.0, 95th 0.4, max 1.4. Worst area type: rural (95th 0.5 and 1.1). PASS. Caveat: routed times cannot be moved, so this tests geometry only; a snapped-to-road routing jump is not covered.
2. Fitted line versus stored scores: median absolute difference 0.1, 95th percentile 3.9, max 49.9 (signed mean -0.29). PASS on the median and 95th. The max is a water-crossing or snapping case. Caveat: the stored scores use routed minutes only for the 99 older airports, so this bounds the line against routed times where they exist; for the 313 new airports there is no routed truth, which is what V1 in the validation brief tests.
3. All-places: largest single rounded score 11.6 percent (87 earlier 19 percent), 46 distinct rounded scores, none at 99.5 or above, none at 0.5 or below. By area type (10th / median / 90th): urban residential 84.2 / 88.6 / 93.5; suburban 83.8 / 86.8 / 92.7; exurban 78.7 / 87.3 / 92.3; rural 65.4 / 85.0 / 92.2; urban core 86.2 / 87.0 / 87.4 (n=16). Clumping, distinct values and ceiling criteria PASS. Urban residential minus rural mean is 7.0 against the required 10: FAIL. This is an adequacy result (most places can reach a major hub); the criterion is reported, not relaxed.
4. Launch pairs: Park Slope 88.7 vs Esparto 67.5 (21.2, PASS); Midtown 88.7 vs Galt 67.1 (21.6, PASS); Palo Alto 84.7 vs Bainbridge Island 34.4 (50.3, PASS, but see limit); Park Slope vs Brooklyn Heights 88.7 and 88.7 (PASS); Cambridge 85.3 vs Brookline 85.4 (PASS); Mountain View 84.7 vs Sunnyvale 84.7 (PASS). All 6 pass. Note the similar pairs are close partly because they share pins' airports, which is expected.
5. Independent validation: NOT RUN. Brief with fixed pass criteria: `docs/AIR_TRAVEL_VALIDATION_BRIEF.md`. It needs a second routing source and published route lists, so it needs owner approval of any keyed service.

Changes this session (2026-11-04): origins 99 to 412 (359 airports added from OurAirports; 313 have nonstop service); served sets rebuilt from BTS T-100 CY2023 (old 99 airports unchanged except SDM, now no qualifying service); per-airport `drive_minutes_source` and summary value `routed_and_estimated`. Catalog recompute: mean 85.3 to 86.1, none lower, 518 up by 1 or more, 15 by 5 or more; diff in `analysis/air_travel_dpv2_diff_2026-11-04.csv`.

Open items and TODOs for sign-off: (a) independent validation; (b) urban over rural criterion failed; (c) Bainbridge Island rose 22.7 to 34.4 because PAE is credited 44 estimated minutes with no ferry modelled, likely overstated, same ferry limit as before; (d) plateau 60 minutes and survey decay unsourced at tier 1 or 2 (range 30 to 90); (e) frequency not measured; (f) vacation catalog (49 records) not yet recomputed; (g) live path density lookup for metadata only; (h) 46 FAA airports without a US coordinate in OurAirports are not origins (mostly Alaska strips and territories; none checked for catalog proximity).
Proposed sign-off: Level 1 now, with TODOs (a) to (h) accepted. Level 2 after the validation brief passes and the owner accepts or overrules criterion 3's urban-rural gap.

Sign-off: Level 1, owner, 2026-11-04. Accepted TODOs: (a) to (h) above. Level 2 pending the validation brief.

Owner decision 2026-11-04: all-places criterion 3 (urban residential minus rural mean >= 10) is accepted as an explained failure. Reason: air travel is an adequacy pillar on a fixed national standard (like healthcare); 7.0 reflects that most places reach a major hub, not a defect. It is recorded here, not relaxed in the criteria above.

### Independent validation results (2026-11-04, validator agent; write-up `analysis/air_travel_validation_writeup_2026-11-04.md`, seed 42)
- V1 drive minutes vs Valhalla (60 pairs): first run FAIL on estimated airports (22.6 percent, 11.6 min). Cause confirmed offline: the single drive-time line ran long beyond 60 km. After the piecewise refit (commit 56e18e88): estimated group 17.0 percent and 7.3 min, routed group 13.5 percent, against limits of 20 percent and 10 min. PASS, criteria unchanged. Remaining: pairs of 120 km or more are still about 34 min high, 6 pairs off by over 30 min (all stored too high, so scores are conservative); Bainbridge Island to Paine Field is stored 44 min against 70 by ferry (stored too low).
- V2 served counts vs published route lists (n=40): Spearman 0.970, median absolute relative difference 22.3 percent. PASS. Caveat: current Wikipedia tables read through a summarising fetch, not 2023 data.
- V3 pair spot check: NOT DONE as specified (no 2023 schedule source found). Partial: 37 of 38 served pairs listed on current pages; 16 of 40 not-served pairs appear on current pages, 3 of them dated as post-2023 additions, 13 unresolved. Written reason none exists: free 2023 schedule data was not reachable.
- V4: not scored; 20 proposed places await owner confirmation (findings only, no pass gate).

Proposed level: Level 2 (Verified), for owner sign-off, with these accepted items: V3 not done (reason above), V2 sourced from current pages, urban-rural gap 7.0 (accepted 2026-11-04), Bainbridge Island ferry overstatement, long-distance estimates about 34 min high, plateau and survey decay unsourced (range 30 to 90 min), frequency not measured, vacation catalog not recomputed, 46 FAA airports without a US coordinate not origins. Not Level 3: plateau, decay, and the 52-departure and 5-passenger cut-offs have no tier 1 or 2 source.
Last re-validated: 2026-11-04 (builder checks 1 to 4, validator V1 to V3). Level 2 not signed off.

### Update after the FAA-ID to IATA fix (2026-11-04, commit d651e680)
Finding: 35 airports in the FAA enplanement file use FAA location IDs, not the IATA codes BTS uses (IWA is Mesa Gateway AZA, GPI is Glacier Park FCA, HXD is Hilton Head HHH, plus Yuma, State College, Marquette, Concord NC and Alaska/territory strips; 0.24 percent of boardings). They could not be reached as destinations or used as origins. Fix: `data_sources/static/faa_id_to_iata.json` (built by `scripts/baselines/build_faa_id_to_iata.py`, unique OurAirports matches only, none ambiguous), applied in the build scripts. Origins with service: 411 to 424 (30 airports added). Remaining airports without a US coordinate (17: territories, one seaplane base) are not origins; this resolves item (h) except those.
Catalog recompute (new files only): mean air score 85.3 to 86.3, none lower, 631 places up by 1 or more, 17 by 5 or more. Builder checks rerun, unchanged: pin shift 95th percentile 0.1 (500 m) and 0.2 (1,000 m); largest rounded score 12.5 percent; all 6 launch pairs pass; urban residential minus rural 6.9 (accepted).
Validator rerun (same samples, criteria unchanged, no new requests): V1 estimated group 17.0 percent and 7.3 min, routed group 13.6 percent over 29 pairs (Gold Canyon to FLG dropped out of the nearest five because AZA now ranks ahead; not replaced because that needs a new Valhalla request). V2 Spearman 0.970, median relative difference 18.4 percent. Both PASS.
Vacation recompute (new file `analysis/vacation_destinations_scores.air_travel_dpv2_2026-11-04.jsonl`, not swapped in): 44 of 49 records recomputed (Galveston, New Orleans, San Francisco, Boston, Scottsdale have no stored airport breakdown); air score mean change -11.4, total score -1.5. Product decision pending: the old vacation scores were largely a flat 76, the new model rewards reach to many nonstop destinations.
Level 2 remains a proposal for owner sign-off (not signed).
