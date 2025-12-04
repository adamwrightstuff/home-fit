# Old San Juan Data Quality Investigation

## Problem
Old San Juan PR is scoring 33/100 (target: 95) due to:
- **0 historic landmarks** from OSM
- **null median_year_built** from Census
- Classified as `suburban` instead of `historic_urban`
- Coverage: 20.9% (should qualify for spacious historic district, but detection fails)

## Current Query Logic

### Historic Landmarks Query
**Location:** `data_sources/osm_api.py`, `query_charm_features()`
- **Radius:** 1000m (1km) - should be sufficient
- **Query:** Only checks `historic` tag:
  ```overpass
  node["historic"](around:1000,lat,lon);
  way["historic"](around:1000,lat,lon);
  relation["historic"](around:1000,lat,lon);
  ```
- **Processing:** Only accepts elements with `historic` tag present

### Census Building Age Query
**Location:** `data_sources/census_api.py`, `get_year_built_data()`
- **Issue:** Returns `null` for Old San Juan
- **Possible reasons:**
  - Puerto Rico Census data may be incomplete
  - Tract might not have building age data
  - API might not support PR

## Potential Issues

### 1. OSM Data Coverage in Puerto Rico
- OSM coverage in Puerto Rico may be sparse
- Buildings might not be tagged with `historic=yes` even though they're historic
- Alternative tags might exist: `heritage=yes`, `building:historic=yes`, `old_town=yes`

### 2. Query Limitations
- Only checks `historic` tag - might miss other historic indicators
- No fallback to building age from OSM (if available)
- No check for historic district boundaries

### 3. Census Data Availability
- Puerto Rico might have different Census data structure
- Building age data might not be available for PR tracts

## Recommended Solutions

### Option A: Expand OSM Historic Query (Low Risk)
Add alternative OSM tags to catch more historic buildings:
- `heritage=yes`
- `building:historic=yes`
- `old_town=yes`
- `tourism=yes` with `historic=yes` in name/tags

**Implementation:**
```python
# In query_charm_features()
query = f"""
[out:json][timeout:25];
(
  // HISTORIC BUILDINGS - expanded query
  node["historic"](around:{radius_m},{lat},{lon});
  way["historic"](around:{radius_m},{lat},{lon});
  relation["historic"](around:{radius_m},{lat},{lon});
  
  // Alternative historic tags
  node["heritage"](around:{radius_m},{lat},{lon});
  way["heritage"](around:{radius_m},{lat},{lon});
  node["building:historic"="yes"](around:{radius_m},{lat},{lon});
  way["building:historic"="yes"](around:{radius_m},{lat},{lon});
);
```

### Option B: Use Building Age from OSM (Medium Risk)
If OSM has building age data (`start_date`, `year_built`, etc.), use it as fallback:
- Query buildings with `start_date < 1950` or `year_built < 1950`
- Count these as historic landmarks if no explicit `historic` tags found

**Implementation:**
```python
# Additional query for old buildings
node["building"]["start_date"](around:{radius_m},{lat},{lon});
way["building"]["start_date"](around:{radius_m},{lat},{lon});
# Filter: start_date < 1950
```

### Option C: Increase Query Radius (Low Risk)
For known historic areas, increase radius from 1000m to 2000m:
- Old San Juan is compact, but might have landmarks just outside 1km
- Low risk of false positives

### Option D: Accept Low Coverage + Uniform Materials (Current Implementation)
Already implemented in `_is_spacious_historic_district()`:
- For coverage < 21%, accept if uniform materials (entropy < 20) or low footprint CV (< 40)
- **Issue:** Old San Juan has high footprint CV (97.0), so this doesn't help

## Recommended Approach

**Start with Option A (Expand OSM Query)** - lowest risk, addresses data quality issue:
1. Add alternative historic tags to query
2. Test on Old San Juan to see if more landmarks are found
3. If still 0 landmarks, proceed to Option B or C

**Then Option C (Increase Radius)** if Option A doesn't help:
- Increase radius to 2000m for historic landmark queries
- Low risk, might catch landmarks just outside current radius

**Option B (OSM Building Age)** as last resort:
- More complex, requires parsing date strings
- Risk of false positives (old buildings ≠ historic landmarks)

## Testing Plan

1. **Manual OSM Check:**
   - Use Overpass Turbo to query Old San Juan manually
   - Check what historic tags exist in the area
   - Verify if buildings are tagged differently

2. **Test Expanded Query:**
   - Implement Option A
   - Test on Old San Juan
   - Compare landmark count before/after

3. **Test Increased Radius:**
   - If Option A doesn't help, test with 2000m radius
   - Check if more landmarks are found

4. **Validate Results:**
   - Ensure expanded query doesn't create false positives
   - Test on other locations to ensure no regressions

