# Wave 2 Implementation Summary

**Status:** ✅ COMPLETED  
**Date:** January 2026

## Overview

Wave 2 implements non-linear scoring improvements for coverage and block grain metrics, making scoring more contextually appropriate for different area types.

---

## Wave 2.1: Coverage with Post-Peak Decline (Hump Shape)

### Problem
Coverage scoring was linear/monotonic, but very high coverage (>50-60%) feels oppressive and should score lower than optimal coverage levels.

### Solution
Implemented `_score_coverage_with_hump()` function that:
- **Peaks** at optimal coverage for each area type
- **Declines** at very high coverage (oppressive)
- Uses **area-type-specific** optimal ranges

### Implementation Details

**Peak Ranges (by area type):**
- **Urban Core**: 30-45% (declines after 55%)
- **Urban Residential**: 25-40% (declines after 50%)
- **Historic Urban**: 20-35% (declines after 45%)
- **Suburban**: 12-20% (declines after 30%)
- **Exurban/Rural**: 5-12% (declines after 20%)
- **Spacious Historic**: 15-25% (relaxed, declines after 35%)

**Scoring Curve:**
1. Below peak: Linear rise (0-80% of max at peak_start)
2. Peak range: Full points (95-100% of max)
3. Post-peak: Gentle decline (100% → 70% of max)
4. High coverage: Steeper decline (70% → 30% of max)
5. Very high: Steep penalty (30% → 0% of max)

### Test Results

```
urban_core:
  Coverage 10%: 4.00 points  (below peak)
  Coverage 30%: 14.25 points (in peak)
  Coverage 50%: 12.75 points (post-peak decline)
  Coverage 70%: 4.50 points  (high coverage penalty)
  Coverage 90%: 1.50 points  (very high penalty)

suburban:
  Coverage 10%: 10.00 points (in peak)
  Coverage 30%: 10.50 points (at decline start)
  Coverage 50%: 4.09 points  (penalty)
```

---

## Wave 2.2: Non-Linear Block Grain with Area-Type Sweet Spots

### Problem
Block grain scoring was linear, but different area types prefer different grain characteristics:
- Urban: Prefer finer grain (more intersections, walkable)
- Suburban: Prefer moderate grain (balanced)
- Exurban/Rural: Prefer coarser grain (more private)

### Solution
Implemented `_score_block_grain_with_sweet_spot()` function that:
- Uses **area-type-specific sweet spots**
- **Penalizes** extreme values (too fine or too coarse)
- **Non-linear** scoring curve

### Implementation Details

**Sweet Spots (by area type):**
- **Urban Core/Residential**: 60-85 (prefers finer grain for walkability)
  - Decline <40 (too coarse) or >95 (too fine)
- **Historic Urban**: 50-75 (slightly lower than urban)
  - Decline <30 or >90
- **Suburban**: 40-65 (moderate grain, balanced)
  - Decline <25 or >80
- **Exurban/Rural**: 30-45 (coarser grain, more private)
  - Decline <15 or >65

**Scoring Curve:**
1. Below sweet spot: Linear rise to sweet spot
2. Sweet spot range: Full points (85-100% of max)
3. Above sweet spot: Gradual decline
4. Extreme values: Steeper penalty

### Test Results

```
urban_core:
  Block Grain 20: 5.00 points  (too coarse)
  Block Grain 40: 10.00 points (rising to sweet spot)
  Block Grain 60: 14.17 points (in sweet spot)
  Block Grain 80: 16.17 points (peak of sweet spot)
  Block Grain 100: 0.00 points (too fine, penalty)

suburban:
  Block Grain 20: 6.67 points  (below sweet spot)
  Block Grain 40: 13.34 points (entering sweet spot)
  Block Grain 60: 16.00 points (peak of sweet spot)
  Block Grain 80: 10.84 points (decline from sweet spot)
  Block Grain 100: 0.00 points (too fine, penalty)

exurban:
  Block Grain 20: 9.17 points  (below sweet spot)
  Block Grain 40: 15.84 points (peak of sweet spot)
  Block Grain 60: 10.42 points (decline from sweet spot)
  Block Grain 80: 4.76 points  (steep decline)
```

---

## Files Changed

- `data_sources/arch_diversity.py`:
  - Added `_score_coverage_with_hump()` function (Wave 2.1)
  - Added `_score_block_grain_with_sweet_spot()` function (Wave 2.2)
  - Updated coverage scoring (line ~2404) to use hump function
  - Updated block grain scoring (line ~2464) to use sweet spot function

---

## Expected Impact

1. **Better Coverage Differentiation**: Very high coverage areas (>60%) will score lower, preventing oppressive environments from scoring well
2. **Area-Type-Appropriate Block Grain**: Each area type now prefers its optimal grain characteristics
3. **More Nuanced Scoring**: Non-linear curves capture human perception better than linear scoring
4. **Contextual Accuracy**: Scores better reflect what's desirable in each context

---

## Testing Recommendations

1. Test on diverse locations with different coverage levels
2. Verify that very high coverage areas score appropriately lower
3. Check that block grain scoring aligns with area-type preferences
4. Compare Wave 2 scores vs. Wave 1 scores to measure impact

---

## Next Steps

- Wave 3: Sprawl detection and extreme variation limits
- Wave 4: Confidence-weighted material entropy
