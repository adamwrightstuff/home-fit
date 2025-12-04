# Built Beauty Analysis: Research vs. Current Model & Proposed Fixes

## Executive Summary

This document compares Perplexity research findings on ideal built beauty characteristics with our current model's behavior, identifies systematic issues, and proposes specific fixes for Priority 1 (coverage expectations), Priority 2 (modern urban core misclassification), and Priority 3 (score capping investigation).

---

## Part 1: Research vs. Current Model Comparison

### A. Spacious Historic Districts

**Research Finding:**
> "Coverage ratio ~30-50%, includes significant open/green space. Spacious historic districts favor less coverage to preserve greenery and sense of openness."

**Current Model Behavior:**
- **Old San Juan PR**: 20.9% coverage → Component score: 16.5 → Total: 41.4 (Target: 95, Gap: -53.8)
- **Garden District New Orleans**: 19.8% coverage → Component score: 30.1 → Total: 67.9 (Target: 85, Gap: -17.1)

**Problem:** Both locations are penalized for low coverage despite being spacious historic districts where lower coverage is **appropriate and desirable**.

**Root Cause:** Coverage expectations are too high for spacious historic districts. The model treats 20% coverage as a penalty, but research indicates 30-50% is ideal (and 20% may still be acceptable for very spacious districts like Old San Juan).

---

### B. Modern Urban Cores

**Research Finding:**
> "Modern Urban Cores: Sleek, functional, large scale, tech expression. Should score for **innovation and coherence**, not historic preservation."

**Current Model Behavior:**
- **Downtown Austin TX**: Median year 2007, 251 landmarks → Classified as `historic_urban` → Scores 100 (Target: 75, Gap: +25)
- **South Lake Union Seattle WA**: Median year 2012, 45 landmarks → Classified as `historic_urban` → Scores 100 (Target: 70, Gap: +30)

**Problem:** Modern areas are misclassified as `historic_urban` and scored using historic criteria, leading to over-scoring.

**Root Cause:** Classification logic uses landmark count (251 for Austin, 45 for SLU) to classify modern areas as historic, when they should be `urban_core` and scored for modern form quality.

**Bug Location:** `data_sources/data_quality.py`, `get_contextual_tags()` function (lines 401-408)

**Current Buggy Logic:**
```python
# Historic tag
is_historic = False
if median_year_built is not None and median_year_built < 1950:
    is_historic = True
if historic_landmarks and historic_landmarks >= 10:
    is_historic = True  # ❌ BUG: No median year check!
if is_historic:
    tags.append('historic')
```

**Why This Is Wrong:**
- Downtown Austin (median 2007) has 251 landmarks → Gets `'historic'` tag → Classified as `historic_urban`
- South Lake Union (median 2012) has 45 landmarks → Gets `'historic'` tag → Classified as `historic_urban`
- These are **modern areas**, not historic districts!

---

### C. Historic Neighborhoods with Modern Infill

**Important Distinction:** Some neighborhoods are **truly historic** but have modern infill development. These should still be classified as historic:

**Examples:**
- **Georgetown DC**: Historic core (1700s-1800s) with modern buildings mixed in. Median year might be 1960s-1970s due to infill, but should still be historic.
- **Back Bay Boston**: Historic (1800s) with modern additions. Median year might be 1950s-1960s.
- **Society Hill Philadelphia**: Historic (1700s-1800s) with modern infill. Median year might be 1960s-1970s.
- **Greenwich Village NYC**: Historic (1800s-1900s) with modern additions.
- **Old Town Alexandria VA**: Historic (1700s-1800s) with modern buildings.
- **French Quarter New Orleans**: Historic (1700s-1800s) with modern infill.

**Key Insight:** These neighborhoods have:
- Median year < 1980 (historic base with infill)
- High landmark count (historic character preserved)
- Should be classified as `historic_urban`

**What We Want to Avoid:**
- Modern areas (median year >= 1980) with high landmark counts being misclassified as historic
- Examples: Downtown Austin (2007), South Lake Union (2012), modern downtowns

---

### D. Material Coherence vs. Diversity

**Research Finding:**
> "Material coherence preferred with some diversity in texture. A balance is ideal: coherence promotes harmony and identity, diversity stimulates visual interest."

**Current Model Behavior:**
- Most locations show 0% material tagging (brick %)
- Material bonuses are minimal (0-1.5 points)
- Material scoring is underutilized due to low OSM tagging

**Problem:** Material coherence/diversity isn't being measured effectively, so this research insight can't be applied.

---

### E. Score Capping

**Current Model Behavior:**
- 11 locations hitting 100 cap
- Many are legitimate high-scorers, but cap prevents differentiation

**Similar to Natural Beauty:** Like `WATER_BONUS_MAX` issue, there may be systematic caps limiting scores.

---

## Part 2: Priority Fixes

### Priority 1: Coverage Expectations for Spacious Historic Districts

**Problem:** Spacious historic districts (Old San Juan, Garden District) are penalized for low coverage (20-30%), but research indicates this is appropriate.

**Solution:** Implement coverage expectation adjustment for spacious historic districts, similar to climate-first architecture for natural beauty.

**Implementation:**

1. **Detect Spacious Historic Districts:**
   - Low coverage (<0.25) + Historic context + Uniform materials + Low density variation
   - Or: Coverage 20-30% + Historic landmarks + Pre-1950 median year

2. **Apply Relaxed Coverage Expectations:**
   - Normal expectation: ~0.30-0.35 for historic urban
   - Spacious historic: Accept 20-30% as good (reduce penalty)
   - Very spacious (Old San Juan): Accept 15-25% as good

3. **Code Changes:**
   - Add `_is_spacious_historic_district()` function
   - Modify coverage scoring to use relaxed expectations for these districts
   - Similar to `_get_adjusted_canopy_expectation()` for natural beauty

**Expected Impact:**
- Old San Juan: Component score increases from 16.5 → ~35-40 (coverage penalty reduced)
- Garden District: Component score increases from 30.1 → ~40-45
- Final scores should approach targets (95 for Old San Juan, 85 for Garden District)

---

### Priority 2: Modern Urban Core Classification Fix

**Problem:** Modern areas (median year >= 1980) are being classified as `historic_urban` due to landmark count alone.

**Solution:** Fix `get_contextual_tags()` to require median year check when using landmark count.

**Implementation:**

**File:** `data_sources/data_quality.py`, function `get_contextual_tags()` (lines 401-408)

**Current Code:**
```python
# Historic tag
is_historic = False
if median_year_built is not None and median_year_built < 1950:
    is_historic = True
if historic_landmarks and historic_landmarks >= 10:
    is_historic = True  # ❌ BUG: No median year check!
if is_historic:
    tags.append('historic')
```

**Fixed Code:**
```python
# Historic tag
is_historic = False
# Primary signal: Census median year < 1950 (definitely historic)
if median_year_built is not None and median_year_built < 1950:
    is_historic = True
# Secondary signal: Landmark count (only if median year is historic OR unknown)
# This handles historic neighborhoods with modern infill (Georgetown, Back Bay)
# But prevents modern areas (Downtown Austin 2007, SLU 2012) from being misclassified
if historic_landmarks and historic_landmarks >= 10:
    # Only use landmark count if:
    # 1. Median year is unknown (fallback), OR
    # 2. Median year is historic (< 1980) - allows historic neighborhoods with infill
    # Do NOT use landmark count alone for modern areas (>= 1980)
    if median_year_built is None or median_year_built < 1980:
        is_historic = True
if is_historic:
    tags.append('historic')
```

**Why This Works:**
- **Historic neighborhoods with infill** (Georgetown, median 1960s): Still get historic tag (1960s < 1980)
- **Modern areas** (Downtown Austin 2007, SLU 2012): Won't get historic tag (2007 >= 1980, 2012 >= 1980)
- **Unknown median year**: Can use landmark count as fallback (preserves backward compatibility)

**Expected Impact:**
- Downtown Austin: Reclassified from `historic_urban` → `urban_core`, scored for modern form
- South Lake Union: Reclassified from `historic_urban` → `urban_core`, scored for modern form
- Scores should drop to targets (75 for Austin, 70 for SLU)
- Historic neighborhoods with infill (Georgetown, Back Bay): Still classified as historic (preserved)

---

### Priority 3: Score Capping Investigation

**Problem:** 11 locations hitting 100 cap, preventing differentiation between very good and exceptional.

**Investigation Findings:**

1. **Component Score:**
   - Architectural diversity score (`arch_component`) appears to max around 50.0
   - This is likely the natural maximum from the scoring function, not a hard cap
   - **Location:** `pillars/built_beauty.py`, `_score_architectural_diversity()` function

2. **Enhancer Bonus Cap:**
   - `BUILT_ENHANCER_CAP = 8.0` (defined in `pillars/beauty_common.py`)
   - Applied at line 296: `built_bonus_scaled = min(BUILT_ENHANCER_CAP, built_bonus_raw * built_scale)`
   - Maximum enhancer bonus is 8.0 points (artwork + fountains)

3. **Final Score Calculation:**
   - `built_native = max(0.0, arch_component + built_bonus_scaled)` (line 300)
   - `built_score_raw = min(100.0, built_native * 2.0)` (line 301)
   - **This is the main cap:** Even if `built_native = 50.0 + 8.0 = 58.0`, the `* 2.0` multiplier would give 116.0, but it's capped at 100.0

4. **Normalization Cap:**
   - `normalize_beauty_score()` applies `max: 100.0` for all area types (line 37 in `beauty_common.py`)
   - This is a final safeguard cap

**Key Insight:**
The `built_score_raw = min(100.0, built_native * 2.0)` cap at line 301 is the primary limiting factor. If a location has:
- Component score: 50.0 (max)
- Enhancer bonus: 8.0 (max)
- Total: 58.0
- After `* 2.0`: 116.0 → Capped to 100.0

**Analysis Needed:**
- Calculate what scores would be without the `min(100.0, ...)` cap
- Identify which locations are truly hitting this cap vs. legitimately scoring 100
- Determine if the `* 2.0` multiplier is appropriate or if it should be adjusted

**Next Steps:**
- Review capped locations (11 locations) to see their `built_native` values
- Calculate uncapped scores: `built_native * 2.0` (without min)
- Compare to targets to determine if caps are limiting legitimate high scores
- Consider if the `* 2.0` multiplier should be adjusted or if exceptional locations should be allowed to exceed 100

---

## Part 3: Historic Neighborhoods with Modern Infill

### Neighborhoods That Should Remain Historic (Even with Modern Buildings)

These neighborhoods have historic character preserved but include modern infill. They should still be classified as `historic_urban`:

1. **Georgetown DC**
   - Historic core: 1700s-1800s
   - Modern infill: 1960s-1980s
   - Median year: Likely 1960s-1970s (historic base + infill)
   - Should be: `historic_urban` ✓

2. **Back Bay Boston**
   - Historic core: 1800s
   - Modern infill: 1950s-1970s
   - Median year: Likely 1950s-1960s
   - Should be: `historic_urban` ✓

3. **Society Hill Philadelphia**
   - Historic core: 1700s-1800s
   - Modern infill: 1960s-1980s
   - Median year: Likely 1960s-1970s
   - Should be: `historic_urban` ✓

4. **Greenwich Village NYC**
   - Historic core: 1800s-1900s
   - Modern infill: 1950s-1970s
   - Median year: Likely 1950s-1960s
   - Should be: `historic_urban` ✓

5. **Old Town Alexandria VA**
   - Historic core: 1700s-1800s
   - Modern infill: 1960s-1980s
   - Median year: Likely 1960s-1970s
   - Should be: `historic_urban` ✓

6. **French Quarter New Orleans**
   - Historic core: 1700s-1800s
   - Modern infill: 1950s-1970s
   - Median year: Likely 1950s-1960s
   - Should be: `historic_urban` ✓

**Key Distinction:**
- **Historic with infill**: Median year < 1980 → Should be historic
- **Modern area**: Median year >= 1980 → Should NOT be historic

**Our Fix Preserves This:**
- The fix checks `median_year_built < 1980` before using landmark count
- This means historic neighborhoods with infill (median 1950s-1970s) still get historic tag
- But modern areas (median 2007, 2012) won't get historic tag

---

## Part 4: Implementation Summary

### Fix 1: Coverage Expectations for Spacious Historic Districts

**File:** `pillars/built_beauty.py`
**Function:** Coverage scoring logic
**Change:** Add `_is_spacious_historic_district()` and adjust coverage expectations
**Risk:** Low - only affects specific district type
**Impact:** Old San Juan (+53.8 points), Garden District (+17.1 points)

### Fix 2: Modern Urban Core Classification

**File:** `data_sources/data_quality.py`
**Function:** `get_contextual_tags()` (lines 401-408)
**Change:** Add median year check when using landmark count
**Risk:** Low - only prevents false positives
**Impact:** Downtown Austin (reclassified), South Lake Union (reclassified)

### Fix 3: Score Capping Investigation

**Files:** `pillars/built_beauty.py`, `pillars/beauty_common.py`
**Action:** Identify all caps, calculate uncapped scores, determine if caps are limiting
**Risk:** Medium - need to ensure caps aren't important safeguards
**Impact:** TBD based on investigation

---

## Part 5: Testing Plan

### Regression Tests

**Before implementing fixes:**
1. Capture baseline scores for all test locations
2. Document current classifications

**After implementing fixes:**
1. Test Old San Juan (should increase significantly)
2. Test Garden District (should increase)
3. Test Downtown Austin (should decrease, reclassified)
4. Test South Lake Union (should decrease, reclassified)
5. Test historic neighborhoods with infill (Georgetown, Back Bay) - should remain historic
6. Test all other locations - should remain stable

### Expected Results

**Fix 1 (Coverage):**
- Old San Juan: 41.4 → ~90-95 (approaching target)
- Garden District: 67.9 → ~80-85 (approaching target)

**Fix 2 (Classification):**
- Downtown Austin: 100 → ~75 (reclassified to urban_core, target)
- South Lake Union: 100 → ~70 (reclassified to urban_core, target)
- Georgetown: Still historic_urban (preserved)
- Back Bay: Still historic_urban (preserved)

**Fix 3 (Capping):**
- TBD based on investigation

---

## Conclusion

The research findings align with identified issues:
1. ✅ Spacious historic districts need relaxed coverage expectations
2. ✅ Modern areas are being misclassified as historic (bug)
3. ⚠️ Score capping needs investigation
4. ⚠️ Material scoring is underutilized (lower priority)

The proposed fixes address the most critical issues while preserving correct classification of historic neighborhoods with modern infill.

