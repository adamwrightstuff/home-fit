# Backlog

Non-urgent follow-ups noted during work, not yet scheduled.

---

## Hardcoded NB/AO preference floors won't generalize past the current 4-metro catalog

**Where:** `frontend/lib/nbPreference.ts` (`NB_PREFERENCE_FLOOR`), `frontend/lib/aoPreference.ts`
(`AO_PREFERENCE_FLOOR`) — added when NB/AO scenery preferences were switched from an OWA blend
to true AND-filters (commit `6d7b639`).

**Issue:** Floors are constants, hardcoded from the 40th percentile of each component's
distribution across the *current* catalog (NYC/SF/LA/Seattle — all temperate, coastal-adjacent
metros). This is fine for `water_score`/`topo_score` (not regionally normalized — absolute
distance/elevation metrics, so they generalize nationally without adjustment) and for the
`ocean`/`lakes_rivers` water-type match (categorical geographic fact, not a score threshold —
a landlocked place fails on `water_type`, not the floor).

It's a real gap for `canopy_score`/`gvi_score`: these ARE regionally normalized in the backend
(`_v9_regional_normalize`, climate-zone-adjusted) so the *score* already accounts for region, but
the floor constant was tuned only on temperate-metro data. A desert or plains metro's normalized
canopy distribution could have different shape/variance even after climate adjustment, so a floor
baked in from Brooklyn/SF data may not transfer correctly.

**Fix, when this matters (i.e. when a non-coastal-temperate metro is added to the catalog):**
compute the floor live as a percentile of whatever catalog is currently loaded, instead of a
hardcoded constant — pass it into `nbPreferencePasses`/`aoPreferencePasses` as a parameter derived
from the active place list at call time.

**Priority:** low today (catalog is 4 similar-climate metros); revisit before/when a
desert, mountain, or plains metro ships.

---

## Area-normalized canopy % doesn't distinguish "tree-lined street" from "sparse dense area"

**Where:** `pillars/natural_beauty.py` (`canopy_pct` / `_v9_score_canopy`), surfaced while
debugging why Carroll Gardens (2.7 canopy_score) failed the new canopy AND-filter despite
feeling like a leafy brownstone block.

**Issue:** `canopy_pct` comes from NLCD Tree Canopy Cover averaged over the *whole* measured
radius — building footprints, roofs, paved yards included. A dense rowhouse block with a full
row of mature street trees (a real "green tunnel" that reads as leafy at street level) still
scores near-zero, because that canopy is confined to a narrow strip along the road while
everything else in the radius (roofs, facades, small paved backyards) contributes zero. A
suburb scores high not because its trees are denser per tree, but because trees sit on every
private lot (front/back/side yards), so a much bigger share of total land area falls under
some canopy. Verified this isn't a data bug — it's consistent catalog-wide (confirmed against
Larchmont, a real leafy town, and 20 other places) and `forest_pct`/`grass_pct` are both ~0 for
both dense-urban and suburban rows, ruling those out as the explanation. It's a real
measurement, just answering "% of all land here is under a tree" rather than "does this street
feel tree-lined."

**Considered and rejected:**
- NYC's Street Tree Census (real per-tree municipal point data, already partially in the
  pipeline as a GVI nudge) — rejected because it's what inflated NYC neighborhoods over
  suburbs previously (better municipal data ≠ more trees) and because it's a one-off
  per-metro integration, not something that scales as new metros get added.
- Real Street View Green View Index (Treepedia-style image segmentation) — most accurate
  option for "does the street feel green," but rejected as not worth it: a new paid API
  plus per-location image-processing cost, for a marginal accuracy gain over what the
  satellite-only option below already gets directionally.

**The actual fix isn't "replace canopy_pct" — it's splitting one conflated question into
two, both served by data already in the pipeline:**
- *"Living there feels green overall"* (yards + streets + parks) — already the right question
  for today's `canopy_pct` (NLCD TCC, whole-radius) + `gvi_pct` (Sentinel-2 NDVI/VARI) +
  `local_green_spaces`/`local_green_score` (OSM park polygons, currently reading ~0 for most
  catalog places and likely underqueried — worth its own look). Keep this as "canopy
  preference" means today.
- *"Walking the street feels green"* — genuinely unserved today. Add as a distinct,
  separately-selectable preference, fed by NLCD TCC sampled only within a buffer of the
  street/sidewalk right-of-way (reuse OSM road geometry `street_geometry.py` already fetches
  for built_environment) instead of the whole radius. Same national dataset already in the
  pipeline, no new API, no per-metro dependency — just a different geometry passed into the
  existing GEE canopy call.

Note this isn't a strict improvement to swap in and call it fixed: a corridor-only metric
would systematically favor tree-lined urban blocks over yard-heavy suburbs (Larchmont's real
backyard canopy stops counting), which is a legitimate but different definition of "canopy" —
hence splitting into two preferences rather than replacing one metric with the other.

**Priority:** medium — this is actively excluding places from the new canopy AND-filter based
on a metric that doesn't measure what users mean by "canopy preference" for dense urban areas.

---

## `ocean_beach` waterfront category has two distinct, separately-validated problems

**Where:** `pillars/active_outdoors.py`, `_score_water_lifestyle_v2` and its `_beach_is_ocean`
helper. Surfaced while investigating why Carroll Gardens failed the AO waterfront AND-filter
and why Piedmont, CA (a landlocked East Bay hill town) scored a perfect `ocean_beach: 100.0`.

### Problem 1 (validated bug, ready to fix): false ocean-confirmation on inland beaches

`_beach_is_ocean` decides whether a `natural=beach`-tagged feature counts as ocean-connected by
comparing **both features' distances from the shared scoring center** (`min_coastline_dist <=
beach_dist + 3000`) rather than the distance **between the beach and the coastline themselves**.
This lets two completely unrelated water bodies pass the check whenever both happen to sit
within the search radius from center, regardless of direction: an inland reservoir beach several
km from any real coastline can pass simply because a real coastline elsewhere is *also* within
range of the same center point.

**Validated with live Overpass data, not just theory** (see chat log for full methodology):
- Random 30-place sample drawn from the 197 catalog places with nonzero `ocean_beach` score.
- Built a corrected version of `_beach_is_ocean` that checks true point-to-point distance
  between each beach feature and its nearest coastline feature (using each feature's own
  lat/lon, not distance-from-center), capped at 2km, and ran both the old and new logic side by
  side against real OSM data for all 30 places.
- **Result: 3 of 30 places have a real, likely score-changing false positive** — Piedmont,
  Temescal, and Rockridge (all CA, all near the same Lake Temescal / Lake Anza cluster in the
  Oakland hills). Lake Temescal Beach (a hillside reservoir beach) sits 3450m from Temescal's
  center — close enough that under the old logic it plausibly *wins* the "best feature" contest
  over the real, farther-away Bay beaches (Albany Beach, Radio Beach), since it takes less
  distance-decay penalty. True distance from Lake Temescal Beach to the nearest real coastline:
  6645m — nowhere close to the same shoreline.
- **7 more flips found, but don't change any score**: junk unnamed candidates at 2-5km in City
  Island, Long Beach, and Half Moon Bay that fail the corrected check but were never going to
  beat those places' real, much closer named beaches anyway (Orchard Beach 96m, Rockaway Beach
  254m, etc.).
- **20 of 30 places: completely unaffected.** This is a narrow, geography-specific bug (one
  lake cluster, not a catalog-wide problem) — confirmed by testing before acting on it, not
  assumed from the first suspicious-looking example found.

**The fix (drafted, reverted pending this validation, ready to reapply):**
1. `data_sources/osm_api.py`, `_process_nature_features` — store each swimming/water feature's
   own `lat`/`lon` on the feature dict (currently only `distance_m` from center is kept).
2. `pillars/active_outdoors.py`, `_beach_is_ocean` — rewrite to compute true haversine distance
   from the beach's own coordinates to its nearest coastline feature's own coordinates, capped
   at 2000m (validated threshold — real beaches in the sample sit under ~1.7km true distance;
   the confirmed false positives sit at 5-7km). Falls back to the old center-relative check only
   when a feature has no stored coordinates (older cached data).
3. Reuse `data_sources/utils.py`'s existing `haversine_distance` — no new dependency.

Needs a live rescore of `waterfront_lifestyle` for the whole catalog after merging (true
beach-to-coastline distance isn't derivable from what's currently stored — genuine new-data
case, not a pure logic fix on existing fields).

**Priority:** medium — real, validated, narrow-scope bug with a small, low-risk, already-tested
fix. Not urgent (only ~10% of a random sample affected, all one cluster) but correct and cheap
enough to ship without further debate.

### Problem 2 (separate, unfixed): `ocean_beach` category conflates beach with coastline/harbor

Independent of Problem 1. `_WATERFRONT_CATEGORY` buckets `beach`, `coastline`, and
`coastline_rocky` into the same `ocean_beach` output category. A place whose winning feature is
plain `natural=coastline` (harbor edge, no swimmable beach — e.g. Carroll Gardens, whose winning
feature is real Upper NY Bay coastline, correctly computed, no bug) gets the same category label
as a place with an actual sand beach (e.g. Larchmont's Manor Beach). The math is correct in both
cases; the label misrepresents what's actually there.

**Fix:** split the category so `ocean_beach` requires a `beach`/`swimming_area` winner
specifically; anything where `coastline`/`bay` wins becomes a separate category (e.g.
`waterfront_access`) instead of being folded into "beach." Same OSM data, no new source, but
this is a bigger surface-area change than Problem 1 since it touches the AND-filter floors
shipped in `frontend/lib/aoPreference.ts` today (`AO_PREFERENCE_FLOOR`, `PREFERENCE_AO_COMPONENTS`)
and the `waterfront_breakdown` shape the frontend already reads.

**Priority:** medium — not a bug, but an active mislabeling that misleads anyone using the
waterfront preference to mean "can I swim here."
