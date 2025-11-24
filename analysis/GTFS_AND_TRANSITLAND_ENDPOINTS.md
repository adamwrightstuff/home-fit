# GTFS Feeds vs Transitland API Endpoints

## What is GTFS?

**GTFS (General Transit Feed Specification)** is a standardized data format for public transit schedules and geographic information. It's used by transit agencies worldwide to publish their route, stop, schedule, and fare data.

### Key Points:

1. **Publicly Available:** ✅ Yes, most transit agencies publish GTFS feeds for free
2. **Free to Use:** ✅ Yes, typically under open data licenses (Creative Commons, etc.)
3. **Format:** ZIP files containing CSV files (routes.txt, stops.txt, stop_times.txt, trips.txt, etc.)
4. **Where to Find:** 
   - Transit agency websites
   - Open data portals (data.gov, city open data sites)
   - GTFS Data Exchange (gtfs-data-exchange.com)
   - Transitland Feed Registry

### GTFS Feed Integration Would Require:

1. **Download feeds** from transit agencies (one per agency)
2. **Parse CSV files** to extract schedule data
3. **Calculate metrics** (headways, service span, trip counts)
4. **Store in database** for fast queries
5. **Update regularly** (feeds change daily/weekly)

**Pros:**
- Direct access to schedule data
- Complete control over data processing
- No API rate limits

**Cons:**
- Need to download/parse feeds for each agency
- Storage and processing overhead
- Requires regular updates
- More complex implementation

## Transitland v2 API Endpoints

You're absolutely right! Transitland v2 **does** have endpoints that can provide schedule data:

### 1. Trips Endpoint
```
GET /api/v2/rest/routes/{route_key}/trips
```

**What it provides:**
- Basic GTFS trip information
- Associated shapes, calendars
- Stop departure details

**Use case:** Get all trips for a specific route to calculate:
- Service frequency (headways)
- Service span (first/last trip)
- Weekday trip counts

### 2. Stop Departures Endpoint
```
GET /api/v2/rest/stops/{stop_key}/departures
```

**What it provides:**
- All upcoming departures (scheduled and real-time)
- From a specific stop

**Use case:** Get real-time or scheduled departure times for:
- Current headway calculation
- Next departure time
- Service availability

## Recommendation: Use Transitland Endpoints ✅

**Why Transitland is Better:**
1. ✅ **Single API** - No need to download/parse multiple GTFS feeds
2. ✅ **Already integrated** - We're already using Transitland for routes/stops
3. ✅ **Real-time data** - Stop departures endpoint includes real-time info
4. ✅ **Simpler implementation** - Just API calls, no file parsing
5. ✅ **Rate limits manageable** - We can cache results

**Implementation Plan:**
1. Update `get_route_schedules()` to use `/routes/{route_id}/trips` endpoint
2. Parse trip data to calculate:
   - Peak/off-peak headways
   - Service span (first/last departure)
   - Weekday trip counts
3. Use stop departures endpoint for real-time headway validation

## Next Steps

1. **Test trips endpoint** with proper error handling and longer timeout
2. **Update `get_route_schedules()` function** to use trips endpoint
3. **Calculate frequency metrics** from trip data
4. **Re-run research** with frequency data
5. **Validate hypothesis** with complete dataset

