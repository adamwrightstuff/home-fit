# Natural Beauty Component Weight Adjustment

## Problem

The original raw score formula weighted tree canopy too heavily, causing:
- Urban areas with high tree coverage to score high (but low natural beauty)
- Mountain/coastal areas with low tree coverage to score low (but high natural beauty)
- Poor correlation with target scores (R² = 0.0242)

## Solution

Adjusted component weights to better reflect natural beauty while staying **data-backed**:

### Original Formula
```python
raw_score = (tree_score + natural_bonus_scaled) * (100/68)
# Tree: 0-50 points (73.5% of max)
# Scenic: 0-18 points (26.5% of max)
```

### New Formula
```python
tree_weighted = tree_score * 0.4  # Max 20 points
scenic_weighted = min(30.0, natural_bonus_scaled * 1.67)  # Max 30 points
raw_score = (tree_weighted + scenic_weighted) * 2.0  # Scale 0-50 to 0-100
# Tree: 0-20 points (40% of max)
# Scenic: 0-30 points (60% of max)
```

## Rationale

1. **Natural beauty is about scenic landscapes**, not just tree coverage
2. **Mountains, coastlines, wilderness** should matter more than urban tree canopy
3. **Data-backed**: All components are still objective, measurable metrics
4. **Design principles**: Additive bonuses, independent caps, objective metrics

## Impact

- **Reduces tree dominance**: Tree score now contributes max 20 points (vs 50)
- **Increases scenic weight**: Scenic bonus now contributes max 30 points (vs 18)
- **Better balance**: Scenic features (60%) weighted more than trees (40%)

## Next Steps

1. ✅ **Component weights adjusted** (this change)
2. ⏳ **Re-collect calibration data** using new scoring formula
3. ⏳ **Calculate new calibration parameters** from fresh data
4. ⏳ **Apply calibration** if needed (may not be needed if weights are correct)

## Design Principles Compliance

✅ **Data-Backed**: All components are objective metrics (tree canopy, topography, water, landcover)
✅ **Additive Bonuses**: Formula uses addition, not multiplication
✅ **Independent Caps**: Tree and scenic components capped independently
✅ **Objective Metrics**: No subjective judgments or location-specific tuning
✅ **Transparent**: Component weights documented in breakdown

## Files Modified

- `pillars/natural_beauty.py`: Adjusted component weights in raw score calculation
