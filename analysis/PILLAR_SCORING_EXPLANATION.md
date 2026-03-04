# Pillar Scoring Logic - Complete Explanation

**Date:** 2026-02-28  
**Status:** All pillars use pure data-backed scoring per design principles. This document covers all 13 pillars (including economic_security, quality_education, social_fabric, climate_risk).

---

## Overview

All pillars follow **pure data-backed scoring** principles:
- ✅ **No calibration** - No tuning toward target scores
- ✅ **No location-specific adjustments** - Works for all locations
- ✅ **Objective metrics** - Based on measurable data (OSM, Census, GEE, Transitland)
- ✅ **Transparent** - All scoring logic is explicit and documented

**Legacy References:** Some pillars retain ridge regression coefficients as "advisory only" for reference, but these are **NOT used for scoring**. Primary scoring uses pure data-backed component sums.

---

## 1. Natural Beauty (`pillars/natural_beauty.py`)

### Active scoring: V8 (ENABLE_NATURAL_BEAUTY_V8 = True)

**Formula (no calibration, no uplift):**
```
final_score = 0.40 × topography_viewshed + 0.30 × water + 0.20 × greenery + 0.10 × natural_context
            + combo_bonus  # optional: up to +10 when both topography and water ≥ 70
```

### V8 Components

#### Topography/Viewshed (40% weight)
- **Data sources:** GEE only
- **Topography:** `get_topography_context(lat, lon, 5km)` — relief, prominence, ruggedness (metric CRS)
- **Viewshed:** `get_viewshed_proxy(lat, lon, 5km)` — scenic_viewshed_score (0–100)
- **Combined:** Topography contribution (relief/prominence/ruggedness scaled) + viewshed contribution, capped 0–100
- **No caps or dampening** on mountain contexts

#### Water (30% weight)
- **Data sources:** Natural Earth 10m (proximity) + GEE landcover (visibility)
- **Proximity (50% of water score):** Distance to coastline, major lakes (scalerank ≤ 2), major rivers (scalerank ≤ 4). Linear decay: coast 50 km, lakes 30 km, rivers 20 km. Weights: 60% coast, 30% lake, 10% river. Implemented in `data_sources/water_proximity_ne.py`. Requires one-time download: `python scripts/download_natural_earth_water.py`
- **Visibility (50% of water score):** GEE `get_landcover_context_gee` water_pct (micro-scale water visibility)
- **OSM water queries:** Not used (removed for reliability)

#### Greenery (20% weight)
- **Data sources:** GEE (single radius 1000 m) + Census/USFS (validation)
- **Formula:** When both available: `0.70 × GEE_canopy_1000m + 0.30 × Census_canopy`; else GEE or Census alone. Already 0–100 (canopy %).
- **Removed:** Multi-radius canopy (400/1000/2000/3000 m), NYC street trees, GVI, OSM parks fallback

#### Natural Context (10% weight)
- **Data sources:** GEE landcover (same call as used for water visibility when possible)
- **Formula:** `forest_pct + 0.5×wetland_pct + 0.25×shrub_pct + 0.125×grass_pct`, capped at 100
- **Unchanged** from previous landcover-based context

### Combo bonus (optional)
- When **both** topography/viewshed ≥ 70 **and** water ≥ 70: add up to +10 points (scaled by how far above 70).
- No other uplift; raw component sum speaks for itself.

### Data sources (V8)
- **GEE API:** Topography, viewshed, tree canopy (1 km), landcover
- **Census/USFS:** Tree canopy (blend with GEE for greenery)
- **Natural Earth 10m:** Coastline, major lakes, major rivers (proximity; optional — if missing, proximity = 0)
- **Not used in V8:** OSM water, NYC street trees, multi-radius canopy, GVI, uplift system

### Legacy (V6/V7) — when ENABLE_NATURAL_BEAUTY_V8 = False

#### Scoring Method
**Data-backed weighted component sum** (no calibration)

#### Formula (legacy)
```
raw_score = (tree_score * 0.3) + min(35.0, scenic_bonus * 2.0)
final_score = min(100.0, raw_score * 2.0)  # Scale 0-50 to 0-100
```

#### Components (legacy)

#### Tree Score (0-50 points)
- **Data Sources:**
  - GEE satellite tree canopy (primary)
  - Census/USFS tree canopy (validation)
  - NYC Street Trees API (NYC only)
  - OSM parks (fallback)
- **Scoring:** Piecewise curve with saturation above 50% canopy
- **Bonuses:** Green View Index, biodiversity, canopy expectation, street trees

#### Scenic Bonus (0-35 points, capped)
- **Topography** (0-18 points): Relief, slope, steep terrain
  - Relief threshold: 300m (lowered from 600m)
  - Area-type-specific weights (rural: 0.6, urban: 0.5)
- **Landcover** (0-8 points): Forest, wetland, shrub, grass
- **Water** (0-40 points): Climate-adjusted expectations
  - Coastal bonuses, rarity bonuses (arid regions)
  - Area-type-specific weights

#### Context Bonus Weights (Area-Type-Specific)
- **Rural:** Topography 60%, Landcover 25%, Water 15%
- **Urban Core:** Topography 50%, Landcover 30%, Water 20%
- **Suburban:** Topography 50%, Landcover 30%, Water 20%

### Climate Adjustments (legacy)
- **Climate-first expectations:** Base expectations by climate zone (arid: 8%, temperate: 35%, etc.)
- **Area-type adjustments:** Multipliers within climate (urban_core: 0.75x, rural: 1.25x)
- **Water expectations:** Adjusted for climate (arid: 0.5x, tropical: 1.5x)

### Calibration/Tuning
- ❌ **No calibration** - `calibrated_raw = natural_score_raw`
- ✅ **Pure data-backed** - Component weights based on measurement importance
- 📊 **Ridge regression:** Advisory only (not used for scoring)

### Data Sources (legacy)
- GEE API (tree canopy, topography, landcover)
- Census API (tree canopy validation)
- OSM API (parks, viewpoints, enhancers)
- NYC API (street trees, NYC only)

### Natural Beauty Personalization (preference-based weights)
When **ENABLE_NATURAL_BEAUTY_PREFERENCE** is True, the pillar accepts a quiz-derived preference and shifts only **internal component weights**; the V7 formula shape, data sources, and caps are unchanged.

- **Quiz question:** “What kind of natural scenery matters most to you?”
- **Options:** `mountains` | `ocean` | `lakes_rivers` | `canopy` | `no_preference`
- **Rules:** Max 2 selections; `no_preference` is single-select only. If 2 options: interpolate (average the two profiles component-by-component).

**Profiles (overrides to V7 weights):**
- **Mountains:** tree_weight 0.20; scenic weights shift to topography-heavy (e.g. rural 75% topo, 15% landcover, 10% water). When **ENABLE_NATURAL_BEAUTY_VIEWSHED_BLEND** is True, topography is blended with V8 viewshed: `0.6×V7_topography + 0.4×viewshed_proxy` (fallback: V7 topography only if GEE viewshed fails).
- **Ocean:** tree_weight 0.20; water-heavy scenic weights; water sub-weights 80% coast, 10% lake, 10% river.
- **Lakes/Rivers:** tree_weight 0.22; water sub-weights 15% coast, 55% lake, 30% river.
- **Canopy:** tree_weight 0.50; landcover-heavy scenic weights. If GEE canopy confidence &lt; **CANOPY_CONFIDENCE_THRESHOLD** (default 0.5), fall back to V7 default weights for that request.

**API:** Request parameter `natural_beauty_preference` (JSON array string, e.g. `["mountains"]` or `["ocean","canopy"]`). Used in `/score`, `/score/jobs`, and `/score/stream`. Cache key includes preference so different preferences do not share cached responses.

#### Token allocation vs natural_beauty_preference (why Natural Beauty can show weight 50)
These are **two separate mechanisms**:

1. **Token allocation (pillar importance in total score)**  
   The **priorities** from the quiz (Life stage, Weekend energy, Car, Horizon) are converted to pillar weights in the frontend (`inferWeights`), then to Low/Medium/High. The backend turns those into a **100-token allocation** (None=0, Low=1, Medium=2, High=3, then proportional). So the "weight" you see for Natural Beauty (e.g. 50 or ~8 tokens) is **only** from that priority logic.  
   **Currently**, the "What kind of natural scenery matters most to you?" answers are **not** used in `inferWeights`, so they do not change Natural Beauty’s priority. If no other answer (e.g. "Outside — hiking, biking, on the water") raises Natural Beauty, it stays at the default **50** (Medium).

2. **natural_beauty_preference (how the pillar score is computed)**  
   Your 1–2 scenery choices are sent as `natural_beauty_preference` and **only** change the **internal** Natural Beauty formula: tree vs topography vs water weights, water type split (coast/lake/river), and viewshed blend for mountains. They change **what** we score (e.g. more weight on mountains or ocean), not **how much** that pillar contributes to the total. So you can have Natural Beauty at weight 50 (Medium) and still have the pillar score personalized (e.g. mountain-heavy or ocean-heavy).

**Optional:** The frontend boosts Natural Beauty’s importance (to High when possible) when the user selects one or two scenery options and not "No strong preference", so the pillar gets more tokens and the displayed weight reflects that they care about natural scenery.

---

## 2. Active Outdoors (`pillars/active_outdoors.py`)

### Scoring Method
**Data-backed weighted component sum** (no calibration)

### Formula
```
daily_score = Daily Urban Outdoors (0-30)
wild_score = Wild Adventure Backbone (0-50)
water_score = Waterfront Lifestyle (0-20)

raw_total = (0.30 * daily_score) + (0.50 * wild_score) + (0.20 * water_score)
final_score = raw_total  # No calibration
```

### Components

#### Daily Urban Outdoors (0-30 points)
- **Parks:** Area (0-15) + Count (0-10) + Playgrounds (0-5)
- **Recreational Facilities:** Tennis courts, fields, etc. (0-3)
- **Data Source:** OSM green spaces
- **Expectations:** Area-type-specific (research-backed)
- **Penalty:** Urban core overflow penalty (prevents OSM artifact inflation)

#### Wild Adventure Backbone (0-50 points)
- **Trails:** Total count (0-28) + Near count (0-18) for mountain towns
- **Canopy:** 5km tree canopy (0-14)
- **Camping:** Distance-based (0-10)
- **Data Source:** OSM nature features, GEE canopy
- **Expectations:** Area-type-specific, higher for mountain towns
- **Filtering:** Urban paths filtered from trails in dense cores

#### Waterfront Lifestyle (0-20 points)
- **Water Types:** Beach (20), Lake (18), Coastline (12), Bay (10)
- **Distance Decay:** Exponential (optimal: 3km)
- **Context Adjustments:** Urban cores downweighted (0.4x), desert contexts (0.3x)

### Special Context Detection
- **Mountain Towns:** Detected by trail count + canopy (objective criteria)
- **Desert Contexts:** Detected by canopy <3% + water <10 features
- **Effective Area Type:** Mountain towns use exurban expectations

### Calibration/Tuning
- ❌ **No calibration** - `calibrated_total = raw_total`
- ✅ **Pure data-backed** - Component weights: 30% daily, 50% wild, 20% water
- 📊 **Ridge regression:** Advisory only (not used for scoring)

### Data Sources
- OSM API (parks, trails, water, camping)
- GEE API (tree canopy 5km)
- Research-backed expected values (area-type-specific)

---

## 3. Access to Nature (`pillars/access_to_nature.py`)

### Scoring Method
**Data-backed weighted component sum** (no calibration)

### Question
“What does it feel like when I step outside my front door?  
How quickly can I be in a natural environment – trees/greenery, water, or hills?”

### Formula
Access to Nature combines three equal-footing components:

```
greenery = local-biased canopy + neighborhood canopy + park access
water    = proximity + visibility (coast / lakes / rivers)
elev     = local relief / topographic variety (5 km radius)

final_score = 0.35 × greenery + 0.35 × water + 0.30 × elev
```

### Components

#### Greenery Access (0–100, 35% weight)
- **Goal:** “Tree-lined streets and everyday neighborhood green.”
- **Signals:**
  - Local canopy (GEE 1000 m radius, blended with Census/USFS canopy when available)
  - Neighborhood canopy (GEE 3000 m radius)
  - Distance to nearest park / large green space (OSM parks, ~5 km search, favoring 10+ acre parks)
- **Scoring (illustrative):**
  - Local canopy: `local_canopy_score = min(100, canopy_local_pct × 2.0)` → 50% canopy = 100 pts
  - Neighborhood canopy: `neighborhood_canopy_score = min(100, canopy_neighborhood_pct × 1.5)`  
  - Park access: `park_access_score = distance_decay(nearest_park_km, max_dist=5)` (0 km → 100, 5 km → 0)
  - Combined:
    - 50% local canopy
    - 20% neighborhood canopy
    - 30% park access

#### Water Access (0–100, 35% weight)
- **Goal:** “Living near real water – ocean, lakes, or rivers – with visible water nearby.”
- **Signals:**
  - **Natural Earth 10m**:
    - Distance to coastline
    - Distance to major lakes (scalerank ≤ 2)
    - Distance to major rivers (scalerank ≤ 4)
  - **GEE landcover**: `water_pct` near the point (micro-scale visibility)
- **Scoring:**
  - Proximity subscore 0–100 from Natural Earth (coast, lakes, rivers) with distance decay.
  - Visibility subscore 0–100 from GEE water_pct.
  - Combined 50% proximity + 50% visibility (implemented via `data_sources.water_proximity_ne.calculate_water_score`).

#### Elevation Access (0–100, 30% weight)
- **Goal:** “Hills and relief you can feel nearby,” not just raw altitude.
- **Signals:**
  - GEE `get_topography_context(lat, lon, 5km)`:
    - `relief_range_m` (max–min elevation in 5 km radius)
- **Scoring (piecewise example):**
  - 0 m relief → 0 pts (flat)
  - 100 m relief → ~25 pts (gentle hills)
  - 500 m relief → ~75 pts (significant hills)
  - 1000 m+ relief → 100 pts (mountainous terrain)
- **Design choice:** No large absolute-elevation bonus – this component measures local **variety/relief**, not just being at high elevation.

### Relationship to Active Outdoors and Natural Beauty
- **Active Outdoors** answers: “Can I be **active** outside regularly?”  
  - Focuses on recreation: trails, camping, swimming, playgrounds, rec facilities.
- **Access to Nature** answers: “Does nature feel like part of my **everyday environment**?”  
  - Focuses on ambient environment at the front door: tree-lined streets, nearby parks, water, and hills.
- **Natural Beauty (legacy)** remains a broader scenic/beauty construct and can be deprecated in favor of Access to Nature if this pillar performs well in practice.

### Calibration/Tuning
- ❌ **No calibration** – final score is direct weighted average of component scores.
- ✅ **Pure data-backed** – components are objective (canopy %, park distance, water distance, relief).
- ✅ **Graceful degradation** – if a data source is missing (e.g., Natural Earth water not installed), that component safely contributes 0 instead of failing.

### Data Sources
- **GEE API:** Tree canopy (1000m, 3000m), topography context (relief).
- **Census/USFS:** Tree canopy (blended with GEE for local canopy).
- **OSM API:** Parks and green spaces (for park access).
- **Natural Earth 10m:** Coastline, major lakes, major rivers (water proximity).

---

## 4. Neighborhood Amenities (`pillars/neighborhood_amenities.py`)

### Scoring Method
**Data-backed component sum** (no calibration)

### Formula
```
home_walkability = density (0-25) + variety (0-20) + proximity (0-15)  # 0-60
location_quality = proximity_to_center (0-20) + vibrancy (0-20)  # 0-40

total_score = home_walkability + location_quality  # 0-100, no calibration
```

### Components

#### Home Walkability (0-60 points)
- **Density** (0-25): Business count within walkable distance
  - Context-aware thresholds (urban: 60+, suburban: 50+, rural: 35+)
- **Variety** (0-20): Tier diversity (daily essentials, social, culture, services)
- **Proximity** (0-15): Median distance to businesses
  - ≤200m: 15pts, ≤400m: 13pts, ≤600m: 11pts, etc.

#### Location Quality (0-40 points)
- **Proximity to Center** (0-20): Distance to downtown cluster
- **Vibrancy** (0-20): Variety + density in cluster
  - Context-aware thresholds (urban: 100+, suburban: 60+)

### Fallback Scoring
- **Urban/suburban areas:** Conservative minimums when OSM fails
- **Rationale:** Distinguishes API failures from genuine lack of amenities

### Calibration/Tuning
- ❌ **No calibration** - `calibrated_total = raw_total`
- ✅ **Pure data-backed** - Component thresholds based on research
- 📊 **Ridge regression:** Advisory only (not used for scoring)

### Data Sources
- OSM API (local businesses, categorized by tier)
- Census API (population density for area type detection)

---

## 4. Healthcare Access (`pillars/healthcare_access.py`)

### Scoring Method
**Data-backed ratio-based scoring** (not calibrated from target scores)

### Formula
```
hospital_score = count_score (0-20) + distance_score (0-15)  # 0-35
primary_care_score = ratio_score(primary_count / expected, max=25)  # 0-25
specialty_score = ratio_score(specialty_count / 8, max=15)  # 0-15
emergency_score = ratio_score(emergency_count / expected, max=10)  # 0-10
pharmacy_score = ratio_score(pharmacy_count / expected, max=15)  # 0-15

total_score = hospital + primary + specialty + emergency + pharmacy + bonuses
```

### Ratio Scoring Curve (Data-Backed)
Uses `RATIO_SCORING_PARAMS` (not calibrated from target scores):
- **1.0× expected** → 50% of max (meets basic needs)
- **1.5× expected** → 85% of max (good access)
- **2.5× expected** → 85% of max (excellent, plateaus)
- **3.0× expected** → 95% of max (exceptional)

**Rationale:** Based on objective healthcare access quality thresholds, not target scores.

### Components

#### Hospital Access (0-35 points)
- **Count-based** (0-20): Ratio to expected hospitals
- **Distance-based** (0-15): Exponential decay (5km=15pts, 10km=12pts, etc.)
- **Fallback:** MAJOR_HOSPITALS database when OSM fails

#### Primary Care (0-25 points)
- **Clinics + Doctors:** Count ratio to expected urgent care
- **Fallback:** Conservative minimums for urban/suburban when OSM fails

#### Specialized Care (0-15 points)
- **Unique Specialties:** Count ratio (expected: 8 specialties)

#### Emergency Services (0-10 points)
- **Hospitals with ER:** Count ratio to expected hospitals

#### Pharmacies (0-15 points)
- **Pharmacy Count:** Ratio to expected (area-type-specific)

### Calibration/Tuning
- ❌ **No calibration** - Uses data-backed ratio thresholds
- ✅ **Pure data-backed** - `RATIO_SCORING_PARAMS` based on objective quality thresholds
- 📝 **Note:** Previously used `CALIBRATED_CURVE_PARAMS` - renamed to `RATIO_SCORING_PARAMS` to clarify data-backed nature

### Data Sources
- OSM API (hospitals, clinics, pharmacies, doctors)
- MAJOR_HOSPITALS database (fallback for hospitals)
- Research-backed expected values (area-type-specific)

---

## 5. Public Transit Access (`pillars/public_transit_access.py`)

### Scoring Method
**Data-backed route count normalization** (no calibration)

### Formula
```
heavy_rail_score = normalize_route_count(heavy_count, expected_heavy)  # 0-95
light_rail_score = normalize_route_count(light_count, expected_light)  # 0-95
bus_score = normalize_route_count(bus_count, expected_bus)  # 0-95

base_supply = max(heavy_rail_score, light_rail_score, bus_score)
multimodal_bonus = 3.0 (2 modes) or 6.0 (3+ modes)

total_score = base_supply + multimodal_bonus + commute_weight + commuter_bonuses
```

### Route Count Normalization (Data-Backed Breakpoints)
- **0 routes** → 0 points
- **1× expected** → 60 points ("meets expectations")
- **2× expected** → 80 points ("good")
- **3× expected** → 90 points ("excellent")
- **5× expected** → 95 points ("exceptional")
- **Above 5×** → Cap at 95

**Rationale:** Based on objective transit quality thresholds, not calibrated from target scores.

### Components

#### Heavy Rail (Subway/Metro/Commuter Rail)
- **Route Count:** Normalized against expected (area-type-specific)
- **Distance:** Nearest stop distance (informational)
- **Commuter Rail Bonuses:** Frequency, weekend service, hub connectivity, destinations

#### Light Rail (Streetcar/Tram)
- **Route Count:** Normalized against expected

#### Bus
- **Route Count:** Normalized against expected

#### Commute Time Weighting
- **Weight:** 5% of final score
- **Scoring:** Context-aware (urban: ≤20min=95pts, suburban: ≤25min=90pts)

#### Commuter Rail Suburb Bonuses
- **Frequency Bonus** (0-8): Weekday trips, peak headway
- **Weekend Service** (0-3): Weekend/weekday ratio
- **Hub Connectivity** (0-10): Direct service to major hubs
- **Destination Diversity** (0-2): Unique destinations
- **Commute Bonus** (0-5): Shorter commute times

### Fallback Scoring
- **Urban/suburban areas:** Conservative minimums when Transitland fails
- **Uses commute_time as proxy** when API unavailable

### Calibration/Tuning
- ❌ **No calibration** - Uses data-backed breakpoints
- ✅ **Pure data-backed** - Breakpoints based on objective transit quality
- 📝 **Note:** Comments updated to remove "calibrated" references

### Data Sources
- Transitland API (routes, stops, schedules)
- OSM API (railway stations, fallback)
- Census API (commute time)

---

## 6. 🏠 Price-to-Space (`pillars/housing_value.py`)

### Scoring Method
**Pure data-backed component sum** (no calibration)

### Formula
```
affordability_score = score_price_to_income_ratio(home_value / income)  # 0-50
space_score = score_rooms(median_rooms)  # 0-30
efficiency_score = score_rooms_per_100k(rooms / home_value * 100k)  # 0-20

total_score = affordability + space + efficiency  # 0-100
```

### Components

#### Local Affordability (0-50 points)
- **Price-to-Income Ratio:**
  - ≤2.0: 50pts (very affordable)
  - ≤3.0: 40pts (affordable, standard threshold)
  - ≤5.0: 20pts (expensive)
  - >7.0: 5pts (extremely expensive)

#### Space (0-30 points)
- **Median Rooms:**
  - ≥8: 30pts (large single-family)
  - ≥6.5: 25pts (typical single-family)
  - ≥4.5: 15pts (2-bed apartment)
  - <3.5: 5pts (studio)

#### Value Efficiency (0-20 points)
- **Rooms per $100k:** Higher = better value
- **Metro Adjustments:** High-cost metros get more forgiving thresholds (prevents double-penalization)
- **Smooth Curve:** 0.5+ rooms/$100k = excellent (18-20pts)

### Calibration/Tuning
- ❌ **No calibration** - Pure data-backed thresholds
- ✅ **Context-aware adjustments:** Metro-specific thresholds (not location-specific)
- 📝 **Note:** Metro adjustments prevent double-penalization, not tuning

### Data Sources
- Census API (median home value, household income, rooms)

---

## 7. Built Beauty (`pillars/built_beauty.py`)

### Scoring Method
**Pure data-backed component sum** (no calibration)

### Formula
```
architectural_score = score_architectural_diversity(...)  # 0-50
built_bonus = artwork + fountains  # 0-6 (capped)

built_native = architectural_score + built_bonus
built_raw = min(100.0, built_native * 2.0)  # Scale 0-50 to 0-100
final_score = normalize_beauty_score(built_raw, area_type)
```

### Components

#### Architectural Diversity (0-50 points)
- **Height Diversity:** Entropy of building levels
- **Type Diversity:** Building type variety
- **Footprint Variation:** Coefficient of variation
- **Form Metrics:** Block grain, streetwall continuity, setback consistency, facade rhythm
- **Bonuses:** Material, heritage, age, modern form, street character, rowhouse, serenity, scenic

#### Built Enhancers (0-6 points, capped)
- **Artwork:** 1.5 pts per artwork (max 4.5)
- **Fountains:** 0.5 pts per fountain (max 1.5)

### Normalization
- **Area-type-specific:** Uses `normalize_beauty_score()` with area-type context
- **Identity normalization:** shift=0, scale=1, max=100

### Calibration/Tuning
- ❌ **No calibration** - Pure data-backed scoring
- ✅ **No tuning** - All thresholds based on architectural measurement

### Data Sources
- OSM API (buildings, landmarks, artwork, fountains)
- Census API (year built, building age)
- Architectural diversity module (computed metrics)

### Built Beauty Personalization (preference-based weights)
When personalization is enabled, the pillar accepts **inline preference selectors** (not quiz questions). These live in the **expanded Built Beauty pillar card** in the UI.

**Two independent preference axes:**

1. **Character preference** — *What kind of architectural character feels like home?*
   - **Options:** Historic character | Contemporary design | No preference (single select).
   - **No preference:** Built Beauty’s weight in the HomeFit composite is halved; design score uses default weights.

2. **Density preference** — *What kind of built environment feels right day-to-day?*
   - **Options:** Houses and open space | Neighborhood blocks | City center (single select).
   - Shifts form-score component weights and area-type scoring targets (block grain, streetwall continuity) to match the selected profile.

**UX interaction:** Preferences are set **inline** on the Built Beauty pillar. The user **taps the Built Beauty pillar card** to expand it, then selects **chips** for character and density inside the expanded card. The **score updates immediately** when a chip is selected; there is **no separate quiz flow** for these preferences.

---

## 8. Air Travel Access (`pillars/air_travel_access.py`)

### Scoring Method
**Pure data-backed distance curves** (no calibration)

### Formula
```
score = score_best_3_airports(airports_within_150km)
  = weighted_sum(airport_scores) + redundancy_bonus

airport_score = base_score(airport_type) * exp(-decay_rate * (distance - optimal))
```

### Components

#### Large Airports (International Hubs)
- **Base Score:** 100pts (international), 90pts (major), 80pts (regional)
- **Optimal Distance:** 25km
- **Decay:** Exponential (decay_rate = 0.02)
- **Extended Range:** 100-150km with minimum floor (5pts)

#### Medium Airports
- **Base Score:** 60pts
- **Optimal Distance:** 30km
- **Decay:** Exponential (decay_rate = 0.015)
- **Extended Range:** Minimum floor (3pts)

#### Small Airports
- **Base Score:** 40pts
- **Optimal Distance:** 20km
- **Decay:** Exponential (decay_rate = 0.01)
- **Extended Range:** Minimum floor (2pts)

#### Redundancy Bonus
- **2+ airports:** +3pts per additional airport (max +10pts)

### Calibration/Tuning
- ❌ **No calibration** - Pure distance-based curves
- ✅ **No tuning** - Smooth exponential decay curves

### Data Sources
- Airport database (`data_sources/static/airports.json`)
- Legacy MAJOR_AIRPORTS list (fallback)

---

## 9. Neighborhood Beauty (`pillars/neighborhood_beauty.py`)

### Scoring Method
**Composition of Built Beauty + Natural Beauty** (no calibration)

### Formula
```
built_score = get_built_beauty_score(...)
natural_score = get_natural_beauty_score(...)

base_score = (tree_component * tree_weight) + (arch_component * arch_weight)
normalized_base = normalize_beauty_score(base_score, area_type)
beauty_bonus = min(cap, built_bonus + natural_bonus)

total_score = normalized_base + beauty_bonus
```

### Components
- **Built Beauty:** Architectural diversity + built enhancers
- **Natural Beauty:** Tree score + scenic bonus
- **Weights:** Area-type-specific (default: 50/50)

### Guardrail Check
- **Purpose:** Detects scores outside expected ranges (debugging)
- **Not Calibration:** Does not modify scores, only alerts
- **Acceptable:** Per design principles (transparent metadata)

### Calibration/Tuning
- ❌ **No calibration** - Composes two pure data-backed pillars
- ✅ **No tuning** - Uses default weights or user-provided weights

### Data Sources
- Composes `built_beauty` and `natural_beauty` pillars

---

## 10. Economic Security (`pillars/economic_security.py`)

### Scoring Method
**Weighted component sum** (Density, Mobility, Ecosystem, Resilience). Pure data-backed; no calibration toward target scores.

### Formula
```
S = w_D·D + w_M·M + w_E·E + w_R·R

D = density_score   (weight 0.40)
M = mobility_score (weight 0.15)
E = ecosystem_score (weight 0.20)
R = resilience_score (weight 0.25)
```

### Components

| Component | Weight | Meaning | Metrics (sub-weights) |
|-----------|--------|---------|------------------------|
| **D (Density)** | 0.40 | Volume and depth (market size) | `emp_pop_ratio` 0.25, `scale` 0.30 (normalized log₁₀ employment & estabs), `estabs_per_1k` 0.25, `wage_p25_annual` 0.20 |
| **M (Mobility)** | 0.15 | Upward trajectory | `qcew_employment_growth_pct` 0.40 (floor 40 when anchored_balance > 75), `net_estab_entry_per_1k` 0.35, `wage_p75_annual` 0.25 |
| **E (Ecosystem)** | 0.20 | Skill adjacency, networking | `industry_diversity` 0.70, `estabs_per_1k` 0.30 |
| **R (Resilience)** | 0.25 | Market stability | `industry_diversity` 0.60, `anchored_balance` 0.40 |

#### Anchored balance
- **Formula:** `(anchored_share - cyclical_share) / 100` (normalized to 0–100 for resilience).
- **Anchored:** Education & health + Public administration (ACS industry shares).
- **Cyclical:** Construction + Manufacturing + Leisure & hospitality.

### Calibration/Tuning
- ❌ **No calibration** - Component weights and sub-metrics are fixed.
- ✅ **Normalization:** Scale (log employment/establishments) normalized within Census Division × area-type bucket.
- **Job-category overlays:** Optional; personalize density only; same weights recompute S.

### Data Sources
- Census ACS (DP03, B01001, B25064) — employment, industry shares, income
- Census BDS — establishments, entry/exit (net establishment entry per 1k)
- BLS QCEW — employment level, YoY growth
- BLS OEWS — wage P25/P75
- Economic baselines (e.g. `data/economic_baselines.json`) — normalized scale, expectations

---

## 11. Quality Education (`pillars/schools.py`)

### Scoring Method
**Data-backed average of school ratings** with quality boost and small bonuses for early education and colleges. No calibration toward target scores.

### Formula
```
base_avg_rating = mean(school_ratings)   # 0–5 stars → 0–100 (×20)
quality_boost = f(base_avg_rating, excellent_schools_count)  # 0–10 pts
avg_rating = base_avg_rating + quality_boost
early_ed_bonus = 0–5 pts (OSM kindergarten/preschool within 2 km)
college_bonus = 0–5 pts (OSM university/college within 10 km)
total_score = min(100, avg_rating + early_ed_bonus + college_bonus)
```

### Components

#### K–12 core (0–100)
- **Rating source:** SchoolDigger API `rankStars` (0–5) → ×20 for 0–100 scale; fallback: `rankStatewidePercentage`.
- **Schools included:** Top schools per level (elementary, middle, high); exclude unrated or very low-rated when better options exist.
- **Quality boost:** Extra points when district has multiple highly-rated schools (e.g. base ≥80 and ≥3 schools → up to +10; 70+ with 3+ excellent → up to +8; etc.).

#### Early education bonus (0–5)
- **Data source:** OSM `amenity` ~ kindergarten|preschool|nursery within 2 km.
- **Thresholds:** 3+ → 5 pts, 2 → 3 pts, 1 → 2 pts; reduced if closest >1 km.

#### College bonus (0–5)
- **Data source:** OSM `amenity` ~ university|college within 10 km.
- **Thresholds:** 2+ → 5 pts; 1 → 2–5 pts by distance (≤2 km → 5, ≤5 km → 3, ≤10 km → 2).

### Calibration/Tuning
- ❌ **No calibration** - Direct use of external ratings and OSM counts.
- ✅ **Quality boost** - Rewards consistency of high ratings (not location-specific tuning).

### Data Sources
- SchoolDigger API (schools, ratings, rank history, level)
- OSM Overpass API (early education, colleges/universities)

---

## 12. Social Fabric (`pillars/social_fabric.py`)

### Scoring Method
**Weighted average of sub-indices** (Stability, Civic gathering, Diversity, Engagement). When a sub-index is missing (e.g. no IRS BMF data), renormalize over available components so score stays 0–100.

### Formula
```
weights = [1.2 (Stability), 1.2 (Civic), 1.0 (Diversity), 1.0 (Engagement)]
# Diversity and Engagement included only when data available
score = weighted_sum(values) / sum(weights)   # 0–100
```

### Components

#### Stability (0–100)
- **Data source:** Census B07003 (same house 1 year ago) → `same_house_pct`.
- **Scoring:** When regional baselines exist: z-score vs division mean/std, clipped, mapped to 0–100. Else: fixed curve (e.g. ≤85% → linear; >85% → gentle penalty for stagnation).

#### Civic gathering (0–100)
- **Data source:** OSM civic nodes (library, community_centre, place_of_worship, townhall, community_garden) within 800 m (walk); if 0, expand to 1500 m and use "proximity" curve.
- **Thresholds:** 0 → 0; 1–2 → 40; 3–5 → 70; 6+ → 100 (density). Proximity curve: 1–2 → 30; 3–5 → 55; 6+ → 85.

#### Diversity (0–100, optional)
- **Data source:** Census (race B02001, income B19001, age B01001).
- **Scoring:** Normalized Shannon entropy over race, income, and age (youth/prime/seniors); average of available dimensions.

#### Engagement (0–100, optional)
- **Data source:** IRS BMF (civic orgs); preprocessed to orgs per 1k.
- **Scoring:** Z-score vs regional (division/CBSA) mean/std, clipped, mapped to 0–100.

### Calibration/Tuning
- ❌ **No calibration** - Fixed weights and threshold curves.
- ✅ **Renormalization** - When Engagement (or Diversity) is missing, weights sum over present components only.

### Data Sources
- Census API (B07003 mobility, B02001/B19001/B01001 diversity)
- OSM API (civic nodes)
- IRS BMF (engagement; optional, when `data/` and build outputs available)
- Stability baselines (e.g. `data/stability_baselines.json`) for regional stability z-score

---

## 13. Climate Risk (`pillars/climate_risk.py`)

### Scoring Method
**Inverse risk:** higher raw risk → lower pillar score. Score 0 = very high risk, 100 = very low risk. **Phase 2:** heat + air + flood (FEMA NFHL) + climate trend (TerraClimate 30-year).

### Formula
```
heat_pts = max(0, 25 - (heat_excess_deg_c / 5) * 25)   # 0–25 pts
air_pts = max(0, 20 - (pm25_proxy_ugm3 / 35) * 20)     # 0–20 pts
flood_pts = from FEMA NFHL (floodway=0, SFHA=15%, X/D/minimal scaled)  # 0–30 pts
trend_pts = max(0, 25 - (trend_c_per_decade / 0.5) * 25)  # 0–25 pts, 0.5°C/decade = 0
total_raw = heat_pts + air_pts + flood_pts + trend_pts   # max 100
score = min(100, total_raw)
# If all data missing: score = 50 (neutral). Missing flood or trend → neutral pts (half of max).
```

### Components

#### Heat exposure (0–25 points)
- **Data source:** GEE (LST — land surface temperature); excess = local minus regional.
- **Threshold:** 5 °C excess → 0 pts; linear in between.

#### Air quality (0–20 points)
- **Data source:** GEE (Sentinel-5P Aerosol Index as PM2.5 proxy).
- **Threshold:** 35 µg/m³ (EPA Unhealthy) → 0 pts; linear below.

#### Flood zone (0–30 points)
- **Data source:** FEMA National Flood Hazard Layer (ArcGIS FeatureServer point-in-polygon).
- **Risk tiers:** floodway → 0 pts; SFHA (1% annual chance) → 15% of max; X (0.2%) → 55%; D → 45%; minimal/not in zone → 100%.
- **Neutral when missing:** 15 pts if FEMA request fails.

#### Climate trend (0–25 points)
- **Data source:** GEE TerraClimate (IDAHO_EPSCOR/TERRACLIMATE) monthly tmmx, 1990–2020.
- **Metric:** Linear trend in °C per decade (warming = worse).
- **Threshold:** 0.5 °C/decade warming → 0 pts; 0 → max pts; linear in between.
- **Neutral when missing:** 12.5 pts if GEE trend unavailable.

### Calibration/Tuning
- ❌ **No calibration** - Fixed thresholds (5 °C, 35 µg/m³, 0.5 °C/decade, FEMA tiers).
- ✅ **Neutral when missing** - No GEE data → score 50; missing flood or trend → half of that component’s max.

### Data Sources
- GEE API (LST for heat; Sentinel-5P Aerosol Index for air; TerraClimate for trend)
- FEMA NFHL (ArcGIS REST FeatureServer)

---


## Summary: Calibration/Tuning Status

| Pillar | Calibration | Tuning | Ridge Regression | Status |
|--------|-------------|--------|------------------|--------|
| **natural_beauty** | ❌ None | ❌ None | 📊 Advisory only | ✅ Pure data-backed (legacy scenic / canopy) |
| **active_outdoors** | ❌ None | ❌ None | 📊 Advisory only | ✅ Pure data-backed (recreation) |
| **access_to_nature** | ❌ None | ❌ None | ❌ None | ✅ Pure data-backed (front-door nature access) |
| **neighborhood_amenities** | ❌ None | ❌ None | 📊 Advisory only | ✅ Pure data-backed |
| **healthcare_access** | ❌ None | ❌ None | ❌ None | ✅ Data-backed ratios |
| **public_transit_access** | ❌ None | ❌ None | ❌ None | ✅ Data-backed breakpoints |
| **Price-to-Space (housing_value)** | ❌ None | ❌ None | ❌ None | ✅ Pure data-backed |
| **built_beauty** | ❌ None | ❌ None | ❌ None | ✅ Pure data-backed |
| **air_travel_access** | ❌ None | ❌ None | ❌ None | ✅ Pure data-backed |
| **neighborhood_beauty** | ❌ None | ❌ None | ❌ None | ✅ Composes other pillars |
| **economic_security** | ❌ None | ❌ None | ❌ None | ✅ Pure data-backed |
| **quality_education** | ❌ None | ❌ None | ❌ None | ✅ Data-backed + bonuses |
| **social_fabric** | ❌ None | ❌ None | ❌ None | ✅ Data-backed, renormalize when optional missing |
| **climate_risk** | ❌ None | ❌ None | ❌ None | ✅ Inverse risk, GEE data-backed |

### Key Points

1. **No Calibration:** All pillars removed `CAL_A`/`CAL_B` transforms
2. **No Tuning:** No location-specific adjustments or target-score-based tuning
3. **Ridge Regression:** Only exists as "advisory only" metadata (not used for scoring)
4. **Data-Backed:** All scoring based on objective metrics and research-backed thresholds
5. **Context-Aware:** Area-type-specific expectations and weights (not calibration)
6. **Fallback Scoring:** Conservative minimums for API failures (not calibration)

---

## Design Principles Compliance

✅ **Additive bonus structure** - No multiplicative multipliers  
✅ **Independent component caps** - Each component has its own cap  
✅ **Climate context awareness** - Adjusts expectations, not scores  
✅ **Identity normalization** - shift=0, scale=1, max=100  
✅ **Objective, data-driven** - No location-specific tuning  
✅ **Graceful degradation** - Fallback scoring for API failures  
✅ **Transparent metadata** - All scoring logic documented

---

## Data Sources Summary

| Source | Used By | Purpose |
|--------|---------|---------|
| **OSM API** | natural_beauty, active_outdoors, neighborhood_amenities, built_beauty, healthcare_access, quality_education, social_fabric | Parks, businesses, buildings, civic nodes, early ed, colleges |
| **GEE API** | natural_beauty, active_outdoors, climate_risk | Tree canopy, topography, landcover; LST heat; Sentinel-5P air quality; TerraClimate trend |
| **FEMA NFHL** | climate_risk | Flood zone (ArcGIS FeatureServer point-in-polygon) |
| **Census API** | All pillars (as needed) | Population density, housing, commute time, tree canopy, mobility B07003, diversity B02001/B19001/B01001 |
| **Transitland API** | public_transit_access | Transit routes, stops, schedules |
| **NYC API** | natural_beauty | Street trees (NYC only) |
| **Airport Database** | air_travel_access | Airport locations and types |
| **MAJOR_HOSPITALS** | healthcare_access | Hospital fallback database |
| **SchoolDigger API** | quality_education | Schools, ratings, rank history |
| **Census BDS / BLS QCEW / BLS OEWS** | economic_security | Establishments, employment growth, wage P25/P75 |
| **IRS BMF** | social_fabric | Civic org density (engagement; optional) |
| **Stability baselines** | social_fabric | Regional stability z-score |
| **Economic baselines** | economic_security | Normalized scale, expectations |

---

## Notes

- **Ridge Regression Coefficients:** Present in code but marked "advisory only" - not used for scoring
- **Expected Values:** Research-backed area-type-specific expectations (not target scores)
- **Fallback Scoring:** Handles API failures, not calibration
- **Context Adjustments:** Area-type-specific weights/expectations (not location-specific tuning)
