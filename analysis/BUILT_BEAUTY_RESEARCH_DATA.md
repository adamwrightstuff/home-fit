# Built Beauty Research Data Collection

**Date:** January 13, 2025 (Updated)  
**Data Source:** Direct computation from `compute_arch_diversity` and `calculate_built_beauty`  
**Sample Sizes:** Urban Core (14 ✅), Urban Residential (7 ⚠️), Suburban (19 ✅), Exurban (5 ⚠️), Rural (15 ✅)  
**Total Locations:** 60  
**Note:** Urban Residential and Exurban still need more samples (target: 10+ per area type)

---

## Summary: Research Findings vs Current CONTEXT_TARGETS

### Urban Core (n=14) ✅ Adequate Sample

| Metric | Research Median | Current Target Plateau | Difference | Recommendation |
|--------|----------------|----------------------|------------|----------------|
| **Height Diversity** | 26.6 | 40-70 | -13.4 | ⚠️ Research shows lower values than target |
| **Type Diversity** | 27.5 | 60-85 | -32.5 | ⚠️ Research shows much lower values than target |
| **Footprint Variation** | 88.8 | 40-60 | +28.8 | ⚠️ Research shows much higher values than target |
| **Built Coverage** | 0.275 | N/A | N/A | Baseline data |

**Key Findings:**
- Height diversity (26.6) is **below** target plateau (40-70) - suggests targets may be too high
- Type diversity (27.5) is **well below** target plateau (60-85) - significant discrepancy
- Footprint variation (88.8) is **much higher** than target (40-60) - suggests targets are too restrictive
- Sample size is now adequate (n=14) - can make confident recommendations

### Suburban (n=19) ✅ Adequate Sample

| Metric | Research Median | Current Target Plateau | Difference | Recommendation |
|--------|----------------|----------------------|------------|----------------|
| **Height Diversity** | 11.6 | 10-40 | +1.6 | ✅ Close match (within target range) |
| **Type Diversity** | 31.2 | 35-55 | -3.8 | ✅ Close match (just below target) |
| **Footprint Variation** | 80.1 | 40-65 | +15.1 | ⚠️ Research shows higher values than target |
| **Built Coverage** | 0.143 | N/A | N/A | Baseline data |

**Key Findings:**
- Height diversity (11.6) aligns well with target (10-40) ✅
- Type diversity (31.2) is close to target (35-55), just slightly below ✅
- Footprint variation (80.1) is **higher** than target (40-65) - suggests target may be too restrictive
- Sample size is now excellent (n=19) - high confidence in findings

### Exurban (n=5) ⚠️ Small Sample

| Metric | Research Median | Current Target Plateau | Difference | Recommendation |
|--------|----------------|----------------------|------------|----------------|
| **Height Diversity** | 0.6 | 5-35 | -4.4 | ⚠️ Research shows lower values, but need more samples |
| **Type Diversity** | 14.8 | 10-40 | +4.8 | ✅ Within target range |
| **Footprint Variation** | 34.3 | 65-95 | -30.7 | ⚠️ Research shows much lower values than target |
| **Built Coverage** | 0.099 | N/A | N/A | Baseline data |

**Key Findings:**
- Height diversity (0.6) is below target (5-35) - but sample size is small
- Type diversity (14.8) is within target range (10-40) ✅
- Footprint variation (34.3) is **much lower** than target (65-95) - significant discrepancy
- Sample size is still small (n=5) - need 5+ more samples for confidence

### Urban Residential (n=7) ⚠️ Small Sample

| Metric | Research Median | Current Target Plateau | Difference | Recommendation |
|--------|----------------|----------------------|------------|----------------|
| **Height Diversity** | 2.0 | 0-15 | +2.0 | ✅ Within target range (but many zeros suggest data issues) |
| **Type Diversity** | 15.7 | 0-20 | -4.3 | ✅ Within target range |
| **Footprint Variation** | 64.4 | 40-70 | -5.6 | ✅ Close to target range |
| **Built Coverage** | 0.207 | N/A | N/A | Baseline data |

**Key Findings:**
- Height diversity (2.0) is within target (0-15), but many zeros suggest missing OSM height data
- Type diversity (15.7) is within target range (0-20) ✅
- Footprint variation (64.4) is close to target (40-70) ✅
- Sample size is still small (n=7) - need 3+ more samples for confidence
- **Data quality concern:** Many locations show zeros, suggesting OSM data gaps

### Rural (n=15) ✅ Adequate Sample

| Metric | Research Median | Current Target Plateau | Difference | Recommendation |
|--------|----------------|----------------------|------------|----------------|
| **Height Diversity** | 0.8 | 5-30 | -4.2 | ⚠️ Research shows lower values than target |
| **Type Diversity** | 13.6 | 10-35 | +3.6 | ✅ Within target range |
| **Footprint Variation** | 39.9 | 70-100 | -30.1 | ⚠️ Research shows much lower values than target |
| **Built Coverage** | 0.034 | N/A | N/A | Baseline data |

**Key Findings:**
- Height diversity (0.8) is below target (5-30) - but many zeros suggest missing OSM data
- Type diversity (13.6) is within target range (10-35) ✅
- Footprint variation (39.9) is **much lower** than target (70-100) - significant discrepancy
- Sample size is now adequate (n=15) - can make recommendations
- **Data quality concern:** Many locations show zeros, suggesting OSM data gaps

---

## Detailed Statistics

### Urban Core (n=14)

```
Height Diversity:   median=26.6  (p25=11.7,  p75=56.6,  min=6.7,   max=76.8)
Type Diversity:     median=27.5  (p25=15.2,  p75=37.5,  min=11.7,  max=63.6)
Footprint Variation: median=88.8  (p25=71.7,  p75=94.2,  min=57.3,  max=96.0)
Built Coverage:     median=0.275 (p25=0.249, p75=0.316, min=0.229, max=0.379)
```

### Suburban (n=19)

```
Height Diversity:   median=11.6  (p25=7.2,   p75=18.5,  min=0.2,   max=60.9)
Type Diversity:     median=31.2  (p25=13.2,  p75=39.2,  min=3.1,   max=64.5)
Footprint Variation: median=80.1  (p25=69.9,  p75=95.6,  min=44.1,  max=100.0)
Built Coverage:     median=0.143 (p25=0.129, p75=0.191, min=0.054, max=0.267)
```

### Urban Residential (n=7)

```
Height Diversity:   median=2.0   (p25=0.0,   p75=23.5,  min=0.0,   max=28.5)
Type Diversity:     median=15.7  (p25=0.0,   p75=29.4,  min=0.0,   max=33.8)
Footprint Variation: median=64.4  (p25=0.0,   p75=71.4,  min=0.0,   max=73.3)
Built Coverage:     median=0.207 (p25=0.000, p75=0.227, min=0.000, max=0.418)
```

### Exurban (n=5)

```
Height Diversity:   median=0.6   (p25=0.25,  p75=15.75, min=0.0,   max=25.0)
Type Diversity:     median=14.8  (p25=1.75,  p75=28.35, min=0.0,   max=41.4)
Footprint Variation: median=34.3  (p25=13.95, p75=72.25, min=0.0,   max=75.9)
Built Coverage:     median=0.099 (p25=0.017, p75=0.145, min=0.000, max=0.162)
```

### Rural (n=15)

```
Height Diversity:   median=0.8   (p25=0.0,   p75=3.2,   min=0.0,   max=15.2)
Type Diversity:     median=13.6  (p25=0.0,   p75=30.7,  min=0.0,   max=48.6)
Footprint Variation: median=39.9  (p25=24.4,  p75=53.5,  min=0.0,   max=72.7)
Built Coverage:     median=0.034 (p25=0.002, p75=0.059, min=0.000, max=0.089)
```

---

## Key Findings

1. **Urban Core targets are too high** for height/type diversity ✅ **CONFIDENT** (n=14)
   - Research median height diversity (26.6) is below target plateau (40-70)
   - Research median type diversity (27.5) is well below target plateau (60-85)
   - **Recommendation:** Lower Urban Core targets to align with research data

2. **Suburban targets align well** for height/type diversity ✅ **CONFIDENT** (n=19)
   - Height diversity median (11.6) is within target (10-40) ✅
   - Type diversity median (31.2) is close to target (35-55) ✅
   - **Recommendation:** Keep Suburban targets as-is for height/type

3. **Footprint variation is consistently higher** than targets across area types ⚠️
   - Urban Core: median 88.8 vs target 40-60 (+28.8)
   - Suburban: median 80.1 vs target 40-65 (+15.1)
   - Rural: median 39.9 vs target 70-100 (-30.1) - **opposite pattern**
   - Exurban: median 34.3 vs target 65-95 (-30.7) - **opposite pattern**
   - **Recommendation:** Investigate footprint variation targets - may need area-specific adjustments

4. **Rural targets show discrepancies** ⚠️ **CONFIDENT** (n=15)
   - Height diversity (0.8) is below target (5-30) - but many zeros suggest data quality issues
   - Type diversity (13.6) is within target (10-35) ✅
   - Footprint variation (39.9) is **much lower** than target (70-100) - significant discrepancy

5. **Sample sizes status:**
   - Urban Core: n=14 ✅ (adequate)
   - Suburban: n=19 ✅ (excellent)
   - Rural: n=15 ✅ (adequate)
   - Urban Residential: n=7 ⚠️ (need 3+ more)
   - Exurban: n=5 ⚠️ (need 5+ more)

---

## Recommended Next Steps

### 1. Update Urban Core Targets ✅ **READY** (n=14)

**Current vs Research:**
- Height Diversity: Target 40-70, Research 26.6 → **Lower target to ~20-50**
- Type Diversity: Target 60-85, Research 27.5 → **Lower target to ~25-50**
- Footprint Variation: Target 40-60, Research 88.8 → **Raise target to ~70-95**

**Action:** Update `CONTEXT_TARGETS["urban_core"]` in `data_sources/arch_diversity.py`

### 2. Investigate Footprint Variation Pattern ⚠️ **CRITICAL**

**Inconsistent Pattern:**
- Urban Core & Suburban: Research values **higher** than targets
- Rural & Exurban: Research values **lower** than targets

**Questions:**
- Is footprint variation calculated differently for different area types?
- Are the targets incorrectly calibrated?
- Should footprint variation targets be area-type specific?

**Action:** Review scoring logic and consider separate footprint targets by area type

### 3. Update Rural Targets ✅ **READY** (n=15)

**Current vs Research:**
- Height Diversity: Target 5-30, Research 0.8 → **Lower target to ~0-15** (but data quality concern)
- Type Diversity: Target 10-35, Research 13.6 → **Keep as-is** ✅
- Footprint Variation: Target 70-100, Research 39.9 → **Lower target to ~30-60**

**Action:** Update `CONTEXT_TARGETS["rural"]` in `data_sources/arch_diversity.py`

### 4. Collect More Data for Remaining Area Types ⚠️

**Still Needed:**
- Urban Residential: n=7 (need 3+ more for n≥10)
- Exurban: n=5 (need 5+ more for n≥10)

**Priority:** Medium - can proceed with updates for Urban Core and Rural now

### 5. Address Data Quality Issues ⚠️

**Problem:** Many locations show zeros for height/type diversity
- This suggests missing OSM height data (building:levels tags)
- Material inference is working (from previous work)
- Need to investigate why height data is missing for many locations

**Action:** Consider height inference similar to material inference for better coverage

---

## Data Files

- **Raw Data**: `analysis/research_data/built_beauty_raw_data.json`
- **Statistics**: `analysis/research_data/built_beauty_statistics.json`
- **Collection Script**: `scripts/collect_built_beauty_research_data.py`

---

## Methodology

1. Collected architectural diversity metrics directly from `compute_arch_diversity()`
2. Collected form metrics from `calculate_built_beauty()` 
3. Grouped by actual area type (from `classify_morphology()`)
4. Calculated medians, percentiles (p25, p75), min, max
5. Compared to current `CONTEXT_TARGETS` values in code

**Radius:** 2000m (standard radius for built beauty scoring)

**Locations:** 60 diverse neighborhoods across different area types and regions

**Collection Date:** January 13, 2025
- Initial collection: 27 locations
- Expanded collection: 33 additional locations (total: 60)
