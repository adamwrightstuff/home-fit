# Natural Beauty Fix Proposal: Back to Data-Backed Principles

## Problem Summary

We've drifted from data-backed principles by adding complex calibrations that patch symptoms. The root cause: **we're measuring tree coverage, not scenic beauty**.

## Root Cause Analysis

### 1. Topography Scoring is Too Strict

**Current Implementation:**
```python
relief_factor = min(1.0, relief / 600.0)  # 600m relief → full credit
slope_factor = min(1.0, max(0.0, (slope_mean - 3.0) / 17.0))  # 20° mean slope → full
TOPOGRAPHY_BONUS_MAX = 12.0
```

**Problem:**
- Requires 600m relief for full credit (very strict)
- Many scenic mountain areas have 200-500m relief
- Max topography bonus is only 12.0 points
- Then weighted by 0.3 in context bonus → effectively max 3.6 points

**Impact:**
- Jackson WY (mountain town): Topography = 0.00
- Taos NM (scenic mountains): Topography = 0.00
- Whitefish MT (mountain resort): Topography = 0.00

### 2. Scenic Components Are Underweighted

**Current Formula:**
```
tree_weighted = tree_score * 0.4  # Max 20 points
scenic_weighted = min(30.0, natural_bonus_scaled * 1.67)  # Max 30 points
```

**Problem:**
- Tree score dominates (max 20 points)
- Scenic bonus (topography/water/landcover) is capped and weighted too low
- Context bonus (topography/water/landcover) is weighted by 0.3, then enhancer is capped at 18

**Impact:**
- Scenic rural areas get low scores despite dramatic landscapes
- Urban areas with parks get moderate scores, but not exceptional

### 3. Missing: Major Park Proximity

**Problem:**
- We measure tree canopy, but not proximity to major parks
- Park Slope has Prospect Park (585 acres, 30,000 trees) but it's not explicitly measured
- Tree score captures some of it, but not the full value

## Proposed Fix: Data-Backed Improvements

### Fix 1: Improve Topography Scoring

**Changes:**
1. Lower relief threshold: 300m instead of 600m (captures more scenic areas)
2. Increase TOPOGRAPHY_BONUS_MAX: 18.0 instead of 12.0 (more impact)
3. Better weighting: Topography should contribute more to scenic bonus

**Code Changes:**
```python
# In _score_topography_component:
relief_factor = min(1.0, relief / 300.0)  # 300m relief → full credit (was 600m)
TOPOGRAPHY_BONUS_MAX = 18.0  # Increased from 12.0
```

**Expected Impact:**
- Scenic mountain areas get proper credit
- Jackson WY, Taos NM, Whitefish MT get higher topography scores

### Fix 2: Increase Scenic Component Weight

**Changes:**
1. Increase context bonus weight: 0.5 instead of 0.3 (topography/water/landcover matter more)
2. Increase enhancer bonus cap: 25 instead of 18 (scenic features can contribute more)
3. Adjust component weights: Scenic features should contribute more than trees

**Code Changes:**
```python
# In context bonus calculation:
context_weights = {
    "topography": 0.5,  # Increased from 0.3
    "landcover": 0.3,   # Decreased from 0.35
    "water": 0.2        # Decreased from 0.35
}

# In enhancer bonus:
NATURAL_ENHANCER_CAP = 25.0  # Increased from 18.0

# In raw score calculation:
tree_weighted = tree_score * 0.3  # Reduced from 0.4 (max 15 points)
scenic_weighted = min(35.0, natural_bonus_scaled * 2.0)  # Increased from 1.67, cap 35
```

**Expected Impact:**
- Scenic features (topography, water, landcover) contribute more
- Rural scenic areas get higher scores
- Urban areas with parks get better recognition

### Fix 3: Measure Major Park Proximity (Future)

**Changes:**
1. Detect proximity to major parks (>100 acres)
2. Add park proximity bonus to enhancer
3. Weight by park size and distance

**Implementation:**
- Use OSM to find large parks within 2km
- Calculate park proximity score based on size and distance
- Add to enhancer bonus

**Expected Impact:**
- Park Slope gets credit for Prospect Park proximity
- Other urban areas with major parks get proper recognition

## Implementation Plan

### Phase 1: Fix Topography (Immediate)
1. Lower relief threshold to 300m
2. Increase TOPOGRAPHY_BONUS_MAX to 18.0
3. Test on scenic rural locations (Jackson WY, Taos NM, Whitefish MT)

### Phase 2: Increase Scenic Weight (Immediate)
1. Increase context bonus weight for topography
2. Increase enhancer bonus cap
3. Adjust component weights (reduce tree, increase scenic)
4. Test across all area types

### Phase 3: Remove Complex Calibration (After Fixes)
1. Re-collect calibration data with fixed raw scores
2. Calculate new calibration parameters
3. If R² improves significantly, keep minimal calibration
4. If R² is still low, investigate further fixes

### Phase 4: Add Park Proximity (Future)
1. Implement major park detection
2. Add park proximity scoring
3. Test on urban areas with major parks

## Success Criteria

1. **Rural scenic areas**: Raw scores closer to targets (gap < 20 points)
2. **Urban areas**: Better recognition of parks and scenic features
3. **Suburban areas**: Moderate improvement
4. **Calibration R²**: > 0.5 (good fit) or remove calibration entirely

## Design Principles

✅ **Data-backed**: Measure what actually makes natural beauty
✅ **No individual tuning**: Fix the measurement, not the calibration
✅ **Context-aware**: Different factors matter in different environments
✅ **Simple**: Fix root cause, not symptoms
