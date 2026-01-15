# Wave 1 Implementation Summary

**Status:** ✅ COMPLETED  
**Date:** January 2026

## Overview

Wave 1 addresses the biggest conceptual bugs in the rule-based Built Beauty scoring system. These fixes tackle cases where scores can be clearly "wrong" to human perception, especially in auto-dominated contexts and everyday strips.

---

## 1.1 Diversity–Coherence Interaction (Suburban/Exurban)

### Problem
High diversity without coherence can feel chaotic in low-intensity contexts (suburban/exurban/rural). The system was scoring diversity positively regardless of coherence, allowing messy strips to score well just by being varied.

### Solution
Added `_apply_diversity_coherence_multiplier()` function that:
- **Urban contexts** (urban_core, historic_urban, urban_residential): No penalty (diversity is good even without strong coherence)
- **Suburban/Exurban/Rural**: Diversity components (height, type, footprint) are multiplied by a coherence-based factor:
  - `f(0.0) = 0.6` (low coherence → 60% of diversity points)
  - `f(0.4) = 0.75` (moderate coherence → 75% of diversity points)
  - `f(0.7) = 1.0` (high coherence → 100% of diversity points)

### Implementation
- **Location:** `data_sources/arch_diversity.py`, lines ~1600-1640 (helper function), ~2340 (application)
- **Applied to:** `height_raw`, `type_raw`, `foot_raw` components
- **Applied after:** Coherence signal calculation (needs coherence_signal)

### Expected Impact
- Suburban/exurban strips with high diversity but low coherence will score lower
- Areas with high coherence (unified materials, consistent setbacks) will maintain diversity scores
- Urban areas unaffected (diversity always rewarded)

---

## 1.2 Parking-Aware Footprint CV

### Problem
Footprint CV (coefficient of variation) treats all variation equally. Large parking lots or big boxes interspersed with small buildings inflate CV positively, making "big box + lot" look like organic variety.

### Solution
Added `_estimate_parking_paved_share()` function that:
- Queries OSM for parking lots, parking areas, and high-capacity roads
- Estimates paved/parking share of the area
- If parking share >15%, applies a penalty to footprint CV:
  - `parking_penalty = min(0.3, parking_share * 2.0)` (max 30% reduction)
  - Re-scores footprint with adjusted CV

### Implementation
- **Location:** `data_sources/arch_diversity.py`, lines ~1642-1695 (helper function), ~2327-2338 (application)
- **OSM Query:** Searches for `amenity=parking`, `parking=*`, and major roads (`highway=motorway|trunk|primary`)
- **Current Limitation:** Uses count-based heuristic (each feature ≈2% paved share, capped at 50%)
  - Future improvement: Calculate actual areas from OSM way geometries

### Expected Impact
- Areas dominated by parking lots won't get inflated footprint variation scores
- Organic neighborhood variety (actual building size diversity) still rewarded
- Graceful degradation: Returns `None` if query fails (no penalty applied)

---

## 1.3 Area-Type-Specific Streetwall Behavior

### Problem
Streetwall continuity was scored the same way for all area types (linear 0-100 → 0-16.67). In rural/exurban contexts, very high continuity can indicate auto-oriented strip development, not beautiful urban form.

### Solution
Added `_score_streetwall_contextual()` function with area-type-specific scoring:

1. **Urban contexts** (urban_core, historic_urban, urban_residential):
   - Linear mapping: 0-100 → 0-16.67 (unchanged behavior)

2. **Suburban**:
   - Peak at moderate continuity (60-80): Full points
   - Decline at extremes (<40 or >80): Reduced points
   - Rationale: Some gaps are OK, but too much continuity = strip mall

3. **Exurban/Rural**:
   - Peak at 50-70: Full points
   - Penalize >70: Too continuous for rural/exurban (indicates stripmall pattern)
   - Maximum penalty: 10.0 points (down from 16.67) at 100% continuity

### Implementation
- **Location:** `data_sources/arch_diversity.py`, lines ~1697-1725 (helper function), ~2395-2399 (application)
- **Replaces:** Previous linear mapping `(streetwall_value / 100.0) * 16.67`

### Expected Impact
- Rural/exurban areas with stripmall patterns will score lower
- Village main streets with appropriate gaps won't be penalized
- Urban areas maintain strong reward for continuous streetwalls

---

## Testing & Validation

### Next Steps
1. **Back-test against 60-location research set:**
   - Verify suburban/exurban strips with low coherence score appropriately lower
   - Check that parking-dominated areas (e.g., strip malls) don't get inflated scores
   - Confirm rural/exurban streetwall scores cap appropriately

2. **Regression testing:**
   - Ensure urban areas maintain similar scores (changes should be minimal)
   - Check that high-quality suburban/exurban areas (with coherence) aren't penalized

3. **Edge cases:**
   - Areas with no parking data (parking query returns None)
   - Areas with very low coherence signal
   - Mixed contexts (e.g., suburban main street transitioning to exurban)

---

## Code Locations

### New Functions
- `_apply_diversity_coherence_multiplier()`: Lines ~1600-1640
- `_estimate_parking_paved_share()`: Lines ~1642-1695
- `_score_streetwall_contextual()`: Lines ~1697-1725

### Modified Sections
- Footprint scoring: Line ~2071 (initial), ~2327-2338 (parking adjustment)
- Diversity multiplier application: Lines ~2340-2344
- Streetwall scoring: Lines ~2395-2399

---

## Known Limitations & Future Improvements

1. **Parking share estimation** (Wave 1.2):
   - Currently uses count-based heuristic
   - Could be improved with actual area calculations from OSM geometries
   - Could incorporate building-to-parcel ratios if parcel data available

2. **Coherence multiplier thresholds** (Wave 1.1):
   - Current thresholds (0.4, 0.7) based on theoretical analysis
   - May need calibration based on test results with 60-location set

3. **Streetwall scoring curves** (Wave 1.3):
   - Piecewise linear functions may need refinement
   - Could consider smoother curves (e.g., sigmoid) based on test feedback

---

## Files Modified

- `data_sources/arch_diversity.py`: Added 3 helper functions, modified scoring logic
