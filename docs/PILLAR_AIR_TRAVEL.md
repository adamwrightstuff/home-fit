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
