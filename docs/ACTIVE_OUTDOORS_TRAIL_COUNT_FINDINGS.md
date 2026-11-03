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
