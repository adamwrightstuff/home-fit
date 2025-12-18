# Air Travel Access Tuning Changes

## Problem Identified
- **Bimodal distribution**: 36.7% of locations scored 0, 46.9% scored ≥90
- **Hard cutoff**: Locations >100km from airports received 0 score
- **Mean vs Median gap**: Mean 53.77 vs Median 84.1 indicates many zeros pulling down average

## Changes Made

### 1. Extended Search Radius
- **Before**: Only airports within 100km were considered
- **After**: Extended to 150km with reduced scoring for 100-150km range
- **Impact**: Locations 100-150km away now get scores instead of 0

### 2. Extended Decay Curves
Added extended decay functions for distances 100-150km:

- **Large airports**: Continue exponential decay with minimum floor of 5 points
- **Medium airports**: Continue decay with minimum floor of 3 points  
- **Small airports**: Continue decay with minimum floor of 2 points

### 3. Scoring Function Updates
- `_score_large_airport_smooth()`: Added extended range handling (100-150km)
- `_score_medium_airport_smooth()`: Added extended range handling (100-150km)
- `_score_small_airport_smooth()`: Added extended range handling (100-150km)

## Expected Impact

### Before Tuning:
- 36.7% zero scores
- Bimodal distribution (many 0s, many high scores)
- Mean: 53.77, Median: 84.1

### After Tuning:
- Reduced zero scores (locations 100-150km now get 2-10 points)
- Smoother distribution with better gradient
- More accurate representation of "moderate" air travel access

## Testing Recommendations

1. Re-run collector on test locations to verify distribution improvement
2. Check that locations 100-150km from airports now receive scores
3. Verify that locations <100km maintain similar scores
4. Confirm no impact on other pillars (air_travel_access is independent)

## Isolation
- Changes are isolated to `pillars/air_travel_access.py`
- No dependencies on other pillars
- No impact on `active_outdoors`, `natural_beauty`, or `quality_education`
