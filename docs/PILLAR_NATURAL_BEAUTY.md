# Pillar Deep-Dive: Natural Beauty

How `pillars/natural_beauty.py` scores a location today: the two-part model (2026-10) plus the scenery preference.
Evidence, judgment calls and open gaps are in `analysis/natural_beauty_two_part_proposal_2026-10-24.md` (local file).

## What it measures
Two kinds of beauty, scored separately and then blended:

- **Streets and greenery**: tree canopy and eye-level green view around the pin.
- **Scenic setting**: terrain (relief, slope, ruggedness) and nearby water.

Landcover and biodiversity are still computed and stored in `details.v9_breakdown`, but they are not scored
(0.95 correlated with each other, no third-party test supports them).

## Model
Per-dimension scores (`gvi_score`, `canopy_score`, `topo_score`, `water_score`) are unchanged curves of the raw
inputs. Green view and canopy are normalized against a regional median first (see judgment calls below).

```
streets = 0.7 x stronger(gvi, canopy) + 0.3 x weaker(gvi, canopy)
scenery = 0.7 x stronger(topo, water) + 0.3 x weaker(topo, water)
blend   = streets_share x streets + (1 - streets_share) x scenery        # streets_share = 0.5 with no preference
score   = quantile map of blend onto the old V9 score distribution       # data/natural_beauty_two_part_scale.json
```

`nb_two_part()` returns `streets`, `scenery`, `blend`, `score`, `streets_share`. The stored breakdown carries
`method = "two_part_v10"`, `streets_score`, `scenery_score`, `blend_raw`.

### Score scale
The blend runs lower than the old six-component score (mean 47 vs 65), so each blend value is mapped to the old-score
value at the same percentile of the catalog (21 metros, 1,476 places). This keeps the catalog mean and spread (64.6 and
18.9), has no cap and no invented constants. It is a calibration to the previous score, **not evidence about beauty**, and
it is relative to the catalog it was built from. Rebuild with `scripts/baselines/build_natural_beauty_two_part_scale.py`
only when the catalog changes materially. The same table is generated into `frontend/lib/nbTwoPartScale.ts`.

### Missing greenery data
If no green view or canopy measurement exists (live: all three fields empty; stored: both inputs exactly 0.0), the
streets part is dropped, the score rests on scenery alone, and the breakdown carries `low_confidence: true` and
`missing_parts: ["streets"]`. A made-up zero is never scored.

## Scenery preference
The preference tilts the blend toward one part instead of forcing a component into a lead slot:

| preference | favors | streets share |
|---|---|---|
| `canopy` | streets | 0.75 |
| `mountains`, `ocean`, `lakes_rivers` | scenery | 0.25 |
| none, or picks from both sides | neither | 0.5 (picks average out) |

An `ocean` or `lakes_rivers` pick that does not match the place's water type cuts its water score to a quarter.

### `v9_score_from_components`
Recomputes the score from the stored component scores (preference-independent) and applies any preference. Used by the
serving fast-path so the served score is always correct regardless of what was cached.

## Where the preference is applied (served, not stored)
The neutral score is stored. The preference is applied at serve time in three mirrored places:
- **Live API:** `nb_two_part` inside the pillar, and the catalog/cache fast-path in `main.py`.
- **Explorer:** `applyNbPreferencesV9` in `frontend/lib/nbPreference.ts`.
- **Catalog filters:** `apply_nb_preferences_v9` in `scripts/catalog/apply_preference_filters.py`.

**Three implementations to keep in sync** if the math changes (`tests/test_natural_beauty_two_part.py` checks the
Python pair).

## Evidence (what each part was tested against)
| Part | Third-party test | Result |
|---|---|---|
| Streets | MIT Place Pulse 2.0 street ratings, 1,320 photos, 13 US cities | r about 0.37 to 0.38 |
| Scenery: terrain | ScenicOrNot landscape ratings, 598 points in Great Britain | r 0.41 (Scotland 0.53, Wales 0.29, England 0.16) |
| Scenery: terrain | USDA Natural Amenities Scale topography, 126 counties | r 0.66 |
| Scenery: water | USDA scale water area / ScenicOrNot | r 0.30 / 0.18 (weakest measure) |
| Old six-component score | ScenicOrNot | r -0.06 |

## Judgment calls (not evidence; say so in any methodology)
1. The 50/50 blend, and the 0.75 / 0.25 preference tilt.
2. The 0.7 / 0.3 pairing inside each part (rank order is stable across 0.6 to 0.8).
3. Regional normalization of green view and canopy: the baselines in `_NB_REGIONAL_BASELINES` have no traceable source and
   showed no effect on matching Place Pulse. Kept because removing it moves Phoenix about 18 and Las Vegas about 12 rank
   points on indirect evidence.
4. Water as part of scenery (it describes what you see; Active Outdoors waterfront covers what you do).
5. The percentile scale (calibration to the old score).

## Related studies (supporting context only, none validates a parameter)
- Yin et al. 2022, Journal of Environmental Psychology 81:101775: VR desert scenes lowered cortisol and blood pressure against an office control in 95 El Paso men. Measures restoration, not beauty ratings, and the authors point to familiarity as a likely factor.
- García-Llorente et al., semi-arid watersheds in southeastern Spain (survey): favorite views mostly had steeper relief, water flows and traditional land use; place attachment went with willingness to pay for conservation. Supports terrain and water as beauty cues in dry landscapes; a local survey, not a rating dataset.

## Known gaps
- Deserts have no human rating data (Phoenix, Las Vegas). Plan: an in-product photo-rating question.
- No pin-shift test yet (green view reads 1.2 km, canopy 0.4 to 2 km, terrain 5 km, water 3 km around the pin).
- Place Pulse photos are 2007 to 2012; ScenicOrNot is Britain only and almost all rural.
- Both canopy sources in `gee_api.py` are flagged deprecated by Google Earth Engine.

## Catalog
The catalog stores the neutral score plus `details.v9_breakdown` (component scores, `streets_score`, `scenery_score`).
`scripts/catalog/recompute_natural_beauty_two_part_offline.py` rewrites stored places from the stored component scores
(no API calls); run `recompute_catalog_composites.py --in-place --no-census` afterwards. The pre-change score is kept in
`details.score_before_two_part`.

## Gotchas
- The stored pillar `score` is the **neutral** score. Don't assume a preference is baked in.
- `ocean` vs `lakes_rivers` both target water; the per-type distinction is only as good as the stored water type.
- Older catalog rows (NYC, LA) keep `v9_breakdown` at the pillar root, not under `details`.
- History: the V7 to V9 upgrade once silently orphaned the preference, so picking one changed nothing for a while.
