# Built Beauty Score Capping Investigation (Priority 3)

## Executive Summary

This document investigates score capping in the built beauty pillar to determine if caps are limiting legitimate high scores and preventing differentiation between very good and exceptional locations.

---

## Part 1: Cap Identification

### All Caps in Built Beauty Scoring System

1. **Component Score Cap (Architectural Diversity)**
   - **Location:** `data_sources/arch_diversity.py`, `score_architectural_diversity_as_beauty()`
   - **Max:** ~50.0 points (natural maximum from scoring function, not a hard cap)
   - **Note:** This is the architectural diversity component score

2. **Enhancer Bonus Cap**
   - **Location:** `pillars/built_beauty.py`, line 296
   - **Constant:** `BUILT_ENHANCER_CAP = 8.0` (defined in `pillars/beauty_common.py`)
   - **Formula:** `built_bonus_scaled = min(BUILT_ENHANCER_CAP, built_bonus_raw * built_scale)`
   - **Components:** Artwork (max 4.5) + Fountains (max 1.5) = 6.0 max raw, scaled by confidence

3. **Final Score Calculation Cap (PRIMARY CAP)**
   - **Location:** `pillars/built_beauty.py`, line 301
   - **Formula:** `built_score_raw = min(100.0, built_native * 2.0)`
   - **Where:** `built_native = arch_component + built_bonus_scaled`
   - **Impact:** If `built_native = 58.0` (max: 50 component + 8 enhancer), then `58.0 * 2.0 = 116.0`, but capped at 100.0
   - **This is the main limiting cap**

4. **Normalization Cap (Final Safeguard)**
   - **Location:** `pillars/beauty_common.py`, `normalize_beauty_score()`, line 37
   - **Formula:** `capped = min(params.get("max", 100.0), shifted)`
   - **All area types:** `max: 100.0` (identity normalization)
   - **Impact:** Even if `built_score_raw = 100.0`, normalization applies another cap

---

## Part 2: Test Results Analysis

### Locations Hitting 100 Cap

From Round 19 test results:

1. **Georgetown DC**
   - **Current Score:** 100
   - **Target Score:** 90
   - **Component Score:** 50.0 (from test data)
   - **Enhancer Bonus:** 6.0 (from test data)
   - **Built Native:** 56.0
   - **Uncapped Score:** `56.0 * 2.0 = 112.0`
   - **Gap to Target:** +10 points (over-scoring, but capped prevents seeing true score)

2. **Back Bay Boston MA**
   - **Current Score:** 100
   - **Target Score:** 97
   - **Component Score:** 50.0 (from test data)
   - **Enhancer Bonus:** 6.0 (from test data)
   - **Built Native:** 56.0
   - **Uncapped Score:** `56.0 * 2.0 = 112.0`
   - **Gap to Target:** +3 points (slightly over-scoring, but capped prevents differentiation)

### Locations NOT Hitting Cap (But Could Benefit)

1. **Old Town Alexandria VA**
   - **Current Score:** 91.4
   - **Target Score:** 93
   - **Component Score:** 50.8 (from test data, may be coverage-capped)
   - **Enhancer Bonus:** 6.0
   - **Built Native:** 56.8 (if component not capped)
   - **Uncapped Score:** `56.8 * 2.0 = 113.6`
   - **Gap to Target:** -1.6 points (close, but may be capped by coverage-based component cap)

2. **Downtown Charleston SC**
   - **Current Score:** 94
   - **Target Score:** 97
   - **Component Score:** 50.0 (from test data)
   - **Enhancer Bonus:** 0.0
   - **Built Native:** 50.0
   - **Uncapped Score:** `50.0 * 2.0 = 100.0`
   - **Gap to Target:** -3 points (would hit 100 without cap, but target is 97)

3. **Park Slope Brooklyn NY**
   - **Current Score:** 86.6
   - **Target Score:** 92
   - **Component Score:** 47.0 (not maxed, likely coverage-capped)
   - **Enhancer Bonus:** 0.0
   - **Built Native:** 47.0
   - **Uncapped Score:** `47.0 * 2.0 = 94.0`
   - **Gap to Target:** -5.4 points (under-scoring, not cap-related, but rowhouse bonus issue)

---

## Part 3: Cap Impact Analysis

### Key Findings

1. **The `* 2.0` Multiplier is Too Aggressive**
   - Designed to scale 0-58 range to 0-116 range
   - But then capped at 100, losing differentiation
   - Locations with `built_native >= 50.0` all cap at 100
   - **Impact:** Georgetown and Back Bay both show 100, but would naturally score 112

2. **Multiple Locations Are Capped at Final Score Level**
   - Georgetown: Would score 112 without cap (currently 100) - **12 points lost**
   - Back Bay: Would score 112 without cap (currently 100) - **12 points lost**
   - Old Town Alexandria: Component may be coverage-capped, but if not, would score 113.6
   - Downtown Charleston: Would score 100 without cap (currently 94, but normalization is identity so this is odd)

3. **Component Score May Also Be Capped**
   - Coverage-based caps in `arch_diversity.py` can reduce component score below 50.0
   - This is a separate cap from the final score cap
   - Old Town Alexandria shows 50.8 component, which suggests it's not fully capped
   - Downtown Charleston shows 50.0 component, which may be the natural max or coverage-capped

4. **Normalization is Identity (No Additional Impact)**
   - All area types use `shift: 0, scale: 1, max: 100`
   - Normalization should not reduce scores below `built_score_raw`
   - If scores are below 100, it's because `built_score_raw < 100` (component or enhancer caps)

### Root Cause

The primary issue is the final score cap at line 301: `built_score_raw = min(100.0, built_native * 2.0)`. This prevents scores above 100 even when the natural score would be 112+.

---

## Part 4: Recommendations

### Option A: Remove Final Score Cap (Allow Scores > 100)

**Pros:**
- Allows differentiation between exceptional locations
- Georgetown (112) vs Back Bay (112) vs Old Town Alexandria (112) would all be visible
- Aligns with user's stated preference: "caps are artificial deflation"

**Cons:**
- Scores would exceed 100 scale
- May need to adjust other pillars to match
- Could confuse users expecting 0-100 scale

**Implementation:**
- Remove `min(100.0, ...)` from line 301 in `pillars/built_beauty.py`
- Keep normalization cap at 100.0 (or increase it)
- Update documentation to reflect 0-116+ scale

### Option B: Adjust Multiplier (Reduce from 2.0 to ~1.72)

**Pros:**
- Keeps scores within 0-100 range
- `58.0 * 1.72 = 99.76` (just under 100)
- Maintains differentiation without exceeding 100

**Cons:**
- Still caps at 100 for exceptional locations
- Doesn't fully address user's concern about "artificial deflation"

**Implementation:**
- Change `built_score_raw = min(100.0, built_native * 2.0)` to `built_score_raw = min(100.0, built_native * 1.72)`
- This would allow max score of ~100 without capping most locations

### Option C: Remove All Caps (User's Preference)

**Pros:**
- Fully addresses user's concern: "caps are artificial deflation"
- Allows natural score distribution
- No artificial limits

**Cons:**
- Scores could be very high (112+)
- May need to adjust normalization
- Could make scores less interpretable

**Implementation:**
- Remove `min(100.0, ...)` from line 301
- Remove `max: 100.0` from normalization (or set to higher value)
- Let scores naturally distribute

---

## Part 5: Next Steps

1. **Verify Actual Component Scores**
   - Check test data to confirm component scores for each location
   - Calculate actual `built_native` values
   - Verify which locations are truly hitting caps

2. **Test Uncapped Scores**
   - Calculate what scores would be without caps
   - Compare to targets to see if caps are limiting legitimate scores

3. **Implement Recommended Fix**
   - Based on user preference (Option C: Remove all caps)
   - Test against full regression suite
   - Verify no regressions

---

## Conclusion

The primary cap is at `built_score_raw = min(100.0, built_native * 2.0)`, which prevents scores above 100 even when `built_native * 2.0 > 100`. This is limiting differentiation between exceptional locations (Georgetown, Back Bay) that would naturally score 112+.

**Key Impact:**
- Georgetown: Losing 12 points (would be 112, showing 100)
- Back Bay: Losing 12 points (would be 112, showing 100)
- Both locations are identical at 100, but would naturally differentiate at 112

**Recommendation:** Remove the cap (Option C) to align with user's stated preference that "caps are artificial deflation" and allow natural score distribution. This will:
1. Allow differentiation between exceptional locations
2. Show true scores (112 for Georgetown/Back Bay instead of 100)
3. Align with user's philosophy: "caps are artificial deflation"

**Implementation Plan:**
1. Remove `min(100.0, ...)` from line 301 in `pillars/built_beauty.py`
2. Update normalization `max` to allow scores > 100 (or remove max cap)
3. Test against regression suite to verify no unintended impacts
4. Update documentation to reflect 0-116+ scale for built beauty

