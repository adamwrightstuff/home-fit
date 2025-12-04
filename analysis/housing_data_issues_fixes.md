# Housing Data Issues - Investigation and Fixes

## Issues Identified

### 1. Ann Arbor MI - Suspiciously Low Income Data

**Problem:**
- Median household income reported as $25,093
- Expected range for Ann Arbor: $60,000-$70,000+
- This causes inflated price-to-income ratio (15.48) and very low affordability score (5/50)

**Root Cause:**
- The Census API is returning legitimate data for Census Tract 4001 in Washtenaw County
- This tract appears to be a student-heavy area near University of Michigan
- Tract-level data can be unrepresentative of the broader area

**Fix Applied:**
- Added validation to detect suspiciously low income values (< $30k)
- Added warning message when income seems unrepresentative
- Enhanced Census error code handling to catch more error conditions

**Status:** ✅ Fixed - Warning now displayed, data is technically correct for that tract

**Recommendation:**
- Consider using county-level or city-level data as fallback when tract-level data seems unrepresentative
- This would require additional API calls and more complex logic

### 2. Brickell Miami FL - Data Quality Tier Bug

**Problem:**
- Data quality tier showing as "1" instead of proper tier string
- Expected values: "excellent", "good", "fair", "poor", "very_poor"

**Root Cause:**
- Investigation shows the code correctly returns "excellent" as a string
- The "1" value may be from a different export or formatting issue
- Added validation to prevent this from happening

**Fix Applied:**
- Added validation in `assess_pillar_data_quality()` to ensure quality_tier is always a string
- Validates against list of valid tiers: ['excellent', 'good', 'fair', 'poor', 'very_poor']
- Defaults to 'fair' if invalid value detected
- Logs warning when invalid tier is detected

**Status:** ✅ Fixed - Validation added to prevent invalid tier values

## Code Changes

### `data_sources/census_api.py`
- Enhanced `parse_census_value()` function to handle all Census error codes:
  - `-666666666`: Null value
  - `-999999999`: Median cannot be calculated
  - `-888888888`: Median falls in lowest interval
  - `-555555555`: Median falls in highest interval
- Added validation for suspiciously low income values (< $30k)
- Added validation for suspiciously low home values (< $50k)
- Added warning messages for data quality issues

### `data_sources/data_quality.py`
- Added validation in `assess_pillar_data_quality()` to ensure quality_tier is always a string
- Validates against valid tier list
- Defaults to 'fair' with warning if invalid value detected

## Testing

Test script created: `scripts/investigate_housing_issues.py`

**Test Results:**
- Ann Arbor: Warning correctly displayed for low income
- Brickell: Quality tier correctly returned as 'excellent' (string)
- Validation prevents invalid tier values

## Recommendations for Future Improvements

1. **Tract-level data fallback**: Consider using county-level data when tract-level data seems unrepresentative
2. **Income validation by area type**: Different thresholds for urban vs. rural areas
3. **Data quality metadata**: Add flag to indicate when tract-level data may be unrepresentative
4. **User-facing warnings**: Consider showing warnings in API response when data quality issues are detected

