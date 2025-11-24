# Missing Factors Investigation Plan

## Overview

This document investigates what data sources and metrics are available to measure the "missing factors" that might explain why Bronxville NY needs a score of 85 but our current scoring only reaches 47.4.

## Missing Factors to Investigate

### 1. Service Reliability (On-Time Performance)
**Status:** NOT MEASURED  
**Potential Data Sources:**
- GTFS-RT (real-time) feeds - but not available via Transitland v2
- Transit agency APIs (e.g., MTA API for Metro-North)
- External reliability databases
- **Investigation:** Check if Transitland provides any reliability metrics

### 2. Hub Connectivity (Travel Time to Major Hubs)
**Status:** NOT MEASURED  
**Potential Data Sources:**
- GTFS `stop_times.txt` - can calculate scheduled travel time between stops
- Route geometry - can identify if route goes to major hub
- **Investigation:** Can we extract destination information from route data?

### 3. Express vs Local Service
**Status:** NOT MEASURED  
**Potential Data Sources:**
- GTFS `routes.txt` - `route_short_name` or `route_long_name` may indicate express/local
- Route stops count - express routes typically have fewer stops
- **Investigation:** Can we identify express routes from route metadata?

### 4. Weekend/Holiday Service
**Status:** PARTIALLY MEASURED (only weekday)  
**Potential Data Sources:**
- GTFS `calendar.txt` and `calendar_dates.txt` - service days
- Transitland departures API - query weekend dates
- **Investigation:** Can we query weekend schedules from Transitland?

### 5. Network Connectivity (Destinations Reachable)
**Status:** NOT MEASURED  
**Potential Data Sources:**
- GTFS `stop_times.txt` + `stops.txt` - can map routes to destinations
- Route metadata - route names often indicate destinations
- **Investigation:** Can we extract destination information from route names?

### 6. Station Quality & Amenities
**Status:** NOT MEASURED  
**Potential Data Sources:**
- OSM data - station amenities (parking, bike share, etc.)
- Transit agency websites (manual research)
- **Investigation:** Can we query OSM for station amenities?

## Investigation Plan

### Phase 1: Test Transitland API Capabilities

1. **Check route metadata** - What fields does Transitland provide for routes?
2. **Check stop metadata** - What fields does Transitland provide for stops?
3. **Test weekend schedule queries** - Can we query weekend dates?
4. **Check route names** - Do route names indicate destinations/express service?

### Phase 2: Test GTFS Data Extraction (if available)

1. **Check if Transitland provides GTFS feed links**
2. **Test GTFS parsing** - Can we extract:
   - Service calendar (weekend service)
   - Route types (express vs local)
   - Stop sequences (destinations)
   - Travel times between stops

### Phase 3: Test OSM Data for Station Amenities

1. **Query OSM for railway stations** - What tags are available?
2. **Check for amenities** - parking, bike share, accessibility

### Phase 4: External Data Sources

1. **Transit agency APIs** - MTA, Metra, etc.
2. **Reliability databases** - National Transit Database, etc.

## Expected Outcomes

For each missing factor, determine:
- ✅ **Available:** Can be measured with current/existing data sources
- ⚠️ **Partially Available:** Can be approximated or inferred
- ❌ **Not Available:** Requires external data sources or manual research

