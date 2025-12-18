# Natural Beauty Fix Summary

## Problem Identified

1. **Low correlation** (R² = 0.0242) between raw scores and target scores
2. **Tree score dominated** (0-50 points) vs scenic bonus (0-18 points)
3. **Urban areas scored high** (high tree canopy) but low natural beauty
4. **Mountain/coastal areas scored low** (low tree canopy) but high natural beauty
5. **Stale calibration data** from old ridge regression implementation

## Solution Implemented

### Component Weight Adjustment

**Adjusted weights to better reflect natural beauty:**

```python
# OLD: Tree dominates (73.5% of max score)
raw_score = (tree_score + natural_bonus_scaled) * (100/68)
# Tree: 0-50 points, Scenic: 0-18 points

# NEW: Scenic features weighted more (60% of max score)
tree_weighted = tree_score * 0.4  # Max 20 points (40%)
scenic_weighted = min(30.0, natural_bonus_scaled * 1.67)  # Max 30 points (60%)
raw_score = (tree_weighted + scenic_weighted) * 2.0  # Scale 0-50 to 0-100
```

### Changes Made

1. ✅ **Reduced tree weight**: Tree score now contributes max 20 points (vs 50)
2. ✅ **Increased scenic weight**: Scenic bonus now contributes max 30 points (vs 18)
3. ✅ **Removed stale calibration**: Calibration using old data removed
4. ✅ **Stayed data-backed**: All components are objective, measurable metrics

## Design Principles Compliance

✅ **Data-Backed**: Tree canopy, topography, water, landcover - all objective metrics
✅ **Additive Bonuses**: Formula uses addition, not multiplication
✅ **Independent Caps**: Tree and scenic components capped independently
✅ **Objective Metrics**: No subjective judgments or location-specific tuning
✅ **Transparent**: Component weights documented in breakdown

## Next Steps

1. ⏳ **Re-collect calibration data** using new scoring formula
   - Run collector script on 177 locations
   - Extract raw scores with new component weights
2. ⏳ **Calculate new calibration parameters** from fresh data
   - Run linear regression on new raw scores vs target scores
   - Calculate CAL_A and CAL_B if needed
3. ⏳ **Apply calibration** (if needed)
   - May not be needed if component weights are correct
   - Test accuracy with validation script

## Files Modified

- `pillars/natural_beauty.py`: Adjusted component weights, removed stale calibration
- `analysis/natural_beauty_component_weight_adjustment.md`: Documentation

## Expected Impact

- **Better correlation** with target scores (scenic features weighted more)
- **More accurate scoring** for mountain/coastal areas
- **Reduced urban bias** (tree canopy less dominant)
- **Maintains variance** (no convergence to single value)
