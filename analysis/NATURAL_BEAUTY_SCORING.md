# Natural Beauty Scoring

Merged from the former root files `NATURAL_BEAUTY_SCORING_EXPLAINED.md` and `NATURAL_BEAUTY_SCORING_ALGORITHM.md`. Canonical implementation: [`pillars/natural_beauty.py`](../pillars/natural_beauty.py).

---

## Score Structure

The Natural Beauty score (0-100) uses a **weighted component sum** that scales to 100:

### Components (Max Total: 93.75 points, scaled to 100)

**1. Base Tree Score (15 points max)**
- Weight: 30% of base canopy score (0-50 scale)
- Formula: `(base_canopy_with_expectation) * 0.30`
- Includes expectation adjustments (climate/area-type adjustments)
- Max: 50 * 0.30 = **15 points**

**2. Green View Index (20 points max)**
- Weight: 20% of GVI (0-100 scale)
- Formula: `(green_view_index / 100.0) * 20.0`
- Visible greenery from street level (eye-level beauty)
- Max: **20 points**

**3. Street Trees (5 points max)**
- Weight: Direct (0-5 scale)
- Formula: `street_tree_bonus * 1.0`
- For urban areas with street trees but low satellite canopy
- Max: **5 points**

**4. Local Green Spaces (10 points max)**
- Weight: Direct (0-10 scale)
- Formula: `local_green_score * 1.0`
- Parks within 400m walking distance
- Max: **10 points**

**5. Context Bonus / Scenic Features (70 points max)**
- Weight: Context bonus (0-40 scale) multiplied by 1.75x
- Formula: `min(70.0, context_bonus * 1.75)`
- **Scenic beauty features beyond trees:**

**Context Bonus Components (capped at 25 points total):**

- **Topography** (max 20 points raw, then weighted):
  - Relief (elevation range): 300m relief = 1.0 factor, 400m+ relief = 1.2 factor (exceptional relief rewarded)
  - Slope (steepness): 20° mean slope = full credit
  - Prominence (peak height above surroundings): >200m = highly scenic
  - Ruggedness (elevation variation): 90m = 1.0 factor, 100m+ = 1.1 factor (exceptional ruggedness rewarded)
  - **Weight varies by landscape**: Mountain areas get 30% boost (0.627 weight for rural+mountain)
  - **Enhanced scoring**: Areas with relief >350m, ruggedness >80m, or prominence >180m get 45% enhanced weight (vs 40%)

- **Landcover** (max ~18 points raw, then weighted):
  - Forest coverage: 40% forest = full credit
  - Wetland coverage: 10% wetland = full credit
  - Shrub/grass diversity: Natural vegetation mix
  - **Weight**: ~0.20-0.30 depending on area type

- **Water** (max 40 points raw, then weighted):
  - Water coverage: Climate-adjusted (arid regions score higher for rare water)
  - Water proximity: Distance to major waterbodies (rivers, lakes, oceans)
    - <1km: 10.0 points
    - <3km: 8.0 points
    - <5km: 6.0 points
    - <10km: 4.0-5.0 points (5.0 for very large lakes >50km²)
    - <15km: 2.0-3.0 points (3.0 for very large lakes >50km²)
  - Large lake bonus: >50km² lakes get 1.4x multiplier and higher proximity bonuses
  - Coastal bonus: Ocean proximity adds extra points
  - Proximity bonus cap: 18.0 points (increased from 16.0 for exceptional water features)
  - **Weight**: ~0.15-0.20 depending on area type and landscape tags

- **Viewshed** (max 4 points):
  - Visible natural area: Percentage of visible landscape that's natural (forests, mountains, water)
  - >30% visible natural = full 4 points
  - Measures scenic backdrop/views (mountain backdrop, forests visible)

**Context Bonus Weight Application:**
Context bonus components are weighted by area type and landscape tags:
- **Mountain tag**: +30% topography weight, -10% landcover weight
- **Coastal tag**: +20% water weight, -15% landcover weight
- **Forest tag**: +15% landcover weight, -10% water weight
- **Desert tag**: +25% topography weight, -20% landcover weight

### Final Score Calculation

**Total Components**: 15 + 20 + 5 + 10 + 70 = **120 points max**
**Scaling**: Multiply by `(100.0 / 120.0)` to scale to 100

This means:
- Context bonus of 40 points → 40 * 1.75 = 70.0 weighted points (maximum)
- Context bonus of 25 points → 25 * 1.75 = 43.75 weighted points
- Context bonus of 11.08 points → 11.08 * 1.75 = 19.39 weighted points

## What Makes a High Natural Beauty Score (80-100)?

### Perfect Score Examples:

**1. Mountain Town with Lake (e.g., Aspen, CO)**
- Base Tree Score: 45-50 points (moderate-to-high canopy: 35-50%)
- Context Bonus: 20-25 points (capped)
  - Topography: 15-20 points (high relief 400m+, prominent peaks)
  - Water: 5-8 points (lake proximity <5km, large lake bonus)
  - Viewshed: 3-4 points (mountain backdrop visible)
  - Landcover: 2-4 points (mountain forests, meadows)
- **Total: 70-75 points**

**2. Coastal Forest (e.g., Pacific Northwest)**
- Base Tree Score: 48-50 points (very high canopy: 50-70%)
- Context Bonus: 18-25 points
  - Topography: 8-12 points (coastal mountains, moderate relief)
  - Water: 8-12 points (ocean proximity, coastal bonus)
  - Viewshed: 3-4 points (ocean views, forest backdrop)
  - Landcover: 4-6 points (dense temperate forests)
- **Total: 66-75 points**

**3. Urban Park City (e.g., Portland, OR)**
- Base Tree Score: 40-45 points (good canopy: 30-40%)
- Context Bonus: 12-18 points
  - Topography: 4-8 points (hills, moderate relief)
  - Water: 4-6 points (river proximity)
  - Viewshed: 2-3 points (visible greenery)
  - Landcover: 4-6 points (parks, street trees, local green spaces)
- **Total: 52-63 points**

## What Truckee, CA is Showing (Score: 41.2)

### Current Performance:

**Base Tree Score: 35.36 points** ✅ Good
- Weighted Canopy: 27.4% (neighborhood 40.3%, local 14.2%)
- Tree Base Score: 27.19 points
- Green View Index: 25.45 (eye-level greenery)
- Local Green Score: 6.0 points (parks nearby)

**Context Bonus: 11.08 points** ⚠️ **Too Low** (capped at 25.0)

**Why Context Bonus is Low:**

1. **Topography: 4.95 points (from raw 7.08)** ⚠️ **Underperforming**
   - Raw score: 7.08 out of 20.0 max
   - Relief: 394m (should be ~13.2 points alone at 300m threshold)
   - Ruggedness: 73.8m (good, but below 100m threshold for full credit)
   - Prominence: 0m (no prominent peak detected)
   - **Issue**: Topography scoring may be too conservative for 394m relief

2. **Water: 1.46 points (from raw 10.36)** ⚠️ **Severely Underperforming**
   - Raw score: 10.36 out of 40.0 max (good!)
   - Distance to Lake Tahoe: ~12-15km
   - **Issue**: Water weight too low (0.14 instead of expected 0.175-0.20)
   - Mountain tag should preserve water weight better with significant water

3. **Landcover: 0.66 points (from raw 4.16)** ⚠️ **Underperforming**
   - Raw score: 4.16 out of ~18.0 max
   - **Issue**: Low forest/vegetation coverage detected (mountain towns may have sparse vegetation)

4. **Viewshed: 4.00 points** ✅ Excellent
   - Visible Natural: 55.9% (excellent mountain backdrop visibility)

### Expected vs Actual:

**Expected for Mountain Town (Truckee):**
- Base Tree Score: 35-40 points ✅ **On target**
- Context Bonus: 18-25 points ❌ **Getting only 11.08** (should improve with new scoring)
  - Topography should be: 12-16 points (394m relief = 1.31 factor, 73.8m ruggedness = 0.82 factor, enhanced weights)
  - Water should be: 4-6 points (Lake Tahoe proximity with mountain tag, improved proximity bonuses for large lakes)
  - Viewshed: 4.0 points ✅ **Perfect**
  - Landcover: 2-3 points (acceptable for mountain towns)

**Total Expected: 55-65 points**
**Current: 41.2 points**
**Gap: -14 to -24 points**

### Why the Math Works Out:

For Truckee's current score of 41.2:
- Base Tree (weighted): ~10.5 points (35% of 15 max)
- GVI (weighted): ~5.1 points (25.45% of 20 max)
- Street Trees: 0 points
- Local Green: 6.0 points
- Context Bonus (weighted): ~19.4 points (11.08 * 1.75)

**Total weighted**: ~40.9 points → scaled to **41.2** (multiplied by 1.0667 to reach 100 scale)

The context bonus contribution is actually **19.4 points** (not 11.08) because it's weighted 1.75x before scaling.

## Why the Score is Low

1. **Topography Raw Score Too Low**: 7.08 points for 394m relief suggests the scoring function needs adjustment for high-relief mountain areas
2. **Water Weight Too Low**: Despite having significant water (Lake Tahoe 12-15km away), the water weight is only 0.14, giving only 1.46 points instead of expected 4-6 points
3. **Mountain Tag Weighting**: While mountain tag increases topography weight, the raw topography score itself is too low to benefit fully

## Recommendations

1. **Adjust Topography Scoring**: Increase raw score for relief >300m (current 394m relief should score higher)
2. **Preserve Water Weight**: Ensure mountain tag preserves water weight better when significant water is present (15km threshold is correct, but weight preservation needs work)
3. **Prominence Detection**: Improve prominence detection for mountain towns (Truckee has 0m prominence but should have some)


---

## Overview
The Natural Beauty score transforms raw environmental data into a 0-100 score that reflects human perception of scenic quality. The algorithm uses a **weighted component sum** approach with separate scoring for greenery, terrain, and water features.

---

## Step-by-Step Algorithm (Using Truckee, CA as Example)

### Step 1: Calculate Individual Component Scores

#### 1.1 Tree Base Score (0-50 scale)
- **Raw Data**: Canopy percentages from multiple radii
  - Neighborhood Canopy: 40.30%
  - Local Canopy: 14.20%
  - Extended Canopy: 41.50%
- **Calculation**: Weighted combination of multi-radius canopy data
- **Truckee Result**: **27.19** (on 0-50 scale)
- **Formula**: `base_tree_score = weighted_canopy_calculation(canopy_data)`

#### 1.2 Green View Index (GVI) (0-100 scale)
- **Raw Data**: Eye-level visible greenery from satellite/street data
- **Calculation**: Composite of visible green fraction, street-level NDVI, and park proximity
- **Truckee Result**: **25.45** (on 0-100 scale)
- **Formula**: `gvi = composite_greenness_metric(lat, lon)`

#### 1.3 Local Green Score (0-10 scale)
- **Raw Data**: Parks and green spaces within 400-1000m radius
- **Calculation**: Count and area of nearby parks with distance weighting
- **Truckee Result**: **6.0** (on 0-10 scale)
- **Formula**: `local_green = park_count_score + park_area_score`

#### 1.4 Context Bonus Components (0-40 raw scale)

The context bonus is the sum of four sub-components, each weighted by area type and landscape context:

##### 1.4.1 Topography Raw Score (0-20 max)
- **Raw Data**: 
  - Terrain Relief: 394m
  - Terrain Prominence: 0m
  - Terrain Ruggedness: 73.8m
- **Calculation**:
  ```
  relief_factor = min(1.3, relief / 250.0)  # 394m → 1.3 (capped)
  ruggedness_factor = min(1.2, ruggedness / 80.0)  # 73.8m → 0.922
  
  traditional_score = (0.4 * relief_factor) + (0.25 * slope) + (0.15 * steep)
  enhanced_score = (0.15 * prominence) + (0.15 * ruggedness_factor)
  
  # Weighted combination based on terrain quality
  if relief > 300 or ruggedness > 70:
      enhanced_weight = 0.45  # More weight to ruggedness
      traditional_weight = 0.55
  else:
      enhanced_weight = 0.30
      traditional_weight = 0.70
      
  combined = (traditional_weight * traditional_score) + (enhanced_weight * enhanced_score)
  topography_raw = TOPOGRAPHY_BONUS_MAX (20.0) * combined
  ```
- **Truckee Raw Result**: **7.16** (out of 20 max)
- **Mountain Tag Boost**: With "mountain" landscape tag, topography weight is 30% higher
- **Truckee Final**: **4.49** (7.16 × 0.627 mountain weight)

##### 1.4.2 Landcover Raw Score (0-20 max)
- **Raw Data**: Forest, wetland, shrub, grass percentages from satellite
- **Calculation**: Weighted sum of natural landcover types
- **Truckee Raw Result**: **4.16** (out of 20 max)
- **Truckee Final**: **0.82** (4.16 × 0.197 landcover weight for rural/mountain)

##### 1.4.3 Water Raw Score (0-18 max for proximity)
- **Raw Data**: 
  - Nearest water distance: 10-15km (Lake Tahoe)
  - Waterbody type: Lake
  - Waterbody area: Large (>50km²)
- **Calculation**:
  ```
  if nearest_distance_km < 1.0:
      proximity_bonus = 10.0 * type_weight
  elif nearest_distance_km < 5.0:
      proximity_bonus = 8.0 * type_weight  # For large lakes, could be 5.0
  elif nearest_distance_km < 10.0:
      proximity_bonus = 5.0 * type_weight  # For large lakes, could be 5.0
  elif nearest_distance_km < 15.0:
      proximity_bonus = 3.0 * type_weight  # For large lakes
  
  # Large lakes (>50km²) get 1.4x multiplier
  if waterbody_area > 50.0:
      proximity_bonus *= 1.4
      
  water_raw = min(18.0, proximity_bonus)  # Capped at 18.0
  ```
- **Truckee Raw Result**: **10.36** (out of 18 max)
- **Truckee Final**: **1.82** (10.36 × 0.176 water weight for rural/mountain)

##### 1.4.4 Viewshed Bonus (0-4 max)
- **Raw Data**: Visible natural area percentage from location
- **Calculation**: `viewshed_bonus = min(4.0, (visible_natural_pct / 30.0) * 4.0)`
- **Truckee Result**: **4.00** (55.9% visible natural → full bonus)

#### 1.5 Total Context Bonus Raw
```
context_bonus_raw = topography_final + landcover_final + water_final + viewshed_bonus
                  = 4.49 + 0.82 + 1.82 + 4.00
                  = 11.13
```

The raw context bonus (11.13) is then scaled:
```
natural_bonus_scaled = min(NATURAL_CONTEXT_BONUS_CAP (40.0), context_bonus_raw)
                     = 11.13  # Below cap, so unchanged
```

---

### Step 2: Apply Component Weights

Each component is weighted separately to create the final score:

```
tree_weighted = base_with_expectation * 0.30
               = 27.19 * 0.30
               = 8.157

gvi_weighted = (green_view_index / 100.0) * 20.0
              = (25.45 / 100.0) * 20.0
              = 5.09

street_tree_weighted = street_tree_bonus * 1.0
                      = 0 * 1.0  # Assuming no street trees
                      = 0.0

local_green_weighted = local_green_score * 1.0
                      = 6.0 * 1.0
                      = 6.0

scenic_weighted = min(70.0, natural_bonus_scaled * 1.75)
                 = min(70.0, 11.13 * 1.75)
                 = min(70.0, 19.48)
                 = 19.48
```

**Component Weight Summary**:
- Base Canopy: **15 points max** (50 × 0.30)
- GVI: **20 points max** (100 × 0.20)
- Street Trees: **5 points max** (5 × 1.0)
- Local Green: **10 points max** (10 × 1.0)
- Scenic/Context: **70 points max** (40 × 1.75)
- **Total Possible**: **120 points**

---

### Step 3: Calculate Raw Natural Beauty Score

```
natural_native = tree_weighted + gvi_weighted + street_tree_weighted + 
                 local_green_weighted + scenic_weighted
               = 8.157 + 5.09 + 0.0 + 6.0 + 19.48
               = 38.727

natural_score_raw = min(100.0, natural_native * (100.0 / 93.75))
                   = min(100.0, 38.727 * 1.0667)
                   = min(100.0, 41.31)
                   = 41.31
```

**Scaling Factor**: `100/93.75 = 1.0667`
- This maintains backwards compatibility with previous scores
- Scores above 93.75 weighted points scale proportionally up to 100
- The 120-point max allows exceptional areas to reach higher scores

---

### Step 4: Area-Type Normalization

The raw score (41.31) is then normalized based on area type to ensure fair comparison across different contexts (urban vs. rural vs. mountain).

**Normalization Function**:
```python
def normalize_beauty_score(raw_score: float, area_type: str) -> float:
    # Adjust expectations based on area type
    # Urban areas: Lower natural beauty baseline (expect less green)
    # Rural/Mountain: Higher natural beauty baseline (expect more scenic)
    
    # For Truckee (rural/mountain):
    # Minor adjustment to align with area-type expectations
    normalized_score = apply_area_type_normalization(raw_score, area_type)
    return normalized_score
```

**Truckee Final Score**: **41.3** (after normalization)

---

## Complete Formula Summary

```
Final Score = normalize(
    min(100.0, (
        (tree_base × 0.30) +
        (gvi / 100 × 20.0) +
        (street_trees × 1.0) +
        (local_green × 1.0) +
        min(70.0, context_bonus × 1.75)
    ) × (100.0 / 93.75)),
    area_type
)
```

Where:
- `context_bonus = (topography_raw × topo_weight) + 
                   (landcover_raw × landcover_weight) + 
                   (water_raw × water_weight) + 
                   viewshed_bonus`
- `topo_weight`, `landcover_weight`, `water_weight` are **adaptive** based on:
  - Area type (urban_core, suburban, rural, exurban)
  - Landscape tags (mountain, coastal, desert, forest, etc.)

---

## Adaptive Weighting System

The context bonus weights **automatically adjust** based on the detected landscape:

### Standard Weights (by Area Type)
- **Urban Core**: 
  - Topography: 0.40
  - Landcover: 0.40
  - Water: 0.20
- **Suburban**: 
  - Topography: 0.45
  - Landcover: 0.35
  - Water: 0.20
- **Rural** (Truckee's base):
  - Topography: 0.50
  - Landcover: 0.30
  - Water: 0.20

### Landscape Tag Adjustments
- **Mountain tag detected** (Truckee): 
  - Topography weight: +30% → **0.627** (was 0.50)
  - Landcover weight: Reduced proportionally → **0.197**
  - Water weight: Preserved → **0.176**

This ensures mountain areas emphasize terrain/views more than greenery, while urban areas prioritize parks and canopy.

---

## Key Design Principles

1. **Component-Based Scoring**: Each component (canopy, GVI, terrain, water) is scored independently and combined with explicit weights
2. **Adaptive Weighting**: Weights adjust automatically based on landscape context (urban vs. mountain vs. coastal)
3. **Transparency**: All raw scores and weights are exposed in the API response
4. **Backwards Compatibility**: Scaling factor (100/93.75) ensures existing scores remain stable
5. **Data-Driven**: All calculations use public/free data sources (GEE, OSM, Census)

---

## Example: How Context Bonus Weights Affect Score

For Truckee (rural, mountain tag):

| Component | Raw Score | Base Weight | Mountain Adjusted Weight | Final Contribution |
|-----------|-----------|-------------|--------------------------|-------------------|
| Topography | 7.16 | 0.50 | **0.627** (+25%) | 4.49 |
| Landcover | 4.16 | 0.30 | **0.197** (-34%) | 0.82 |
| Water | 10.36 | 0.20 | **0.176** (-12%) | 1.82 |
| Viewshed | 4.00 | 1.00 | **1.00** (unchanged) | 4.00 |
| **Total** | - | - | - | **11.13** |

**Without mountain tag** (standard rural weights):
- Topography: 7.16 × 0.50 = 3.58
- Landcover: 4.16 × 0.30 = 1.25
- Water: 10.36 × 0.20 = 2.07
- Viewshed: 4.00 × 1.00 = 4.00
- **Total**: **10.90**

The mountain tag boost adds **+0.23 points** to the context bonus, which translates to **+0.40 points** in the final score (after 1.75× scaling).

---

## References

- Full implementation: `pillars/natural_beauty.py`
- Topography scoring: `_score_topography_component()`
- Water proximity: `_score_landcover_component()`
- Adaptive weights: `_get_adaptive_context_weights()`
- Landscape tags: `data_sources/data_quality.py::get_natural_landscape_tags()`
