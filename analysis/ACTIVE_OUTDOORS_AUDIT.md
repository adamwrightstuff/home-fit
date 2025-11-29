# Active Outdoors Pillar Audit
## Methodology & Design Principles Compliance

**Purpose:** Audit the Active Outdoors pillar against the methodology and design principles used to tune the Public Transit pillar.

**Date:** 2024-12-XX  
**Reference:** `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md`

---

## Executive Summary

This audit evaluates Active Outdoors (v1 and v2) against the comprehensive methodology established for Public Transit. Key findings:

- ✅ **Strengths:** Uses area-type-specific expectations, smooth curves, objective metrics
- ⚠️ **Gaps:** Missing research-backed expected values documentation, no formal calibration methodology, limited structured logging
- ❌ **Issues:** Hardcoded expectations in v2, calibration parameters need refitting, no correlation-based bonus sizing

---

## 1. Research-Backed Expected Values

### Public Transit Standard
- **Research Script:** `scripts/research_expected_values.py` collects real-world data
- **Sample Sizes:** 10+ locations per area type
- **Statistics:** Medians and percentiles (p25, p75) from empirical data
- **Documentation:** All expected values documented with sample sizes and data sources

### Active Outdoors Current State

#### ✅ What's Good
- Expected values exist in `regional_baselines.py` for `active_outdoors`
- Some documentation of sample sizes (e.g., "n=10 successful", "n=13 successful")
- Area-type-specific expectations are defined

#### ⚠️ Gaps Identified

1. **Incomplete Documentation**
   - Expected values in `regional_baselines.py` have minimal comments
   - Sample sizes mentioned but not consistently documented
   - No reference to research script or methodology used

2. **Hardcoded Expectations in v2**
   ```python
   # In _score_daily_urban_outdoors_v2():
   if area_type in {"urban_core", "historic_urban"}:
       exp_park_ha, exp_park_count, exp_play = 5.0, 8.0, 4.0  # Hardcoded!
   ```
   - v2 uses hardcoded expectations instead of `get_contextual_expectations()`
   - This violates the design principle of using research-backed expected values

3. **Missing Research Data Files**
   - No `analysis/research_data/expected_values_raw_data.json` for active_outdoors
   - No `analysis/research_data/expected_values_statistics.json` for active_outdoors
   - Cannot verify expected values against empirical data

### Recommendations

1. **Document Expected Values**
   ```python
   'active_outdoors': {
       # RESEARCH-BACKED (2024-XX-XX):
       # - Research script: scripts/research_expected_values.py
       # - Sample size: n=10 urban_core locations
       # - Median parks within 1km: 8 (p25=6, p75=10)
       # - Median park area: 3 ha (p25=2, p75=5)
       'expected_parks_within_1km': 8,  # Median from research
       'expected_park_area_hectares': 3,  # Median from research
       # ...
   }
   ```

2. **Fix v2 to Use Contextual Expectations**
   - Replace hardcoded values with `get_contextual_expectations(area_type, 'active_outdoors')`
   - Document rationale for any deviations

3. **Run Research Script**
   - Execute `scripts/research_expected_values.py --pillars active_outdoors` for all area types
   - Generate research data files similar to transit pillar
   - Update expected values based on empirical medians

---

## 2. Calibrated Scoring Curve

### Public Transit Standard
- **Calibration Script:** `scripts/calibrate_transit_scoring.py`
- **Target Scores:** 16 locations with known transit quality
- **Approach:** Reverse-engineer breakpoints from route ratios vs target scores
- **Metrics:** Minimize average error, max error, RMSE
- **Documentation:** Calibration methodology and results fully documented

### Active Outdoors Current State

#### ✅ What's Good (v2)
- v2 has calibration parameters: `CAL_A` and `CAL_B`
- Linear calibration: `calibrated_total = CAL_A * raw_total + CAL_B`
- TODO comment acknowledges need for recalibration after component changes

#### ⚠️ Gaps Identified

1. **No Formal Calibration Methodology**
   - No calibration script equivalent to `calibrate_transit_scoring.py`
   - No documented target scores panel
   - No calibration results file (like `transit_curve_calibration.json`)

2. **Calibration Parameters Outdated**
   ```python
   # Current values are placeholders and will need recalibration.
   # Previous calibration (pre-Round 11): a ≈ 1.768, b ≈ 36.202
   # Current values are placeholders and will need recalibration.
   CAL_A = 1.184147
   CAL_B = 50.713368
   ```
   - Parameters marked as placeholders
   - No documentation of calibration methodology
   - No error metrics (avg error, max error, RMSE)

3. **v1 Has No Calibration**
   - v1 uses weighted blend without calibration
   - No documented methodology for weight selection
   - Weights appear to be tuned rather than calibrated

4. **No Calibration Documentation**
   - Missing equivalent of `analysis/TRANSIT_SCORING_CALIBRATION.md`
   - No documentation of calibration panel locations
   - No error analysis or validation

### Recommendations

1. **Create Calibration Script**
   - Create `scripts/calibrate_active_outdoors_v2.py`
   - Follow pattern from `calibrate_transit_scoring.py`
   - Collect target scores for 15-20 diverse locations

2. **Document Calibration Methodology**
   - Create `analysis/ACTIVE_OUTDOORS_CALIBRATION.md`
   - Document target scores panel
   - Document calibration approach (linear fit vs curve fitting)
   - Include error metrics and validation

3. **Refit Calibration Parameters**
   - After Round 11 component changes, rerun calibration
   - Update `CAL_A` and `CAL_B` with documented methodology
   - Validate against calibration panel

4. **Consider v1 Calibration**
   - Evaluate if v1 needs calibration or if v2 should replace it
   - Document weight selection methodology if keeping v1

---

## 3. Context-Aware Scoring Architecture

### Public Transit Standard
- **Core Principle:** Best single mode + small multimodal bonus
- **Rationale:** Prioritizes depth over breadth
- **Multimodal Bonus:** Small (3-6 points) to avoid penalizing excellent single-mode systems
- **Application Pattern:** `max(component1, component2, component3) + small_bonus`

### Active Outdoors Current State

#### ✅ What's Good
- v2 uses weighted blend: `W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score`
- Components are normalized and weighted appropriately
- No multiplicative stacking

#### ⚠️ Gaps Identified

1. **No "Best Component" Pattern**
   - Active Outdoors uses weighted average, not `max()` pattern
   - This is actually appropriate for Active Outdoors (different from transit)
   - But should be documented why weighted blend is preferred

2. **v1 Has Unusual Weight Distribution**
   ```python
   W_LOCAL = 0.15   # local parks / playgrounds
   W_TRAIL = 0.15   # trail access
   W_WATER = 0.20   # water access
   W_CAMP = 0.50    # camping access (50%!)
   ```
   - Camping gets 50% weight, which seems disproportionate
   - No documentation of rationale
   - May violate design principle of balanced scoring

3. **No Multimodal Bonus Pattern**
   - Active Outdoors doesn't use "best component + bonus" pattern
   - This is fine, but should be documented why

### Recommendations

1. **Document Architecture Choice**
   - Explain why weighted blend is preferred over `max()` pattern for Active Outdoors
   - Document rationale for component weights

2. **Review v1 Weights**
   - Evaluate if 50% camping weight is appropriate
   - Consider if weights should be recalibrated or if v1 should be deprecated

3. **Consider Bonus Pattern (Optional)**
   - Evaluate if "outdoor gateway bonus" pattern (similar to multimodal bonus) would improve scoring
   - If adding bonuses, follow correlation-based sizing (see Section 5)

---

## 4. Area-Type-Specific Logic

### Public Transit Standard
- **Commuter Rail Suburb Detection:** Objective criteria (distance, population, route counts)
- **Area Type Mapping:** `historic_urban` → `urban_residential` (documented)
- **Area-Type-Specific Radii:** Via `radius_profiles.py` (objective, scalable)
- **No City Name Matching:** All detection is objective

### Active Outdoors Current State

#### ✅ What's Good
- Uses `get_radius_profile()` for area-type-specific radii
- Uses `get_area_classification()` for objective area type detection
- Area-type-specific expectations and scoring curves
- No hardcoded city exceptions

#### ⚠️ Gaps Identified

1. **Hardcoded Expectations in v2**
   - v2 has hardcoded area-type logic instead of using `get_contextual_expectations()`
   - This violates the design principle of using research-backed expected values

2. **No Special Area Type Detection**
   - Public Transit has "commuter_rail_suburb" detection
   - Active Outdoors could benefit from "mountain_town" or "coastal_gateway" detection
   - But this should be objective (elevation, trail density, etc.), not city names

3. **Inconsistent Area Type Handling**
   - v1 uses `get_contextual_expectations()` correctly
   - v2 hardcodes expectations, creating inconsistency

### Recommendations

1. **Fix v2 to Use Contextual Expectations**
   ```python
   # Replace hardcoded values:
   expectations = get_contextual_expectations(area_type, 'active_outdoors')
   exp_park_ha = expectations.get('expected_park_area_hectares', 5.0)
   exp_park_count = expectations.get('expected_parks_within_1km', 8.0)
   ```

2. **Consider Special Area Type Detection (Optional)**
   - If adding "mountain_town" or "coastal_gateway" detection, use objective criteria:
     - Elevation > threshold
     - Trail density > threshold
     - Distance to major trailheads
   - Document detection criteria and rationale

3. **Document Area Type Mapping**
   - Document any area type mappings (e.g., `historic_urban` → `urban_core` for active_outdoors)
   - Ensure consistency with other pillars

---

## 5. Contextual Bonuses

### Public Transit Standard
- **Correlation-Based Sizing:** Bonuses sized by correlation coefficient (r)
  - r=0.5-0.6 (moderate) → 5-8 points
  - r=0.3-0.5 (weak-moderate) → 3-5 points
  - r<0.3 (weak) → 0-2 points
- **Smooth Curves:** Sigmoid, exponential decay, linear (no hard thresholds)
- **Research-Backed:** All bonuses derived from correlation analysis

### Active Outdoors Current State

#### ✅ What's Good
- v2 has no bonuses (clean, simple model)
- v1 has "outdoor gateway bonus" and "urban penalty" (bounded, smooth)

#### ⚠️ Gaps Identified

1. **No Correlation Analysis for Bonuses**
   - v1 bonuses (`outdoor_bonus`, `urban_penalty`) have no documented correlation analysis
   - Bonus amounts (max +15, -8 to -12) appear arbitrary
   - No research backing for bonus sizes

2. **Bonus Rationale Not Documented**
   - Why +15 for outdoor gateway? Why -8 to -12 for urban penalty?
   - No correlation coefficients or research data
   - Violates design principle of research-backed bonuses

### Recommendations

1. **Document Bonus Rationale**
   - If keeping v1 bonuses, document why these amounts were chosen
   - Add correlation analysis if possible
   - Or mark as "preliminary, needs research"

2. **Consider Removing Bonuses (v1)**
   - If bonuses can't be research-backed, consider removing them
   - Or move to v2 with proper correlation analysis

3. **If Adding Bonuses to v2**
   - Follow Public Transit pattern:
     - Calculate correlation coefficient (r) between metric and target scores
     - Size bonus by correlation strength
     - Use smooth curves (sigmoid, exponential, linear)
     - Document methodology

---

## 6. Fallback Scoring for Unexpected Components

### Public Transit Standard
- **Conservative Scoring:** Max 50 points for unexpected modes (vs 95 for expected)
- **Smooth Scaling:** No hard thresholds
- **Research-Backed:** Based on calibration analysis
- **TODO:** Documented for future research

### Active Outdoors Current State

#### ✅ What's Good
- v2 handles unexpected components gracefully (e.g., camping in urban areas)
- Smooth curves prevent discontinuities

#### ⚠️ Gaps Identified

1. **No Explicit Fallback Logic**
   - Active Outdoors doesn't have explicit "unexpected component" fallback
   - Components that aren't expected for area type may be scored normally
   - This could lead to over-scoring

2. **Camping Handling**
   - v1 has logic: "If camping not expected, return neutral score (5.0)"
   - This is good, but not documented as "fallback scoring"
   - v2 has area-type-aware camping scoring, which is better

### Recommendations

1. **Document Fallback Logic**
   - Document how unexpected components are handled
   - Consider conservative scoring for unexpected components (similar to transit)

2. **Review Component Scoring**
   - Ensure components that aren't expected for area type are scored conservatively
   - Document rationale

---

## 7. Data Quality & Performance Optimizations

### Public Transit Standard
- **Route Deduplication:** Prevents inflated scores from double-counting
- **Performance Optimizations:**
  - Cached stops data (reuse for multiple functions)
  - Parallel API calls (ThreadPoolExecutor)
  - Reuse data from previous calls
  - ~95% speedup achieved
- **Enhanced Logging:** Structured JSON logging with context

### Active Outdoors Current State

#### ✅ What's Good
- Uses `assess_pillar_data_quality()` for data quality metrics
- Data quality included in breakdown

#### ⚠️ Gaps Identified

1. **No Performance Optimizations**
   - No caching of OSM queries
   - No parallel API calls
   - Multiple sequential OSM queries could be optimized

2. **Limited Structured Logging**
   - Uses `print()` statements instead of structured logging
   - No JSON logging with context
   - Missing key metrics in logs (area_type, radii, component scores)

3. **No Data Deduplication**
   - OSM queries may return duplicate features
   - No deduplication logic documented

### Recommendations

1. **Add Structured Logging**
   ```python
   # Replace print() with:
   logger.info("🏃 Analyzing active outdoors access...", extra={
       "pillar_name": "active_outdoors",
       "lat": lat,
       "lon": lon,
       "area_type": area_type,
       "location_scope": location_scope
   })
   ```

2. **Add Performance Optimizations**
   - Cache OSM query results if reused
   - Consider parallel queries for independent data sources
   - Measure before/after performance

3. **Add Data Deduplication**
   - Check for duplicate OSM features (by osm_id)
   - Log deduplication stats

---

## 8. Design Principles Adherence

### Checklist from Public Transit Methodology

#### ✅ Research-Backed, Not Artificially Tuned
- **Status:** ⚠️ **PARTIAL**
- **Issues:**
  - v2 has hardcoded expectations (not research-backed)
  - Calibration parameters are placeholders
  - No research data files to verify expected values

#### ✅ Objective and Data-Driven
- **Status:** ✅ **GOOD**
- **Notes:** All metrics are objective (OSM counts, distances, areas)

#### ✅ Scalable and General
- **Status:** ✅ **GOOD**
- **Notes:** No city name matching, uses area type classification

#### ✅ Transparent and Documented
- **Status:** ⚠️ **PARTIAL**
- **Issues:**
  - Missing research methodology documentation
  - Missing calibration documentation
  - Limited rationale for design choices

#### ✅ Smooth and Predictable
- **Status:** ✅ **GOOD**
- **Notes:** Uses smooth curves (exponential decay, saturation functions)

#### ✅ Context-Aware Expectations
- **Status:** ⚠️ **PARTIAL**
- **Issues:**
  - v1 uses contextual expectations correctly
  - v2 hardcodes expectations (inconsistent)

---

## 9. Key Architectural Decisions

### Public Transit Decisions
1. Best single mode scoring (`max()`)
2. Small multimodal bonus (3-6 points)
3. Commute time as weighted component (5%)
4. Contextual bonuses for commuter rail suburbs
5. Fallback scoring for unexpected modes

### Active Outdoors Decisions

#### ✅ Documented Decisions
- v2 uses weighted blend (not `max()`)
- v2 has global calibration (linear fit)
- v1 has outdoor gateway bonus and urban penalty

#### ⚠️ Missing Documentation
- Why weighted blend instead of `max()`?
- Why these specific weights?
- Why linear calibration instead of curve fitting?
- Why outdoor gateway bonus amounts?

### Recommendations

1. **Document All Architectural Decisions**
   - Create `analysis/ACTIVE_OUTDOORS_ARCHITECTURE.md`
   - Document rationale for each decision
   - Compare to Public Transit decisions and explain differences

2. **Review Decision Rationale**
   - Ensure decisions align with design principles
   - Update documentation if rationale changes

---

## 10. Lessons Learned & Patterns

### Public Transit Patterns
1. Research → Expected Values → Calibration → Implementation
2. Correlation-Based Bonus Sizing
3. Smooth Curve Selection
4. Area-Type-Specific Detection
5. Performance Optimization Strategy

### Active Outdoors Patterns

#### ✅ Patterns Applied
- Smooth curve selection (exponential decay, saturation)
- Area-type-specific expectations
- Context-aware scoring

#### ⚠️ Patterns Missing
- Research → Expected Values → Calibration → Implementation (incomplete)
- Correlation-Based Bonus Sizing (not applied)
- Performance Optimization Strategy (not applied)

### Recommendations

1. **Apply Missing Patterns**
   - Follow Research → Expected Values → Calibration → Implementation pattern
   - Apply correlation-based bonus sizing if adding bonuses
   - Apply performance optimization strategy

2. **Document Patterns**
   - Document which patterns are applied and why
   - Document any pillar-specific patterns

---

## 11. Anti-Patterns Avoided

### Public Transit Anti-Patterns
- ❌ No hardcoded city exceptions
- ❌ No tuning to target scores
- ❌ No artificial caps without justification
- ❌ No location-specific logic
- ❌ No multiplicative stacking
- ❌ No post-normalization shifts

### Active Outdoors Status

#### ✅ Avoided
- No hardcoded city exceptions
- No location-specific logic
- No multiplicative stacking
- No post-normalization shifts

#### ⚠️ Potential Issues
- v2 has hardcoded expectations (not city exceptions, but still hardcoded)
- Calibration parameters may be tuned to target scores (needs verification)
- v1 camping weight (50%) may be arbitrary (needs documentation)

---

## 12. Documentation Gaps

### Missing Documentation

1. **Research Methodology**
   - No equivalent of `analysis/RESEARCH_BACKED_EXPECTED_VALUES.md`
   - No research data files
   - No documentation of sample sizes and methodology

2. **Calibration Methodology**
   - No equivalent of `analysis/TRANSIT_SCORING_CALIBRATION.md`
   - No calibration results file
   - No error metrics

3. **Architecture Documentation**
   - No equivalent of `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md`
   - Limited rationale for design choices
   - No decision log

4. **Component Documentation**
   - Limited documentation of scoring functions
   - No rationale for curve parameters
   - No documentation of weight selection

### Recommendations

1. **Create Comprehensive Documentation**
   - `analysis/ACTIVE_OUTDOORS_METHODOLOGY.md` (similar to transit)
   - `analysis/ACTIVE_OUTDOORS_CALIBRATION.md`
   - `analysis/ACTIVE_OUTDOORS_RESEARCH.md`

2. **Document All Functions**
   - Add docstrings with rationale
   - Document curve parameters and breakpoints
   - Document expected value sources

---

## 13. Priority Recommendations

### High Priority (Critical Gaps)

1. **Fix v2 Hardcoded Expectations**
   - Replace with `get_contextual_expectations()`
   - Document any deviations

2. **Create Calibration Methodology**
   - Create calibration script
   - Document calibration panel and methodology
   - Refit calibration parameters

3. **Add Structured Logging**
   - Replace `print()` with structured JSON logging
   - Include context (lat, lon, area_type, etc.)

4. **Document Expected Values**
   - Add research-backed documentation to `regional_baselines.py`
   - Reference research script and sample sizes

### Medium Priority (Important Improvements)

5. **Run Research Script**
   - Execute `research_expected_values.py` for active_outdoors
   - Generate research data files
   - Update expected values based on empirical data

6. **Document Architecture Decisions**
   - Create architecture documentation
   - Document rationale for all decisions

7. **Review v1 Weights**
   - Evaluate camping weight (50%)
   - Document rationale or recalibrate

### Low Priority (Nice to Have)

8. **Performance Optimizations**
   - Cache OSM queries
   - Parallelize independent queries

9. **Data Deduplication**
   - Add deduplication logic
   - Log deduplication stats

10. **Consider Special Area Types**
    - Evaluate if "mountain_town" detection would help
    - Use objective criteria if adding

---

## 14. Compliance Score

| Category | Score | Notes |
|----------|-------|-------|
| Research-Backed Expected Values | 6/10 | Has values, but incomplete documentation and v2 hardcoded |
| Calibrated Scoring Curve | 4/10 | v2 has calibration but no methodology; v1 has no calibration |
| Context-Aware Scoring | 8/10 | Good area-type awareness, but v2 inconsistencies |
| Area-Type-Specific Logic | 7/10 | Good, but v2 hardcoded expectations |
| Contextual Bonuses | 5/10 | v1 has bonuses but no correlation analysis |
| Fallback Scoring | 7/10 | Handled but not explicitly documented |
| Data Quality & Performance | 5/10 | Data quality good, but no performance optimizations or structured logging |
| Design Principles Adherence | 6/10 | Good overall, but gaps in research-backing and documentation |
| **Overall** | **6.0/10** | **Good foundation, needs methodology alignment** |

---

## 15. Next Steps

1. **Immediate Actions**
   - Fix v2 hardcoded expectations
   - Add structured logging
   - Document expected values

2. **Short Term (1-2 weeks)**
   - Create calibration script and methodology
   - Run research script for active_outdoors
   - Refit calibration parameters

3. **Medium Term (1 month)**
   - Create comprehensive methodology documentation
   - Document architecture decisions
   - Review and optimize performance

4. **Long Term (Ongoing)**
   - Maintain research data files
   - Update calibration as needed
   - Monitor and improve based on feedback

---

## Conclusion

The Active Outdoors pillar has a solid foundation with good design principles, but needs alignment with the comprehensive methodology established for Public Transit. Key gaps are in research documentation, calibration methodology, and structured logging. Addressing these will bring Active Outdoors to the same level of rigor and transparency as Public Transit.

**Priority:** High - Active Outdoors is a core pillar and should follow the same methodology standards as Public Transit.

---

**End of Audit**

