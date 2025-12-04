# Active Outdoors Pillar - Next Steps Roadmap

**Status:** High-priority fixes completed ✅  
**Date:** 2024-12-XX  
**Reference:** `analysis/ACTIVE_OUTDOORS_AUDIT.md`

---

## ✅ Completed (High Priority)

1. ✅ **Fixed v2 hardcoded expectations** - Now uses `get_contextual_expectations()`
2. ✅ **Added structured logging** - Replaced all `print()` with `logger.info()`
3. ✅ **Documented expected values** - Enhanced documentation in `regional_baselines.py`

---

## 🔄 Immediate Next Steps (This Week)

### 1. Recalibrate v2 After Component Changes

**Priority:** HIGH  
**Status:** Script exists, needs to be run

**Action:**
```bash
# Run calibration script with updated v2 implementation
python scripts/calibrate_active_outdoors_v2.py
```

**Why:** The v2 implementation was updated to use research-backed expected values instead of hardcoded ones. This changes the raw scores, so calibration parameters (CAL_A, CAL_B) need to be refit.

**Expected Output:**
- New calibration parameters (CAL_A, CAL_B)
- Error metrics (mean error, max error, R²)
- Calibration report saved to `analysis/active_outdoors_calibration_round11.json`

**Next:** Update `pillars/active_outdoors.py` with new CAL_A and CAL_B values.

**Reference:** `analysis/ACTIVE_OUTDOORS_ROUND11_CHANGES.md` documents the component changes that require recalibration.

---

### 2. Run Research Script to Expand Expected Values

**Priority:** MEDIUM  
**Status:** Script exists, needs execution

**Action:**
```bash
# Run research script for active_outdoors pillar
python scripts/research_expected_values.py --pillars active_outdoors --area-types urban_core suburban exurban rural urban_residential
```

**Why:** Current expected values have limited sample sizes:
- Urban Core: n=10 ✅ (good)
- Suburban: n=13 ✅ (good)
- Exurban/Rural: Limited data ⚠️ (needs expansion)
- Urban Residential: Uses urban_core values (may need separate research)

**Expected Output:**
- `analysis/research_data/expected_values_raw_data.json` (or similar)
- `analysis/research_data/expected_values_statistics.json`
- Updated medians and percentiles (p25, p75) for all area types

**Next:** Update `regional_baselines.py` with expanded research data, including percentiles.

---

### 3. Validate Calibration Results

**Priority:** HIGH  
**Status:** After step 1

**Action:**
- Review calibration report from step 1
- Verify mean absolute error ≤ 10 points
- Check that no location is off by >20 points without documented reason
- Ensure correct relative ordering (outdoor towns > urban cores)

**Success Criteria:**
- Mean absolute error: ≤ 10 points
- Max absolute error: ≤ 20 points (or documented reason)
- R²: > 0.7 (good fit)
- Relative ordering maintained

**If validation fails:**
- Investigate outliers
- Review component scoring functions
- Consider additional calibration panel locations

---

## 📚 Documentation (Next 1-2 Weeks)

### 4. Create Comprehensive Methodology Documentation

**Priority:** MEDIUM  
**Status:** Not started

**Action:** Create `analysis/ACTIVE_OUTDOORS_METHODOLOGY.md` following the pattern of `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md`

**Sections to include:**
1. Research-Backed Expected Values (with sample sizes, data sources)
2. Calibrated Scoring Curve (methodology, results, error metrics)
3. Context-Aware Scoring Architecture (component weights, aggregation)
4. Area-Type-Specific Logic (expectations, radii, special types)
5. Component Scoring Functions (rationale, curves, breakpoints)
6. Calibration Methodology (panel, approach, validation)
7. Design Principles Adherence (checklist compliance)
8. Key Architectural Decisions (rationale for choices)
9. Lessons Learned & Patterns (reusable patterns)
10. Anti-Patterns Avoided (what not to do)

**Reference:** Use `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md` as template.

---

### 5. Document Calibration Methodology

**Priority:** MEDIUM  
**Status:** Script exists, needs documentation

**Action:** Create `analysis/ACTIVE_OUTDOORS_CALIBRATION.md`

**Sections to include:**
- Calibration panel locations (Round 11)
- Calibration approach (linear fit: `target = CAL_A * raw_total + CAL_B`)
- Calibration results (parameters, error metrics)
- Validation results (per-location errors, outliers)
- Comparison to previous calibration (if applicable)
- Next steps for future calibration

**Reference:** Use `analysis/TRANSIT_SCORING_CALIBRATION.md` as template.

---

### 6. Document Research Methodology

**Priority:** LOW  
**Status:** Script exists, needs documentation

**Action:** Create `analysis/ACTIVE_OUTDOORS_RESEARCH.md` or enhance `analysis/RESEARCH_BACKED_EXPECTED_VALUES.md`

**Sections to include:**
- Research script: `scripts/research_expected_values.py`
- Sample sizes by area type
- Data sources (OSM queries, radii used)
- Statistics calculated (medians, percentiles)
- Expected values derived from research
- Gaps and TODOs (exurban/rural need more samples)

---

## 🔍 Review & Optimization (Next Month)

### 7. Review v1 Weights

**Priority:** MEDIUM  
**Status:** Needs review

**Current v1 weights:**
```python
W_LOCAL = 0.15   # local parks / playgrounds
W_TRAIL = 0.15   # trail access
W_WATER = 0.20   # water access
W_CAMP = 0.50    # camping access (50%!)
```

**Action:**
- Evaluate if 50% camping weight is appropriate
- Document rationale for weights or recalibrate
- Consider if v1 should be deprecated in favor of v2

**Questions to answer:**
- Why does camping get 50% weight?
- Is this research-backed or calibrated?
- Should v1 be maintained or deprecated?

---

### 8. Performance Optimizations

**Priority:** LOW  
**Status:** Not started

**Action:** Apply performance optimization patterns from Public Transit

**Potential optimizations:**
- Cache OSM query results if reused
- Parallelize independent API calls (e.g., parks + trails + water)
- Reuse data from previous calls
- Measure before/after performance

**Reference:** Public Transit achieved ~95% speedup through caching and parallelization.

---

### 9. Data Deduplication

**Priority:** LOW  
**Status:** Not started

**Action:** Add deduplication logic for OSM features

**Implementation:**
- Check for duplicate OSM features (by osm_id)
- Log deduplication stats
- Prevent inflated scores from double-counting

**Reference:** Public Transit deduplicates routes by `onestop_id` or `route_id`.

---

## 🎯 Long-Term Improvements

### 10. Expand Research Data

**Priority:** LOW  
**Status:** Ongoing

**Action:** Continue expanding research data for underrepresented area types

**Focus areas:**
- Exurban: Need 10+ samples (currently limited)
- Rural: Need 10+ samples (currently limited)
- Urban Residential: Consider separate research pass
- Percentiles: Calculate p25, p75 for better calibration

---

### 11. Consider Special Area Type Detection

**Priority:** LOW  
**Status:** Optional enhancement

**Action:** Evaluate if special area types would improve scoring

**Potential special types:**
- "Mountain Town" (elevation > threshold, trail density > threshold)
- "Coastal Gateway" (distance to coast < threshold, water access)

**Requirements:**
- Use objective criteria (not city name matching)
- Document detection logic
- Research-backed thresholds

**Reference:** Public Transit has "commuter_rail_suburb" detection using objective criteria.

---

## 📋 Summary Checklist

### This Week
- [ ] Run `calibrate_active_outdoors_v2.py` to refit calibration parameters
- [ ] Update CAL_A and CAL_B in `pillars/active_outdoors.py`
- [ ] Validate calibration results (error metrics, relative ordering)

### Next 1-2 Weeks
- [ ] Run `research_expected_values.py` for active_outdoors
- [ ] Update expected values in `regional_baselines.py` with expanded research
- [ ] Create `ACTIVE_OUTDOORS_METHODOLOGY.md`
- [ ] Create `ACTIVE_OUTDOORS_CALIBRATION.md`
- [ ] Document research methodology

### Next Month
- [ ] Review v1 weights and document rationale
- [ ] Consider performance optimizations
- [ ] Add data deduplication logic
- [ ] Expand research data for underrepresented area types

---

## 🎓 Key Learnings from Public Transit

When implementing these steps, follow the patterns established by Public Transit:

1. **Research → Expected Values → Calibration → Implementation**
   - Don't skip steps
   - Document each step thoroughly

2. **Correlation-Based Bonus Sizing** (if adding bonuses)
   - Calculate correlation coefficient (r)
   - Size bonuses by correlation strength
   - Use smooth curves

3. **Smooth Curve Selection**
   - Exponential decay for distance-based scoring
   - Sigmoid for normalized ratios
   - Linear for simple scaling

4. **Performance Optimization Strategy**
   - Identify bottlenecks
   - Cache reusable data
   - Parallelize independent operations
   - Measure impact

---

## 📊 Success Metrics

**Calibration:**
- Mean absolute error: ≤ 10 points
- Max absolute error: ≤ 20 points
- R²: > 0.7

**Research:**
- 10+ samples per area type
- Medians and percentiles calculated
- Expected values documented with sources

**Documentation:**
- Comprehensive methodology document
- Calibration documentation
- Research methodology documented

**Compliance:**
- All design principles followed
- No hardcoded exceptions
- Research-backed expected values
- Transparent and documented

---

**End of Roadmap**

