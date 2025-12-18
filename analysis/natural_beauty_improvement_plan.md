# Natural Beauty Calibration Improvement Plan

## Current Status

- **R²**: 0.0999 (improved from 0.0242, but still low)
- **Mean Error**: 16.93 points
- **Max Error**: 46.01 points (Jackson WY)

## Key Findings

### Pattern 1: High Target, Low Raw (Mountain/Coastal Areas)
**8 locations** with errors > 30 points
- Jackson WY (Target: 98, Raw: 20.91, Error: 46.01)
- Taos NM (Target: 90, Raw: 21.82, Error: 37.70)
- Whitefish MT (Target: 92, Raw: 30.90, Error: 36.63)

**Root Cause**: Low enhancer bonus (4-10 points) despite scenic beauty
- Topography bonus is too low (requires 600m relief for full credit)
- Many scenic areas have 200-500m relief (not 600m+)
- Topography is weighted by 0.3 in context bonus, further reducing impact

### Pattern 2: Low Target, High Raw (Urban Areas)
**4 locations** with errors > 30 points
- Harlem Manhattan NY (Target: 35, Raw: 83.92, Error: 38.32)
- Greenpoint Brooklyn NY (Target: 35, Raw: 72.73, Error: 34.53)

**Root Cause**: High tree coverage scores high, but Perplexity sees as low natural beauty
- Urban tree canopy ≠ natural beauty
- Already addressed by reducing tree weight, but may need further adjustment

## Proposed Solutions

### Option 1: Improve Topography Scoring (Recommended)
**Problem**: Topography bonus too low for scenic mountain areas

**Current Formula**:
```python
relief_factor = min(1.0, relief / 600.0)  # 600m relief → full credit
slope_factor = min(1.0, max(0.0, (slope_mean - 3.0) / 17.0))  # 20° mean slope → full
combined = (0.5 * relief_factor) + (0.3 * slope_factor) + (0.2 * steep_factor)
topography_bonus = TOPOGRAPHY_BONUS_MAX * combined  # Max 12.0
topography_weighted = topography_bonus * 0.3  # Context weight
```

**Proposed Changes**:
1. **Lower relief threshold**: 300m instead of 600m (captures more scenic areas)
2. **Increase TOPOGRAPHY_BONUS_MAX**: 18.0 instead of 12.0 (more impact)
3. **Increase topography weight**: 0.4 instead of 0.3 in context bonus
4. **Area-type-specific**: Rural/mountain areas get higher topography weight

### Option 2: Area-Type-Specific Calibration
**Problem**: Urban areas need different calibration than scenic areas

**Proposed**: Separate calibration for:
- **Urban areas** (urban_core, urban_residential): Different CAL_A, CAL_B
- **Scenic areas** (rural, exurban with high topography): Different CAL_A, CAL_B
- **Coastal areas**: Different calibration

### Option 3: Further Component Weight Adjustment
**Problem**: Scenic features still not weighted enough

**Current**:
- Tree: 40% (max 20 points)
- Scenic: 60% (max 30 points)

**Proposed**:
- Tree: 30% (max 15 points)
- Scenic: 70% (max 35 points)

## Recommendation

**Start with Option 1 (Improve Topography Scoring)**:
1. Lower relief threshold to 300m
2. Increase TOPOGRAPHY_BONUS_MAX to 18.0
3. Increase topography weight in context bonus to 0.4
4. Re-collect calibration data
5. Re-calculate calibration parameters

This should improve scores for mountain/coastal areas without affecting urban areas.

## Next Steps

1. ✅ Analyze errors (done)
2. ⏳ Implement topography improvements
3. ⏳ Re-collect calibration data
4. ⏳ Re-calculate calibration parameters
5. ⏳ Validate improvements
