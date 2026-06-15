# Pillar Deep-Dive: Natural Beauty

How `pillars/natural_beauty.py` scores a location today (the V9 model + scenery preference).

## What it measures
The natural scenic quality reachable/visible at a point — tree canopy, eye-level greenery,
water, terrain, landcover, biodiversity — judged on a place's **strengths**, optionally
biased toward a user's scenery **preference** (mountains / ocean / lakes & rivers / canopy).

## V9 model: Ordered Weighted Average (OWA)
`ENABLE_NATURAL_BEAUTY_V9 = True`. Six per-dimension component scores are computed:

| component | source |
|---|---|
| `gvi_score` | green-view index (eye-level greenery), regionally normalized |
| `water_score` | proximity + type (coast/lake/river) |
| `canopy_score` | tree canopy %, regionally normalized |
| `topo_score` | terrain relief / ruggedness |
| `landcover_score` | natural landcover mix |
| `bio_score` | biodiversity index |

They are **sorted descending** and combined with fixed positional weights:
```
OWA_WEIGHTS = [0.62, 0.25, 0.10, 0.02, 0.01, 0.00]
score = Σ  weight[i] · sorted_component[i]
```
**Rationale:** a place is judged on what it's *great* at, not penalized for lacking features
outside its character. Two exceptional dimensions reach ~80+, three reach ~90+. (The older V7
`tree_weight`/`context_weights` path still computes for comparison but its output is discarded
when V9 is on.)

## Scenery preference (the part that re-ranks)
A preference forces its dimension into the OWA **lead slot** (weight 0.62), making it the
lead criterion. `apply_v9_preference(owa_score, component_scores, preference_names)`:
```
targets   = preferred dimension(s)        # mountains→topo, ocean/lakes→water, canopy→canopy+gvi
preferred = mean(target component scores)
others    = the remaining components, sorted desc
score     = OWA([preferred, *others])     # preferred takes the 0.62 slot
```
- A place whose preferred dimension is already its strength stays high (Santa Monica keeps its
  water-led score for "ocean"); a place weak in it is forced to lead with that weakness and
  drops (landlocked Bedford falls for "ocean", keeps its canopy lead for "canopy").
- **No arbitrary tuning constant** — it reuses the OWA weights. Validated: ocean→waterfront
  towns, mountains→foothill towns, canopy→leafy suburbs.
- ⚠️ **History:** an earlier attempt used a guaranteed-weight blend (0.40) that *reduced*
  water's influence for water-strong places (backwards). The lead-slot version replaced it.

### `v9_score_from_components`
Recomputes the neutral OWA from the stored component scores (preference-independent) and then
applies any preference. Used by the serving fast-path so the served score is always correct
regardless of what was cached.

## Where the preference is applied (important — it's served, not stored)
The neutral V9 score is what's stored. The preference is applied **at serve time** in two
mirrored places:
- **Live API:** `apply_v9_preference` inside the pillar + the catalog/cache fast-path
  (`_apply_allocation_to_cached_response` recomputes NB from `details.v9_breakdown`).
- **Explorer:** `applyNbPreferenceV9` in `frontend/lib/nbPreference.ts` — a TS mirror of the
  Python, verified **bit-identical** (Santa Monica ocean 64.43 / canopy 33.3; Bedford ocean
  51.66 / canopy 92.27). **Two implementations to keep in sync** if the math changes.

History worth knowing: the V7→V9 upgrade silently orphaned the preference (V9's OWA ignored
it), so for a while picking a scenery preference changed nothing anywhere. Both paths now
implement it.

## Catalog
No catalog rescore needed for the preference — it's serve-time. The catalog stores the neutral
V9 score plus `details.v9_breakdown` (the six component scores), which is everything the
fast-path and the Explorer need to re-bias on demand.

## Gotchas
- The stored pillar `score` is the **neutral** OWA. Don't assume a preference is baked in.
- `ocean` vs `lakes_rivers` both target `water_score`; the per-type distinction is only as good
  as the stored water type — a coarse approximation for the rare mixed-water place.
- Keep the Python and TS preference implementations in lock-step.
