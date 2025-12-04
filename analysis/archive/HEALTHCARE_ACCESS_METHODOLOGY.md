# Healthcare Access Pillar: Methodology Audit & Alignment

**Purpose:** Audit Healthcare Access pillar against Public Transit methodology principles and identify improvements needed.

**Last Updated:** 2024-12-19

---

## Current State Analysis

### 1. Research-Backed Expected Values

**Status:** [ ] Needs Research / [x] Partial / [ ] Complete

**Current Implementation:**

- Expected hospitals within 10km: `exp_hosp` (from `get_contextual_expectations`)
  - Urban core: 2 hospitals
  - Suburban: 1 hospital
  - Exurban: 0 hospitals
  - Rural: 0 hospitals

- Expected urgent care within 5km: `exp_urgent` (from `get_contextual_expectations`)
  - Urban core: 5 urgent care facilities
  - Suburban: 3 urgent care facilities
  - Exurban: 1 urgent care facility
  - Rural: 0 urgent care facilities

- Expected pharmacies within 2km: `exp_pharm` (from `get_contextual_expectations`)
  - Urban core: 3 pharmacies
  - Suburban: 2 pharmacies
  - Exurban: 1 pharmacy
  - Rural: 0 pharmacies

**Issues Found:**

- [x] Hardcoded values in code (check for magic numbers)
  - Values in `data_sources/regional_baselines.py` lines 653-783 are hardcoded
  - No documentation of sample sizes or research methodology
  - Values appear to be target-tuned rather than research-backed

- [x] No research data collection script
  - `scripts/research_expected_values.py` exists but does not collect healthcare metrics
  - No healthcare-specific research has been conducted

- [x] Expected values not documented with sample sizes
  - No comments indicating research methodology
  - No medians/percentiles documented
  - No data source citations

- [x] Values may be target-tuned rather than research-backed
  - Values are simple integers (2, 1, 0) without research justification
  - No evidence of empirical data collection

**Action Items:**

1. Run `scripts/research_expected_values.py` for healthcare metrics
   - Add healthcare data collection to research script
   - Collect 10+ samples per area type (urban_core, suburban, exurban, rural)
   - Document medians and percentiles (p25, p75)
2. Update `data_sources/regional_baselines.py` with research-backed values
   - Add research methodology comments
   - Document sample sizes and data sources
   - Include percentiles for better calibration

---

### 2. Calibrated Scoring Curves

**Status:** [x] Needs Calibration / [ ] Partial / [ ] Complete

**Current Implementation:**

- **Hospital Access:** Distance-based with hard thresholds (0-35pts)
  - 5km = 35pts, 10km = 30pts, 15km = 25pts, 25km = 20pts, 40km = 15pts, 60km = 10pts, >60km = 5pts
  - Uses hard thresholds, not smooth curves
  - Located in `pillars/healthcare_access.py` lines 364-379

- **Primary Care:** Binary + density bonus (0-25pts)
  - Base: 10pts if clinic exists, 10pts if doctors exist
  - Density bonus: 0-5pts based on ratio to expected urgent care count
  - Located in `pillars/healthcare_access.py` lines 386-400

- **Specialized Care:** Count-based with hard thresholds (0-15pts)
  - Simple count of unique specialties
  - Score = min(15.0, count of specialties)
  - Located in `pillars/healthcare_access.py` lines 402-411

- **Emergency Services:** Binary (0-10pts)
  - 10pts if any hospital has `emergency=yes` tag, else 0pts
  - Hard threshold, no smooth curve
  - Located in `pillars/healthcare_access.py` lines 413-419

- **Pharmacies:** Ratio-based with expectations (0-15pts)
  - Uses ratio: `pharm_count / target_pharm`
  - Score = `15.0 * min(pharm_ratio, 1.5)`
  - Not using smooth saturation function
  - Located in `pillars/healthcare_access.py` lines 421-429

**Issues Found:**

- [x] Hard thresholds (not smooth curves)
  - Hospital scoring uses piecewise constant function (lines 366-379)
  - Emergency services is binary (line 419)
  - Specialized care is linear count (line 411)

- [x] No calibration panel or target scores
  - No calibration script exists (`scripts/calibrate_healthcare_scoring.py` does not exist)
  - No target scores documented for known healthcare quality locations
  - No calibration methodology

- [x] Scoring may not align with real-world quality perception
  - Hard thresholds create discontinuities
  - No validation against known good/bad healthcare locations

- [x] Different scoring approaches for different components (inconsistent)
  - Hospital: Distance-based thresholds
  - Primary Care: Binary + density
  - Specialized: Count-based
  - Emergency: Binary
  - Pharmacies: Ratio-based (closest to smooth, but not using saturation function)

**Action Items:**

1. Create calibration panel (16+ locations with known healthcare quality)
   - Include urban cores, suburbs, exurban, rural locations
   - Document target scores based on real-world quality perception
2. Create `scripts/calibrate_healthcare_scoring.py`
   - Follow pattern from `scripts/calibrate_transit_scoring.py`
   - Fit smooth curves to minimize error vs target scores
3. Replace hard thresholds with smooth saturation functions
   - Use `_sat_ratio_v2` pattern from Active Outdoors (exponential saturation)
   - Or use piecewise linear with smooth transitions
4. Align all components to use similar scoring methodology
   - Standardize on saturation functions for all ratio-based components
   - Use consistent curve shapes across components

---

### 3. Context-Aware Architecture

**Status:** [x] Needs Improvement / [ ] Good

**Current Implementation:**

- Uses `area_type` for radius profiles (via `get_radius_profile`)
  - Urban core: 5km facilities, 2km pharmacies
  - Suburban: 10km facilities, 3km pharmacies
  - Exurban: 15km facilities, 5km pharmacies
  - Rural: 20km facilities, 8km pharmacies
  - Located in `data_sources/radius_profiles.py` lines 84-93

- Uses `area_type` for expected values (via `get_contextual_expectations`)
  - Area-type-specific expectations for hospitals, urgent care, pharmacies
  - Located in `data_sources/regional_baselines.py` lines 653-783

- Fallback to MAJOR_HOSPITALS database when OSM fails
  - 127 major hospitals in hardcoded database
  - Located in `pillars/healthcare_access.py` lines 17-127
  - Used when OSM query fails or returns no hospitals (lines 273-282)

**Issues Found:**

- [x] No special context detection (e.g., medical centers, rural health deserts)
  - No detection of proximity to major medical centers
  - No identification of rural health access patterns
  - No special handling for healthcare deserts

- [x] Fallback database may not be comprehensive
  - Only 127 hospitals (major medical centers)
  - Missing many regional hospitals and community hospitals
  - No urgent care facilities in fallback (MAJOR_URGENT_CARE_CHAINS is minimal, lines 130-149)
  - Urgent care fallback function exists but is not used in main scoring (lines 152-169)

- [x] No area-type-specific scoring adjustments
  - All area types use same scoring curves (only expectations differ)
  - No special scoring for commuter rail suburbs equivalent (e.g., medical center suburbs)

**Action Items:**

1. Add context detection (medical center proximity, rural health access)
   - Detect proximity to major medical centers (similar to commuter rail suburb detection)
   - Identify rural health deserts (no hospitals within 40km)
   - Add contextual bonuses if correlations support them
2. Expand fallback database or improve OSM coverage
   - Add more regional hospitals to MAJOR_HOSPITALS database
   - Expand MAJOR_URGENT_CARE_CHAINS database
   - Or improve OSM query coverage/completeness
3. Consider area-type-specific scoring curves
   - Similar to transit pillar's commuter rail suburb bonuses
   - Medical center suburbs could have different expectations/scoring

---

### 4. Data Quality & Performance

**Status:** [x] Needs Improvement / [ ] Good

**Current Implementation:**

- OSM query with fallback to MAJOR_HOSPITALS
  - Single OSM query via `osm_api.query_healthcare_facilities()` (lines 261, 585-628)
  - Fallback triggered when query fails or returns no hospitals (lines 273-282)
  - Located in `data_sources/osm_api.py` lines 2071-2200+

- Data quality assessment via `data_quality.assess_pillar_data_quality`
  - Called in `get_healthcare_access_score` (line 449)
  - Confidence adjusted if query failed (lines 452-459)

- Radius filtering applied
  - Filters facilities by area-type-specific radii (lines 328-332)
  - Uses `_filter_by_radius` helper function (lines 294-326)

**Issues Found:**

- [x] No parallel API calls (sequential OSM queries)
  - Single OSM query is sequential (no parallelization
  - Could parallelize if multiple queries were needed (currently one query)

- [x] Fallback database may be incomplete
  - Only 127 major hospitals
  - Missing regional/community hospitals
  - Urgent care fallback is minimal and unused

- [x] No structured logging for debugging
  - Uses `print()` statements (lines 233, 257, 260, 274, 282, 286-290, 292, 334, 531-539)
  - Should use `logger.info()` with structured JSON logging
  - No logging of API responses, query parameters, or data quality metrics

**Action Items:**

1. Add parallel fetching (ThreadPoolExecutor)
   - If multiple queries needed, parallelize them
   - Cache reusable data (similar to transit pillar)
2. Expand or verify fallback database coverage
   - Add regional hospitals to MAJOR_HOSPITALS
   - Expand MAJOR_URGENT_CARE_CHAINS
   - Or verify OSM coverage is sufficient
3. Add structured logging similar to Active Outdoors
   - Replace `print()` with `logger.info()` and structured JSON
   - Log: query parameters, API responses, facility counts, data quality metrics
   - Include context: lat, lon, area_type, pillar_name

---

### 5. Component Scoring Consistency

**Status:** [x] Inconsistent / [ ] Needs Alignment

**Current Issues:**

- **Hospital:** Distance-based with hard thresholds (lines 364-379)
  - Piecewise constant function: 5km=35, 10km=30, 15km=25, etc.
  - Not smooth, has discontinuities

- **Primary Care:** Binary + density (lines 386-400)
  - Binary base (10pts if clinic, 10pts if doctors)
  - Density bonus uses ratio but caps at 1.5x
  - Mixed approach (binary + ratio)

- **Specialized:** Count-based with hard thresholds (lines 402-411)
  - Simple linear: `min(15.0, count)`
  - No expectations, no saturation

- **Emergency:** Binary (lines 413-419)
  - Hard threshold: 10pts if any hospital has emergency tag, else 0pts
  - No smooth curve

- **Pharmacies:** Ratio-based (lines 421-429)
  - Uses ratio: `15.0 * min(pharm_ratio, 1.5)`
  - Closest to smooth, but not using saturation function
  - Should use `_sat_ratio_v2` pattern

**Action Items:**

1. Standardize all components to use saturation functions (`_sat_ratio_v2`)
   - Hospital: Convert distance thresholds to smooth distance curve
   - Primary Care: Replace binary with ratio-based saturation
   - Specialized: Add expectations, use saturation function
   - Emergency: Consider ratio-based (hospitals with ER / total hospitals)
   - Pharmacies: Use `_sat_ratio_v2` instead of linear ratio
2. Align scoring philosophy across all components
   - All components should use: expectations → ratio → saturation function
   - Consistent curve shapes (exponential saturation)
   - Consistent max scores and breakpoints
3. Document scoring rationale for each component
   - Why each component uses its current scoring
   - How scores map to real-world quality perception
   - Calibration methodology (once implemented)

---

## Priority Action Items

### High Priority

1. **Research Expected Values** - Run research script, collect data, update baselines
   - Add healthcare data collection to `scripts/research_expected_values.py`
   - Collect 10+ samples per area type
   - Calculate medians and percentiles
   - Update `data_sources/regional_baselines.py` with research-backed values

2. **Calibrate Scoring** - Create calibration panel, build calibration script, replace hard thresholds
   - Create calibration panel (16+ locations)
   - Build `scripts/calibrate_healthcare_scoring.py`
   - Replace hard thresholds with smooth saturation functions
   - Document calibration methodology

3. **Standardize Scoring** - Use saturation functions for all components
   - Convert all components to use `_sat_ratio_v2` pattern
   - Align scoring philosophy across all components
   - Document scoring rationale

### Medium Priority

4. **Add Context Detection** - Medical centers, rural health access patterns
   - Detect proximity to major medical centers
   - Identify rural health deserts
   - Add contextual bonuses if correlations support them

5. **Performance Optimization** - Parallel API calls
   - Add parallel fetching if multiple queries needed
   - Cache reusable data
   - Measure performance improvements

6. **Expand Fallback Database** - Verify coverage, add missing hospitals
   - Add regional hospitals to MAJOR_HOSPITALS
   - Expand MAJOR_URGENT_CARE_CHAINS
   - Or verify OSM coverage is sufficient

### Low Priority

7. **Enhanced Logging** - Structured logging for debugging
   - Replace `print()` with structured JSON logging
   - Log API responses, query parameters, data quality metrics
   - Include context: lat, lon, area_type, pillar_name

8. **Documentation** - Complete methodology document
   - Document research methodology
   - Document calibration results
   - Document scoring rationale for each component

---

## Files to Review/Modify

1. `pillars/healthcare_access.py` - Main scoring logic
   - Replace hard thresholds with smooth curves
   - Standardize all components to use saturation functions
   - Add structured logging

2. `data_sources/regional_baselines.py` - Expected values
   - Add research-backed expected values with documentation
   - Include sample sizes and medians/percentiles

3. `data_sources/radius_profiles.py` - Radius configuration
   - Already uses area-type-specific radii (good)
   - No changes needed

4. `data_sources/osm_api.py` - OSM query logic
   - Already has comprehensive healthcare query (good)
   - Consider parallelization if multiple queries needed

5. `scripts/research_expected_values.py` - Research data collection
   - Add healthcare metrics collection
   - Add healthcare to pillar list

6. `scripts/calibrate_healthcare_scoring.py` - [NEW] Calibration script
   - Create new script following transit calibration pattern
   - Fit smooth curves to target scores

7. `analysis/HEALTHCARE_ACCESS_METHODOLOGY.md` - [THIS FILE] Methodology document
   - Document research methodology
   - Document calibration results
   - Document scoring rationale

---

## Key Questions to Answer

1. **Are expected values research-backed or target-tuned?**
   - **Answer:** Target-tuned. Values are hardcoded integers (2, 1, 0) without research justification. No empirical data collection has been conducted.

2. **Are scoring curves calibrated or arbitrary?**
   - **Answer:** Arbitrary. Hard thresholds (5km=35pts, 10km=30pts) appear to be chosen without calibration. No calibration panel or target scores exist.

3. **Do all components use consistent scoring methodology?**
   - **Answer:** No. Hospital uses distance thresholds, primary care uses binary+density, specialized uses count-based, emergency is binary, pharmacies use ratio-based. Inconsistent approaches.

4. **Is there context-aware logic for special cases?**
   - **Answer:** Limited. Uses area_type for expectations and radii, but no special context detection (medical centers, rural health deserts). Fallback database exists but may be incomplete.

5. **Is performance optimized (parallel calls)?**
   - **Answer:** No. Single OSM query is sequential. No parallelization or caching implemented.

6. **Is fallback mechanism comprehensive?**
   - **Answer:** Partial. MAJOR_HOSPITALS database has 127 hospitals (major medical centers) but missing regional/community hospitals. Urgent care fallback is minimal and unused.

---

## Alignment with Public Transit Methodology

### ✅ What Healthcare Does Well

1. **Area-type-specific radii** - Uses `radius_profiles.py` for context-aware search radii
2. **Area-type-specific expectations** - Uses `get_contextual_expectations()` for context-aware scoring
3. **Fallback mechanism** - Has MAJOR_HOSPITALS database as fallback when OSM fails
4. **Data quality assessment** - Uses `data_quality.assess_pillar_data_quality()` for confidence scoring

### ❌ What Healthcare Needs to Improve

1. **Research-backed expected values** - Transit has medians from 10+ samples per area type; healthcare has hardcoded integers
2. **Calibrated scoring curves** - Transit has calibrated breakpoints (1×=60, 2×=80, 3×=90); healthcare has arbitrary thresholds
3. **Smooth functions** - Transit uses smooth piecewise linear; healthcare uses hard thresholds
4. **Consistent scoring methodology** - Transit uses consistent normalization; healthcare uses mixed approaches
5. **Structured logging** - Transit uses structured JSON logging; healthcare uses `print()` statements
6. **Performance optimization** - Transit uses parallel calls and caching; healthcare is sequential

### 📋 Recommended Next Steps

1. **Phase 1: Research** (High Priority)
   - Add healthcare data collection to research script
   - Collect 10+ samples per area type
   - Calculate medians and percentiles
   - Update expected values in `regional_baselines.py`

2. **Phase 2: Calibration** (High Priority)
   - Create calibration panel (16+ locations)
   - Build calibration script
   - Replace hard thresholds with smooth curves
   - Standardize all components to use saturation functions

3. **Phase 3: Context & Performance** (Medium Priority)
   - Add context detection (medical centers, rural health deserts)
   - Optimize performance (parallel calls, caching)
   - Expand fallback database
   - Add structured logging

4. **Phase 4: Documentation** (Low Priority)
   - Complete methodology document
   - Document research methodology
   - Document calibration results

---

## References

- **Public Transit Methodology:** `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md`
- **Design Principles:** `DESIGN_PRINCIPLES.md`
- **Active Outdoors Saturation Function:** `pillars/active_outdoors.py` line 533 (`_sat_ratio_v2`)
- **Transit Calibration Script:** `scripts/calibrate_transit_scoring.py`
- **Research Script:** `scripts/research_expected_values.py`

---

**End of Audit Document**

