# Transit Data Discrepancy Investigation

## Issue
Koreatown Los Angeles CA transit data changed dramatically between Round 5 and Round 6:

**Round 5:**
- Area type: `urban_residential`
- Light rail routes: 15
- Bus routes: 27
- Transit score: 68

**Round 6:**
- Area type: `urban_core` (changed - correct classification)
- Light rail routes: 0
- Bus routes: 16
- Transit score: 36.8

## Root Causes Identified

### 1. Area Type Classification Change ✅ (Expected)
- **Round 5**: Classified as `urban_residential` (possibly via `TARGET_AREA_TYPES` override)
- **Round 6**: Correctly classified as `urban_core` after removing hardcoded overrides
- **Impact**: Different expected values used for scoring
- **Status**: This is correct - Koreatown should be `urban_core`

### 2. Transit Data Discrepancy ❌ (Needs Investigation)
- **Light rail**: 15 routes → 0 routes (100% drop)
- **Bus**: 27 routes → 16 routes (41% drop)
- **Possible causes**:
  1. **No route deduplication**: `_get_nearby_routes()` doesn't deduplicate routes by `onestop_id` or `route_id`
  2. **Transitland API data changes**: API might return different data between calls
  3. **Route type misclassification**: Routes might be classified differently (e.g., light rail vs bus)
  4. **Caching issues**: Different cached data between rounds
  5. **Radius differences**: Different search radius (unlikely - both use 1500m)

## Code Analysis

### `_get_nearby_routes()` Function
- Location: `pillars/public_transit_access.py:588-682`
- Issues:
  1. **No deduplication**: Routes are not deduplicated by `onestop_id` or `route_id`
  2. **No filtering by distance**: All routes within radius are included, even if far away
  3. **Route type filtering**: Only filters out routes with `route_type = None`

### Route Categorization
- Location: `pillars/public_transit_access.py:285-294`
- GTFS route types:
  - `0` = Tram/Light Rail
  - `1` = Subway/Metro
  - `2` = Rail (Commuter)
  - `3` = Bus
- **Issue**: If Transitland API misclassifies routes or returns inconsistent `route_type` values, counts will vary

## Recommendations

### Immediate Fixes
1. **Add route deduplication** in `_get_nearby_routes()`:
   ```python
   # Deduplicate by onestop_id or route_id
   seen_ids = set()
   unique_routes = []
   for route in processed_routes:
       route_id = route.get("route_id") or route.get("onestop_id")
       if route_id and route_id not in seen_ids:
           seen_ids.add(route_id)
           unique_routes.append(route)
   ```

2. **Add logging** to track route counts and types:
   ```python
   print(f"   📊 Route breakdown: {len(heavy_rail_routes)} heavy, {len(light_rail_routes)} light, {len(bus_routes)} bus")
   ```

3. **Add distance filtering** (optional):
   - Filter routes beyond a reasonable distance (e.g., 2km)
   - Or use distance-weighted scoring

### Long-term Improvements
1. **Cache Transitland API responses** to ensure consistency
2. **Add route validation** to detect misclassified routes
3. **Add monitoring** to track route count changes over time
4. **Consider alternative data sources** for route verification (OSM, GTFS feeds)

## Next Steps
1. Add route deduplication to `_get_nearby_routes()`
2. Test with Koreatown location to verify route counts are stable
3. Compare Round 5 vs Round 6 API responses (if available)
4. Add logging to track route type distribution

