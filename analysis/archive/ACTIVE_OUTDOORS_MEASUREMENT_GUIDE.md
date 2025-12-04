# Active Outdoors Pillar - What It Measures

**Purpose:** This guide explains exactly what the Active Outdoors v2 pillar analyzes when scoring a location. Use this to guide your research for target scores.

**Last Updated:** 2024-12-XX

---

## Overview

The Active Outdoors pillar answers: **"Can I be active outside regularly?"**

It measures access to outdoor recreation opportunities across three components:

1. **Daily Urban Outdoors (0-30 points)** - Local, walkable outdoor spaces
2. **Wild Adventure Backbone (0-50 points)** - Hiking trails, nature access, camping
3. **Waterfront Lifestyle (0-20 points)** - Access to beaches, lakes, rivers

**Total Score:** 0-100 (calibrated from raw component scores)

---

## Component 1: Daily Urban Outdoors (0-30 points)

**What it measures:** Access to local parks and playgrounds within walking distance

### Data Sources:
- **OpenStreetMap (OSM):** Parks and playgrounds
- **Search Radius:** 
  - Urban core: 800m (0.8 km)
  - Suburban: 1.5 km
  - Exurban/Rural: 2.0 km

### Metrics Analyzed:

1. **Park Count** (within local radius)
   - Number of parks/green spaces
   - Expected values vary by area type:
     - Urban core: ~8 parks within 1km
     - Suburban: ~8 parks within 1km
     - Exurban/Rural: Varies

2. **Total Park Area** (hectares)
   - Combined area of all parks within radius
   - Expected values:
     - Urban core: ~3 hectares
     - Suburban: ~6 hectares
     - Exurban/Rural: Varies

3. **Playground Count** (within local radius)
   - Number of playgrounds
   - Expected values:
     - Urban core: ~2 playgrounds within 1km
     - Suburban: ~1 playground within 1km

### Scoring Logic:
- Uses saturation curves (smooth, asymptotic)
- Compares actual counts/area to research-backed expected values
- **Urban Core Penalty:** Applies overflow penalty if park counts/area significantly exceed expectations (prevents OSM micro-polygon artifacts from inflating scores)

### What to Research:
- **ParkScore rankings** (Trust for Public Land)
- **Park acreage per capita**
- **Number of parks within 1-2km**
- **Playground availability**
- **Walkability to green spaces**

---

## Component 2: Wild Adventure Backbone (0-50 points)

**What it measures:** Access to hiking trails, natural areas, and camping opportunities

### Data Sources:
- **OpenStreetMap (OSM):** Hiking trails, camping sites
- **Google Earth Engine:** Tree canopy percentage (5km radius)
- **Search Radius:**
  - Trails: 15km (all area types)
  - Camping: 15-50km (varies by area type)

### Metrics Analyzed:

1. **Hiking Trail Count** (within 15km)
   - Total number of hiking trails
   - Expected values:
     - Urban core: ~2 trails within 15km
     - Suburban: ~9 trails within 15km
     - Exurban/Rural: ~20+ trails within 15km

2. **Nearby Trail Count** (within 5km)
   - Trails within close proximity
   - Expected values:
     - Urban core: ~8 trails within 5km
     - Suburban: ~6 trails within 5km
     - Exurban/Rural: ~15 trails within 5km

3. **Tree Canopy Percentage** (5km radius)
   - Percentage of area covered by tree canopy
   - Measured via Google Earth Engine (USGS NLCD Tree Canopy Cover)
   - Expected values:
     - Urban core: ~35% canopy
     - Suburban: ~30% canopy
     - Exurban/Rural: ~45% canopy

4. **Camping Site Proximity** (within 15-50km)
   - Distance to nearest camping site
   - Scoring varies by area type:
     - Urban core: Full score if ≤15km, exponential decay beyond
     - Suburban: Full score if ≤20km, exponential decay beyond
     - Exurban/Rural: Full score if ≤25km, exponential decay beyond

### Special Context Detection:

**Mountain Town Detection:**
- Detected if:
  - Very high trail count (≥40 trails) OR
  - High trail count (≥30) with reasonable canopy (≥8%) OR
  - Good near-trail access (≥5 within 5km) with canopy (≥8%)
- Mountain towns get higher expectations and max contributions
- Example: Boulder, Denver, Park City, Truckee

**Urban Core Trail Cap:**
- Caps trail count at 3x expected for urban cores
- Prevents OSM data artifacts (urban paths tagged as hiking trails) from inflating scores
- Example: Times Square has 94 "trails" but these are urban paths, not true hiking trails

### Scoring Logic:
- Uses saturation curves for trails and canopy
- Exponential decay for camping distance
- Mountain towns get higher max contributions (up to 28 points for trails vs 8 for urban cores)

### What to Research:
- **Trail system quality/quantity** (AllTrails, state park data)
- **Hiking trail density** within 15km
- **Tree canopy coverage** (can use ParkScore or city tree canopy reports)
- **Camping site proximity** (state/national park data)
- **Outdoor recreation rankings** (Outside Magazine, Men's Journal)
- **Mountain town designations** (elevation, proximity to mountain ranges)

---

## Component 3: Waterfront Lifestyle (0-20 points)

**What it measures:** Access to swimmable water (beaches, lakes, rivers)

### Data Sources:
- **OpenStreetMap (OSM):** Water features (beaches, lakes, rivers, bays, coastlines)
- **Search Radius:** 15-50km (varies by area type)

### Metrics Analyzed:

1. **Water Feature Type** (highest value):
   - **Beach:** 20.0 points (full score)
   - **Swimming Area:** 18.0 points
   - **Lake:** 18.0 points
   - **Bay:** 16.0 points
   - **Coastline:** 16.0 points
   - **Other:** 12.0 points

2. **Distance to Nearest Water Feature**
   - Optimal distance: ≤3km (full base score)
   - Exponential decay beyond 3km
   - Decay rate: 0.00025 per meter

### Context-Aware Adjustments:

**Urban Core Downweighting:**
- Non-beach water in dense urban cores: 60% of base score
- Prevents coastline fragments or ornamental water from inflating scores
- Example: Times Square has coastline fragments, but shouldn't score high on water access

**Desert Context Downweighting:**
- Non-beach/lake water in desert: 30% of base score
- Beaches/lakes in desert: 60% of base score
- Prevents reservoirs/ornamental water from inflating desert scores
- Example: Las Vegas has water features, but they're mostly ornamental/reservoirs

**Suburban Mild Downweighting:**
- Non-beach/lake water: 90% of base score

### Scoring Logic:
- Base score determined by water type
- Context adjustments applied (urban core, desert)
- Distance decay applied beyond 3km

### What to Research:
- **Beach access** (distance to swimmable beaches)
- **Lake/river access** (distance to swimmable water)
- **Water quality** (swimmable vs ornamental)
- **Coastal rankings** (beach quality rankings)
- **Water recreation opportunities**

---

## Context Detection

The pillar automatically detects special contexts that affect scoring:

### Mountain Town Detection
- **Criteria:** High trail count + reasonable canopy
- **Effect:** Uses exurban expectations, higher max contributions
- **Examples:** Boulder, Denver, Park City, Truckee, Asheville

### Desert Context Detection
- **Criteria:** Very low canopy (≤3%) + limited water features (≤10)
- **Effect:** Downweights water feature scoring
- **Examples:** Las Vegas, Phoenix

---

## Area Type Expectations

The pillar uses **research-backed expected values** that vary by area type:

| Area Type | Parks (1km) | Park Area (ha) | Trails (15km) | Canopy (%) |
|-----------|-------------|----------------|---------------|------------|
| Urban Core | 8 | 3 | 2 | 35 |
| Suburban | 8 | 6 | 9 | 30 |
| Exurban | Varies | Varies | 20+ | 45 |
| Rural | Varies | Varies | 20+ | 45 |

**Source:** `data_sources/regional_baselines.py` (research-backed from `scripts/research_expected_values.py`)

---

## Research Priorities for Target Scores

When researching target scores, prioritize:

1. **Park Access** (Daily Urban Outdoors)
   - ParkScore rankings
   - Park acreage per capita
   - Walkability to parks

2. **Trail Access** (Wild Adventure)
   - Trail system quality/quantity
   - Outdoor recreation rankings
   - Mountain town designations

3. **Water Access** (Waterfront Lifestyle)
   - Beach/lake proximity
   - Water recreation opportunities
   - Coastal rankings

4. **Overall Outdoor Recreation**
   - Outside Magazine "Best Towns"
   - Men's Journal outdoor rankings
   - State tourism outdoor recreation data

---

## Key Research Sources

1. **Trust for Public Land ParkScore**
   - URL: https://www.tpl.org/parkscore
   - Provides: Park access scores, acreage, spending

2. **Outside Magazine "Best Towns"**
   - Annual rankings of best outdoor recreation towns

3. **Men's Journal Outdoor Rankings**
   - Best places for outdoor activities

4. **AllTrails / Trail Data**
   - Trail system quality and quantity

5. **State Park/Natural Resource Data**
   - Camping site locations
   - Trail system information

6. **City Tree Canopy Reports**
   - Tree canopy coverage data

7. **Beach/Water Quality Rankings**
   - Swimmable water access

---

## Example: How to Research Boulder CO

**Daily Urban Outdoors:**
- ParkScore: Check Boulder's park access ranking
- Park count: How many parks within 1km of downtown?
- Park area: Total park acreage per capita

**Wild Adventure:**
- Trails: How many hiking trails within 15km? (Boulder Open Space)
- Canopy: Tree canopy percentage (should be ~18-20%)
- Camping: Distance to nearest camping (Rocky Mountain National Park)
- Mountain town: Is Boulder considered a mountain town? (Yes - elevation, proximity to mountains)

**Waterfront Lifestyle:**
- Water access: Any lakes/rivers nearby? (Boulder Creek, reservoirs)

**Overall:**
- Outside Magazine: Is Boulder ranked as a top outdoor town? (Yes, typically top 10)
- Expected score: 90-95 (world-class outdoor recreation)

---

## Notes

- **All measurements are objective** - no subjective assessments
- **Area-type aware** - expectations vary by urban/suburban/exurban/rural
- **Context-aware** - mountain towns and desert contexts get special handling
- **Research-backed** - expected values come from empirical data collection
- **No city-name exceptions** - all logic uses objective criteria

