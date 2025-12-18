# Calibration Data Collection Plan for 177 Locations

## Goal

Collect calibration data (target scores + raw component scores) for all 177 locations to improve calibration accuracy.

## Current Situation

### What We Have
- ✅ **177 locations**: Statistics in `pillar_regression_data.json`
- ✅ **56 locations**: Calibration data for `active_outdoors` (with target scores)
- ✅ **15 locations**: Calibration data for `neighborhood_amenities` (with target scores)

### What We Need
- ❌ **Target scores** for all 177 locations
- ❌ **Raw component scores** for all 177 locations
- ❌ **Area types** for all 177 locations

## Data Collection Options

### Option 1: Extract from Existing API Results

**If we have API results stored:**
- Check `data/results.csv` for existing API responses
- Extract pillar scores and component breakdowns
- Extract area types from responses

**Pros**: Fast, no API calls needed
**Cons**: May not have all 177 locations

### Option 2: Call API for All Locations

**Steps:**
1. Get list of 177 locations (from `pillar_regression_data.json` or `data/locations.csv`)
2. Call HomeFit API for each location
3. Extract:
   - Current scores for each pillar
   - Raw component scores (from breakdown)
   - Area types
4. Save to JSON file

**Pros**: Complete data, current scores
**Cons**: Requires API calls (rate limiting), takes time

### Option 3: Use Existing Collector Script

**If `scripts/collector.py` has the data:**
- Check `data/results.csv` for collected responses
- Parse JSON responses to extract pillar data
- Match with 177 locations

**Pros**: May already have data
**Cons**: Need to verify data completeness

## Target Score Sources

### Option A: LLM Evaluation (Like Previous Calibration)

**Process:**
1. For each location, provide context (city, area type, features)
2. Ask LLM to evaluate target score for each pillar
3. Use median of multiple evaluations for robustness

**Pros**: Consistent methodology with existing calibration
**Cons**: Time-consuming, requires LLM API calls

### Option B: User Feedback

**Process:**
1. Present locations to users/experts
2. Collect target scores via survey or interface
3. Aggregate responses

**Pros**: Real user validation
**Cons**: Requires user recruitment, time-consuming

### Option C: Use Existing Calibration Data

**Process:**
1. Use 56 locations from `active_outdoors_tuning_from_ridge.json` as seed
2. Interpolate/extrapolate for similar locations
3. Validate on subset

**Pros**: Fast, leverages existing data
**Cons**: Less accurate, may not cover all locations

## Recommended Approach

### Phase 1: Collect Current Scores (No Target Scores Needed)

1. **Extract locations** from `data/locations.csv` or `pillar_regression_data.json`
2. **Call API** or use existing `data/results.csv` to get:
   - Current scores for all pillars
   - Raw component scores
   - Area types
3. **Save to**: `analysis/calibration_data_177_locations.json`

### Phase 2: Add Target Scores

1. **For active_outdoors**: Use existing 56 target scores, collect remaining 121
2. **For natural_beauty**: Collect all 177 target scores (none exist currently)
3. **For other pillars**: Collect as needed

### Phase 3: Calculate Calibration

1. **Run linear regression** on raw scores vs target scores
2. **Calculate calibration parameters** (`CAL_A`, `CAL_B`)
3. **Validate** on holdout set
4. **Apply** to pillars

## Implementation Script

Created `scripts/collect_calibration_data.py` as a template. It needs:

1. **API integration**: Call HomeFit API or use scoring functions directly
2. **Data extraction**: Parse responses to get component scores
3. **Geocoding**: Get lat/lon for locations if needed
4. **Output format**: Save in format suitable for calibration

## Next Steps

1. **Check existing data**: See if `data/results.csv` has the 177 locations
2. **Complete collection script**: Add API calls and data extraction
3. **Run collection**: Gather current scores for all locations
4. **Add target scores**: Via LLM evaluation or user feedback
5. **Calculate calibration**: Run regression to get parameters
6. **Apply calibration**: Update pillars with new parameters

## Files Created

- `scripts/collect_calibration_data.py`: Template script for data collection
- `analysis/calibration_data_collection_plan.md`: This document

## Questions to Answer

1. Do we have API results for the 177 locations already? (Check `data/results.csv`)
2. What's the source of target scores? (LLM evaluation, user feedback, etc.)
3. Which pillars need calibration? (Currently: `active_outdoors` ✅, `natural_beauty` ⚠️)
4. Should we prioritize certain pillars or do all at once?
