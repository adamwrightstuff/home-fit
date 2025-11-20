# Research-Backed Expected Values - Final Results

**Date:** November 20, 2025  
**Data Source:** OSM queries from real-world locations  
**Sample Sizes:** Urban Core (10), Suburban (4), Exurban (2), Rural (0)  
**Note:** Failed queries (0 parks AND 0 businesses) excluded from analysis

---

## Summary: Current vs Research-Backed Values

### Active Outdoors Pillar

| Area Type | Metric | Current Expected | Research Median | Difference | Recommendation |
|-----------|--------|-----------------|-----------------|------------|----------------|
| **urban_core** | Parks (1km) | 3 | **8.5** | +183% | ✅ Update to 8.5 |
| **urban_core** | Park Area (ha) | 3 | **2.79** | -7% | ✅ Keep at 3 (close match) |
| **urban_core** | Trails (15km) | 2 | **69.5** | +3375% | ✅ Update to 70 |
| **suburban** | Parks (1km) | 2 | **6.0** | +200% | ⚠️ Update to 6 (low sample: n=4) |
| **suburban** | Park Area (ha) | 5 | **20.98** | +320% | ⚠️ Update to 21 (low sample: n=4) |
| **suburban** | Trails (15km) | 1 | **5.5** | +450% | ⚠️ Update to 6 (low sample: n=4) |
| **exurban** | Parks (1km) | 1 | **7.5** | +650% | ❌ Need more samples (n=2) |
| **exurban** | Trails (15km) | 1 | **9.0** | +800% | ❌ Need more samples (n=2) |

### Neighborhood Amenities Pillar

| Area Type | Metric | Current Expected | Research Median | Difference | Recommendation |
|-----------|--------|-----------------|-----------------|------------|----------------|
| **urban_core** | Businesses (1km) | 50 | **188.5** | +277% | ✅ Update to 189 |
| **urban_core** | Restaurants (1km) | 15 | **109.5** | +630% | ✅ Update to 110 |
| **urban_core** | Business Types | 12 | **12** | 0% | ✅ Keep at 12 (perfect match) |
| **suburban** | Businesses (1km) | 25 | **55.0** | +120% | ⚠️ Update to 55 (low sample: n=4) |
| **suburban** | Restaurants (1km) | 8 | **20.5** | +156% | ⚠️ Update to 21 (low sample: n=4) |
| **suburban** | Business Types | 8 | **11.5** | +44% | ⚠️ Update to 12 (low sample: n=4) |
| **exurban** | Businesses (1km) | 10 | **67.0** | +570% | ❌ Need more samples (n=2) |
| **exurban** | Restaurants (1km) | 3 | **24.5** | +717% | ❌ Need more samples (n=2) |

---

## Recommended Updates (High Confidence)

### Urban Core (n=10) ✅

```python
'urban_core': {
    'active_outdoors': {
        'expected_parks_within_1km': 8.5,  # was 3
        'expected_park_area_hectares': 3,   # keep (2.79 is close)
        'expected_trails_within_15km': 70,  # was 2
    },
    'neighborhood_amenities': {
        'expected_businesses_within_1km': 189,  # was 50
        'expected_restaurants_within_1km': 110, # was 15
        'expected_business_types': 12,          # keep (perfect match)
    }
}
```

### Suburban (n=4) ⚠️ Medium Confidence

```python
'suburban': {
    'active_outdoors': {
        'expected_parks_within_1km': 6,    # was 2
        'expected_park_area_hectares': 21,  # was 5
        'expected_trails_within_15km': 6,   # was 1
    },
    'neighborhood_amenities': {
        'expected_businesses_within_1km': 55,  # was 25
        'expected_restaurants_within_1km': 21, # was 8
        'expected_business_types': 12,         # was 8
    }
}
```

**Note:** Suburban has only 4 samples - consider collecting more for higher confidence.

---

## Pending (Need More Samples)

### Exurban (n=2) ❌
- Need 8+ more samples (target: 10)
- Current medians show 7.5 parks, 67 businesses (much higher than current expected values)
- **Do not update yet** - sample size too small

### Rural (n=0) ❌
- No successful samples collected
- Need 10+ samples
- **Do not update yet** - no data

---

## Key Findings

1. **Current values are significantly too low** across all area types
   - Parks: 2-7x higher than current
   - Businesses: 2-6x higher than current
   - Trails: 5-70x higher than current

2. **Urban Core has sufficient data** (n=10) for confident updates

3. **Suburban needs more samples** (n=4) but patterns are clear

4. **Exurban/Rural need significant expansion** before updating

---

## Next Steps

1. ✅ **Update Urban Core values** - High confidence (n=10)
2. ⚠️ **Update Suburban values** - Medium confidence (n=4), consider collecting more samples
3. ❌ **Collect more Exurban samples** - Need 8+ more (target: 10)
4. ❌ **Collect more Rural samples** - Need 10+ samples
5. 📝 **Cross-reference with external research** (TPL ParkScore, NRPA, etc.)
6. 📝 **Document all sources and methodology**

---

## Data Quality Notes

- **Failed queries filtered:** 3 locations with 0 parks AND 0 businesses excluded
- **Confidence levels:**
  - High: Urban Core (n=10)
  - Medium: Suburban (n=4)
  - Low: Exurban (n=2), Rural (n=0)
- **Variance:** Some metrics show high variance (P25=0 for some), indicating data quality issues for some locations

