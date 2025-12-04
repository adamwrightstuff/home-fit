# Active Outdoors v2 Round 11 Adjustments

## Overview

Based on Round 11 calibration panel results, adjustments were made to address:
1. **Urban core over-scoring** (Times Square, Park Slope, Upper West Side scoring 10-30 points above target)
2. **Mountain town under-scoring** (Boulder, Park City, Denver, Seattle below target)
3. **Water access distance decay** (needed refinement for better proximity scoring)

## Changes Made

### 1. Wild Adventure Backbone - Urban Core Tree Canopy Reduction

**Problem**: Urban cores were over-scoring due to tree canopy contributing too much to "wild adventure" score. Urban tree canopy (even high percentages like 15-20%) shouldn't contribute significantly to "wildness" in dense areas.

**Change**: Reduced `max_canopy` for `urban_core` from **20.0 → 12.0**

```python
# Before:
max_trails_total, max_trails_near, max_canopy = 10.0, 5.0, 20.0  # urban_core

# After:
max_trails_total, max_trails_near, max_canopy = 10.0, 5.0, 12.0  # urban_core
```

**Impact**: This should reduce wild adventure scores for dense urban areas by up to 8 points (40% of canopy contribution), helping bring Times Square, Park Slope, and Upper West Side closer to targets.

### 2. Wild Adventure Backbone - Rural/Exurban Trail Expectations

**Problem**: Mountain towns like Boulder, Park City, and rural areas weren't scoring high enough for their trail richness.

**Changes**:
- Increased trail count expectations: **30.0 → 40.0**
- Increased near trail (within 5km) expectations: **10.0 → 15.0**
- Increased canopy expectations: **40.0 → 45.0**
- Increased max contributions:
  - `max_trails_total`: **20.0 → 22.0**
  - `max_trails_near`: **10.0 → 12.0**

```python
# Before:
exp_trails, exp_near, exp_canopy = 30.0, 10.0, 40.0
max_trails_total, max_trails_near, max_canopy = 20.0, 10.0, 10.0

# After:
exp_trails, exp_near, exp_canopy = 40.0, 15.0, 45.0
max_trails_total, max_trails_near, max_canopy = 22.0, 12.0, 10.0
```

**Impact**: Mountain towns and rural areas with dense trail networks should now score higher on wild adventure, helping Boulder, Park City, Truckee, etc. reach targets.

### 3. Camping Access - Area-Type-Aware Scoring

**Problem**: Camping scoring wasn't properly differentiated by area type. Urban areas with distant camping were being scored the same as rural areas.

**Change**: Made camping proximity scoring area-type-aware with different thresholds and decay rates:

```python
# Urban core: tighter threshold (15km), lower max (8.0), steeper decay
if area_type in {"urban_core", "historic_urban"}:
    if d <= 15_000:
        s_camp = 8.0
    else:
        s_camp = 8.0 * math.exp(-0.0001 * (d - 15_000))

# Suburban: medium threshold (20km), full max (10.0)
elif area_type in {"suburban", "urban_residential", "urban_core_lowrise"}:
    if d <= 20_000:
        s_camp = 10.0
    else:
        s_camp = 10.0 * math.exp(-0.00008 * (d - 20_000))

# Rural/exurban: more generous (25km), slower decay
else:
    if d <= 25_000:
        s_camp = 10.0
    else:
        s_camp = 10.0 * math.exp(-0.00005 * (d - 25_000))
```

**Impact**: More appropriate camping scoring based on area type expectations.

### 4. Water Access - Distance Decay Adjustment

**Problem**: Water access distance decay was too aggressive, penalizing moderate-distance water access.

**Changes**:
- Increased optimal distance: **2000m → 3000m**
- Slowed decay rate: **0.0003 → 0.00025**

```python
# Before:
optimal = 2_000.0
return max(0.0, base * math.exp(-0.0003 * (d - optimal)))

# After:
optimal = 3_000.0
return max(0.0, base * math.exp(-0.00025 * (d - optimal)))
```

**Impact**: Better scoring for locations with water access at moderate distances (e.g., Seattle with Puget Sound).

## Calibration Status

**⚠️ IMPORTANT**: Calibration parameters (CAL_A, CAL_B) need to be refit after these component changes.

Current placeholder values (from Round 9):
- `CAL_A = 1.768`
- `CAL_B = 36.202`

### Next Steps for Recalibration

1. Run the updated Active Outdoors v2 model on the Round 11 calibration panel
2. Collect raw_total scores (before calibration) for all locations
3. Fit linear regression: `target_score ≈ CAL_A * raw_total + CAL_B`
4. Update CAL_A and CAL_B in `active_outdoors.py`

### Expected Impact of Changes

**Urban Cores (should score lower)**:
- Times Square: Currently +29.3 above target → Should reduce by ~10-15 points
- Park Slope: Currently +15.9 above target → Should reduce by ~8-12 points
- Upper West Side: Currently +8.5 above target → Should reduce by ~5-8 points

**Mountain Towns (should score higher)**:
- Boulder: Currently -15.9 below target → Should increase by ~8-12 points
- Park City: Currently -10.4 below target → Should increase by ~6-10 points
- Denver: Currently -24.3 below target → Should increase by ~8-15 points
- Seattle: Currently -17.4 below target → Should increase by ~8-12 points

**Water Access**:
- Seattle: Should see improvement from better distance decay
- Other coastal locations: Moderate improvement for moderate-distance water

## Testing Recommendations

1. Re-run all Round 11 locations with updated model
2. Calculate new calibration parameters
3. Verify mean absolute error is ≤ 10 points
4. Check that no individual location is off by more than ~20 points without documented reason
5. Ensure correct relative ordering (outdoor towns > urban cores) is maintained

## Notes

- These changes maintain the design principles: no per-city hacks, area-type-aware expectations, smooth curves
- Component scoring changes affect raw_total, which then flows through calibration
- After recalibration, the overall score distribution should better match targets while maintaining relative ordering

