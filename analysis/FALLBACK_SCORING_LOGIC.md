# Fallback Scoring Logic - Comprehensive Guide

## Overview

Fallback scoring is a mechanism to handle API/data gaps when external data sources (OSM, Census, Transitland) fail or return incomplete data. It prevents urban/suburban locations from incorrectly scoring 0 when data is unavailable due to API failures, timeouts, or data gaps (rather than genuinely having no amenities/services).

## Core Principles

1. **Only applies to urban/suburban/high-density areas** - Rural locations with truly no services should still score 0
2. **Conservative minimum floors** - Fallback scores are conservative estimates, not full scores
3. **Area-type aware** - Different fallback scores based on area type and density
4. **Distinguishes API failures from genuine lack of services** - Uses proxies (commute_time, density) to detect when services likely exist but data is unavailable

## Detection Logic

### When Fallback Applies

Fallback scoring applies when **ALL** of the following conditions are met:

1. **Primary data source fails or returns no data**:
   - OSM API returns `None` or empty results
   - Census API returns `None` or incomplete data
   - Transitland API returns no routes

2. **Location is urban/suburban/high-density**:
   ```python
   is_urban_suburban = (
       area_type in ("urban_core", "urban_residential", "suburban") or 
       (density and density > 1500)
   )
   ```

3. **Additional validation** (pillar-specific):
   - **Public Transit**: Also requires `commute_time < 60 min` (proxy for transit existence)
   - **Healthcare**: Checks if OSM query failed (`query_failed=True`)
   - **Housing Value**: Checks if Census returned `None` (incomplete data)

### When Fallback Does NOT Apply

- Rural locations (density ≤ 1500 and area_type not urban/suburban)
- When primary data source succeeds (even if sparse)
- When additional validation fails (e.g., commute_time unavailable or > 60 min)

## Fallback Score Tables

### 1. Neighborhood Amenities (`neighborhood_amenities.py`)

**Trigger**: OSM business query returns `None` or empty

| Area Type | Density Threshold | Fallback Score |
|-----------|------------------|----------------|
| Urban Core | > 5000 | 25.0 |
| Urban Residential | > 2000 | 20.0 |
| Suburban | > 1500 | 15.0-18.0 |

**Rationale**: Urban areas should have businesses; OSM gaps don't mean no amenities exist.

---

### 2. Healthcare Access (`healthcare_access.py`)

**Trigger**: OSM query fails (`query_failed=True`) AND no pharmacies/clinics/doctors found

| Component | Urban Core | Urban Residential | Suburban |
|-----------|-----------|------------------|----------|
| Primary Care | 15.0 | 12.0 | 10.0 |
| Pharmacies | 10.0 | 8.0 | 6.0 |
| Specialized Care* | 8.0 | 6.0 | 4.0 |

*Only applies if hospitals available from fallback database

**Total Fallback Range**: 33.0 - 45.0 points

**Rationale**: Urban areas should have healthcare facilities; OSM gaps don't mean no healthcare exists.

---

### 3. Public Transit Access (`public_transit_access.py`)

**Trigger**: Transitland API returns no routes AND OSM railway stations unavailable AND `commute_time < 60 min`

| Area Type | Density Threshold | Heavy Rail | Bus | Total* |
|-----------|------------------|------------|-----|--------|
| Urban Core | > 5000 | 15.0 | 12.0 | ~27.0 |
| Urban Residential | > 2000 | 10.0 | 10.0 | ~20.0 |
| Suburban | > 1500 | 5.0 | 8.0 | ~13.0 |

*Plus commute_time score weighted at 5% (COMMUTE_WEIGHT)

**Rationale**: Reasonable commute times suggest transit exists; Transitland gaps don't mean no transit.

---

### 4. Housing Value (`housing_value.py`)

**Trigger**: Census API returns `None` (incomplete housing data)

| Component | Urban Core | Urban Residential | Suburban |
|-----------|-----------|------------------|----------|
| Affordability | 15.0 | 20.0 | 25.0 |
| Space | 20.0 | 22.0 | 25.0 |
| Efficiency | 10.0 | 12.0 | 15.0 |

**Total Fallback Range**: 45.0 - 65.0 points

**Rationale**: Urban areas have housing; Census gaps don't mean no housing data exists. Scores reflect typical urban characteristics (expensive but moderate space/efficiency).

---

## Implementation Pattern

All fallback implementations follow this pattern:

```python
# 1. Check if primary data source failed
if primary_data is None or primary_data == []:
    
    # 2. Detect area type and density
    if density is None:
        density = census_api.get_population_density(lat, lon) or 0.0
    if area_type is None:
        area_type = data_quality.detect_area_type(lat, lon, density)
    
    # 3. Check if urban/suburban/high-density
    is_urban_suburban = (
        area_type in ("urban_core", "urban_residential", "suburban") or 
        (density and density > 1500)
    )
    
    # 4. Apply pillar-specific validation (if needed)
    if is_urban_suburban and [additional_validation]:
        
        # 5. Determine fallback scores based on area type/density
        if area_type in fallback_scores:
            fallback = fallback_scores[area_type]
        elif density > 5000:
            fallback = fallback_scores["urban_core"]
        elif density > 2000:
            fallback = fallback_scores["urban_residential"]
        elif density > 1500:
            fallback = fallback_scores["suburban"]
        
        # 6. Return fallback breakdown with flag
        return fallback_total, {
            "score": round(fallback_total, 1),
            "breakdown": {...},
            "summary": {
                "fallback_applied": True,
                "fallback_reason": "..."
            }
        }
    
    # 7. Return 0 for rural/genuinely no services
    return 0, _empty_breakdown()
```

## Density Thresholds

Consistent thresholds across all pillars:

- **Urban Core**: `density > 5000` people/km²
- **Urban Residential**: `density > 2000` people/km²  
- **Suburban**: `density > 1500` people/km²
- **Rural**: `density ≤ 1500` people/km² (no fallback)

## Key Design Decisions

### Why Density-Based Fallback?

- **Area type classification can misclassify** small cities as "rural" when they're actually suburban
- **Density is objective** - high density (> 1500) suggests urban/suburban characteristics
- **Consistent threshold** across all pillars ensures predictable behavior

### Why Conservative Scores?

- **Fallback is a safety net**, not a replacement for real data
- **Prevents over-scoring** when data is genuinely sparse
- **Maintains score integrity** - locations with real data still score higher

### Why Area-Type Specific Scores?

- **Urban cores** are typically more expensive (lower affordability) but have better amenities
- **Suburban areas** are typically more affordable with more space
- **Reflects real-world patterns** - fallback scores should match typical characteristics

## Examples

### Example 1: Neighborhood Amenities

**Location**: Coconut Grove Miami FL
- **Density**: 2500 (urban_residential)
- **OSM Query**: Returns `None` (API failure)
- **Fallback Applied**: Yes (density > 1500)
- **Score**: 20.0 (urban_residential fallback)
- **Before**: 0.0
- **After**: 20.0

### Example 2: Healthcare Access

**Location**: Pilsen Chicago IL
- **Density**: High (urban_residential)
- **OSM Query**: Failed (`query_failed=True`)
- **Fallback Applied**: Yes (urban_residential, OSM failed)
- **Score**: 50.1 (Primary Care: 15.0, Pharmacies: 10.0, Specialized: 8.0, Hospital: 14.5, Emergency: 2.1)
- **Before**: 17.1
- **After**: 50.1

### Example 3: Public Transit Access

**Location**: St Augustine FL
- **Density**: 2367 (classified as rural, but density > 1500)
- **Transitland**: No routes found
- **OSM**: Railway query failed (504)
- **Commute Time**: 20.3 min (< 60 min)
- **Fallback Applied**: Yes (density > 1500 AND commute_time reasonable)
- **Score**: 24.2 (Heavy Rail: 10.0, Bus: 10.0, Commute: 85.0 * 5% = 4.2)
- **Before**: 0.0
- **After**: 24.2

### Example 4: Housing Value

**Location**: Brickell Miami FL
- **Density**: 48219 (urban_residential)
- **Census API**: Returns `None` (incomplete data)
- **Fallback Applied**: Yes (density > 1500)
- **Score**: 54.0 (Affordability: 20.0, Space: 22.0, Efficiency: 12.0)
- **Before**: 0.0
- **After**: 54.0

## Benefits

1. **Reduces false zeros** - Urban locations no longer score 0 due to API failures
2. **Improves reliability** - System handles data gaps gracefully
3. **Maintains accuracy** - Rural locations with truly no services still score 0
4. **Consistent behavior** - Same thresholds and logic across all pillars
5. **Transparent** - `fallback_applied: true` flag indicates when fallback was used

## Limitations

1. **Conservative estimates** - Fallback scores are minimum floors, not full scores
2. **Area type dependency** - Relies on accurate area type classification (mitigated by density check)
3. **No real-time validation** - Can't verify if services actually exist when APIs fail
4. **Pillar-specific** - Each pillar has different fallback logic (by design, as needs differ)

## Future Improvements

1. **Expand fallback databases** - Add more comprehensive static databases (like MAJOR_HOSPITALS)
2. **Calibrate fallback scores** - Use historical data to refine fallback score amounts
3. **Multi-source validation** - Cross-reference multiple data sources before applying fallback
4. **Adaptive thresholds** - Adjust density thresholds based on regional patterns
