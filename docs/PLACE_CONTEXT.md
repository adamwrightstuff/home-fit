# Place context and the single area type

`data_sources/place_context.py` holds the `PlaceContext` object that `main.py` builds once per request before any pillar runs. It carries coordinates, density, census tract, metro distance and the area type. It never carries a pillar's result.

## How the area type is decided (once)
1. One OSM business read at 1,500 m (covers the 1 km classification count and the widest amenities query).
2. A provisional type from density plus the raw 1 km count. It picks the radius the amenities pillar would use (1,200 m or 1,500 m, from its radius profile for that type and the location scope) and budgets the Google Places top-up. It is stored as `provisional_area_type` for audit and never reaches a pillar.
3. At most one Places top-up, run on the OSM list trimmed to that radius, only when the existing thin-OSM rule asks for it. The radius matters: for Flatlands the top-up finds 16 grocery and bakery results at 1,200 m and 4 at 1,500 m, so a list built at one radius cannot stand in for the other.
4. The final type is decided from the surrounding 1 km circle (`data_sources/surrounding_density.py`): people per square mile over the tracts in the circle and people plus jobs per gross acre, both from local tables. The OSM business count and the Places top-up no longer change the type, so the provisional and final types agree. Nothing changes it afterwards: the post-pillar reclassification and the active outdoors re-score were removed.

## What amenities does with it
Amenities takes the merged list from the context and skips its own Places call, but only when its own radius for the final area type equals the radius the list was built at. Otherwise it falls back to its own OSM read and its own Places call: vacation mode, `include_chains=False`, a failed OSM read, a different radius (the final type's profile differs from the provisional one), or a shared-cache hit (the cache stores the type, not the businesses).

## Why the business list is not cached
Google's Places policy lets place IDs be stored indefinitely and says other Places content must not be pre-fetched, cached or stored beyond the allowed exceptions. The merged list therefore lives only on the request-local context. The shared pre-pillar cache (schema 2) stores the area type label, as before.

## How every pillar gets its place
Every pillar that depends on the area type or density (active outdoors, built environment, natural beauty, amenities, air travel, transit, healthcare, economic, housing, climate, social fabric, diversity, community safety, schools) takes `place_context=` and `main.py` passes the same object to all of them. The pillar reads `area_type` and `density` from it and no longer detects its own. The data-quality step (`assess_pillar_data_quality`, `get_expected_minimums`) takes the context's density too, so it does not fetch a second, possibly different, density from the Census.

`resolve_place_context` is the one resolver. Given a context it returns it unchanged and ignores any conflicting `area_type` or `density` argument. Given none (catalog batch scripts, tests, direct calls) it derives the place once, with the density-first rule each pillar used to carry its own copy of, and marks the result `area_type_source="derived_by_pillar"`. Density is fetched only when the type must be derived or the pillar needs it.

Four pillars used to ignore the type they were handed and re-detect it from density alone, without the business count: housing value, climate risk (for its data-quality step), healthcare (for its data-quality step) and transit (for its data-quality step). They now use the context's type. Housing value's Census lookup is area-type aware, so its score can move for places where the two types differed. Political lean and the shelved cost-of-living pillar do not use an area type.

## Known limits
- Direct calls without a context still derive per pillar (through the one resolver). The catalog batch scripts work this way; they are not changed here.
- Built environment, natural beauty and transit keep their own fallback inside helper functions for direct callers; with a context those paths are not reached.
- Catalog results scored under older area types (249 places, 656 pillar results in the 2026-10-26 check) are not touched by this change.
