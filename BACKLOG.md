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

## `ocean_beach` waterfront category: three distinct, separately-validated problems

**Where:** `pillars/active_outdoors.py`, `_score_water_lifestyle_v2` and its `_beach_is_ocean`
helper. Surfaced while investigating why Carroll Gardens failed the AO waterfront AND-filter
and why Piedmont, CA (a landlocked East Bay hill town) scored a perfect `ocean_beach: 100.0`.

### False ocean-confirmation on inland beaches (SHIPPED)

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

**Status: SHIPPED.** Fix applied (`f56c83d`), plus two follow-on fixes found only after
rescoring real data:
- `query_water_only`'s cache-key line crashed on catalog rows where lat/lon are stored as
  strings (`Unknown format code 'f' for object of type 'str'`), silently skipping ~60% of a
  first NYC rescore attempt — fixed by coercing to `float` up front (`229342d`).
- The `natural=coastline` **relation** query (as opposed to `way`) was expensive enough to
  reliably time out for ~30% of NYC places even after retries; dropped it (real coastline is
  essentially always tagged as `way`) and gave the query more time budget (`8e6954f`).

NYC (193 places) fully rescored and applied: 133 changed, composites recomputed. LA/SF/Seattle
still pending as of this writing.

### Arbitrary winner among tied beaches (SHIPPED)

Every confirmed-ocean beach under 3km gets the *identical* base score (25.0, flat — distance
decay only starts past 3km), so when a place has multiple real beaches in that zone, which one
gets reported as the town's `winning_feature` (used for the category label and the persisted
audit trail) depended entirely on Overpass's arbitrary element order, not on which beach is
actually closer, more local, or better-known.

**Validated with a full-candidate-list live export** (`scripts/catalog/export_full_water_candidates.py`,
new tool — dumps every feature Overpass returns per place, not just the winner, since the
stored catalog and rescore log only ever keep the single winner): Larchmont's own named Manor
Beach (1251m, confirmed ocean) was losing to a closer unnamed sliver; Mamaroneck's Shore Acres
Pool Club Beach (651m) was losing to an unnamed one at 409m; Coney Island's own Coney Island
Beach (703m) was losing to the neighboring Manhattan Beach (2248m) purely on list order. None of
these were numeric scoring errors — the tied features scored identically either way — just
which feature got *credited*.

**Fix (shipped, `44c837e`):** deterministic tiebreak nudge inside `feature_score` — prefer a
named feature over unnamed, then prefer closer over farther. Nudge (~0.01 on a 0-25 scale) is
far below the score's 0.1 rounding precision, so it only changes which feature wins, never the
displayed score; both downstream clamps (`min(25.0, ...)`, `min(100.0, ...)`) absorb it with no
overflow risk. Reverified against the live CSV export after shipping — Larchmont, Mamaroneck,
Coney Island, and Long Beach all now correctly pick their own real named beach.

### `ocean_beach` category conflated real beach with plain coastline/harbor (SHIPPED — coastline split; see below for the definition question this raised)

`_WATERFRONT_CATEGORY` used to bucket `beach`, `coastline`, and `coastline_rocky` into the same
`ocean_beach` output category. A place whose winning feature was plain `natural=coastline`
(harbor edge, no beach — e.g. Carroll Gardens, real Upper NY Bay coastline) got the same label as
a place with an actual sand beach (e.g. Larchmont's Manor Beach). Fixed by splitting `coastline`/
`coastline_rocky` into their own `waterfront_access` category (`6945492`). Validated against
NYC's 133-place rescore: only 4 places win on `coastline` at all (Cos Cob, Edgewater, Leonia,
Mount Vernon — real waterfront towns, none of them beach destinations), 0 of 16 ground-truth
beach towns win on `coastline`, so the split cost no real beach town its score.

**Resolved definition question raised after shipping this:** does `ocean_beach` require
swimmability? Initially assumed yes, and started designing tag-based fixes (OSM `swimming` tag,
name-keyword detection for kayak/launch features) to downgrade non-swim beaches. Rejected after
checking real beach-activity research — the Outdoor Foundation's 2025 Outdoor Participation
Trends Report, a Kailua Beach Park usage study, and Hawaii DBEDT's visitor survey all find
walking and sunbathing are the most common beach activities, consistently ahead of swimming.
So `ocean_beach` correctly means general beach lifestyle (walking, sunbathing, views, casual
paddle/boat access) — not swim access specifically. Non-swim beaches that already win this
category today (Gansevoort Peninsula, Pier 4 Beach, Hallet's Cove, Dyckman St. Beach) are
correctly scored as-is; no code change needed beyond correcting the stale comment in
`pillars/active_outdoors.py` (`_WATERFRONT_CATEGORY`) that had described the split in swim-specific
terms. No swim-tag gate was ever shipped.

### Cross-neighborhood reuse of one real beach within the 15-18km search radius (OPEN)

The bigger driver of `ocean_beach` false positives — separate from both problems above.
Analyzed all 68 places in NYC's 133-rescore that score ≥80% `ocean_beach` but aren't an actual
ground-truth beach town (of a hand-picked, non-exhaustive 16-place reference list — likely
undercounts real beach places, e.g. Pelham Bay/Orchard Beach was mistakenly left off). 89%
(58/68) win on either a completely unnamed `natural=beach` tag (37, unverifiable — could be
anything) or a named feature that's *also* winning for 2+ other unrelated places (25) — Pebble
Beach (a real but non-swim decorative rock/pebble strip in Brooklyn Bridge Park, `surface=pebblestone`,
confirmed) alone is the winning feature for 12 different NYC/Brooklyn places boroughs apart;
Dyckman Street Beach for 4; Maxwell Place Beach for 3. Only 6/68 have a genuinely unique named
feature (real beach, just doesn't make the town itself a beach destination — e.g. Jersey City,
Harrison, Roslyn).

Named-vs-unnamed correlates but isn't a clean filter on its own: 4 of the 16 real ground-truth
towns also win on an unnamed feature (Larchmont, Long Beach, Mamaroneck, Old Greenwich — the
real local beach just isn't `name`-tagged in OSM), and 4 more share a feature with exactly one
adjacent neighbor legitimately on the same beach (Brighton Beach/Coney Island both near
Manhattan Beach; Manhasset/Port Washington both near PWEA Beach) — the difference is
share-count-and-distance-spread (1 adjacent neighbor vs. up to 11 places boroughs apart), not
"shared: yes/no."

`surface=sand` looked promising as an automatic "is this a real beach" signal but the evidence
is mixed: 13/14 known-real LA beach towns win on a `surface=sand` feature (El Segundo Beach,
Hermosa City Beach, Manhattan Beach, Santa Monica State Beach, Venice Beach, etc.) — clean
signal there — but NYC data doesn't hold up nearly as well (lots of `surface=None`/untagged on
real winners, `surface=pebblestone` confirmed non-swim on Pebble Beach specifically). `surface`
is now persisted on `winning_feature` (`0f45d9e`) for future analysis but isn't used in scoring.

**Fix:** not yet designed. Shrinking the 15-18km search radius is the most direct lever but
needs care (some real, correctly-scored places sit farther than 3km from their own beach); the
category split above (previous section) doesn't address this since it only separates
beach-vs-coastline labels, not reuse of the same beach across many unrelated places.

**Priority:** medium — a meaningful fraction of `ocean_beach` near-max scores in dense NYC
neighborhoods reflect a borrowed beach several km away rather than a real local amenity.

### 15km trail-count radius draws from the same citywide pool for most neighborhoods in a metro (OPEN)

`wild_adventure`'s trail count queries `route=hiking` within 15km — a circle roughly the size of
NYC itself. Different, unrelated neighborhoods showed identical or near-identical trail counts
(Astoria, Bay Ridge, Bed-Stuy, and Bensonhurst all stored `count_total=30`; a separate cluster of
NYC places plus Boyle Heights, LA all stored `count_total=10`). Initially suspected as a caching
bug — traced the cache-key generation directly (`_generate_cache_key` in `data_sources/cache.py`)
using each place's real stored coordinates and confirmed all four produce distinct, correctly-keyed
cache entries (no collision at that layer). A live re-pull of Astoria's own trail data returned 27
relations (vs. the stored 30) at a slightly different query center within the neighborhood,
consistent with normal circle-boundary movement, not a bug.

**Root cause (not a bug):** at 15km, a metro like NYC has a relatively small, finite pool of
named/tagged hiking-route relations (Prospect Park's color-coded loops, NYC Parks path networks,
Empire State Trail segments). Most neighborhoods' 15km circles overlap this same pool almost
entirely, so many different places legitimately converge on the same or a very similar count —
independent of the trail-tag/urban-vs-wild question tracked elsewhere in this file. Same
underlying issue as the beach-reuse problem above, one level up: too large a radius relative to
the size of the thing being measured, applied uniformly regardless of area type.

**Fix:** not yet designed. A smaller trail radius (or one that scales with area_type/metro
density rather than a flat 15km for every place) is the likely direction, but hasn't been
tested against real data yet.

**Priority:** medium — doesn't change any specific place's score by itself, but explains why
trail count so often fails to distinguish one urban neighborhood's real outdoor access from
another's (feeds the "urban wild_adventure inflated" problem above).
