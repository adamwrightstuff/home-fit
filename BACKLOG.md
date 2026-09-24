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
