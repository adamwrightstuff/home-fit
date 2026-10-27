# Place context and the single area type

`data_sources/place_context.py` holds the `PlaceContext` object that `main.py` builds once per request before any pillar runs. It carries coordinates, density, census tract, metro distance and the area type. It never carries a pillar's result.

## How the area type is decided (once)
1. One OSM business read at 1,500 m (covers the 1 km classification count and the widest amenities query).
2. A provisional type from density plus the raw 1 km count. It only budgets the Google Places top-up (call limit, whether OSM is thin enough to need it). It is stored as `provisional_area_type` for audit and never reaches a pillar.
3. At most one Places top-up at 1,500 m, only when the existing thin-OSM rule asks for it.
4. The final type is `classify_morphology` on density plus the 1 km count of the merged list. Nothing changes it afterwards: the post-pillar reclassification and the active outdoors re-score were removed. `_log_area_type_drift` only logs a warning when the amenities count would have said otherwise.

## What amenities does with it
Amenities takes the merged list from the context (trimmed to its own radius) and skips its own Places call. It falls back to its own OSM read, and its own Places call, when the list cannot stand in: vacation mode, `include_chains=False`, a failed OSM read, a radius over 1,500 m, or a shared-cache hit (the cache stores the type, not the businesses).

## Why the business list is not cached
Google's Places policy lets place IDs be stored indefinitely and says other Places content must not be pre-fetched, cached or stored beyond the allowed exceptions. The merged list therefore lives only on the request-local context. The shared pre-pillar cache (schema 2) stores the area type label, as before.

## Known limits
- Eleven pillars still re-derive an area type when called without one (direct calls, scripts). In the API path they always receive the context's value.
- Pillars take `area_type` and `density` as arguments rather than the whole object; only amenities takes `place_context`.
- Catalog results scored under older area types (249 places, 656 pillar results in the 2026-10-26 check) are not touched by this change.
