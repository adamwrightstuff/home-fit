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

**Considered and rejected:** NYC's Street Tree Census (real per-tree municipal point data,
already partially in the pipeline as a GVI nudge) — rejected because it's what inflated NYC
neighborhoods over suburbs previously (better municipal data ≠ more trees) and because it's a
one-off per-metro integration, not something that scales as new metros get added.

**Scalable options (same national datasets already in the pipeline, no per-metro dependency):**
1. Sample NLCD TCC only within a buffer of the street/sidewalk right-of-way (reuse OSM road
   geometry already pulled elsewhere) instead of the whole radius — isolates canopy over where
   you'd actually walk from canopy anywhere on any property nearby. Cheapest, no new data source.
2. Real Street View Green View Index (actual Treepedia-style street-view image segmentation,
   not the current NDVI satellite proxy mislabeled as "eye-level" in the code's own docstrings)
   — most accurate, but needs a Street View API integration and per-location image processing
   cost.

**Priority:** medium — this is actively excluding places from the new canopy AND-filter based
on a metric that doesn't measure what users mean by "canopy preference" for dense urban areas.
