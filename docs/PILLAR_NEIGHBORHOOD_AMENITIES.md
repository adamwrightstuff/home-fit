# Pillar Deep-Dive: Neighborhood Amenities

How `pillars/neighborhood_amenities.py` scores a location. Audit: `analysis/audit_amenities_2026-10-25.md`. Pending changes: `analysis/amenities_remove_location_proposal_2026-10-25.md`.

## v2 spec sheet

```
Pillar: neighborhood_amenities
Construct (one sentence): Access to a variety of daily-life businesses near home, within about a 10-minute walk (density, variety, essentials), plus access to a nearby business center. It is not a walkability score: street layout and walking routes are not measured, and Walk Score is not the target (owner decision 2026-10-26).
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
  proximity decay | linear, full credit within 400 m, zero at 1,200 m | judgment anchored on Walk Score's 5-minute (0.25 mile) full-credit point; Walk Score's own curve is not public and ends at a 30-minute walk | zero point 1,200 to 2,400 m, linear or exponential | proximity-only variants +2.5 to +4.2 points on average (analysis/amenities_proximity_decay_estimate_2026-10-26.md)
  home x0.6 + location 0-40 | 60/40 | judgment (added 2026-09-06) | 0.5 to 0.7 on home | mean -5.1 to +4.8 points
  location steps and divisors | 400/800/1200/1600 m; divisors 12.5/10/7.5/3.75 by area type | judgment | uniform divisor | mean -0.3, max 3.6 points
  grocery run | supermarkets only (convenience stores and greengrocers do not count) | USDA Food Access Research Atlas defines access to supermarkets, supercenters and large grocers (policy definition, not a study) | n/a | mean -1.1 points on stored records
Shared inputs with other pillars: business_list feeds Status Signal luxury presence; location quality and home score share one business list (correlation 0.86)
Pin-shift sensitivity (200 m): median 2.2 points, p95 about 12, max 69; 405 of 1,426 places move more than 5. Reported live as pin_sensitivity.
Independent validation source and result: none on file. Walk Score is not a matching source: it measures walkability (routes, street layout) and this pillar does not, so it is a reference for contrast, not a target (owner decision 2026-10-26); the 54-place comparison compared town averages with point scores and is not valid evidence. The "Walk Score Pearson 0.90" in commit e701eb5 is not reproducible here and predates location quality. Price sanity check (2026-10-26, tier 2, weak): within-metro Spearman of amenities score against median home value is 0.03 (median of 20 metros), against household income -0.21; rich suburbs are car-dependent, so this neither supports nor contradicts the score. Walk Score pull not done (needs owner permission).
All-places check: 2026-10-25, n = 1,476 (this audit)
Fail-loud conditions: failed or unconfirmed-empty Overpass read = no data with reason; empty read confirmed on a second endpoint = low score with warning; failed Places fallback = degraded
Launch check: scripts/qa/launch_check.py passes for amenities (urban core vs rural gap +48.2 against the owner's 20; 1.2% of places at 100, 3.3% at 0). Proposed pairs (not yet owner-approved, scores looked up first): West Village vs Plano 100 vs 35.5, Park Slope vs Sherborn 99.1 vs 0, Back Bay vs Hamilton 99.5 vs 0, Hayes Valley vs Los Altos Hills 97.6 vs 0, Lincoln Park vs Lakeway 88.3 vs 0 (all differ by 20 or more); West Village vs Greenwich Village 100 vs 100, Back Bay vs Beacon Hill 99.5 vs 91.5, Mission District vs Hayes Valley 98.8 vs 97.6 (all within 10).
Known data limits: OSM sparsity outside cities; chains included; 49 places score 0.0 because no tracked business lies within 1,500 m of the pin (verified by a control query on the private Overpass server); 43 places had stored coordinates that disagreed with the pin their business list was measured from; 36 were re-read at the stored pin, 5 (Tiburon, Youngtown, Cherry Hills Village, Corinth, Prosper) were re-read at the OSM place-node pin their old lists came from and the pin is recorded on the pillar (pin_used; the stored catalog coordinates are boundary-area centers 1.0 to 1.6 km away, and the other pillars were scored there), Highland Village keeps its previous score of 82.0 by owner decision although that list was measured at a different place 401 km away (flagged in its data warnings; at its own pin there is no business within 1.5 km and the retail cluster of 43 businesses is 2.7 to 4.0 km away), and Ridgewood, NJ (254 m; I first mistook it for Ridgewood, Queens, which has Google Places records and no mismatch) was re-read at its stored pin on 2026-10-27 (92.9 to 92.8); every catalog row now carries data_source, source_counts, limits and pin_sensitivity; stored Places grocery records have no subtype (counted)
Last re-validated: 2026-10-26
Re-validation schedule: quarterly (next 2027-01-26), and whenever the OSM source, the Places policy or the formula changes. Run: `PYTHONPATH=. python3 scripts/qa/launch_check.py`, `PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --no-unversioned --pillar neighborhood_amenities`, `PYTHONPATH=. python3 scripts/qa/amenities_pin_consistency.py` (exits 1 if any stored business list disagrees with its stored pin), then compare the live scorer with the catalog (docs/LIVE_SCORER_VS_EXPLORER.md).
```

## Components
| component | cap | signal |
|---|---|---|
| walkable density | 0-50 | log-scaled count of businesses within 800 m |
| variety | 0-25 | distinct types across tiers t1 to t4 within 800 m |
| essentials proximity | 0-25 | nearest supermarket, cafe or bakery, restaurant or bar, linear decay 400 to 1,200 m |
| location quality | 0-40 | pin distance to the center of nearby businesses, plus cluster variety and density |

Score = min(100, 0.6 x (density + variety + proximity) + location quality). Version tag (live and catalog): `amenities_v3_1_decay_grocery_2026-10-26` (v3 walkable density plus the supermarket-only grocery rule and the 400 to 1,200 m proximity decay).

## Owner decisions on the design (2026-10-26)
- The 60/40 split between home access and the nearby business center stays, as documented judgment. The score serves movers who walk to things and movers who drive to a town center; dense cores are unaffected by the split (West Village and Park Slope score 98 to 100 under any split), and it matters mostly for car-dependent suburbs (Plano 36 today, 22 at 80/20, 9 home only; Frisco 65, 59, 53).
- The 1,200 m reach stays. A longer, drive-distance reach (credit for a downtown several kilometers away, including in the next town) and a whole-town-boundary measure were considered and rejected as too messy: boundaries erase "near me" and break on neighborhoods and big cities, and a longer reach needs much larger map queries and overlaps with hub effects in other pillars. No published source sets the weight or the reach (searched 2026-10-26: hedonic distance-to-center studies, Huff gravity distance decay, resident surveys).
- Known consequence: a town whose shopping district lies beyond 1,200 m of the pin scores low even though it has amenities people use (Highland Village's retail cluster is 2.7 km from its stored pin; Preston Hollow, Granite Bay and similar places score 0.0).

## Known weaknesses
- Location quality measures the median coordinate of all nearby businesses, not a real town center, and counts auto-oriented clusters. Redesign pending.
- Every weight and threshold is judgment (table above).
- Pin placement matters: the walkable circle can miss the commercial strip. Spot-check a place's real main street if its score looks off.
