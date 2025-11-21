## Active Outdoors Pillar – Design Principles and Spec (v1)

**Purpose:** Score access to outdoor recreation (0–100) using objective OSM data, with context-aware expectations and a transparent aggregation layer.

---

### 1. Inputs and Data Sources

- **Primary source:** OpenStreetMap via `data_sources.osm_api`:
  - `query_green_spaces(lat, lon, radius_m)` → local `parks`, `playgrounds`
  - `query_nature_features(lat, lon, radius_m)` → regional `hiking`, `swimming`, `camping`
  - Fallback coastline detection for water when regional query is empty
  - Optional local path clusters to avoid missing informal trails
- **Context:**
  - `get_area_classification(lat, lon, city)` → `area_type`, `metro_name`, `metadata`
  - `get_contextual_expectations(area_type, "active_outdoors")` → expectations per area type
  - `get_radius_profile("active_outdoors", area_type, location_scope)` → `local_radius`, `trail_radius`, `regional_radius`
- **Diagnostics / data quality:**
  - `assess_pillar_data_quality("active_outdoors", combined_data, lat, lon, area_type)`

---

### 2. Component Scores (Data-Backed Layer)

All component scores are **objective, reproducible functions of OSM geometry and expectations**.

- **Local Parks & Playgrounds (`local_score`, 0–40):**
  - `local_score = _score_local_recreation_smooth(parks, playgrounds, expectations)`
  - `parks` (0–25):
    - Uses `expected_parks_within_1km` and `expected_park_area_hectares`
    - Smooth functions of **count** and **area_hectares**
  - `playgrounds` (0–15):
    - Uses `expected_playgrounds_within_1km`
    - Smooth function of playground count

- **Trail Access (`trail_score`, 0–30):**
  - `_score_trail_access_smooth(hiking, expectations, area_type)`
  - Uses closest `distance_m` to any hiking / nature feature
  - Area-type-aware optimal distances and exponential decay:
    - `urban_core`: shorter optimal distance, faster decay
    - `suburban`: medium optimal distance
    - `exurban/rural`: longer optimal distance, slower decay

- **Water Access (`water_score`, 0–20):**
  - `_score_water_access_smooth(swimming, expectations)`
  - Uses closest `distance_m` and feature `type`:
    - `beach`, `lake`, `swimming_area`, `coastline`, `bay`
  - Type-specific base scores with smooth distance decay beyond an optimal radius

- **Camping Access (`camping_score`, 0–10):**
  - `_score_camping_smooth(camping, expectations, area_type)`
  - Uses closest camping `distance_m` and `expected_camping_within_15km`
  - Area-type-aware optimal distances / caps:
    - Urban core: lower cap, closer optimal distances
    - Suburban: medium cap
    - Exurban/rural: full cap, longer optimal distances
  - If camping is **not expected** for this area type, absence gives a **neutral partial score** (no penalty).

> **Principles 1 & 2:** All components are driven by objective counts/areas/distances and expectations keyed by `area_type`. No hardcoded city exceptions.

---

### 3. Aggregation (Transparent, Balanced Layer)

The total Active Outdoors score is a **two-step aggregation**:

1. **Normalized, weighted blend of components** (base score)
2. **Small, bounded adjustment** for outdoor gateways vs dense cores

#### 3.1 Normalized Weighted Blend (Base Score)

- Each component is normalized to a 0–1 scale:
  - `local_norm   = local_score   / 40.0`
  - `trail_norm   = trail_score   / 30.0`
  - `water_norm   = water_score   / 20.0`
  - `camping_norm = camping_score / 10.0`
- Global weights (sum to 1.0):
  - `W_LOCAL = 0.25`
  - `W_TRAIL = 0.35`
  - `W_WATER = 0.25`
  - `W_CAMP  = 0.15`
- Base score:

```python
total_base = (
    W_LOCAL * local_norm +
    W_TRAIL * trail_norm +
    W_WATER * water_norm +
    W_CAMP * camping_norm
) * 100.0  # → 0–100
```

- This is **area-type agnostic**; all context enters via the component layer (expectations, radii, decay curves).

> **Principles 1, 3 & 7:** Simple, explainable weighted blend; no location-specific hacks; scalable across geographies.

#### 3.2 Outdoor Backbone and Contextual Adjustment

- Define an **outdoor backbone index** emphasizing trails + water:

```python
outdoor_backbone = (0.6 * trail_norm + 0.4 * water_norm) * 100.0  # 0–100
```

- Two bounded adjustments:
  - **Outdoor gateway bonus (`outdoor_bonus`, max +15):**
    - Applies only to `{"rural", "exurban", "suburban", "urban_core_lowrise", "urban_residential"}`.
    - Triggered when `outdoor_backbone >= 70`.
    - Bonus grows linearly above 70 and is capped at +15.
  - **Dense core penalty (`urban_penalty`, typically −8 to −12):**
    - Applies only to `area_type == "urban_core"`.
    - Triggered when `local_score` and `trail_score` are both high.
    - Slightly stronger if `water_norm` is low (<60% of max).

- Final score:

```python
total_score = max(0.0, min(100.0, total_base + outdoor_bonus - urban_penalty))
```

> **Principles 2, 3 & 5:** Adjustments are area-type aware, bounded, and applied via smooth, piecewise-linear curves—no sudden cliffs or unbounded multipliers.

---

### 4. Calibration and Test Set

Calibration is done on a **small, diverse set of labeled locations** with Target AI scores, including:

- Outdoor towns & gateways (e.g., Bend, Boulder, Bar Harbor, Park City)
- Coastal cores (e.g., Santa Monica)
- Dense urban cores (e.g., Times Square, Downtown Phoenix, Downtown Las Vegas)
- High-park urban neighborhoods (e.g., Upper West Side, Park Slope)

For each calibration location, we track:

- `area_type`, component scores (`local`, `trail`, `water`, `camping`), and `total_score`
- Target AI outdoor score
- Error metrics: `model − target`, absolute error

Calibration rules:

- Mean absolute error across the panel should remain **≤ ~10 points**.
- No individual location should be off by more than **~20 points** without a documented reason.
- We prioritize **correct relative ordering and bands** (e.g., outdoor towns > urban cores) over exact point matching.

> **Principle 4:** Calibration is explicit and repeatable, using a documented, diverse panel of locations.

---

### 5. Smoothness, Caps, and Failure Modes

- **Component caps:** Each component has a fixed design max:
  - Local: 40, Trails: 30, Water: 20, Camping: 10
  - Prevents any single component from dominating.
- **Smooth curves:** All distance-based functions use exponential or piecewise-smooth curves (no hard jumps for small distance changes).
- **Adjustment caps:** 
  - `outdoor_bonus` ≤ +15
  - `urban_penalty` is modest (single-digit to low double-digit).
- **Data failures:**
  - If OSM returns `None` or an empty set for a category, that component can be 0 but the pillar still returns a valid score.
  - Data quality metrics are included in the breakdown so callers can distinguish weak data from genuine 0 access.

> **Principle 5 & 6:** Transitions are smooth and bounded; breakdowns and data quality flags expose behavior transparently.

---

### 6. Anti-Patterns Explicitly Avoided

- No hardcoded city or neighborhood overrides (e.g., `if city == "Boulder": score += 5`).
- No multiplicative stacking of multipliers on top of component scores.
- No artificial post-normalization shifts (e.g., `score * 0.8 + 10`).
- No special-case paths for individual calibration locations.

---

### 7. Future Improvements (v2 Ideas)

- Broaden OSM park/waterfront definitions (more inclusive of coastal promenades and protected areas) while keeping queries efficient.
- Expand calibration panel to more exurban/rural and non-US locations.
- Add a small automated test harness that:
  - Reads the calibration CSV,
  - Runs `get_active_outdoors_score`,
  - Reports mean / max error and basic ranking checks.


