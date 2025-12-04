# Scoring Analysis: Rate Limiting and 0 Scores

## Executive Summary

The 0 scores you're seeing are primarily caused by **API rate limiting and timeouts**, which cause critical data sources to return `None`. When APIs fail, the scoring logic correctly returns 0, but this masks the distinction between "no amenities available" vs "API unavailable."

## Root Cause: API Failures → 0 Scores

### 1. Neighborhood Amenities Pillar

**Failure Point:** `query_local_businesses()` returns `None` when:
- OSM Overpass API rate limits (429)
- Request timeouts (>70s)
- Network errors

**Code Path:**
```python
# pillars/neighborhood_amenities.py:38-42
business_data = osm_api.query_local_businesses(lat, lon, radius_m=query_radius, include_chains=include_chains)

if business_data is None:
    print("⚠️  OSM business data unavailable")
    return 0, _empty_breakdown()  # ← Returns 0 immediately
```

**Impact:** When OSM fails, the entire pillar returns 0/100, even if the location might have excellent amenities that just couldn't be queried.

### 2. Healthcare Access Pillar

**Failure Point:** `query_healthcare_facilities()` returns empty dict with `_query_failed: True` flag when:
- OSM Overpass API rate limits
- Request timeouts (>45s)
- Network errors

**Code Path:**
```python
# data_sources/osm_api.py:1797-1817
resp = _retry_overpass(_do_request, query_type="healthcare")

if resp is None or resp.status_code != 200:
    # Returns empty dict with _query_failed flag
    return {
        "hospitals": [],
        "urgent_care": [],
        ...
        "_query_failed": True
    }
```

**Impact:** Healthcare pillar continues scoring but with 0 facilities, resulting in very low scores. The `_query_failed` flag is used to adjust confidence but doesn't prevent 0 scores.

### 3. Public Transit Access Pillar

**Failure Point:** Transitland API timeouts/errors return empty routes list

**Code Path:**
```python
# pillars/public_transit_access.py:535-540
if response is None:
    return []  # Empty routes list

if response.status_code != 200:
    print(f"   ⚠️  Transitland API returned status {response.status_code}")
    return []
```

**Impact:** With no routes, transit scoring returns 0/100.

## Scoring Logic Analysis (When Data IS Available)

### Neighborhood Amenities Scoring Breakdown

The amenities pillar uses a **dual scoring system** (0-100):

#### Home Walkability (0-60 points)
1. **Density Score (0-25 pts)**: Context-aware thresholds
   - Urban core: 60+ businesses = 25 pts, 36+ = 20 pts, 18+ = 12 pts
   - Suburban: 50+ = 25 pts, 30+ = 20 pts, 15+ = 12 pts
   - Exurban/Rural: 35+ = 25 pts, 21+ = 20 pts, 11+ = 12 pts

2. **Variety Score (0-20 pts)**: Business type diversity
   - Tier 1 (Daily Essentials): 3+ types = 8 pts, 2 types = 5.3 pts, 1 type = 2.6 pts
   - Tier 2 (Social/Dining): 2+ types = 6.6 pts, 1 type = 4 pts
   - Tier 3 (Culture): 2+ types = 3.4 pts, 1 type = 2 pts
   - Tier 4 (Services): 2+ types = 2 pts, 1 type = 0.7 pts

3. **Proximity Score (0-15 pts)**: Median distance to businesses
   - ≤200m: 15 pts (optimal)
   - ≤400m: 13 pts (good)
   - ≤600m: 11 pts
   - ≤800m: 10 pts (adequate)
   - ≤1000m: 7 pts
   - >1000m: 2.5 pts

#### Location Quality (0-40 points)
1. **Proximity to Town Center (0-20 pts)**: Distance to business cluster centroid
   - ≤400m: 20 pts
   - ≤800m: 15 pts
   - ≤1200m: 10 pts
   - ≤1600m: 5 pts
   - >1600m: 0 pts

2. **Town Center Vibrancy (0-20 pts)**: Cluster quality within 500m of center
   - **Variety (0-20 pts)**: Business type diversity in cluster
     - Daily essentials: 3+ types = 6 pts, 2 = 4 pts, 1 = 2 pts
     - Social/Dining: 2+ types = 6 pts, 1 = 4 pts
     - Culture: 2+ types = 5 pts, 1 = 3 pts
     - Services: 2+ types = 3 pts, 1 = 1 pt
   - **Density Bonus (0-8 pts)**: Context-aware
     - Urban: 50+ businesses = 8 pts (50/6.25)
     - Suburban: 40+ businesses = 8 pts (40/5.0)
     - Exurban/Rural: 30+ businesses = 8 pts (30/3.75)
   - **Cultural Bonus (0-2 pts)**: 5+ cultural venues = +2, 3-4 = +1

**Key Logic:**
- If businesses are too scattered (avg distance >1500m from home), returns 0.0
- If no businesses within 500m of cluster center, vibrancy = 0
- If distance to center >1600m, vibrancy = 0

### Recent Fix: Median Location Calculation

**Before:** Used separate median lat/lon (incorrect for cluster representation)
```python
median_lat = sorted([b["lat"] for b in all_businesses])[len(all_businesses) // 2]
median_lon = sorted([b["lon"] for b in all_businesses])[len(all_businesses) // 2]
```

**After:** Uses centroid (mean) for accurate cluster center
```python
median_lat = sum(b["lat"] for b in all_businesses) / len(all_businesses)
median_lon = sum(b["lon"] for b in all_businesses) / len(all_businesses)
```

This fix ensures the "town center" is calculated as the actual centroid of the business cluster, not a potentially misleading median point.

## Error Handling Patterns Across Pillars

### Pattern 1: Hard Fail (Returns 0 Immediately)
- **Neighborhood Amenities**: Returns 0 if `business_data is None`
- **Schools**: Returns 0 if no schools found

### Pattern 2: Graceful Degradation (Scores with Empty Data)
- **Healthcare**: Continues scoring with 0 facilities, adjusts confidence
- **Public Transit**: Scores with empty routes list (results in 0)

### Pattern 3: Partial Data Handling
- **Active Outdoors**: Can score with partial data (parks but no trails)
- **Housing Value**: Requires census data, returns 0 if unavailable

## Recommendations

### Short-Term (Rate Limiting Fixes)
1. **Increase Retry Attempts**: Current retry config may be too aggressive
   - OSM amenities uses "STANDARD" profile (check `retry_config.py`)
   - Consider upgrading to "CRITICAL" profile for amenities
   
2. **Add Exponential Backoff**: Already implemented, but verify timing
   - Current: Base wait 1.0s, max wait 10s (STANDARD)
   - Critical: Base wait 2.0s, max wait 30s

3. **Request Throttling**: Already implemented with `_query_lock` and adaptive intervals
   - Base interval: 0.5s
   - Adaptive: Increases to 3.0s on rate limit (6x multiplier)

### Medium-Term (Scoring Improvements)
1. **Distinguish API Failures from No Data**
   - Return partial score with low confidence when API fails
   - Use cached data if available
   - Add `data_quality.warning: "api_unavailable"` flag

2. **Better Error Reporting**
   - Include API failure reason in breakdown
   - Distinguish between "no amenities" vs "API unavailable"
   - Add retry-after information to logs

### Long-Term (Architecture Improvements)
1. **Caching Strategy**
   - Cache successful API responses longer
   - Pre-populate cache for common locations
   - Use stale cache with confidence adjustment when fresh data unavailable

2. **Circuit Breaker Pattern**
   - Stop making requests to failing APIs temporarily
   - Use cached data during circuit open state
   - Gradually resume requests after cooldown

3. **Data Quality Indicators**
   - Already implemented in some pillars (`data_quality.assess_pillar_data_quality`)
   - Extend to all pillars
   - Use quality metrics to adjust confidence scores

## Current Scoring Behavior Summary

| Pillar | API Failure Behavior | Score on Failure | Confidence Adjustment |
|--------|---------------------|------------------|----------------------|
| Neighborhood Amenities | Returns 0 immediately | 0/100 | No (returns empty breakdown) |
| Healthcare Access | Scores with 0 facilities | Very low (0-20/100) | Yes (sets to 10%) |
| Public Transit | Scores with empty routes | 0/100 | No |
| Active Outdoors | Partial scoring possible | Variable | Partial |
| Housing Value | Returns 0 if census fails | 0/100 | No |
| Schools | Returns 0 if no schools | 0/100 | No |

## Conclusion

The scoring logic itself is **sound and well-designed** with context-aware thresholds and proper dual scoring. The 0 scores are a **data availability issue**, not a scoring algorithm issue. Once rate limiting is resolved and APIs return data reliably, the scoring should work correctly.

The median location fix was important for accurate cluster detection, and the scoring thresholds are research-backed and context-aware. The main improvement needed is better handling of API failures to distinguish between "no amenities" and "API unavailable."

