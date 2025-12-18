# Natural Beauty Fixes Applied: Back to Data-Backed Principles

## Summary

Implemented data-backed fixes to restore natural beauty scoring across urban, suburban, and rural environments. Removed complex calibration that was patching symptoms instead of fixing root causes.

## Changes Applied

### 1. Fixed Topography Scoring ✅

**Problem**: Topography scoring was too strict (600m relief required) and weighted too low.

**Changes**:
- Lowered relief threshold: **300m** instead of 600m (captures more scenic areas)
- Increased TOPOGRAPHY_BONUS_MAX: **18.0** instead of 12.0 (more impact)

**Code**:
```python
# pillars/natural_beauty.py
relief_factor = min(1.0, relief / 300.0)  # Was 600.0
TOPOGRAPHY_BONUS_MAX = 18.0  # Was 12.0
```

**Impact**: Scenic mountain areas (Jackson WY, Taos NM, Whitefish MT) will now get proper topography credit.

### 2. Increased Scenic Component Weight ✅

**Problem**: Scenic features (topography, water, landcover) were underweighted compared to tree coverage.

**Changes**:
- Increased topography context weight: **0.5-0.6** (was 0.3-0.45) depending on area type
- Increased enhancer cap: **25.0** instead of 18.0 (was NATURAL_ENHANCER_CAP)
- Rural areas: Topography weight **0.6** (was 0.45)
- Urban areas: Topography weight **0.5** (was 0.3)

**Code**:
```python
# pillars/natural_beauty.py - CONTEXT_BONUS_WEIGHTS
"rural": {
    "topography": 0.6,   # Was 0.45
    "landcover": 0.25,   # Was 0.35
    "water": 0.15        # Was 0.20
}
"urban_core": {
    "topography": 0.5,   # Was 0.30
    "landcover": 0.3,    # Was 0.35
    "water": 0.2         # Was 0.35
}

# pillars/beauty_common.py
NATURAL_ENHANCER_CAP = 25.0  # Was 18.0
```

**Impact**: Scenic features contribute more to natural beauty score.

### 3. Adjusted Raw Score Formula ✅

**Problem**: Tree score dominated, scenic features underweighted.

**Changes**:
- Reduced tree weight: **0.3** instead of 0.4 (max 15 points instead of 20)
- Increased scenic weight: **2.0** instead of 1.67, cap **35** instead of 30
- Scenic features now contribute max 35 points (was 30)

**Code**:
```python
# pillars/natural_beauty.py
tree_weighted = tree_score * 0.3  # Was 0.4
scenic_weighted = min(35.0, natural_bonus_scaled * 2.0)  # Was min(30.0, ... * 1.67)
```

**Impact**: Better balance between tree coverage and scenic beauty.

### 4. Removed Complex Calibration ✅

**Problem**: Area-type-specific calibration was patching symptoms (low R² values) instead of fixing root causes.

**Changes**:
- Temporarily disabled calibration
- Raw score is now used directly (no calibration transform)
- Will re-calculate calibration after fixes are validated

**Code**:
```python
# pillars/natural_beauty.py
# Calibration: Temporarily disabled pending re-calculation with fixed raw scores
calibrated_raw = natural_score_raw  # No calibration transform
```

**Impact**: Pure data-backed scoring. If calibration is needed after fixes, it will be minimal and based on properly measured raw scores.

## Expected Impact

### Rural Scenic Areas
- **Before**: Raw scores 20-30, gap 60-80 points from target
- **After**: Raw scores 45-60 (estimated), gap 30-50 points
- **Improvement**: ~25-30 points better

### Urban Areas
- **Before**: Mixed results, some high (parks), some low (downtowns)
- **After**: Better recognition of scenic features, topography matters more
- **Improvement**: More consistent scoring

### Suburban Areas
- **Before**: Moderate gap (~16 points)
- **After**: Better balance, scenic features weighted appropriately
- **Improvement**: Moderate improvement

## Next Steps

1. ✅ **Fixes Applied**: Topography, component weights, raw score formula
2. ⏳ **Test**: Run API calls on scenic locations to validate improvements
3. ⏳ **Re-collect Data**: Collect fresh calibration data with new raw scores
4. ⏳ **Re-calculate Calibration**: If needed, calculate new calibration parameters
5. ⏳ **Validate**: Check if R² improves or if calibration can be removed entirely

## Design Principles Restored

✅ **Data-backed**: Measure what actually makes natural beauty (topography, scenic features)
✅ **No individual tuning**: Fixed the measurement, not calibration for specific locations
✅ **Context-aware**: Different factors matter in different environments
✅ **Simple**: Fix root cause, not symptoms

## Files Modified

- `pillars/natural_beauty.py`: Topography scoring, context weights, raw score formula, calibration
- `pillars/beauty_common.py`: NATURAL_ENHANCER_CAP increased
