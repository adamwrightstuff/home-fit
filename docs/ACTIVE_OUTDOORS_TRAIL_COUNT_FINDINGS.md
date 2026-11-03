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
