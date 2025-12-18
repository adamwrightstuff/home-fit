# All Pillars Data-Backed Status

## Summary

After migrating `natural_beauty` and `active_outdoors` from model-driven to data-backed scoring, **all pillars now use pure data-backed approaches**.

## ✅ Data-Backed Pillars (All Others)

### 1. air_travel_access
**Scoring Method:** Direct distance-based scoring
- **Data Source:** Airport database (lat/lon coordinates)
- **Calculation:** Haversine distance to airports, smooth decay curves based on distance
- **Components:** Distance to nearest airports (0-150km), airport size/type, redundancy bonus
- **No Models:** Pure geometric distance calculations with calibrated distance curves

### 2. healthcare_access
**Scoring Method:** Direct count/distance-based scoring
- **Data Source:** OSM (hospitals, clinics, pharmacies) + fallback database
- **Calculation:** Count facilities within radius, distance to nearest, calibrated ratio scoring
- **Components:** Hospital access (distance), primary care (count), specialized care (count), pharmacies (count)
- **No Models:** Direct counts and distances from OSM queries

### 3. public_transit_access
**Scoring Method:** Direct route count/distance-based scoring
- **Data Source:** Transitland API (routes, stops) + OSM (railway stations)
- **Calculation:** Route counts by mode, distance to nearest stops, calibrated route count scoring
- **Components:** Heavy rail, light rail, bus (route counts + distances)
- **No Models:** Direct route counts and stop distances from Transitland API

### 4. housing_value
**Scoring Method:** Direct Census data-based scoring
- **Data Source:** Census API (median home value, median income, median rooms)
- **Calculation:** Price-to-income ratio, rooms per unit, rooms per $100k
- **Components:** Affordability (ratio), space (rooms), efficiency (rooms/$100k)
- **No Models:** Direct Census data calculations

### 5. neighborhood_amenities
**Scoring Method:** Direct business count/distance-based scoring with linear calibration
- **Data Source:** OSM (businesses, amenities)
- **Calculation:** Business counts within radius, distance to nearest, calibrated ratio scoring
- **Components:** Home walkability (nearby businesses), location quality (vibrant town nearby)
- **Calibration:** Linear calibration (area-type-specific) - this is a transform on data-backed scores, not a model
- **No Models:** Direct business counts from OSM

### 6. built_beauty
**Scoring Method:** Direct component-based scoring
- **Data Source:** OSM (buildings, architecture), GEE (tree canopy)
- **Calculation:** Architecture diversity score, tree canopy percentage, enhancer bonuses
- **Components:** Architecture diversity (0-50), tree canopy (0-50), enhancer bonuses (artwork, fountains, etc.)
- **No Models:** Direct measurements from OSM building data and GEE canopy data

### 7. natural_beauty (✅ Just Migrated)
**Scoring Method:** Direct component-based scoring
- **Data Source:** GEE (tree canopy), OSM (parks), Census (canopy), GEE (water, topography, landcover)
- **Calculation:** Tree score + context bonus, scaled to 0-100
- **Components:** Tree score (0-50), context bonus (0-18) from water/topography/landcover
- **No Models:** Direct measurements from GEE, OSM, Census

### 8. active_outdoors (✅ Just Migrated)
**Scoring Method:** Direct weighted component sum
- **Data Source:** OSM (parks, trails, swimming, camping), GEE (tree canopy)
- **Calculation:** Weighted sum of component scores
- **Components:** Daily urban outdoors (0-30), wild adventure (0-50), waterfront lifestyle (0-20)
- **No Models:** Direct counts and distances from OSM queries

## Calibration vs Models

**Important Distinction:**
- **Linear Calibration** (used in `neighborhood_amenities`): A simple transform `y = ax + b` applied to data-backed scores. This is acceptable because:
  - Input `x` is data-backed (business counts)
  - Transform is transparent and explainable
  - Not a statistical model trained on data
  - Just adjusts scale/offset, doesn't introduce non-transparent weighting

- **Ridge Regression** (removed from `natural_beauty` and `active_outdoors`): A statistical model with:
  - Trained weights from training data
  - Non-transparent feature interactions
  - Requires training data to reproduce
  - Violates "Objective, Data-Driven Scoring" principle

## Fallback Scoring

Fallback scoring (used in `healthcare_access`, `public_transit_access`, `housing_value`) is **NOT** model-driven:
- Conservative estimates when primary data unavailable
- Based on measurable proxies (area type, density)
- Clearly marked with `fallback_applied: true`
- Compliant with design principles (graceful degradation)

## Conclusion

**All 8 pillars now use pure data-backed scoring:**
- ✅ Direct measurements from APIs (OSM, Census, Transitland, GEE)
- ✅ Direct calculations (distances, counts, ratios)
- ✅ Transparent and reproducible
- ✅ No statistical models or training data dependencies
- ✅ Aligned with "Objective, Data-Driven Scoring" design principle
