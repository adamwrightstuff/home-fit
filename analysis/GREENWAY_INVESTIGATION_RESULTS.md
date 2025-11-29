# Greenway Investigation Results

**Date:** 2024-12-XX  
**Investigation:** How are Hudson Greenway and East River Walkway captured?

---

## Key Findings

### 1. Parks ARE Captured ✅
- **Hudson River Park area**: Found 159 parks within 2km
- **East River Park area**: Found 224 parks within 2km
- **Largest parks found:**
  - Brooklyn Bridge Park: 24.5 ha
  - John V. Lindsay East River Park: 18.9 ha
  - Weehawken Waterfront Park: 7.7 ha

### 2. Greenways Are NOT Captured ❌

**Why greenways are missing:**
- **OSM Tagging**: Greenways are typically tagged as:
  - `highway=cycleway` (bike paths)
  - `highway=footway` (walking paths)
  - NOT `leisure=park` (unless they're within a park polygon)
  - NOT `relation[route=hiking]` (unless mis-tagged)

**What our queries capture:**
1. **Parks query** (`query_green_spaces`):
   - ✅ Captures: `leisure=park`, `landuse=park`
   - ❌ Does NOT capture: `highway=cycleway`, `highway=footway`

2. **Hiking trails query** (`query_nature_features`):
   - ✅ Captures: `relation[route=hiking]`
   - ❌ Does NOT capture: `highway=cycleway`, `highway=footway`

3. **Large park trails query** (`_query_trails_in_large_parks`):
   - ✅ Captures: `highway=path|footway|track` within large parks (>50 hectares)
   - ❌ Does NOT capture: `highway=cycleway`
   - ❌ Does NOT capture: Standalone greenways (not in parks)

**Result:**
- Hudson Greenway/East River Walkway are **NOT being captured** because:
  1. They're tagged as `highway=cycleway` or `highway=footway` (not parks)
  2. They're not in large parks (>50 ha) so the large park trails query doesn't find them
  3. They're not `relation[route=hiking]` (unless mis-tagged, which would be filtered anyway)

### 3. No Duplication Issue ✅

**For greenways:**
- Greenways are NOT captured at all → No duplication
- Parks are captured → Daily Urban Outdoors scores them
- Greenways within parks would be captured IF:
  - Park is >50 hectares (none found in test areas)
  - Greenway is tagged as `highway=footway` (not `cycleway`)

**For outdoor locations (e.g., Boulder, Denver):**
- Parks are captured → Daily Urban Outdoors
- Trails (including those in parks) are captured → Wild Adventure
- This is **intentional double-counting** (parks = local/daily, trails = regional/adventure)

---

## Implications

### Missing Features
1. **Hudson Greenway**: Not captured (likely `highway=cycleway`)
2. **East River Walkway**: Not captured (likely `highway=footway` or `cycleway`)
3. **Other urban greenways**: Not captured unless they're:
   - Within large parks (>50 ha) AND tagged as `highway=footway` (not `cycleway`)

### Current Behavior
- **Parks**: ✅ Captured (Daily Urban Outdoors)
- **Greenways**: ❌ NOT captured
- **Hiking trails**: ✅ Captured (Wild Adventure, but filtered in urban cores)

---

## Recommendations

### Option 1: Add Greenways to Parks Query (Recommended)
**Rationale:** Greenways are legitimate urban outdoor infrastructure, similar to parks
**Implementation:**
- Add `highway=cycleway` and `highway=footway` to parks query
- Treat them as "urban paths" category (separate from parks, but similar scoring)
- Score them in Daily Urban Outdoors component

**Pros:**
- Captures legitimate urban outdoor activity
- Aligns with Daily Urban Outdoors (local/daily use)
- Doesn't inflate Wild Adventure scores

**Cons:**
- May capture too many urban paths (need filtering)
- Need to distinguish between greenways and regular sidewalks

### Option 2: Create Separate "Urban Paths" Category
**Rationale:** Greenways are distinct from parks and hiking trails
**Implementation:**
- New query for `highway=cycleway|footway` with filtering (e.g., minimum length, not in residential areas)
- Score in Daily Urban Outdoors or new component

**Pros:**
- More precise categorization
- Better control over what's captured

**Cons:**
- More complex implementation
- Need to define filtering criteria

### Option 3: Lower Large Park Threshold
**Rationale:** Many urban parks with greenways are <50 hectares
**Implementation:**
- Reduce threshold from 50 ha to, say, 10 ha
- This would capture greenways in medium-sized parks

**Pros:**
- Simple change
- Captures greenways in parks

**Cons:**
- Still misses standalone greenways
- May capture too many small park paths

---

## Next Steps

1. **Verify OSM tagging**: Check actual OSM tags for Hudson Greenway/East River Walkway
2. **Decide on approach**: Choose Option 1, 2, or 3 (or combination)
3. **Implement**: Add greenway capture to appropriate query
4. **Test**: Verify greenways are captured and scored appropriately
5. **Re-calibrate**: If scoring changes significantly, re-run calibration

---

## Design Principles Compliance

✅ **Research-Backed**: Greenways are legitimate urban outdoor infrastructure  
✅ **Objective**: Based on OSM tags (`highway=cycleway`, `highway=footway`)  
✅ **Scalable**: Works for all locations, not just NYC  
✅ **Transparent**: Clear rationale for capturing greenways  

**Question**: Should greenways be scored in Daily Urban Outdoors (local/daily use) or separate category?

