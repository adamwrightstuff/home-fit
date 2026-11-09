# Proposal: active outdoors wild term and the regional gap (2026-11-10). Proposal only, nothing changed.

## What the numbers say (stored catalog, 1,476 places)
Wild adventure is trail points at 15 km (budget 25, expected 24 destinations) plus trail points at 5 km (budget 15, expected 4) plus camping (budget 10). Northeast and Chicago minus other metros: wild 43.2 vs 28.3, gap 14.9 points = 15 km term 9.6, 5 km term 4.8, camping 0.6. Mean destinations at 15 km: 65.8 vs 20.2; at 5 km: 10.9 vs 4.4.
Evidence on the count (see results file): routes carry about 57% of the excess and the parks and protected land part about 43%; PAD-US confirms a real but smaller protected-land gap (0.63 to 0.80 SD against OSM's 1.13 SD); USGS does not show the route difference (OSM routes 26 vs 1 median, USGS trails 23 vs 15.5).

## Options
A. Keep as disclosed (done). No change to scores.
B. Replace the OSM destination count with the PAD-US count of named public protected units of at least 100 ha (both terms), keep camping. Independent of OSM tagging, uniform in every state, source is a government database.
C. Keep OSM but count only parks, reserves and protected areas (drop hiking routes) in both terms. Keeps the live scorer unchanged in data source. OSM undercounts large areas around the other metros (0.5 SD), so part of the overstatement would remain.
D. Cap route count at some level. Rejected: any cap is an invented constant with no source.

## Offline estimate for B, 15 km term only (all 1,475 places with a PAD-US count; 5 km term and camping left as stored)
Expected value refit as the catalog median of the PAD-US count (25.0; stored count median is 24.0), same saturation curve. Wild gap 14.9 to 9.4 points; active outdoors total gap 20.3 to 14.7; mean active outdoors change A -3.7, B +1.8, so the total score changes about -0.31 for A and +0.15 for B (the 8.7-point overall gap shrinks by about 0.5). 514 places move more than 5 active outdoors points, 63 more than 10. About 4.8 points of the wild gap (the 5 km term) are not touched by this estimate.
Biggest drops are Connecticut places with very high OSM counts and PAD-US counts of 5 to 9 (Wilton 80.5 to 60.0, Westport 92.5 to 72.2, Fairfield 93.5 to 74.9). Connecticut has a large real blue-blazed trail network, so this is a case where PAD-US may undercount hiking, not only where OSM overcounts. Biggest rises are Texas suburbs (Rowlett 52.3 to 65.4, Grapevine 66.1 to 78.2) and Glassboro NJ.

## Problems to settle before choosing B
1. PAD-US stops being independent. Level 2 check 4b validated trails against PAD-US protected land. If the term is built on PAD-US that check becomes circular and a different outside check is needed (USGS in good-coverage states, or the human check you set aside).
2. The live scorer uses OSM per request. B needs a national per-place PAD-US lookup table (the catalog could use it directly); the live scorer would diverge until that exists (docs/LIVE_SCORER_VS_EXPLORER.md).
3. The 5 km term needs PAD-US within 5 km, which needs a second pass over the 18 state files (1.37 GB re-download).
4. Border-state units are missing for places near RI, SC, VA, OR, ID and UT edges (PAD-US states not downloaded).
5. The 100 ha cutoff, 15 km and 5 km radii, budgets and camping are still unsourced.
6. PAD-US counts easements and state wildlife land that people may not hike (1,323 of 13,627 qualifying units are easement-only).

## Recommendation
B for the catalog and Explorer, staged: (1) re-download the PAD-US files and compute the 5 km count; (2) recompute wild, active outdoors and totals offline from stored camping and daily and water (no rescore); (3) report all 1,476 places who moves and why, including Connecticut, before anything is written; (4) a different independent check for the new term; (5) live scorer difference recorded, not fixed. If Connecticut-type places look wrong on inspection, fall back to C. Not recommended: A alone, because the largest regional effect stays in the headline score with no outside confirmation.

## Needs your explicit approval
The PAD-US re-download (about 1.37 GB, 18 files, same ScienceBase item as before), then each later step, then any push. No score, file in data/ or code has been changed so far.

## Update after the PAD-US re-run (2026-11-10): B is withdrawn, C is the recommendation
1. The OA/RA access filter I used undercounted the Northeast (unknown or closed access on 62% of its large units against 38% elsewhere). Corrected, PAD-US confirms more of the parks excess is real: overstatement 0.31 to 0.41 SD (was 0.50).
2. B on both terms moves 851 to 887 places by more than 5 points (352 to 361 by more than 10) and drops Connecticut places 16 to 23 points. Reasons found: access flags (Devil's Den recorded as closed or unknown), parcels under 100 ha, and units that are fragments of one connected network. B counts units, not networks.
3. Any cutoff or access rule chosen to rescue Connecticut would be fitting a constant to a result; not allowed without an independent source.
Recommendation now: C, drop hiking routes from the destination count in both terms and keep OSM named parks, reserves and protected areas of at least 100 ha. It targets the part with the weakest outside support (routes: OSM 26 vs 1 in the median, USGS 23 vs 15.5), keeps the OSM source the live scorer uses, and leaves the parks part, which PAD-US largely confirms. Its effect cannot be sized offline because the catalog stores totals only. Next step needs a trimmed Overpass re-read of all 1,476 places (about 4 seconds each, about 1.6 hours, both servers) to store routes and areas separately, then a refit of the expected values and an offline recompute, with the same all-places before and after report. No data or code has been changed.
