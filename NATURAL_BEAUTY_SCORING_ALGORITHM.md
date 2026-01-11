# Natural Beauty Scoring Algorithm - Complete Breakdown

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
