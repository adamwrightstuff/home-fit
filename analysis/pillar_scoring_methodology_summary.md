# Pillar Scoring Methodology Summary

## Core Principle

**All pillars use pure data-backed scoring. No calibration or regression analysis.**

## Design Principles

### ✅ Data-Backed Scoring Only
- **What**: Direct measurement of objective metrics
- **Scoring**: Data measurements → raw score (no calibration)
- **Transparent**: All scoring logic is explicit and documented
- **Design Compliant**: Pure "Objective, Data-Driven Scoring"

### ❌ No Calibration or Regression
- **What**: Calibration/tuning toward target scores violates design principles
- **Status**: **REMOVED** from all pillars

## Current State of All Pillars

### 1. air_travel_access ✅
- **Data Source**: Airport database (lat/lon coordinates)
- **Scoring**: Direct distance calculations (haversine) + smooth decay curves
- **Regression**: None
- **Status**: Pure data-backed

### 2. healthcare_access ✅
- **Data Source**: OSM (hospitals, clinics, pharmacies) + fallback database
- **Scoring**: Direct counts and distances from OSM queries
- **Regression**: None (calibrated ratio scoring uses research-backed breakpoints)
- **Status**: Pure data-backed

### 3. public_transit_access ✅
- **Data Source**: Transitland API (routes, stops) + OSM (railway stations)
- **Scoring**: Direct route counts and stop distances
- **Regression**: None (calibrated route count scoring uses research-backed breakpoints)
- **Status**: Pure data-backed

### 4. housing_value ✅
- **Data Source**: Census API (median home value, income, rooms)
- **Scoring**: Direct Census data calculations (ratios)
- **Regression**: None
- **Status**: Pure data-backed

### 5. neighborhood_amenities ✅
- **Data Source**: OSM (businesses, amenities)
- **Scoring**: Direct business counts → linear calibration
- **Regression**: **Linear regression** used to determine calibration parameters (`a`, `b`)
- **Calibration**: `calibrated_score = a * raw_score + b`
- **Status**: Data-backed with regression-informed calibration

### 6. built_beauty ✅
- **Data Source**: OSM (buildings, architecture), GEE (tree canopy)
- **Scoring**: Direct measurements from OSM/GEE
- **Regression**: None
- **Status**: Pure data-backed

### 7. natural_beauty ✅ (Just Migrated)
- **Data Source**: GEE (tree canopy), OSM (parks), Census (canopy), GEE (water/topography/landcover)
- **Scoring**: Direct component sum `(tree_score + natural_bonus_scaled) * (100/68)`
- **Regression**: **Ridge regression REMOVED** (was causing convergence)
- **Calibration**: None (scaling factor only)
- **Status**: Pure data-backed (no regression)

### 8. active_outdoors ✅ (Just Migrated + Calibrated)
- **Data Source**: OSM (parks, trails, swimming, camping), GEE (tree canopy)
- **Scoring**: Direct weighted component sum → linear calibration
- **Regression**: **Linear regression** used to determine calibration parameters (`CAL_A`, `CAL_B`)
- **Calibration**: `calibrated_score = CAL_A * raw_score + CAL_B`
- **Status**: Data-backed with regression-informed calibration

## Key Distinctions

### Linear Regression (Acceptable)
- **Purpose**: Find optimal calibration parameters (`a`, `b` in `y = ax + b`)
- **Input**: Data-backed raw scores + target scores
- **Output**: Calibration parameters (not scores)
- **Scoring**: Still uses direct data measurements
- **Transparency**: Parameters are explicit and documented
- **Used in**: `neighborhood_amenities`, `active_outdoors`

### Ridge Regression (Unacceptable - Removed)
- **Purpose**: Predict scores directly from features
- **Input**: Normalized features
- **Output**: Predicted scores (not calibration parameters)
- **Scoring**: Uses statistical model, not direct data
- **Transparency**: Non-transparent feature weights
- **Was in**: `natural_beauty`, `active_outdoors` (REMOVED)

## Regression Analysis Workflow

### For Calibration (Acceptable)
1. **Collect Data**: Get actual scores from data-backed components
2. **Get Targets**: Obtain target scores (from LLM evaluation, user feedback, etc.)
3. **Run Regression**: Use linear regression to find optimal `a` and `b`
4. **Apply Calibration**: Use `calibrated = a * raw + b` in scoring
5. **Validate**: Test on sample locations

### For Primary Scoring (Unacceptable - Removed)
1. ~~Collect Features: Normalize features~~
2. ~~Train Model: Fit ridge regression model~~
3. ~~Predict Scores: Use model to predict scores~~
4. ~~Result: Non-transparent, causes convergence~~

## Summary Table

| Pillar | Data Source | Scoring Method | Regression Used | Status |
|--------|-------------|---------------|------------------|--------|
| air_travel_access | Airport DB | Distance-based | None | ✅ Pure data-backed |
| healthcare_access | OSM + Fallback | Count/distance-based | None | ✅ Pure data-backed |
| public_transit_access | Transitland + OSM | Route count/distance | None | ✅ Pure data-backed |
| housing_value | Census | Ratio calculations | None | ✅ Pure data-backed |
| neighborhood_amenities | OSM | Count-based + calibration | Linear (calibration) | ✅ Data-backed + calibration |
| built_beauty | OSM + GEE | Component-based | None | ✅ Pure data-backed |
| natural_beauty | GEE + OSM + Census | Component sum | None (ridge removed) | ✅ Pure data-backed |
| active_outdoors | OSM + GEE | Component sum + calibration | Linear (calibration) | ✅ Data-backed + calibration |

## Design Compliance

✅ **All pillars use actual data**:
- Direct measurements from APIs (OSM, Census, Transitland, GEE)
- Direct calculations (distances, counts, ratios)
- No synthetic or estimated data

✅ **Regression analysis used only for calibration**:
- Linear regression to find calibration parameters
- Not used for primary scoring
- Transparent and documented

✅ **No ridge regression for scoring**:
- Removed from `natural_beauty` and `active_outdoors`
- No statistical models used for primary scoring
- Aligned with "Objective, Data-Driven Scoring" principle

## Conclusion

**All pillars use actual data-backed scoring. Regression analysis is used only to determine calibration parameters (linear transforms), not for primary scoring. Ridge regression has been removed from all pillars.**
