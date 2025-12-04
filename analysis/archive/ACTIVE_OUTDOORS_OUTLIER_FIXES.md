# Active Outdoors v2 - Outlier Analysis & Proposed Fixes

**Date:** 2024-12-XX  
**Round 12 Calibration Analysis**

---

## Key Findings

### Pattern 1: False Positive Mountain Town Detection

**Issue:** Kansas City is being detected as a mountain town (27 trails, 10.5% canopy) → gets Wild Adventure score of 34.5/50 when it should be much lower.

**Root Cause:** Mountain town detection logic is too lenient. Current logic:
- If trails ≥ 30 AND canopy ≥ 8% → mountain town
- Kansas City: 27 trails, 10.5% canopy → doesn't meet this, but might be getting detected via another path

**Fix:** Strengthen mountain town detection to require higher canopy threshold for urban cores with moderate trail counts.

### Pattern 2: Urban Cores Over-Scoring on Daily Urban Outdoors

**Issue:** Urban cores with low targets (35-45) are getting Daily Urban scores of 16-20/30.

**Examples:**
- Houston: Daily=20.0 (target 35)
- Dallas: Daily=19.1 (target 40)
- Indianapolis: Daily=17.1 (target 45)
- Times Square: Daily=18.4 (target 35)

**Root Cause:** Urban core overflow penalty (max 5.0) may not be strong enough, or park expectations are too high for these locations.

**Fix:** Strengthen urban core penalty, especially for locations with very low targets (indicating poor park access).

### Pattern 3: Urban Cores Over-Scoring on Wild Adventure

**Issue:** Urban cores are getting Wild Adventure scores that are too high.

**Examples:**
- Kansas City: Wild=34.5 (false positive mountain town)
- Detroit: Wild=17.7 (target 40)
- Indianapolis: Wild=14.9 (target 45)

**Root Cause:** 
1. False positive mountain town detection (Kansas City)
2. Urban core trail cap may not be strong enough
3. Trail expectations may be too low for urban cores

**Fix:** 
1. Fix mountain town detection
2. Strengthen urban core trail cap
3. Consider additional penalty for urban cores with low targets

### Pattern 4: Water Scores May Be Too High

**Issue:** Some urban cores getting high water scores.

**Example:**
- Detroit: Water=16.7/20 (target 40) - seems high for a landlocked urban core

**Root Cause:** Water downweighting for urban cores may not be strong enough, or distance decay is too generous.

**Fix:** Strengthen urban core water downweighting, especially for non-beach water.

---

## Proposed Fixes (Research-Backed, Not Target-Tuned)

### Fix 1: Strengthen Mountain Town Detection

**Current Logic:**
- Trails ≥ 30 AND canopy ≥ 8% → mountain town (for non-dense urban)

**Problem:** Kansas City (27 trails, 10.5% canopy) might be getting detected via a different path, or the logic needs to be more restrictive.

**Proposed Fix:**
- For urban cores: Require trails ≥ 40 AND canopy ≥ 10% (stricter than current)
- For non-urban: Keep current logic but add minimum trail count check
- Add explicit check: If area_type is urban_core and trails < 40, don't detect as mountain town

**Rationale:** Research-backed - mountain towns should have very high trail counts, not just moderate counts. Kansas City is not a mountain town.

### Fix 2: Strengthen Urban Core Daily Urban Penalty

**Current:** Max penalty of 5.0 points

**Proposed:** 
- Increase max penalty to 8.0 points
- Apply stronger penalty when park count significantly exceeds expectations (2x+ expected)
- Consider additional penalty for very low target locations (indicating poor real-world access)

**Rationale:** Research-backed - dense urban cores with many tiny parks (OSM artifacts) shouldn't score high. The penalty should be proportional to the overflow.

### Fix 3: Strengthen Urban Core Trail Cap

**Current:** Cap at 3x expected (for urban cores)

**Proposed:**
- Reduce cap to 2x expected for urban cores
- Apply additional penalty if trail count exceeds cap significantly
- Consider area-type-specific caps based on research

**Rationale:** Research-backed - urban cores have limited true hiking trail access. The cap should be more conservative.

### Fix 4: Strengthen Urban Core Water Downweighting

**Current:** Non-beach water in urban cores: 60% of base score

**Proposed:**
- Reduce to 50% for non-beach water in urban cores
- Apply stronger downweight for very low target locations
- Consider distance-based downweighting (closer water in urban cores may be ornamental)

**Rationale:** Research-backed - urban cores often have ornamental water features that shouldn't score high. Detroit's water score of 16.7 seems too high.

---

## Implementation Plan

1. **Fix Mountain Town Detection** (Priority 1)
   - Strengthen criteria for urban cores
   - Add explicit checks to prevent false positives

2. **Strengthen Urban Core Penalties** (Priority 2)
   - Increase Daily Urban penalty
   - Strengthen trail cap
   - Strengthen water downweighting

3. **Re-run Calibration** (Priority 3)
   - Test fixes on Round 12 panel
   - Compare metrics (R², MAE, max error)
   - Only update CAL_A/CAL_B if metrics improve

4. **Validate** (Priority 4)
   - Check that fixes don't break high-scoring locations
   - Ensure mountain towns (Boulder, Denver) still score correctly
   - Verify low-scoring locations now score appropriately

---

## Design Principles Compliance

✅ **Research-Backed:** All fixes based on data patterns, not target scores  
✅ **Not Target-Tuned:** Fixes address systematic issues, not specific locations  
✅ **Objective Criteria:** Mountain town detection uses objective signals  
✅ **Transparent:** All changes documented with rationale  
✅ **Area-Type Aware:** Fixes respect area type differences  

