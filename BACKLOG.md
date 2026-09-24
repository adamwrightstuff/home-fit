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
