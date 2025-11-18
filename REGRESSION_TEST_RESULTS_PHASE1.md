# Phase 1 Calibration - Regression Test Results

## Test Summary

**Total Tests:** 13  
**✅ Passed:** 7  
**❌ Regressions:** 6  
**⚠️ Errors:** 0

---

## ✅ Passed Tests (Within Tolerance)

| Location | Baseline | Current | Change | Status |
|----------|----------|---------|--------|--------|
| Old Town Scottsdale AZ | 13.3 | 14.0 | +0.7 | ✅ (tolerance: ±3.0) |
| Sedona AZ | 61.2 | 64.6 | +3.4 | ✅ (tolerance: ±5.0) |
| Coconut Grove Miami FL | 51.9 | 48.8 | -3.1 | ✅ (tolerance: ±8.0) |
| Carmel-by-the-Sea CA | 91.1 | 91.6 | +0.5 | ✅ (tolerance: ±5.0) |
| Pearl District Portland OR | 100.0 | 100.0 | +0.0 | ✅ (tolerance: ±5.0) |
| Georgetown DC | 100.0 | 100.0 | +0.0 | ✅ (tolerance: ±5.0) |
| Venice Beach Los Angeles CA | 20.0 | 23.8 | +3.8 | ✅ (tolerance: ±5.0) |

**Key Observations:**
- ✅ **Sedona**: +3.4 increase - Topography boost working as expected!
- ✅ **Old Town Scottsdale**: +0.7 increase - Small topography boost applied
- ✅ **High performers maintained**: Pearl District and Georgetown still at 100

---

## ❌ Regressions (Outside Tolerance)

### 1. Manhattan Beach CA
- **Baseline:** 30.5
- **Current:** 23.5
- **Change:** -7.0
- **Tolerance:** ±6.0
- **Status:** ❌ Regression

**Analysis:**
- Low canopy (7.87%) - not affected by saturation
- Moderate water (11.63%) - not arid, no topography boost
- Possible causes:
  - Canopy expectation penalty might be too harsh
  - Water scoring might have changed
  - Need to investigate component breakdown

**Action:** Investigate component scores to identify cause

---

### 2. Garden District New Orleans LA
- **Baseline:** 20.1
- **Current:** 26.2
- **Change:** +6.2
- **Tolerance:** ±5.0
- **Status:** ❌ Regression (but positive)

**Analysis:**
- Very low canopy (2%) - street tree bonus might be helping
- Moderate water (13.3%)
- This might be an **intentional improvement** from street tree bonus

**Action:** Review if this is acceptable improvement or needs adjustment

---

### 3. Beacon Hill Boston MA
- **Baseline:** 35.7
- **Current:** 44.2
- **Change:** +8.5
- **Tolerance:** ±5.0
- **Status:** ❌ Regression (but positive)

**Analysis:**
- Low canopy (7.65%) - street tree bonus might be helping
- Good water (16.33%)
- This might be an **intentional improvement** from street tree bonus

**Action:** Review if this is acceptable improvement or needs adjustment

---

### 4. Bronxville NY
- **Baseline:** 75.0 (approximate)
- **Current:** 99.7
- **Change:** +24.7
- **Tolerance:** ±5.0
- **Status:** ❌ Regression (but baseline was approximate)

**Analysis:**
- Baseline was **approximate** (not from actual production data)
- High score suggests high canopy or GVI
- Might be correct score, baseline was wrong

**Action:** Capture actual baseline score from production

---

### 5. The Woodlands TX
- **Baseline:** 60.0 (approximate)
- **Current:** 85.4
- **Change:** +25.4
- **Tolerance:** ±5.0
- **Status:** ❌ Regression (but baseline was approximate)

**Analysis:**
- Baseline was **approximate** (not from actual production data)
- Planned community with good canopy
- Might be correct score, baseline was wrong

**Action:** Capture actual baseline score from production

---

### 6. Stowe VT
- **Baseline:** 70.0 (approximate)
- **Current:** 100.0
- **Change:** +30.0
- **Tolerance:** ±8.0
- **Status:** ❌ Regression (but baseline was approximate)

**Analysis:**
- Baseline was **approximate** (not from actual production data)
- Rural, scenic area with high canopy (53.8%)
- High topography (relief: 607m, slope: 7.5°)
- **Canopy saturation might be affecting this** - 53.8% canopy is above 50% threshold
- Might be correct score, baseline was wrong

**Action:** 
- Capture actual baseline score from production
- Review if canopy saturation is too aggressive for high-canopy rural areas

---

## Key Findings

### ✅ Working as Expected:
1. **Topography boost for arid regions**: Sedona (+3.4) and Old Town Scottsdale (+0.7) both increased
2. **High performers maintained**: Pearl District and Georgetown still at 100
3. **Canopy saturation**: Not causing major issues for most locations

### ⚠️ Issues to Address:

1. **Manhattan Beach drop (-7.0)**: Need to investigate why score decreased
2. **Canopy saturation impact on high-canopy areas**: Stowe (53.8% canopy) might be affected
3. **Approximate baselines**: 3 locations (Bronxville, The Woodlands, Stowe) need actual baseline scores

---

## Recommendations

### Immediate Actions:

1. **Investigate Manhattan Beach:**
   - Get component breakdown (canopy, water, topography, GVI)
   - Check if expectation penalty is too harsh
   - Review water scoring

2. **Capture actual baselines:**
   - Test Bronxville, The Woodlands, and Stowe in production
   - Update regression test baseline scores

3. **Review canopy saturation:**
   - Check if 50% threshold is appropriate
   - Consider if rural areas should be exempt from saturation

4. **Review street tree bonus:**
   - Garden District and Beacon Hill increases might be from street tree bonus
   - Verify if these are intentional improvements

### Next Steps:

1. Run detailed component analysis for Manhattan Beach
2. Capture production baselines for approximate locations
3. Consider adjusting canopy saturation threshold or exempting rural areas
4. Validate street tree bonus is working as intended

---

## Phase 1 Status

**Overall:** ✅ **Mostly successful**
- Topography boost working for arid regions
- High performers maintained
- Some regressions need investigation
- Approximate baselines need updating

**Recommendation:** Proceed with investigation of Manhattan Beach and baseline updates before Phase 2.

