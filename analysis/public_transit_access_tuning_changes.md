# Public Transit Access Pillar Tuning Changes

## Problem Identified

Several urban/suburban/high-density locations were scoring 0 on public transit access, despite being in areas that should have reasonable transit infrastructure. Analysis revealed:

1. **Transitland API Data Gaps**: When Transitland API fails (timeouts, rate limits, network errors) or returns no routes, the pillar was scoring 0, even in urban/suburban areas.
2. **OSM Fallback Limitations**: OSM railway station fallback also fails in some cases (504 errors), leaving no transit data.
3. **Misclassification**: Some small cities with density > 1500 are classified as "rural" but should have transit access.

## Root Cause

- Transitland API failures result in 0 routes found, even in urban areas
- OSM fallback also fails in some cases (504 errors)
- No fallback mechanism for urban/suburban/high-density areas when both Transitland and OSM fail
- Commute_time is available but not used as a proxy for transit availability when routes aren't found

## Changes Made

### Added Fallback Scoring for Urban/Suburban Areas

**File**: `pillars/public_transit_access.py`

When no routes are found from Transitland or OSM, and we're in an urban/suburban/high-density area, apply conservative fallback scores based on commute_time:

- **Detection**: Checks if area is urban/suburban/high-density (area_type in urban_core/urban_residential/suburban OR density > 1500)
- **Commute Time Proxy**: Uses commute_time as proxy for transit availability - if commute_time is reasonable (< 60 min), it suggests transit might exist but Transitland API isn't finding it
- **Fallback Scores**: Conservative minimum floors based on area type and density:
  - **Urban Core** (density > 5000): Heavy Rail 15.0, Bus 12.0
  - **Urban Residential** (density > 2000): Heavy Rail 10.0, Bus 10.0
  - **Suburban** (density > 1500): Heavy Rail 5.0, Bus 8.0
- **Commute Time Weight**: Adds commute_score weighted at 5% (COMMUTE_WEIGHT)

### Fallback Logic Flow

1. Check if Transitland API returns routes → if yes, score normally
2. If no routes, check OSM railway stations → if found, convert and score
3. If still no routes AND area is urban/suburban/high-density:
   - Fetch commute_time from Census API
   - If commute_time is reasonable (< 60 min), apply fallback scores
   - Return fallback breakdown with `fallback_applied: true`
4. If rural/low-density OR commute_time unavailable/unreasonable → return 0

## Expected Impact

1. **Reduced Zero Scores**: Urban/suburban/high-density locations will no longer score 0 when Transitland API fails
2. **Better Handling of API Data Gaps**: Conservative minimum scores account for Transitland/OSM incompleteness
3. **Commute Time as Proxy**: Uses commute_time to distinguish between "no transit exists" vs "API failed"
4. **Maintained Accuracy**: Rural locations with truly no transit still score 0 appropriately

## Testing Results

### Before Tuning
- **St Augustine FL**: 0.0/100 (density: 2367, classified as rural)
- **Kalispell MT**: 0.0/100 (density: 2334, classified as rural)

### After Tuning
- **St Augustine FL**: 24.2/100 (Heavy Rail: 10.0, Bus: 10.0, Commute Time: 85.0)
  - **Improvement**: +24.2 points
  - Fallback applied due to high density (2367) and reasonable commute_time (20.3 min)
- **Kalispell MT**: Will receive fallback if commute_time is reasonable

## Isolation

All changes are confined to `pillars/public_transit_access.py`:
- Added fallback detection logic after Transitland/OSM route queries fail
- Added fallback score calculation using commute_time and area type/density
- Returns fallback breakdown with `fallback_applied: true` flag
- No changes to other pillars or shared infrastructure

## Notes

- Fallback scores are conservative minimums, not full scores
- Fallback only applies when Transitland/OSM fail AND location is urban/suburban/high-density AND commute_time is reasonable
- Rural locations with truly no transit will still score appropriately low (0)
- Commute_time serves as proxy to distinguish API failures from genuine lack of transit
- Area type classification might misclassify small cities as "rural", but density check (> 1500) ensures fallback applies when appropriate
