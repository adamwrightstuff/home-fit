# Missing Factors Investigation Results

## Summary

Investigation of data sources to measure "missing factors" that might explain why Bronxville NY needs a score of 85 but current scoring only reaches 47.4.

## Investigation Results

### ✅ Available Factors

#### 1. Weekend/Holiday Service
**Status:** ✅ **AVAILABLE**  
**Data Source:** Transitland API `/rest/stops/{stop_id}/departures` with `service_date` parameter  
**Test Result:** Successfully queried weekend schedule (25 departures on Saturday)  
**Implementation:** Can query any date (weekday, weekend, holiday) by setting `service_date` parameter  
**Next Steps:** 
- Extend `get_route_schedules()` to accept `service_date` parameter
- Query both weekday and weekend schedules
- Calculate weekend service availability as a metric

#### 2. Route Destinations (from Trip Headsigns)
**Status:** ✅ **AVAILABLE**  
**Data Source:** Transitland API departure data includes `trip_headsign` field  
**Test Result:** Departures include trip headsigns indicating destinations (e.g., "Grand Central", "New Rochelle")  
**Implementation:** 
- Extract unique trip headsigns from departures
- Identify if route serves major hubs (Grand Central, Penn Station, etc.)
- Count unique destinations reachable

#### 3. Express vs Local Service (from Route/Trip Names)
**Status:** ⚠️ **PARTIALLY AVAILABLE**  
**Data Source:** Route names and trip headsigns may indicate express/local  
**Test Result:** Route names don't consistently indicate express/local, but trip headsigns might  
**Implementation:** 
- Check trip headsigns for "Express" or "Local" indicators
- Infer from route patterns (fewer stops = likely express)
- **Limitation:** Not all agencies clearly mark express vs local in names

### ⚠️ Partially Available Factors

#### 4. Hub Connectivity (Travel Time to Major Hubs)
**Status:** ⚠️ **PARTIALLY AVAILABLE**  
**Data Source:** Can infer from trip headsigns and route names  
**Test Result:** Trip headsigns indicate destinations (e.g., "Grand Central")  
**Implementation:** 
- Identify if route serves major hubs from trip headsigns
- **Limitation:** Cannot calculate actual travel time without GTFS `stop_times.txt`
- **Workaround:** Use route name/headsign to identify hub service, score based on hub importance

#### 5. Station Amenities
**Status:** ⚠️ **PARTIALLY AVAILABLE**  
**Data Source:** OSM railway station tags  
**Test Result:** OSM stations have basic tags but amenities not consistently tagged  
**Implementation:** 
- Query OSM for station amenities (parking, bike share, wheelchair access)
- **Limitation:** Incomplete tagging in OSM
- **Workaround:** Use presence/absence of tags, don't rely on completeness

### ❌ Not Available Factors

#### 6. Service Reliability (On-Time Performance)
**Status:** ❌ **NOT AVAILABLE**  
**Data Source:** Transitland API does not provide reliability metrics  
**Alternative Sources:**
- GTFS-RT (real-time) feeds - but not available via Transitland v2
- Transit agency APIs (e.g., MTA API) - requires agency-specific integration
- National Transit Database - requires manual data collection
- **Recommendation:** Skip for now, or use external data source if critical

#### 7. Network Connectivity (Unique Destinations Count)
**Status:** ⚠️ **PARTIALLY AVAILABLE**  
**Data Source:** Can count unique trip headsigns, but not comprehensive  
**Test Result:** Trip headsigns show some destinations  
**Implementation:** 
- Count unique trip headsigns from departures
- **Limitation:** Only shows destinations for trips at queried stop, not full network
- **Workaround:** Query multiple stops on route to get comprehensive destination list

#### 8. Route Quality (Express vs Local, Speed)
**Status:** ⚠️ **PARTIALLY AVAILABLE**  
**Data Source:** Can infer from route/trip names and stop patterns  
**Test Result:** Not consistently available  
**Implementation:** 
- Use trip headsigns to identify express service
- Count stops per route (fewer stops = likely express)
- **Limitation:** Requires GTFS data for accurate stop counts

## Recommended Implementation Plan

### Phase 1: Implement Available Factors (High Value, Low Effort)

1. **Weekend Service Availability**
   - Extend `get_route_schedules()` to query weekend dates
   - Calculate weekend service ratio (weekend trips / weekday trips)
   - Add bonus for good weekend service

2. **Hub Connectivity**
   - Extract trip headsigns from departures
   - Identify major hub destinations (Grand Central, Penn Station, etc.)
   - Add bonus for direct service to major hubs

3. **Route Destinations**
   - Count unique destinations from trip headsigns
   - Add bonus for high destination diversity

### Phase 2: Implement Partially Available Factors (Medium Value, Medium Effort)

4. **Express vs Local Service**
   - Check trip headsigns for express indicators
   - Infer from route patterns
   - Add bonus for express service availability

5. **Station Amenities** (if time permits)
   - Query OSM for station amenities
   - Score based on available amenities
   - **Note:** Low priority due to incomplete OSM data

### Phase 3: Skip or Defer

6. **Service Reliability** - Skip (not available via current APIs)
7. **Network Connectivity** - Defer (requires comprehensive GTFS parsing)

## Expected Impact on Bronxville NY

**Current Score:** 47.4  
**Target Score:** 85  
**Gap:** +37.6 points

**Potential Bonuses from New Factors:**
- Weekend service: +3-5 points (if good weekend service)
- Hub connectivity: +5-10 points (Grand Central is major hub)
- Express service: +3-5 points (if express available)
- Destination diversity: +2-3 points

**Total Potential:** +13-23 points → **New Score: 60-70** (still below 85)

**Conclusion:** New factors help but won't fully close the gap. Need to investigate:
1. Base route scoring (is 40 points for 1 route too low?)
2. Commute time weight (should it be higher for commuter rail suburbs?)
3. Frequency bonuses (from previous analysis)

## Next Steps

1. **Implement Phase 1 factors** (weekend service, hub connectivity, destinations)
2. **Re-test Bronxville** with new factors
3. **If still below target:** Investigate base scoring adjustments
4. **If at target:** Validate with other commuter rail suburbs

