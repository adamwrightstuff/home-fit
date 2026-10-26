# Pillar Deep-Dive: Neighborhood Amenities

How `pillars/neighborhood_amenities.py` scores a location. Audit: `analysis/audit_amenities_2026-10-25.md`. Pending changes: `analysis/amenities_remove_location_proposal_2026-10-25.md`.

## v2 spec sheet

```
Pillar: neighborhood_amenities
Construct (one sentence): Walk-time access to daily life from home (density, variety, essentials), plus access to a nearby business center.
Reference frame: fixed standard (walk-time access, absolute counts, no area-type input in the home part)
  Evidence for the frame: tier 1 for the construct (Couture and Handbury: walking-time restaurant and nightlife density explains young college graduates' location choices). Says nothing about any number below.
Measurement area: pin + 800 m (10-minute walk) for the home part; business sample queried to 1,200 m (neighborhood scope) or 1,500 m (3,000 m in vacation mode)
  Reason: 800 m is a planning convention, not a validated cutoff. Walk Score gives full credit within about 400 m and decays to zero at a 30-minute walk; a decay curve is the proposed replacement.
Inputs and data sources (with vintage): OSM via Overpass (live), Google Places fallback when OSM is thin (83 of 1,476 catalog places)
Parameters:
  name | value | source | plausible range | sensitivity result
  walk window | 800 m | judgment | 600 to 1,000 m | mean -3.9 to +2.5 points, up to 33 at the max
  density curve anchor | log, 400 businesses | judgment | 200 to 800 | at most 3.5 points
  home split | 50 density / 25 variety / 25 proximity | judgment | 40/30/30 to 60/20/20 | at most 4.6 points
  variety tier points | 10 / 7 / 5 / 3 | judgment | 7/7/7/4 to 12/6/4/3 | at most 1.8 points
  proximity weights | grocery .45, cafe or bakery .30, restaurant or bar .25 | judgment | .34/.33/.33 to .6/.2/.2 | at most 2.2 points
  proximity steps | 150/300/500/800 m = 1.0/.85/.6/.35 | judgment | n/a | part of the window result
  home x0.6 + location 0-40 | 60/40 | judgment (added 2026-09-06) | 0.5 to 0.7 on home | mean -5.1 to +4.8 points
  location steps and divisors | 400/800/1200/1600 m; divisors 12.5/10/7.5/3.75 by area type | judgment | uniform divisor | mean -0.3, max 3.6 points
  grocery run | supermarkets only (convenience stores and greengrocers do not count) | USDA Food Access Research Atlas defines access to supermarkets, supercenters and large grocers (policy definition, not a study) | n/a | mean -1.1 points on stored records
Shared inputs with other pillars: business_list feeds Status Signal luxury presence; location quality and home score share one business list (correlation 0.86)
Pin-shift sensitivity (200 m): median 2.2 points, p95 about 12, max 69; 405 of 1,426 places move more than 5. Reported live as pin_sensitivity.
Independent validation source and result: none on file. The "Walk Score Pearson 0.90" in commit e701eb5 is not reproducible here and predates location quality.
All-places check: 2026-10-25, n = 1,476 (this audit)
Fail-loud conditions: failed or unconfirmed-empty Overpass read = no data with reason; empty read confirmed on a second endpoint = low score with warning; failed Places fallback = degraded
Launch check pairs: not yet defined
Known data limits: OSM sparsity outside cities; chains included; 50 catalog places have no score pending a re-read; stored Places grocery records have no subtype (counted)
Last re-validated: 2026-10-25 (audit only)
```

## Components
| component | cap | signal |
|---|---|---|
| walkable density | 0-50 | log-scaled count of businesses within 800 m |
| variety | 0-25 | distinct types across tiers t1 to t4 within 800 m |
| essentials proximity | 0-25 | nearest supermarket, cafe or bakery, restaurant or bar |
| location quality | 0-40 | pin distance to the center of nearby businesses, plus cluster variety and density |

Score = min(100, 0.6 x (density + variety + proximity) + location quality). Catalog version tag: `amenities_v3_walkable_density`.

## Known weaknesses
- Location quality measures the median coordinate of all nearby businesses, not a real town center, and counts auto-oriented clusters. Redesign pending.
- Every weight and threshold is judgment (table above).
- Pin placement matters: the walkable circle can miss the commercial strip. Spot-check a place's real main street if its score looks off.
