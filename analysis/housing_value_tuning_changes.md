# Housing Value Pillar Tuning Changes

## Problem Identified

Several urban/suburban locations were scoring 0 on housing value, despite being in areas that should have housing data. Analysis revealed:

1. **Census API Data Gaps**: When Census API returns incomplete housing data (missing or error-coded values), the pillar was scoring 0, even in urban/suburban areas.
2. **No Fallback Mechanism**: Unlike other pillars, housing_value had no fallback scoring when Census data was unavailable.
3. **Urban Locations Affected**: Locations like Brickell Miami FL, Wynwood Miami FL, and Washington Heights Manhattan NY were scoring 0 due to Census data gaps.

## Root Cause

- Census API returns `None` when housing data is incomplete (error codes, missing values)
- No fallback mechanism for urban/suburban areas when Census data is unavailable
- Urban areas with incomplete Census data were incorrectly scoring 0

## Changes Made

### Added Fallback Scoring for Urban/Suburban Areas

**File**: `pillars/housing_value.py`

When Census API returns `None` (incomplete data) and we're in an urban/suburban/high-density area, apply conservative fallback scores based on typical urban housing characteristics:

- **Detection**: Checks if area is urban/suburban/high-density (area_type in urban_core/urban_residential/suburban OR density > 1500)
- **Fallback Scores**: Conservative minimum floors based on area type and density:
  - **Urban Core** (density > 5000): Affordability 15.0, Space 20.0, Efficiency 10.0 (Total: 45.0)
  - **Urban Residential** (density > 2000): Affordability 20.0, Space 22.0, Efficiency 12.0 (Total: 54.0)
  - **Suburban** (density > 1500): Affordability 25.0, Space 25.0, Efficiency 15.0 (Total: 65.0)

### Fallback Logic Rationale

- **Urban Cores**: Typically expensive (lower affordability), moderate space (apartments/condos), moderate efficiency
- **Urban Residential**: Slightly more affordable than cores, moderate space, moderate efficiency
- **Suburban**: More affordable, more space (houses), better efficiency

These scores reflect typical urban housing characteristics and are conservative minimums, not full scores.

## Expected Impact

1. **Reduced Zero Scores**: Urban/suburban locations will no longer score 0 when Census API fails or returns incomplete data
2. **Better Handling of Census Data Gaps**: Conservative minimum scores account for Census incompleteness
3. **Maintained Accuracy**: Rural locations with truly no housing data still score 0 appropriately
4. **Realistic Scores**: Fallback scores reflect typical urban housing characteristics (expensive but moderate space/efficiency)

## Testing Results

### Before Tuning
- **Brickell Miami FL**: 0.0/100 (Census data unavailable)
- **Wynwood Miami FL**: 0.0/100 (Census data unavailable)
- **Washington Heights Manhattan NY**: 0.0/100 (Census data unavailable)

### After Tuning
- **Brickell Miami FL**: 54.0/100 (Affordability: 20.0, Space: 22.0, Efficiency: 12.0)
  - **Improvement**: +54.0 points
- **Wynwood Miami FL**: 65.0/100 (Affordability: 25.0, Space: 25.0, Efficiency: 15.0)
  - **Improvement**: +65.0 points
- **Washington Heights Manhattan NY**: 54.0/100 (Affordability: 20.0, Space: 22.0, Efficiency: 12.0)
  - **Improvement**: +54.0 points

## Isolation

All changes are confined to `pillars/housing_value.py`:
- Added fallback detection logic when Census API returns `None`
- Added fallback score calculation using area type and density
- Returns fallback breakdown with `fallback_applied: true` flag
- No changes to other pillars or shared infrastructure

## Notes

- Fallback scores are conservative minimums, not full scores
- Fallback only applies when Census API fails AND location is urban/suburban/high-density
- Rural locations with truly no housing data will still score appropriately low (0)
- Fallback scores reflect typical urban housing characteristics (expensive but moderate space/efficiency)
- Area type classification might misclassify small cities, but density check (> 1500) ensures fallback applies when appropriate
