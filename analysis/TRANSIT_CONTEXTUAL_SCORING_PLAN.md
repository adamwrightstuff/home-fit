# Transit Contextual Scoring System - Implementation Plan

## Overview

This document outlines the plan to implement a research-backed, contextual scoring system for public transit that accounts for different transit needs across area types (urban core, suburban/commuter, rural/exurban).

## Hypothesis

**Urban Core:**
- Multimodality, close proximity to transit from all locations, high frequency, reliability (on-time performance), and full network connectivity across the city.

**Suburban / Commuter Towns:**
- Strong emphasis on reliability (on-time), sufficient frequency, high-quality (fast) service, and connectivity primarily to major hubs or job centers.

**Rural / Exurban:**
- Basic mobility within the local area, reliable service (on-time), and connectivity to regional hubs or transit lines for extended trips.

## Implementation Status

### ✅ Phase 1: Data Collection Infrastructure (COMPLETED)

1. **Added Transitland API Schedule Query Function** (`data_sources/transitland_api.py`)
   - `get_route_schedules(route_onestop_id)`: Queries Transitland API for route schedule data
   - Extracts: service span, peak/off-peak headways, weekday trip counts, first/last departure times
   - Note: This is a best-effort implementation; Transitland API structure may require adjustment based on actual responses

2. **Extended Research Script** (`scripts/research_expected_values.py`)
   - `collect_transit_data()` now collects service frequency metrics:
     - Peak/off-peak headways per mode (heavy rail, light rail, bus)
     - Service span (hours)
     - Weekday trip counts
   - Statistics calculation updated to include these new metrics

### 🔄 Phase 2: Research Data Collection (IN PROGRESS)

**Next Steps:**
1. Run research script on commuter rail suburbs with new metrics:
   ```bash
   python3 scripts/research_expected_values.py --area-types commuter_rail_suburb --pillars transit
   ```

2. Run research on all area types to establish baselines:
   ```bash
   python3 scripts/research_expected_values.py --pillars transit
   ```

3. Analyze collected data to identify:
   - Median peak/off-peak headways by area type
   - Service span expectations
   - Trip count patterns
   - Correlation between frequency metrics and perceived transit quality

### 📋 Phase 3: Contextual Scoring Implementation (PENDING)

Based on research findings, implement contextual scoring components:

**Urban Core Scoring:**
- **Multimodality**: Count of distinct high-frequency modes (already partially implemented)
- **Proximity**: Walking distance to nearest stop (already captured)
- **Frequency**: Headway-based scoring (NEW - needs implementation)
- **Reliability**: On-time performance (requires GTFS-RT or agency data)
- **Network Connectivity**: Destinations reachable within 30/45 minutes (requires route graph analysis)

**Suburban/Commuter Scoring:**
- **Reliability**: On-time performance (requires GTFS-RT or agency data)
- **Frequency**: Sufficient frequency thresholds (lower than urban core)
- **Service Quality**: Travel time to major hub vs. car travel time
- **Connectivity**: Direct links to metro cores

**Rural/Exurban Scoring:**
- **Basic Mobility**: Presence of any scheduled service
- **Reliability**: Consistent service days/hours
- **Regional Connectivity**: Links to intercity/regional transit

### 📊 Phase 4: Validation (PENDING)

1. Test new scoring system against benchmark locations
2. Compare scores with qualitative assessments
3. Ensure no location-specific tuning
4. Document methodology and rationale

## Data Sources

- **Transitland API**: Routes, stops, schedules (v2 REST API)
- **Census ACS**: Mean commute times (already integrated)
- **GTFS Feeds** (future): Direct access to schedule data for more accurate frequency calculations
- **GTFS-RT** (future): Real-time data for on-time performance metrics

## Design Principles Compliance

✅ **Research-Backed**: All metrics derived from empirical data collection  
✅ **Objective**: Based on measurable metrics (headways, trip counts, commute times)  
✅ **Scalable**: Works for all locations, not just test cases  
✅ **Transparent**: Methodology documented, data sources clear  
✅ **No Artificial Tuning**: No location-specific exceptions

## Notes

- The Transitland API schedule query function (`get_route_schedules`) is a best-effort implementation. The actual Transitland API structure may differ, requiring adjustments based on testing.
- Service frequency data collection may be rate-limited; the script includes delays between queries.
- On-time performance (reliability) metrics require GTFS-RT or agency-specific APIs, which are not yet integrated.

## Next Actions

1. **Test schedule query function** with a sample location (e.g., Bronxville NY) to verify Transitland API response structure
2. **Run research pass** on commuter rail suburbs to collect initial frequency data
3. **Analyze results** to identify patterns and establish baselines
4. **Design scoring curves** based on research findings
5. **Implement contextual scoring** components
6. **Validate** against benchmark locations

