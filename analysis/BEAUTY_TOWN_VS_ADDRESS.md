# Why Built/Natural Beauty Scores Differ: Town vs Specific Address (e.g. Larchmont NY vs 2 Springdale Dr)

## Summary

**2 Springdale Dr Larchmont NY** and **Larchmont NY** can get different built beauty and natural beauty scores because:

1. **They use different coordinates** — Town name → town center; address → that street location. All beauty inputs are computed in a radius around that point, so different center ⇒ different data.
2. **Location scope can differ** — Addresses often geocode with a neighbourhood/suburb in the response ⇒ `location_scope = "neighborhood"`. Town-only queries usually get `location_scope = "city"`. That changes the **tree canopy radius** used for natural beauty (1 km vs 2 km for suburban).
3. **Area type can differ** — Density, business count, and built coverage are computed at the point. Town center vs residential street can yield different `area_type` or built coverage ⇒ different expectations and normalization.

So the difference is by design: we score **the place you asked for** (that lat/lon and its local context), not the whole town.

---

## How It Works

### Built beauty

- **Data**: OSM buildings (and roads for form metrics) in a **2 km radius** around the geocoded point.
- **Radius**: From `get_radius_profile('built_beauty', area_type, location_scope)` → `architectural_diversity_radius_m` is 2000 m for both suburban and neighborhood.
- So the **center** is what changes: “Larchmont NY” uses the town center; “2 Springdale Dr” would use that address’s coordinates. Different circles ⇒ different building set, different built coverage, form metrics (streetwall, setback, facade rhythm), and thus different built beauty score.

### Natural beauty

- **Data**: Tree canopy (GEE) and other context in a radius around the point. The **radius** depends on `area_type` and **`location_scope`**:
  - **Neighborhood** scope ⇒ `tree_canopy_radius_m = 1000`
  - **City** scope (and suburban) ⇒ `tree_canopy_radius_m = 2000`
- So:
  - “Larchmont NY” (typically scope **city**) ⇒ 2 km tree radius around town center.
  - A specific address that geocodes as a **neighborhood** ⇒ 1 km tree radius around that address.
- Different center and/or different radius ⇒ different tree canopy % and scenic bonuses ⇒ different natural beauty score.

### Location scope

- From `data_sources/data_quality.py`: `detect_location_scope(lat, lon, geocode_result)`.
- If the geocode result has a **neighbourhood** or **suburb** in the address, scope is `"neighborhood"`; otherwise `"city"`.
- So: “Larchmont NY” → usually no neighbourhood in reply → **city**. “2 Springdale Dr Larchmont NY” (if it geocodes) might return a suburb/neighbourhood → **neighborhood**.

---

## Note on 2 Springdale Dr Larchmont NY

With the current geocoding pipeline (Census + Nominatim), **“2 Springdale Dr Larchmont NY”** does not return a result (geocode fails). So we cannot show live scores for that exact string. The same behaviour applies to any **specific address** in Larchmont that does geocode (e.g. “1 Palmer Avenue Larchmont NY”): different (lat, lon), possibly different scope/area type, hence different built and natural beauty scores.

---

## Script

`scripts/compare_beauty_larchmont.py` compares beauty scores for “Larchmont NY” vs a Larchmont address that geocodes (e.g. “1 Palmer Avenue Larchmont NY”), printing coordinates, `location_scope`, `area_type`, radii, and built/natural scores. Run from project root:

```bash
PYTHONPATH=. python3 scripts/compare_beauty_larchmont.py
```

(Requires GEE and OSM APIs; may take a few minutes.)
