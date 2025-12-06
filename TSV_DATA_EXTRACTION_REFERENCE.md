# TSV Data Extraction Reference

This document maps TSV column names to API response paths for all pillars.

## Common Fields (All Pillars)

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Location** | `location` (from request) | Original location string |
| **Form Context** | `data_quality_summary.form_context` | Architectural classification (beauty pillars only) |
| **Area Type** | `data_quality_summary.area_classification.type` or `livability_pillars.{pillar}.area_classification.area_type` | Area classification |
| **Lat / Lon** | `location.lat,location.lon` | Single column with comma-separated coordinates (format: "lat,lon", e.g., "29.9594926,-90.0655403") |
| **Data quality tier** | `livability_pillars.{pillar}.data_quality.quality_tier` | Quality tier (excellent, good, fair, poor, very_poor) |
| **Confidence score** | `livability_pillars.{pillar}.confidence` | Confidence percentage (0-100) |

---

## Active Outdoors

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Total Active Score** | `livability_pillars.active_outdoors.score` | Total score (0-100) |
| **Daily Urban Outdoors** | `livability_pillars.active_outdoors.breakdown.daily_urban_outdoors` | Component score (0-30) |
| **Wild Adventure Backbone** | `livability_pillars.active_outdoors.breakdown.wild_adventure` | Component score (0-50) |
| **Waterfront Lifestyle** | `livability_pillars.active_outdoors.breakdown.waterfront_lifestyle` | Component score (0-20) |
| **Park Count** | `livability_pillars.active_outdoors.summary.local_parks.count` | Number of parks |
| **Playground Count** | `livability_pillars.active_outdoors.summary.local_parks.playgrounds` | Number of playgrounds |
| **Park Area** | `livability_pillars.active_outdoors.summary.local_parks.total_park_area_ha` | Total park area in hectares |
| **Trails Within 5km** | `livability_pillars.active_outdoors.summary.trails.count_within_5km` | Trail count within 5km |
| **Swimmable Count** | `livability_pillars.active_outdoors.summary.water.features` | Total water features found |
| **Nearest Swimming km** | `livability_pillars.active_outdoors.summary.water.nearest_km` | Distance to nearest water feature |
| **Campsite Count** | `livability_pillars.active_outdoors.summary.camping.sites` | Number of campsites |
| **Nearest Camping km** | `livability_pillars.active_outdoors.summary.camping.nearest_km` | Distance to nearest campsite |
| **Tree Canopy 5km** | `livability_pillars.active_outdoors.summary.environment.tree_canopy_pct_5km` | Tree canopy percentage |

---

## Built Beauty

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Built Beauty Score** | `livability_pillars.built_beauty.score` | Total score (0-100) |
| **Height Diversity** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.height_diversity` | Height diversity metric |
| **Type Diversity** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.type_diversity` | Building type diversity |
| **Footprint Variation** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.footprint_variation` | Footprint area CV |
| **Built Coverage Ratio** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.built_coverage_ratio` | Built coverage ratio |
| **Block Grain** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.block_grain` | Block grain metric |
| **Streetwall Continuity** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.streetwall_continuity` | Streetwall continuity |
| **Setback Consistency** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.setback_consistency` | Setback consistency |
| **Facade Rhythm** | `livability_pillars.built_beauty.breakdown.architectural_analysis.metrics.facade_rhythm` | Facade rhythm |
| **Landmark Count** | `livability_pillars.built_beauty.breakdown.architectural_analysis.historic_context.landmarks` | Historic landmarks count |
| **Median Year Built** | `livability_pillars.built_beauty.breakdown.architectural_analysis.historic_context.median_year_built` | Median year built |
| **Material Share (Brick %)** | `livability_pillars.built_beauty.breakdown.architectural_analysis.material_profile.brick_pct` | Brick percentage (if available) |
| **Enhancer Bonus** | `livability_pillars.built_beauty.breakdown.enhancer_bonus.built_scaled` | Scaled enhancer bonus |
| **Rowhouse Bonus** | `livability_pillars.built_beauty.breakdown.architectural_analysis.bonus_breakdown.rowhouse` | Rowhouse bonus |

---

## Natural Beauty

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Natural Beauty Score** | `livability_pillars.natural_beauty.score` | Total score (0-100) |
| **Tree Score (0-50)** | `livability_pillars.natural_beauty.breakdown.tree_score_0_50` | Tree score component |
| **Water %** | `livability_pillars.natural_beauty.breakdown.natural_context.landcover_metrics.water_pct` | Water percentage |
| **Slope Mean (deg)** | `livability_pillars.natural_beauty.breakdown.natural_context.topography_metrics.slope_mean_deg` | Mean slope in degrees |
| **Developed %** | `livability_pillars.natural_beauty.breakdown.natural_context.landcover_metrics.developed_pct` | Developed land percentage |
| **Neighborhood Canopy % (1000m)** | `livability_pillars.natural_beauty.breakdown.multi_radius_canopy.neighborhood_1000m` | Canopy at 1000m radius |
| **Green View Index** | `livability_pillars.natural_beauty.breakdown.green_view_index` | Green view index |
| **Enhancer Bonus Raw** | `livability_pillars.natural_beauty.breakdown.enhancer_bonus.natural_raw` | Raw enhancer bonus |
| **Context Bonus Raw** | `livability_pillars.natural_beauty.breakdown.enhancer_bonus.context_raw` | Raw context bonus |
| **Enhancer Bonus Scaled** | `livability_pillars.natural_beauty.breakdown.enhancer_bonus.natural_scaled` | Scaled enhancer bonus |
| **Total Context Bonus** | `livability_pillars.natural_beauty.breakdown.natural_context.total_bonus` | Total context bonus |

---

## Amenities (Neighborhood Amenities)

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Total score (0-100)** | `livability_pillars.neighborhood_amenities.score` | Total score (0-100) |
| **Home walkability (0-60)** | `livability_pillars.neighborhood_amenities.breakdown.home_walkability.score` | Home walkability score |
| **Density subscore (0-25)** | `livability_pillars.neighborhood_amenities.breakdown.home_walkability.breakdown.density` | Density component |
| **Variety subscore (0-20)** | `livability_pillars.neighborhood_amenities.breakdown.home_walkability.breakdown.variety` | Variety component |
| **Proximity subscore (0-15)** | `livability_pillars.neighborhood_amenities.breakdown.home_walkability.breakdown.proximity` | Proximity component |
| **Location quality (0-40)** | `livability_pillars.neighborhood_amenities.breakdown.location_quality` | Location quality score |
| **Total businesses** | `livability_pillars.neighborhood_amenities.summary.total_businesses` | Total business count |
| **Businesses within walkable distance** | `livability_pillars.neighborhood_amenities.breakdown.home_walkability.businesses_within_1km` | Businesses within walkable distance |
| **Tier 1 count** | `livability_pillars.neighborhood_amenities.summary.by_tier.daily_essentials.count` | Tier 1 (daily essentials) count |
| **Tier 2 count** | `livability_pillars.neighborhood_amenities.summary.by_tier.social_dining.count` | Tier 2 (social dining) count |
| **Tier 3 count** | `livability_pillars.neighborhood_amenities.summary.by_tier.culture_leisure.count` | Tier 3 (culture/leisure) count |
| **Tier 4 count** | `livability_pillars.neighborhood_amenities.summary.by_tier.services_retail.count` | Tier 4 (services/retail) count |
| **Median distance** | `livability_pillars.neighborhood_amenities.summary.downtown_center_distance_m` | Median distance in meters |
| **Businesses ≤400m** | `livability_pillars.neighborhood_amenities.summary.within_5min_walk` | Businesses within 400m |
| **Businesses ≤800m** | `livability_pillars.neighborhood_amenities.summary.within_10min_walk` | Businesses within 800m |

---

## Healthcare Access

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Total Healthcare Score** | `livability_pillars.healthcare_access.score` | Total score (0-100) |
| **Hospital score** | `livability_pillars.healthcare_access.breakdown.hospital_access` | Hospital access score |
| **Primary care score** | `livability_pillars.healthcare_access.breakdown.primary_care` | Primary care score |
| **Pharmacy score** | `livability_pillars.healthcare_access.breakdown.pharmacies` | Pharmacy score |
| **hospital_count** | `livability_pillars.healthcare_access.summary.hospital_count` | Hospital count |
| **urgent_care_count** | `livability_pillars.healthcare_access.summary.urgent_care_count` | Urgent care count |
| **pharmacy_count** | `livability_pillars.healthcare_access.summary.pharmacy_count` | Pharmacy count |
| **clinic_count** | `livability_pillars.healthcare_access.summary.clinic_count` | Clinic count |
| **nearest_hospital** | `livability_pillars.healthcare_access.summary.nearest_hospital.distance_km` | Distance to nearest hospital (km) |
| **nearest_urgent_care** | `livability_pillars.healthcare_access.summary.nearest_urgent_care.distance_km` | Distance to nearest urgent care (km) |
| **nearest_pharmacy** | `livability_pillars.healthcare_access.summary.nearest_pharmacy.distance_km` | Distance to nearest pharmacy (km) |

---

## Housing Value

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Housing score (0-100)** | `livability_pillars.housing_value.score` | Total score (0-100) |
| **Local affordability subscore** | `livability_pillars.housing_value.breakdown.local_affordability` | Affordability component (0-50) |
| **Space subscore** | `livability_pillars.housing_value.breakdown.space` | Space component (0-30) |
| **Value efficiency subscore** | `livability_pillars.housing_value.breakdown.value_efficiency` | Value efficiency component (0-20) |
| **Median home value** | `livability_pillars.housing_value.summary.median_home_value` | Median home value |
| **Median household income** | `livability_pillars.housing_value.summary.median_household_income` | Median household income |
| **Median rooms** | `livability_pillars.housing_value.summary.median_rooms` | Median rooms |
| **Price-to-income ratio** | `livability_pillars.housing_value.summary.price_to_income_ratio` | Price to income ratio |
| **Cost per room** | `livability_pillars.housing_value.summary.cost_per_room` | Cost per room |
| **Rooms per 100k income** | `livability_pillars.housing_value.summary.rooms_per_100k_income` | Rooms per $100k income |
| **Housing type** | `livability_pillars.housing_value.summary.housing_type` | Housing type description |
| **Affordability rating** | `livability_pillars.housing_value.summary.affordability_rating` | Affordability rating |

---

## Public Transit Access

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Transit score (0-100)** | `livability_pillars.public_transit_access.score` | Total score (0-100) |
| **Heavy rail score (0-100)** | `livability_pillars.public_transit_access.breakdown.heavy_rail` | Heavy rail component |
| **Light rail score (0-100)** | `livability_pillars.public_transit_access.breakdown.light_rail` | Light rail component |
| **Bus score (0-100)** | `livability_pillars.public_transit_access.breakdown.bus` | Bus component |
| **Commute time score (0-100)** | `livability_pillars.public_transit_access.breakdown.commute_time` | Commute time component (if available) |
| **Total stops** | `livability_pillars.public_transit_access.summary.total_stops` | Total transit stops |
| **Heavy rail stops** | `livability_pillars.public_transit_access.summary.heavy_rail_stops` | Heavy rail stops |
| **Light rail stops** | `livability_pillars.public_transit_access.summary.light_rail_stops` | Light rail stops |
| **Bus stops** | `livability_pillars.public_transit_access.summary.bus_stops` | Bus stops |
| **Mean commute minutes** | `livability_pillars.public_transit_access.summary.mean_commute_minutes` | Mean commute time (if available) |
| **Transit modes available** | `livability_pillars.public_transit_access.summary.transit_modes_available` | Array of available modes |
| **Access level** | `livability_pillars.public_transit_access.summary.access_level` | Access level description |

---

## Air Travel Access

| TSV Column | API Response Path | Notes |
|------------|------------------|-------|
| **Air travel score (0-100)** | `livability_pillars.air_travel_access.score` | Total score (0-100) |
| **Primary airport code** | `livability_pillars.air_travel_access.breakdown.primary_airport.code` | Primary airport IATA code |
| **Primary airport name** | `livability_pillars.air_travel_access.breakdown.primary_airport.name` | Primary airport name |
| **Primary airport type** | `livability_pillars.air_travel_access.breakdown.primary_airport.type` | Airport type/category |
| **Primary airport distance (km)** | `livability_pillars.air_travel_access.breakdown.primary_airport.distance_km` | Distance to primary airport |
| **Has international hub** | `livability_pillars.air_travel_access.summary.has_international_hub` | Boolean - has international hub |
| **Has regional airport** | `livability_pillars.air_travel_access.summary.has_regional_airport` | Boolean - has regional airport |
| **Access level** | `livability_pillars.air_travel_access.summary.access_level` | Access level description |
| **Nearest international code** | `livability_pillars.air_travel_access.summary.nearest_international.code` | Nearest international airport code |
| **Nearest international name** | `livability_pillars.air_travel_access.summary.nearest_international.name` | Nearest international airport name |
| **Nearest international distance (km)** | `livability_pillars.air_travel_access.summary.nearest_international.distance_km` | Distance to nearest international airport |

---

## Notes

1. **Response Structure**: All pillar data is nested under `livability_pillars.{pillar_name}` in the API response.

2. **Common Fields**: Location, Form Context, Area Type, Lat/Lon, Data quality tier, and Confidence score are available for all pillars.

3. **Null Values**: Some fields may be `null` if data is unavailable. Handle nulls appropriately in your extraction script.

4. **Nested Objects**: Some fields (like `transit_modes_available`) are arrays. Extract as comma-separated values or handle as arrays.

5. **Distance Units**: All distances are in kilometers unless otherwise specified (e.g., `downtown_center_distance_m` is in meters).

6. **Form Context**: Only available for beauty pillars (built_beauty, natural_beauty) and is located at `data_quality_summary.form_context`.

7. **Area Type**: Can be found at either `data_quality_summary.area_classification.type` (top-level) or `livability_pillars.{pillar}.area_classification.area_type` (pillar-specific).

8. **Lat/Lon Format**: The Lat/Lon field should be extracted as a single column with comma-separated values (e.g., "29.9594926,-90.0655403"), not as two separate columns.
