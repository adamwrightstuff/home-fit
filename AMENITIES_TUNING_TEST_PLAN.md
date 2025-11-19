# Amenities Pillar Tuning - Test Plan

**Date:** 2025  
**Status:** Ready for execution  
**Changes Applied:** ✅ All code changes implemented

---

## Overview

This test plan validates the amenities pillar tuning changes based on Perplexity research recommendations. The changes include:
1. Context-aware density thresholds (urban/suburban/rural)
2. 40-business density tier
3. Adjusted proximity point allocations
4. Cultural bonus for downtown clusters
5. Context-aware location quality thresholds

---

## Pre-Test Checklist

- [x] Code changes applied
- [x] No linting errors
- [ ] Backup current analysis results (if needed)
- [ ] Ensure test data CSV is available
- [ ] Verify API credentials are configured

---

## Test Execution Steps

### Step 1: Run Full Regression Test

**Command:**
```bash
cd /Users/adamwright/home-fit
python3 scripts/analyze_amenities.py --input test_data/amenities_test_cases.csv --output analysis
```

**Expected Output:**
- Analysis completes without errors
- Generates 3 files:
  - `analysis/amenities_analysis.json` (full data)
  - `analysis/amenities_summary.txt` (summary report)
  - `analysis/amenities_analysis.csv` (spreadsheet format)

**Success Criteria:**
- ✅ No Python errors or exceptions
- ✅ All 43 locations analyzed
- ✅ Output files generated successfully

---

### Step 2: Validate Score Ranges

**Check:** `analysis/amenities_analysis.csv`

**Expected Score Ranges by Location Type:**

| Location Type | Expected Score Range | Notes |
|--------------|---------------------|-------|
| Urban cores (West Village, Pearl District) | 85-100 | Should maintain high scores |
| Suburban downtowns (Boulder, Traverse City) | 75-95 | May see +0-2 point increases |
| Small towns (Sun Valley, Marblehead) | 50-85 | May see +2-5 point increases |
| Resort towns (Aspen, Carmel, Taos) | 85-100 | Should maintain high scores |
| Zero-score locations (Napa, Monterey) | 0 | Expected (OSM data gaps) |

**Success Criteria:**
- ✅ Urban cores: 85-100 range
- ✅ Suburban: 75-95 range
- ✅ Small towns: 50-85 range (improved from previous)
- ✅ No unexpected 0 scores (except known OSM gaps)

---

### Step 3: Validate Context-Aware Density Scoring

**Check:** Urban cores should require 60+ businesses for max density (25 points)

**Test Cases:**

1. **West Village Manhattan** (759 businesses within 1km)
   - **Expected:** Density score = 25.0 (max)
   - **Verify:** Urban core threshold (60+) is applied correctly

2. **Downtown Boulder** (172 businesses within 1km)
   - **Expected:** Density score = 25.0 (max)
   - **Verify:** Suburban baseline threshold (50+) is applied

3. **Downtown Sun Valley** (4 businesses within 1km)
   - **Expected:** Density score = ~4.8 (low, but context-adjusted)
   - **Verify:** Exurban/rural threshold (35+) is applied (won't max, but threshold is lower)

**Success Criteria:**
- ✅ Urban cores need 60+ for max density
- ✅ Suburban needs 50+ for max density
- ✅ Small towns need 35+ for max density
- ✅ 40-business tier awards 24 points (between 30 and 50)

---

### Step 4: Validate 40-Business Tier

**Check:** Locations with 40-49 businesses should get 24 points (not 20)

**Test Cases:**

1. **Locations with 40-49 businesses**
   - **Expected:** Density score = 24.0
   - **Verify:** New tier is working

2. **Locations with 30-39 businesses**
   - **Expected:** Density score = 20.0 (good threshold)
   - **Verify:** No regression

3. **Locations with 50+ businesses**
   - **Expected:** Density score = 25.0 (excellent threshold)
   - **Verify:** No regression

**Success Criteria:**
- ✅ 40-49 businesses = 24 points
- ✅ Smooth progression: 30→20, 40→24, 50→25

---

### Step 5: Validate Proximity Adjustments

**Check:** Proximity scores should be tighter for longer distances

**Test Cases:**

1. **Location with median distance ≤200m**
   - **Expected:** Proximity score = 15.0 (optimal)
   - **Previous:** 15.0 (unchanged)

2. **Location with median distance 400m**
   - **Expected:** Proximity score = 13.0
   - **Previous:** 14.0 (reduced by 1 point)

3. **Location with median distance 900m**
   - **Expected:** Proximity score = 7.0
   - **Previous:** ~15.0 (reduced by ~8 points)

4. **Location with median distance >1000m**
   - **Expected:** Proximity score = 2.5
   - **Previous:** 5.0 (reduced by 2.5 points)

**Success Criteria:**
- ✅ ≤200m = 15 points (unchanged)
- ✅ ≤400m = 13 points (reduced from 14)
- ✅ ≤800m = 10 points (reduced from 20)
- ✅ ≤1000m = 7 points (reduced from 15)
- ✅ >1000m = 2.5 points (reduced from 5)

---

### Step 6: Validate Cultural Bonus

**Check:** Downtowns with 5+ cultural venues should get +2 bonus

**Test Cases:**

1. **Downtown Asheville** (20 cultural venues in cluster)
   - **Expected:** Cultural bonus = 2.0
   - **Verify:** Location Quality score includes bonus

2. **Downtown with 3-4 cultural venues**
   - **Expected:** Cultural bonus = 1.0
   - **Verify:** Bonus is applied

3. **Downtown with 0-2 cultural venues**
   - **Expected:** Cultural bonus = 0.0
   - **Verify:** No bonus applied

**Success Criteria:**
- ✅ 5+ cultural venues = +2 bonus
- ✅ 3-4 cultural venues = +1 bonus
- ✅ 0-2 cultural venues = 0 bonus
- ✅ Bonus is capped at Location Quality max (40 points)

---

### Step 7: Validate Context-Aware Location Quality

**Check:** Vibrancy thresholds should vary by area type

**Test Cases:**

1. **Urban Core** (e.g., West Village)
   - **Expected:** Needs 50+ businesses in 500m cluster for max vibrancy (8 density points)
   - **Verify:** density_divisor = 6.25

2. **Suburban** (e.g., Downtown Boulder)
   - **Expected:** Needs 40+ businesses in 500m cluster for max vibrancy (8 density points)
   - **Verify:** density_divisor = 5.0

3. **Small Town** (e.g., Downtown Sun Valley)
   - **Expected:** Needs 30+ businesses in 500m cluster for max vibrancy (8 density points)
   - **Verify:** density_divisor = 3.75

**Success Criteria:**
- ✅ Urban cores: 50+ businesses = max vibrancy
- ✅ Suburban: 40+ businesses = max vibrancy
- ✅ Small towns: 30+ businesses = max vibrancy

---

### Step 8: Compare Before/After Scores

**Action:** Compare new scores with previous analysis results

**Key Metrics to Track:**

1. **Score Changes >5 points**
   - **Action:** Investigate why
   - **Expected:** Mostly small towns benefiting from lower thresholds

2. **Score Changes 0-2 points**
   - **Action:** Expected fine-tuning
   - **Expected:** Most locations

3. **Score Changes <0 points**
   - **Action:** Verify if intentional (e.g., proximity tightening)
   - **Expected:** Some locations with scattered businesses

**Success Criteria:**
- ✅ No unexpected large score drops (>10 points)
- ✅ Small towns show improvement (+2-5 points)
- ✅ Urban cores maintain high scores (±0-2 points)

---

### Step 9: Validate Edge Cases

**Test Cases:**

1. **Zero-score locations** (Napa, Monterey, Sonoma, Durango)
   - **Expected:** Still 0 (OSM data gaps, not scoring issue)
   - **Verify:** Error handling works correctly

2. **Very high density** (West Village: 759 businesses)
   - **Expected:** Scores appropriately (not capped incorrectly)
   - **Verify:** Context-aware thresholds work at extremes

3. **Very low density** (Sun Valley: 4 businesses)
   - **Expected:** Low score but context-adjusted
   - **Verify:** Small town thresholds are applied

**Success Criteria:**
- ✅ Zero scores remain zero (data issue, not scoring)
- ✅ High-density locations score correctly
- ✅ Low-density locations use context-adjusted thresholds

---

### Step 10: Validate Data Quality Metrics

**Check:** Data quality confidence should remain high

**Test Cases:**

1. **Locations with good OSM coverage**
   - **Expected:** Confidence ≥85%
   - **Verify:** Quality metrics unchanged

2. **Locations with poor OSM coverage**
   - **Expected:** Confidence <85%
   - **Verify:** Quality metrics reflect data gaps

**Success Criteria:**
- ✅ Data quality metrics still accurate
- ✅ Confidence scores reflect actual data availability

---

## Expected Results Summary

### Score Distribution Changes

| Category | Before Avg | After Avg | Change | Reason |
|----------|-----------|-----------|--------|--------|
| Urban cores | 85-95 | 85-95 | ±0-2 | Context-aware thresholds balance out |
| Suburban downtowns | 75-90 | 75-92 | +0-2 | 40-business tier helps |
| Small towns | 65-85 | 70-90 | +2-5 | Lower thresholds help, cultural bonus possible |
| Resort towns | 85-100 | 85-100 | ±0 | Already scoring high |

### Key Improvements

1. **Better differentiation:** 40-business tier creates smoother progression
2. **Context awareness:** Urban vs. small town expectations properly calibrated
3. **Cultural recognition:** Bonus rewards exceptional cultural offerings
4. **Distance realism:** Proximity scoring better reflects walking comfort

---

## Red Flags to Watch For

### ⚠️ Critical Issues

1. **Syntax errors or exceptions**
   - **Action:** Fix immediately, do not proceed

2. **All scores = 0**
   - **Action:** Check API connectivity, OSM data availability

3. **Scores >100**
   - **Action:** Check for capping bugs in scoring functions

4. **Urban cores scoring lower than small towns**
   - **Action:** Verify context-aware thresholds are applied correctly

### ⚠️ Warning Signs

1. **Score changes >10 points for same location**
   - **Action:** Investigate, may indicate bug

2. **Many locations scoring exactly 100**
   - **Action:** Check for over-capping

3. **Proximity scores all the same**
   - **Action:** Verify proximity function is working

---

## Post-Test Actions

### If Tests Pass ✅

1. **Document results**
   - Save analysis output
   - Note any interesting patterns
   - Update implementation notes

2. **Compare with research**
   - Verify scores align with Perplexity recommendations
   - Check threshold application is correct

3. **Deploy changes**
   - Code is ready for production
   - Monitor for any edge cases in real usage

### If Tests Fail ❌

1. **Identify issue**
   - Check error messages
   - Review score anomalies
   - Verify function logic

2. **Fix and retest**
   - Apply fixes
   - Re-run regression test
   - Validate fixes work

3. **Rollback if needed**
   - Use git to revert changes
   - Document what went wrong
   - Plan alternative approach

---

## Test Data Reference

**Test File:** `test_data/amenities_test_cases.csv`  
**Total Locations:** 43  
**Location Types:**
- Urban cores: 15 locations
- Suburban downtowns: 20 locations
- Small towns/resort: 8 locations

**Key Test Locations:**
- **High density:** West Village (759 businesses), Pearl District (451 businesses)
- **Medium density:** Downtown Boulder (172 businesses), Downtown Traverse City (120 businesses)
- **Low density:** Downtown Sun Valley (4 businesses), Downtown Marblehead (7 businesses)
- **Zero score:** Napa, Monterey, Sonoma, Durango (OSM data gaps)

---

## Quick Validation Commands

**Check specific location:**
```bash
python3 -c "
from pillars.neighborhood_amenities import get_neighborhood_amenities_score
from data_sources.geocoding import geocode

# Test West Village Manhattan
result = geocode('West Village Manhattan NY')
if result:
    lat, lon = result[0], result[1]
    score, breakdown = get_neighborhood_amenities_score(lat, lon)
    print(f'Score: {score}')
    print(f'Density: {breakdown[\"breakdown\"][\"home_walkability\"][\"breakdown\"][\"density\"]}')
    print(f'Location Quality: {breakdown[\"breakdown\"][\"location_quality\"]}')
"
```

**Check score components:**
```bash
# View analysis CSV
cat analysis/amenities_analysis.csv | grep "West Village"
```

---

## Success Criteria Summary

✅ **All tests pass if:**
1. No errors during analysis
2. Score ranges match expected values
3. Context-aware thresholds work correctly
4. Cultural bonus applies appropriately
5. Proximity adjustments are correct
6. No unexpected score anomalies
7. Data quality metrics remain accurate

---

**Ready to execute?** Run Step 1 and proceed through each validation step systematically.

