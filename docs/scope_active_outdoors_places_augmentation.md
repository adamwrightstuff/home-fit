# Scope: Google Places augmentation for Active Outdoors (AO)

## Goal

Increase **realistic** `parks` / `playgrounds` / (optionally) **named** regional **water** and **camping** signals when **OpenStreetMap (Overpass) is thin**, without double-counting geometry OSM already represents well. Improve **`data_quality.completeness`** where it is currently dominated by sparse OSM lists, while keeping **scoring interpretable** (same pillar semantics as today).

## Non-goals (explicit)

- **Replace** OSM for linear features: `highway=cycleway|footway`, `route=hiking` relations, arbitrary water polygons — **remain OSM-only**.
- Use **marina** (or other boat/commerce types) in AO — **out of scope** for this pillar.
- Guarantee parity with NA Places policy (different triggers, caps, and types).
- Change **token weights** or the **30 / 50 / 20** component budgets without a separate product decision.

## Current pipeline (reference)

| Stage | Code | Inputs used by AO v2 |
|-------|------|------------------------|
| Local green | `osm_api.query_green_spaces` | `parks`, `playgrounds`, `recreational_facilities` |
| Trail window | `osm_api.query_nature_features(..., include_hiking=True)` | `hiking` (+ swimming/camping in same call, but AO also uses regional-only pass) |
| Regional water/camp | `osm_api.query_nature_features(..., include_hiking=False)` | `swimming`, `camping` |
| Canopy | GEE | `tree_canopy_pct_5km` |
| Completeness | `data_quality._assess_outdoors_completeness` | counts of `parks`, `playgrounds`, `hiking`, `swimming`, `camping` vs `local_facilities` / `regional_facilities` |

Radii: `data_sources/radius_profiles.py` → `get_radius_profile("active_outdoors", ...)`.

Scoring: `pillars/active_outdoors.py` → `get_active_outdoors_score_v2`.

## Proposed augmentation buckets

### Bucket A — Local (`query_green_spaces` radius)

**Intent:** OSM primary; Places **supplements** when local park/playground **counts** are thin.

| OSM signal | Places `includedTypes` (candidate) | Rule |
|------------|-------------------------------------|------|
| Park-like polygons / landuse | `park`, `national_park`, `botanical_garden` | Merge as extra **points** into `parks` list with `source: google_places` (or merge_note on feature dict). |
| Playgrounds | `playground` | Merge into `playgrounds`. |
| Dog parks | `dog_park` | Merge into parks or separate list consistent with OSM `leisure=dog_park` handling today. |
| Pitches / field sports | Prefer `athletic_field`, `tennis_court` if API exposes; avoid **`stadium`**, **`sports_complex`** as default (spectator bias). |
| Golf | `golf_course` | Map into park-like or `recreational_facilities` per existing OSM classification — **must match** how `_score_daily_urban_outdoors_v2` consumes `recreational_facilities`. |
| `highway=cycleway` / `footway` | *none* | **Do not** approximate with Places. |

**Dedup:** Before adding to `parks` / `playgrounds`, dedupe by **Google `place_id`** (and distance-to-existing OSM feature &lt; **X m** if same name centroid — configurable). Same spirit as `places_fallback_client` dedupe for businesses.

**Trigger (Places call):** Separate from NA’s `business_count` logic. Proposal:

- Compute **OSM-only** counts: `n_local = len(parks) + len(playgrounds)` (and optionally facilities).
- Call Places **only if** `n_local < T_local` **or** `completeness` pre-call &lt; threshold (see §Triggers). Start with **`T_local = 3`** (tunable); document why (suburban towns may have 2 OSM parks but many named Places parks).

**Caps:** Max **Places-derived** POIs per bucket per request (e.g. 15–25) and max **extra** API calls (align with NA Places budget patterns).

### Bucket B — Trail radius (`query_nature_features` with hiking)

**Intent:** OSM dominates; Places only for **named anchors** where OSM has no good POI.

| OSM | Places | Rule |
|-----|--------|------|
| `route=hiking`, linear trails | *none* | OSM-only. |
| Protected areas / reserves (polygons in OSM) | `national_park`, `hiking_area`, `park` | Optional **supplement** when hiking list is thin **and** no duplicate within radius of existing OSM-derived trail cluster. Prefer **access points** only if we can represent as point features with `distance_m`. |
| `piste:type` / ski | `ski_resort` | Supplement **commercial** resorts; backcountry remains OSM-only. |

**Low priority for v1** — highest risk of double-counting and geometry mismatch. **Recommendation:** ship Bucket A (+ optional D) first; defer B unless metrics show trail-window completeness still broken.

### Bucket C — Regional pass (`include_hiking=False`)

**Intent:** Same water/camp OSM tags; Places helps **named beaches** and **commercial campgrounds** often missing in OSM at 15–50 km.

| OSM-derived `swimming` / `camping` | Places | Rule |
|-----------------------------------|--------|------|
| Beach / swim | `beach` | Add if OSM swimming list below threshold at regional radius. |
| Camp | `campground`, `rv_park` | Add when OSM `tourism=camp_site` thin. |

**Dedup:** Strong dedupe against OSM by distance + name fuzzy match; Places IDs stable.

### Cross-cutting

- **Env:** Reuse `GOOGLE_PLACES_API_KEY` / `HOMEFIT_GOOGLE_PLACES_API_KEY`, new flag e.g. `HOMEFIT_PLACES_AO_FALLBACK_ENABLED` (default off in dev).
- **Metadata:** `places_fallback` block on AO breakdown (mirrors NA): `used`, `mapped_added`, `reason`, `http_calls`, `stop_reason`.
- **Completeness:** After merge, `assess_pillar_data_quality("active_outdoors_v2", combined_data, ...)` must see **longer lists** — completeness rises only if merged rows are **counted** in the same keys OSM uses (`parks`, `playgrounds`, `hiking`, `swimming`, `camping`).
- **Scoring:** Merged features must expose **`distance_m`** from catalog `(lat,lon)` and compatible **`type`** for water (`_score_water_lifestyle_v2` uses `nearest.get("type")` in `beach` | `swimming_area` | `lake` | `coastline` | …). Map Places types → those **internal** types explicitly (small table in code).

## Triggers (summary)

| Layer | Proposed trigger |
|-------|------------------|
| Local Places | `n_parks + n_playgrounds < T_local` (start **3**) **or** pre-merge AO completeness &lt; **0.8** |
| Regional Places | `len(swimming) < T_swim` or `len(camping) < T_camp` at regional radius (tune from catalog distribution) |

**Do not** reuse NA `HOMEFIT_PLACES_COMPLETENESS_THRESHOLD` without calibration — AO completeness is **outdoors list counts**, not business tiers.

## Files likely to change

1. **New module** (parallel to `places_fallback_client.py`): e.g. `data_sources/places_active_outdoors_client.py` — `maybe_augment_active_outdoors_with_places(...)`.
2. **`pillars/active_outdoors.py`** — after OSM fetches, call augmenter; pass through to `combined_data` and existing scoring functions.
3. **`main.py`** — only if env wiring / feature flag must be read once at import (prefer reading env inside augmenter).
4. **Tests** — unit tests for dedupe, type mapping, and “no call when OSM sufficient.”
5. **`.env.example`** — document new env vars.

## Testing plan

- **Unit:** Dedupe (same park from OSM + Places → one counted feature); type mapping for water.
- **Integration:** Fixed lat/lon fixtures (suburban thin OSM vs known Places-rich); assert completeness increases bounded.
- **Catalog batch:** Optional dry-run mode counting how many rows would trigger Places (no API key burn).

## Rollout

1. Ship behind **`HOMEFIT_PLACES_AO_FALLBACK_ENABLED`**; default **false** in production until spot-checked.
2. Run catalog rescoring subset (completeness &lt; 0.8) on staging/prod API; compare before/after distributions.
3. Enable in production; monitor Places quota and 429/504 rates.

## Open questions

- Exact **`includedTypes`** list per Nearby Search call (Google caps per request).
- Whether **botanical_garden** merges into `parks` only or separate bucket (avoid double park boundary).
- Whether v1 includes **Bucket B** (trail-window anchors) or defers to v2.

## Success metrics

- Median **`active_outdoors` `data_quality.completeness`** on NYC+LA catalog **up** without median pillar score jumping unrealistically.
- **Zero** increase in duplicate obvious double-counts (manual audit sample of 20 locations).
