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
| Drive minutes, live | 10 + 0.95 x straight-line km | Fitted to 1,474 routed catalog pins (tier 2 proxy) | Intercept 9.5 to 11.4, slope 0.92 to 0.98 by area type; median error 4 to 9 minutes |
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

Proposed level: Level 1 candidate, not signed off. Level 2 checks not yet run (pin-shift on routed times, independent validation, launch pairs rerun).

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
Inputs and data sources (with vintage): BTS T-100 segment 2023; FAA CY2023 enplanements; airports.json (99 hand-listed airports); OSRM free-flow routed minutes (catalog, built 2026-10-25); fitted line 10 + 0.95 x km (live).
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
