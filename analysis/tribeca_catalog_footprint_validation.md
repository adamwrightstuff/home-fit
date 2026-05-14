# Tribeca (NYC catalog) — pillar footprint validation

**Catalog row:** `Tribeca, Manhattan, NY` in `data/nyc_metro_place_catalog_scores_merged.jsonl` — `type: neighborhood`, pin **`40.7163, -74.0086`** (ZIP 10007 in stored score).

**Important:** The catalog stores a **point** (lat/lon + search string), **not** a neighborhood polygon. Any “Tribeca boundary” check must pick a definition:

- **Census tract footprint (ACS):** For this pin, `census_api.get_census_tract` resolves **`36061003300`** (Census Tract 33, Manhattan). This is the only **closed polygon** the engine consistently anchors to for **tract-level Census** pillars.
- **Colloquial / OSM neighborhood outline:** **Not** what the scorer uses for OSM-based pillars; those use **geodesic disks** (and similar) from the **catalog pin**, not an OSM relation boundary.

---

## Census tract boundary — logic by pillar

“Census tract boundary” means the **TIGER/ACS census tract polygon** that contains the scored pin (for Tribeca catalog coordinates, **`36061003300`**). Most pillars **do not** use that polygon as their analysis window.

| Pillar | Uses tract polygon as the scoring window? | Tract-related logic (what the code actually does) |
|--------|---------------------------------------------|-----------------------------------------------------|
| **diversity** | **Yes — primary** | All mix/entropy inputs are **ACS variables for the containing tract** of the pin (`get_census_tract` → tract GEOID). The tract is the geographic unit of record. |
| **housing_value** | **Yes — primary** | Affordability and housing stock signals come from **`get_housing_data(..., tract=…)`** on that same containing tract. |
| **economic_security** | **No** | Tract is only used to **look up CBSA (and county) codes** (`get_economic_geography` from `economic_security_data.py`). Labor-market tables are fetched for **CBSA** (metro), not clipped to the tract polygon. |
| **social_fabric** | **Partial** | **Stability / mobility** side uses **tract-level Census** tied to the pin’s tract. **Civic / participation** queries use a **geodesic disk** from the pin (radius rules from density + `area_type`), not the tract outline. |
| **community_safety** | **Partial (denominator only)** | Crime rates are for the **agency/jurisdiction covering the pin**, not “tract crime.” For per-capita scaling, population may be estimated by **intersecting many tract polygons with the same geodesic crime disk** (areal weighting in `estimate_community_safety_disk_population` when enabled), so tract boundaries matter as **intersection pieces**, not as “score = this one tract.” |
| **neighborhood_amenities** | **No** | **No tract geometry.** OSM amenity pulls use **`get_radius_profile`** meter radii from the pin only. |
| **active_outdoors** | **No** | **No tract geometry.** Local / trail / regional Overpass + GEE windows are **disks from the pin** per profile. |
| **public_transit_access** | **No** | **No tract geometry.** Transit network search uses **`routes_radius_m`** from the pin. |
| **healthcare_access** | **No** | **No tract geometry.** OSM + fallbacks use **facility / pharmacy radii** from the pin via `get_radius_profile`. |
| **built_beauty** | **No** | **No tract geometry** for the architectural OSM/GEE window; Census **year-built** helpers are point→tract lookups for **attributes**, not “clip OSM to tract.” |
| **natural_beauty** | **No** | **No tract geometry** for canopy/green/water context; radii from profile + GEE from the pin. |
| **air_travel_access** | **No** | **No tract geometry.** Airport discovery uses a **large km radius** from the pin. |
| **quality_education** | **No** | **No tract geometry.** School discovery uses a **mile-radius** disk from the pin. |
| **climate_risk** | **No** | **No tract polygon** in the pillar path; hazards are evaluated from **lat/lon** against hazard datasets (not “inside tract outline”). |

---

## 1) Is tract `36061003300` captured with **expected** per-pillar boundaries?

**Central routing (current code):** `main.py` computes one shared `area_type` via `detect_area_type(...)` plus `detect_location_scope` → for Tribeca this is **`neighborhood` scope** (verified by geocoding `Tribeca, Manhattan, New York`) and, with live Census/OSM inputs at the catalog pin, **`urban_core`** (recomputed locally: density ≈ 43,867/sq mi, metro distance to principal city ≈ 5.1 km).

With **`urban_core` + `neighborhood` scope**, `get_radius_profile` in `data_sources/radius_profiles.py` yields the nominal disk radii below.

| Pillar | What “boundary” means in practice | Tract polygon `36061003300`? | Nominal geometry (expected) |
|--------|-----------------------------------|-------------------------------|-----------------------------|
| **diversity** | ACS race/income/age mix | **Yes — tract is the unit** | Tract polygon (data keyed to GEOID) |
| **housing_value** | ACS housing / affordability | **Yes — tract is the unit** | Tract polygon |
| **economic_security** | Labor market / earnings scale | **No** | Uses **CBSA** derived from tract pointer (`New York-Newark-Jersey City, NY-NJ`), not tract-level employment fields |
| **social_fabric** | Stability + civic OSM | **Partial** | Stability inputs tied to **tract**; civic amenities queried in a **disk** (`civic_search_radius_m` — stored Tribeca example **600 m** at that density) |
| **neighborhood_amenities** | OSM businesses / walk | **No** | **1200 m** query disk, **800 m** walk band (`neighborhood` scope) |
| **active_outdoors** | Parks / trails / regional | **No** | **800 m** local parks, **15 km** trails, **15 km** regional (urban_core profile) |
| **public_transit_access** | Transitland routes | **No** | **3000 m** routes search (`urban_core`) |
| **healthcare_access** | OSM + fallbacks | **No** | **5000 m** facilities, **2000 m** pharmacies (`urban_core`) |
| **built_beauty** / **natural_beauty** | OSM + GEE windows | **No** | Beauty radii from profile (e.g. **1000 m** canopy / **2000 m** arch diversity with `neighborhood` scope — see `radius_profiles.py`) |
| **air_travel_access** | Airport search | **No** | **100 km** search radius |
| **quality_education** | School search | **No** | **1.5 miles** (`urban_core`) |
| **climate_risk** | Hazard layers at point | **No** | Point/raster intersection (not tract outline) |
| **community_safety** | Crime rates per population | **No** | **800 m** crime-data disk (`urban` in area_type string); population denominator can **overlap many tracts** (stored Tribeca run: **16** tracts overlapping that disk) |

**Verdict on (1):** If “expected” means “every pillar should clip to the Tribeca **tract** outline,” that is **false by design** — only the **Census-tract pillars** use that polygon. OSM/network pillars intentionally use **different disks** (and economic uses **metro CBSA**).

---

## 2) Is Tribeca captured **similarly across pillars**?

**No — and it should not be.** The engine mixes:

- **Tract-only** (diversity, housing),
- **Tract → CBSA** (economic),
- **Tract + short civic disk** (social fabric),
- **Many different meter/mile radii from the same pin** (amenities, transit, healthcare, outdoors, beauty),
- **Very wide** search windows (air 100 km, education 1.5 mi, trail 15 km).

So **spatial overlap between pillars is partial**, not “one shared neighborhood polygon.”

**Reporting caveat:** In an older **`nyc_metro_place_catalog_scores_merged.jsonl`** snapshot, some pillars’ `area_classification.area_type` strings disagree (e.g. `urban_residential` vs `urban_core`). A **fresh** run at the catalog pin with current `detect_area_type(..., metro_distance_km=...)` yields **`urban_core`** for the shared router; pillar payloads can still differ in **which** metadata they echo. For verification, trust **`data_quality_summary.area_classification`** plus the **radius profile** table above, not inconsistent per-pillar echo fields in stale JSONL.

---

## How to re-check yourself

1. Resolve tract: `PYTHONPATH=. python3 -c "from data_sources import census_api; print(census_api.get_census_tract(40.7163,-74.0086)['geoid'])"`  
2. Recompute `area_type` / `location_scope` the same way `main.py` does (density + business count + metro distance + `detect_area_type`).  
3. For OSM pillars, read **`get_radius_profile(pillar, area_type, location_scope)`** and compare to pillar `details` / `summary` where radii are logged.
