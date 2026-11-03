# Active outdoors: what the trail count rests on (2026-11-03)

Status: findings only. No code, scoring or catalog change. Area type is not used as an input anywhere below.

## What the stored data holds
The catalog stores only `summary.trails.count_total` (within 15 km) and `count_within_5km`. It does not store the OSM tags or the feature types behind the count, so greenway and cycle routes cannot be separated offline. A read is needed for that; the one done on 2026-11-03 (owner approved in chat, Park Slope plus the 20 check 5 places, private server) is the only source of the mix.

## What the count rests on (from the code, `data_sources/osm_api.py`)
Every one of these is counted as a "trail": route=hiking relations (cycle routes dropped when bicycle is yes, designated or official, or the network is icn, ncn, rcn or lcn), piste:type ways, "(trails)" path entries for large parks, and area boundaries (boundary=national_park, leisure=nature_reserve, boundary=protected_area). Features carry only type, name and distance. Counts are not de-duplicated.

## What the 2026-11-03 read shows
Park Slope, 175 features within 9.3 miles: 20 hiking routes, 90 park path entries, 36 nature reserves, 29 protected areas. 8 of the protected areas are historic districts (Boerum Hill, NoHo) and others are ponds or islands. 22 features have no name.
The 20 check 5 places (`analysis/ao_trail_mix_pilot.csv`): in 6 places boundaries are more than half of the count (for example Mar Vista 189 of 212, Woodland Hills 262 of 295, Sauganash 108 of 167). Real hiking routes are 0 to 36 per place. Trail points (0 to 40) fall from 36.9 to 33.6 for Windsor Terrace and from 34.0 to 19.3 for Chinatown IL if boundaries are dropped, but from 35.1 to 16.3 for Mar Vista and 39.7 to 15.2 for Woodland Hills, which sit beside the Santa Monica Mountains where those boundaries are real wild land. So a filter on type alone would trade one error for another.

## Not answered offline
- Park Slope vs Brooklyn Heights and the other inner NYC places under a greenway filter: Brooklyn Heights and the other NYC places were not read, and greenway status is a tag the read does not keep (only names such as "Jamaica Bay Greenway (trails)" survive).
- Next read, if approved: also keep boundary area (bounding box) and protect_class, exclude historic districts, rerun the same 20 places. Waiting on the tunnel (port 12345 dropped).

## Numbers with no source (TODO)
Scale 56.5 trails per 15 km and 8.0 per 5 km (catalog medians of this same mixed count), budgets 25 and 15, any area threshold for boundaries, and any protect_class cutoff.

## Boundary size and protection class read (2026-11-03, same 20 places, owner approved in chat)
Tags and bounding boxes for every nature reserve, protected area and national park within 9.3 miles (about 2,700 features). Results:
- `protect_class` is missing on about 75% of features (for example 178 of 189 at Mar Vista), so it cannot be a filter.
- Bounding-box size does separate them. Features of at least 100 ha (bounding box, so an overestimate for long thin areas): Mar Vista 29 of 189, Woodland Hills 69 of 264, Sauganash 29 of 160, Chinatown IL 2 of 60. The biggest are the real wild land (Santa Monica Mountains NRA, Topanga, forest preserves); the small ones are pocket parks, ponds and historic districts.
- Sensitivity of trail points (0 to 40) for routes plus park paths plus distinct, non-historic boundaries of at least 50 / 100 / 500 ha: Mar Vista 21.3 / 20.2 / 17.2 (current 35.1), Woodland Hills 30.3 / 28.1 / 23.3 (current 39.7), Chinatown IL 18.8 / 17.0 / 15.2 (current 34.0), Windsor Terrace 33.6 / 33.4 / 33.1 (current 36.9). The within 5 km term is approximated from bounding box centres, so treat these as rough.
- Main finding: the inner NYC count is not mostly boundaries. At Windsor Terrace 112 of 160 are 26 hiking routes plus 86 "(trails)" entries, one per large park within 9.3 miles. A boundary filter leaves it almost unchanged. Whether many nearby parks with trails should saturate the trail term is a design decision, not a data-quality one.
- TODO (unsourced): the 50 / 100 / 500 ha cutoffs, de-duplication by name, the historic-district exclusion list, and the scale (56.5 per 15 km, 8.0 per 5 km).

## Extended read, 21 more places (2026-11-03, owner approved in chat; `analysis/ao_trail_mix_pilot2.csv`)
Includes Brooklyn Heights, 12 more NYC neighborhoods, Jersey City, Hollywood, Westwood, Koreatown, Santa Monica, Lincoln Park, Evanston and Winnetka.
- Park Slope vs Brooklyn Heights: live raw trail counts are 175 vs 193 and trail points 37.9 vs 38.7, so they are nearly the same. The stored wild gap (31.0 vs 34.8) is not a real difference in trails.
- Stored `count_total` is exactly 30 for 136 of 1,476 catalog rows (NYC 67, Chicago 19, SF 18, Philadelphia 12, LA 5, Boston 6, others 8) while live reads give 90 to 250 for the same NYC places. 30 is the old urban trail cap, so those rows still carry capped trail counts, and their wild scores are not comparable with uncapped rows. The true count behind them is not stored, so fixing them needs a read (TODO owner decision). Some of the 136 may be genuine 30s.
- Dense NYC places read 170 to 193 raw features regardless of neighborhood, 74 to 91 of them "(trails)" path entries named per path, not per park. Examples seen at Park Slope include "Cycleway Path (trails)", "Leif Ericson Drive (trails)", "Hudson River Waterfront Walkway (trails)" and several "Greenway (trails)". A name-based greenway and cycleway filter on this type is possible, but the names were not saved for this run; one repeat read that saves names would be needed to size it.
- Routes plus park paths alone give 30 to 36 trail points in every inner NYC place (versus 8 to 13 for LA coastal places like Hollywood and Santa Monica, where boundaries carry the score). So a boundary filter does not touch the NYC result; a path-type filter would.
- TODO (unsourced): any name list for greenway or cycle paths, and what share of park path entries it would remove.

## Park Slope path names (repeat read, 2026-11-03; `analysis/ao_parkslope_park_path_names.json`)
90 "(trails)" entries, 81 distinct names, none unnamed. 28 of 90 (31%) match greenway, cycleway, bike path, bridge path, promenade, esplanade, avenue or boulevard words (for example "Hudson River Greenway", "Manhattan Bridge Bike Path", "Flatbush Avenue", "Belt Parkway Bike Path"). Many of the other 62 are not trails either: golf courses (Marine Park Golf Course, Liberty National Golf Club), piers and beaches (Canarsie Pier, Midland Beach, Breezy Point Tip), a bridge (Bayonne Bridge), and the same park repeated ("Park (trails)" three times, "Jamaica Bay Greenway" three times).
Effect on the 15 km trail term at the current scale (56.5, budget 25): 20 routes plus 90 path entries (110) scores 21.4 of 25; removing the 28 name matches (82) scores 19.1. So a name filter lowers Park Slope by about 2 points of trail term, and does not remove the saturation. The scale itself (a catalog median of this mixed count) is what makes any count above about 80 look near the maximum. TODO (unsourced): the word list, whether golf courses and piers should count, and the scale.

## Scope of a clean-count rebuild (2026-11-03, plan only, nothing run)
Goal: replace the mixed count with one that counts real hiking routes and distinct parks with trails, then refit the scale. All definitions below are TODO until the owner approves them.

Candidate count (every piece unsourced): hiking routes (route=hiking minus cycle routes, as now); one entry per named park or reserve with paths, not per path, dropping golf courses, piers, beaches and street or bridge paths by name; boundaries only at or above a size cutoff, one per name, historic districts excluded. No area type input.

Reads: the catalog stores only totals, so every place needs a fresh read: 1,476 places, 931 on the first server (NY NJ CT CA WA TX IL IN PA DE MD) and 545 on the second (AZ CO FL GA MA NC NV, which the owner would have to open). Measured rate of the full read function in this session: 21 places in 31 minutes, about 1.5 minutes per place, so about 37 hours one stream. A trimmed trail-only query is untested; a 5-place timing test would show whether it is much faster. Parallel tabs gave little speedup on 2026-11-03, so plan for the sequential figure unless the trimmed query is fast.

Offline after the reads: refit the scale (median of the clean counts at 15 km and 5 km), recompute wild for all 1,476 places, recompute totals and composites from stored daily and water, health check, then an independent verifier rerun of checks 3, 4b and 5. Daily and water are not rescored.

Risks: every wild score moves, so every launch comparison moves; the budgets (25 and 15) and camping limits stay unsourced; a new scale fitted to the same catalog is still relative, not a published standard.

Decisions for the owner: approve the definition (or a simpler one), accept the read time or approve the 5-place timing test first, and open the second server for the 545 places.
