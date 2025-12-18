# Neighborhood Amenities Tuning Changes

## Problem Identified
- **11 locations (6.2%) scoring 0** - including urban neighborhoods that should have amenities
- **OSM data gaps**: Some locations return 0 businesses from OSM even though they're in urban areas
- **Examples**: Coconut Grove Miami FL, Hyde Park Cincinnati OH, Sugar House Salt Lake City UT, 12 South Nashville TN

## Root Cause
- OSM data is incomplete for some locations (data gaps, not truly no amenities)
- Code returned 0 immediately when OSM returned no businesses
- No fallback mechanism for urban/suburban areas with OSM data gaps

## Changes Made

### 1. Added Fallback Scoring for OSM Data Gaps
- **Urban/Suburban areas**: Apply conservative minimum scores when OSM returns no data
- **High-density areas**: Use density as proxy when area_type classification is uncertain
- **Fallback scores by area type**:
  - Urban core: 25.0 points
  - Urban residential: 20.0 points
  - Suburban: 15.0 points
- **Density-based fallback** (when area_type uncertain):
  - >5000 people/km²: 25.0 points
  - >2000 people/km²: 20.0 points
  - >1500 people/km²: 18.0 points

### 2. Early Area Type Detection
- Moved area_type detection before checking for businesses
- Enables fallback logic to work even when OSM data is unavailable

### 3. Fallback Breakdown Function
- Added `_empty_breakdown_with_fallback()` to properly document when fallback is applied
- Includes metadata: `fallback_applied: true`, `fallback_reason`

## Expected Impact

### Before Tuning:
- 11 locations (6.2%) with zero scores
- Many urban neighborhoods incorrectly scoring 0 due to OSM data gaps

### After Tuning:
- Reduced zero scores for urban/suburban areas
- Better handling of OSM data incompleteness
- More accurate representation of amenity access

## Testing Results

✅ **Coconut Grove Miami FL**: 0 → 20.0 (fallback applied, density: 3880/km²)
✅ **12 South Nashville TN**: 0 → 18.0 (fallback applied, density: 1804/km²)
✅ **Capitol Hill Seattle WA**: 87.2 (maintained high score, no regression)

## Isolation
- Changes are isolated to `pillars/neighborhood_amenities.py`
- No dependencies on other pillars
- No impact on `active_outdoors`, `natural_beauty`, or `quality_education`
