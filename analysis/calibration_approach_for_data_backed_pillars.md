# Calibration Approach for Data-Backed Pillars

## Summary

We should use regression analysis from 177 locations to **calibrate** the data-backed scoring for `natural_beauty` and `active_outdoors`, but **NOT** use regression as the primary scoring method.

## Key Distinction: Calibration vs Model-Driven Scoring

### ✅ Acceptable: Regression-Informed Calibration
- **What**: Use regression analysis to determine optimal weights/thresholds for data-backed components
- **Example**: `neighborhood_amenities` uses linear calibration `y = ax + b` where `a` and `b` are determined from regression
- **Scoring remains**: Direct measurements (business counts) → calibrated score
- **Transparent**: Calibration parameters are explicit and documented

### ❌ Unacceptable: Regression as Primary Scoring
- **What**: Use ridge regression model to predict scores directly
- **Problem**: Non-transparent, requires training data, causes convergence
- **We just removed**: This from `natural_beauty` and `active_outdoors`

## Current Calibration Data

### active_outdoors
- **Source**: `analysis/active_outdoors_tuning_from_ridge.json`
- **Locations**: 56 locations with target scores
- **Components**: `daily_urban_outdoors`, `wild_adventure`, `waterfront_lifestyle`
- **Current calibration**: `CAL_A = 0.3445`, `CAL_B = 67.8642` (linear: `y = 0.3445x + 67.8642`)
- **Current scoring**: Weighted sum `0.30 * daily + 0.50 * wild + 0.20 * water` (no calibration applied yet)

### natural_beauty
- **Source**: `analysis/natural_beauty_tuning_from_ridge.json`
- **Locations**: 56 locations with target scores
- **Components**: `Tree Score`, `Water %`, `Slope`, `Developed %`, `Context Bonus`
- **Current scoring**: `(tree_score + natural_bonus_scaled) * (100/68)` (no calibration applied yet)

## Proposed Calibration Approach

### Option 1: Linear Calibration (Like neighborhood_amenities)
**Apply linear transform to data-backed scores:**
```python
# For active_outdoors
raw_score = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score
calibrated_score = CAL_A * raw_score + CAL_B
```

**Pros:**
- Simple and transparent
- Proven approach (used in `neighborhood_amenities`)
- Easy to understand and debug

**Cons:**
- May not capture non-linear relationships
- Single calibration for all area types

### Option 2: Area-Type-Specific Linear Calibration
**Apply different calibration per area type:**
```python
# For active_outdoors
raw_score = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score
cal_params = AREA_TYPE_CALIBRATIONS.get(area_type, DEFAULT_CAL)
calibrated_score = cal_params["a"] * raw_score + cal_params["b"]
```

**Pros:**
- Accounts for area-type differences
- Still transparent and data-backed
- Better fit to target scores

**Cons:**
- More parameters to maintain
- Requires sufficient data per area type

### Option 3: Component Weight Calibration
**Use regression to determine optimal component weights:**
```python
# For active_outdoors - optimize weights instead of applying calibration
# Regression suggests optimal weights from 56 locations
W_DAILY_OPTIMAL = 0.25  # From regression analysis
W_WILD_OPTIMAL = 0.55   # From regression analysis  
W_WATER_OPTIMAL = 0.20  # From regression analysis

calibrated_score = W_DAILY_OPTIMAL * daily_score + W_WILD_OPTIMAL * wild_score + W_WATER_OPTIMAL * water_score
```

**Pros:**
- Directly optimizes component weights
- No post-hoc calibration needed
- More interpretable (weights reflect importance)

**Cons:**
- Requires re-running regression analysis
- May need to update weights as data grows

## Recommended Approach

**Use Option 2: Area-Type-Specific Linear Calibration**

1. **For active_outdoors:**
   - Keep current component weights (0.30, 0.50, 0.20) - they're reasonable
   - Apply area-type-specific linear calibration from regression data
   - Use existing calibration parameters from `active_outdoors_tuning_from_ridge.json`

2. **For natural_beauty:**
   - Keep current component sum `(tree_score + natural_bonus_scaled) * (100/68)`
   - Apply area-type-specific linear calibration if needed
   - Or adjust the scaling factor `(100/68)` based on regression analysis

## Implementation Steps

1. **Extract calibration parameters from regression data**
   - Parse `active_outdoors_tuning_from_ridge.json` and `natural_beauty_tuning_from_ridge.json`
   - Calculate area-type-specific calibration parameters
   - Document calibration methodology

2. **Apply calibration to data-backed scoring**
   - Add calibration step after component calculation
   - Keep scoring data-backed (components remain direct measurements)
   - Mark calibration parameters clearly in code

3. **Test on 177 locations**
   - Verify variance restored (std > 1.0)
   - Verify scores align with target scores
   - Check for regressions >10 points

4. **Document calibration**
   - Create calibration documentation similar to `neighborhood_amenities_calibration_results.json`
   - Explain calibration methodology
   - Document calibration parameters

## Example Implementation

```python
# active_outdoors.py
# After calculating raw_total from components:

# Area-type-specific linear calibration (from regression analysis)
AREA_TYPE_CALIBRATIONS = {
    "urban_core": {"a": 0.35, "b": 65.0},      # From regression
    "urban_residential": {"a": 0.34, "b": 68.0},  # From regression
    "suburban": {"a": 0.36, "b": 67.0},        # From regression
    "exurban": {"a": 0.38, "b": 65.0},         # From regression
    "rural": {"a": 0.40, "b": 60.0},          # From regression
}

cal_params = AREA_TYPE_CALIBRATIONS.get(area_type, {"a": 0.3445, "b": 67.8642})
calibrated_total = cal_params["a"] * raw_total + cal_params["b"]
calibrated_total = max(0.0, min(100.0, calibrated_total))
```

## Benefits

1. **Maintains data-backed scoring**: Components remain direct measurements
2. **Improves accuracy**: Calibration aligns scores with target scores
3. **Restores variance**: Should eliminate convergence issues
4. **Transparent**: Calibration parameters are explicit and documented
5. **Design compliant**: Aligns with "Objective, Data-Driven Scoring" principle

## Next Steps

1. Extract calibration parameters from regression data files
2. Implement area-type-specific calibration
3. Test on 177 locations
4. Document calibration methodology
5. Commit changes
