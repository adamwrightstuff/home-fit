# Amenities Pillar Data Issues - Investigation & Fixes

## Summary
This document tracks investigation and fixes for data quality issues affecting the Amenities pillar (and related Built Beauty calculations).

## Issues Identified

### 1. ✅ FIXED: Height Data Ingestion / Normalization Failing Intermittently

**Problem**: Height data from OSM `building:levels` tags was failing to parse when values were:
- Decimal numbers (e.g., "2.5", "3.0")
- Invalid strings (e.g., "unknown", "mixed", empty)
- Out of reasonable range

**Impact**: Buildings with invalid height data were defaulting to 1 story, causing incorrect height diversity calculations across multiple cities.

**Fix Applied** (`data_sources/arch_diversity.py`):
- Enhanced parsing to handle float values (rounds to nearest integer)
- Added validation for reasonable range (1-200 floors)
- Better error handling for invalid strings
- Added logging for suspicious height diversity patterns

**Code Changes**:
```python
# Before: Simple int() conversion that failed on decimals/invalid values
lv = int(lv_raw) if lv_raw is not None else None

# After: Robust parsing with float conversion and validation
lv_float = float(str(lv_raw).strip())
lv = int(round(lv_float))
if lv < 1 or lv > 200:
    lv = None
```

### 2. 🔍 IN PROGRESS: Area Type Classifier Mis-labeled Big Bear

**Problem**: Big Bear Lake CA is classified as "rural" but should likely be "exurban" or "suburban" given its characteristics as a mountain resort town.

**Current Classification**: 
- Target: `rural` (65.0 median target)
- Actual: `rural`
- Characteristics: 54 businesses, 48 within walkable distance

**Root Cause Analysis**:
Big Bear has 54 businesses, which gives a business_score of ~0.274. With low density (<450) and low coverage, the intensity calculation uses weights: density 40%, coverage 40%, business 20%. This results in intensity ~0.135, which falls just below the 0.15 threshold for "exurban" classification.

**Investigation Findings**:
- Resort towns and small communities often have:
  - Low population density (rural-like)
  - High business/tourism activity relative to population (urban-like)
  - Business activity that should indicate "small town" rather than "rural"

**Potential Fix**: 
Adjust `_calculate_intensity_score()` in `data_sources/data_quality.py` to give more weight to business_count when:
- Density is low (<450)
- Business count is moderate-high (50+)
- This indicates a small town/resort rather than true rural

**Proposed Change**:
```python
# In _calculate_intensity_score(), add special case for low-density, high-business areas
if density and density < 450 and business_count and business_count >= 50:
    # Small town/resort: business activity more important
    intensity = (
        density_score * 0.30 +
        coverage_score * 0.30 +
        business_score * 0.40  # Increased weight for business
    )
```

**Testing**: This change should be tested with Big Bear and other resort towns to ensure it doesn't over-classify other rural areas.

### 3. ✅ FIXED: Missing Values (Rowhouse Bonus = Blank in Bozeman)

**Problem**: `rowhouse_bonus` could be `None` or missing, causing issues in TSV extraction and downstream regressions.

**Impact**: Bozeman and other locations with missing rowhouse_bonus values would break data extraction.

**Fix Applied** (`pillars/built_beauty.py`):
- Ensured rowhouse_bonus defaults to 0.0 when missing
- Changed: `coverage_cap_metadata.get("rowhouse_bonus")` 
- To: `coverage_cap_metadata.get("rowhouse_bonus") or 0.0`

**Note**: The underlying `_rowhouse_bonus()` function in `arch_diversity.py` already returns 0.0 for non-qualifying areas, but this ensures the metadata field is never None.

### 4. 🔍 IN PROGRESS: Brickell's Height Diversity Catastrophically Wrong

**Problem**: Brickell Miami FL shows height diversity of 13.3, which seems incorrect for a dense urban core area with many high-rises.

**Current Data**:
- Location: Brickell Miami FL (25.7625951, -80.1952987)
- Area Type: historic_urban
- Height Diversity: 13.3 (seems low for dense urban area)
- Total Businesses: 65
- Data Quality Tier: 2 (poor)
- Confidence: 77%

**Investigation Needed**:
- Check if height queries are failing for dense urban areas
- Verify OSM building:levels data availability for Brickell
- Review height diversity calculation for areas with many high-rises
- Check if normalization is incorrectly penalizing high-rise areas

**Potential Issues**:
1. OSM data may be missing `building:levels` tags for many buildings in Brickell
2. Height diversity calculation may not properly handle areas with many 9+ story buildings
3. Entropy calculation may be biased when most buildings fall into the "9+" bin

**Added Validation**: Enhanced logging to detect dense urban areas with suspiciously uniform low heights (likely indicating failed height queries).

### 5. ✅ FIXED: Suburban Places with 1-3 Height Diversity Need Data Validation

**Problem**: Suburban areas with 1-3 height diversity likely indicate failed height queries (most buildings defaulting to 1 story).

**Fix Applied** (`data_sources/arch_diversity.py`):
- Added validation to detect suspiciously low height diversity
- Flags cases where:
  - 10+ buildings exist
  - Height diversity < 5.0
  - >85% of buildings are in the "1" bin (missing/inferred height)
- Logs warning with location coordinates for debugging
- Sets `data_warning` flag to "suspiciously_low_height_diversity"

**Additional Validation**: Added check for dense urban areas (50+ buildings) with suspiciously uniform low heights, which may indicate systematic height query failures.

## Testing Recommendations

1. **Height Data Parsing**: Test with various invalid `building:levels` values:
   - Decimals: "2.5", "3.0"
   - Invalid strings: "unknown", "mixed", ""
   - Out of range: "0", "500"

2. **Big Bear Classification**: 
   - Test classification with business_count=54, density=low
   - Verify if it should be "exurban" instead of "rural"

3. **Brickell Height Diversity**:
   - Query OSM for building:levels tags in Brickell area
   - Verify height diversity calculation for high-rise areas
   - Check if entropy calculation handles "9+" bin correctly

4. **Rowhouse Bonus**: 
   - Verify Bozeman and other locations now return 0.0 instead of None
   - Test TSV extraction with locations that don't qualify for rowhouse bonus

5. **Height Diversity Validation**:
   - Test suburban locations with 1-3 height diversity
   - Verify warnings are logged correctly
   - Check that data_warning flag is set appropriately

## Files Modified

1. `data_sources/arch_diversity.py`:
   - Enhanced height data parsing (lines ~249-272)
   - Added height diversity validation (lines ~343-347)
   - Added dense urban area validation (lines ~353-361)

2. `pillars/built_beauty.py`:
   - Fixed rowhouse_bonus default value (line ~250)

## Next Steps

1. **Big Bear Classification**: Review classification logic for resort towns and small communities with high business activity
2. **Brickell Investigation**: Debug height diversity calculation for dense urban areas
3. **Monitoring**: Set up alerts for locations with suspiciously low height diversity
4. **Data Quality Dashboard**: Create dashboard to track height data quality across locations

