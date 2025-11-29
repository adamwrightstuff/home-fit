# Active Outdoors Data Extraction Guide

## Your Current Columns → API Response Path

Your existing columns **have NOT changed** - they all still map to the same locations. Here's the mapping:

| Your Column | API Response Path | Notes |
|------------|------------------|-------|
| **Effective Area Type** | `location.area_classification.area_type` | Or use `pillars.active_outdoors.area_classification.area_type` |
| **Lat / Lon** | `location.lat` / `location.lon` | From geocoding result |
| **Total Score** | `pillars.active_outdoors.score` | Calibrated score (0-100) |
| **Daily Urban Outdoors** | `pillars.active_outdoors.breakdown.daily_urban_outdoors` | Component score (0-30) |
| **Wild Adventure Backbone** | `pillars.active_outdoors.breakdown.wild_adventure` | Component score (0-50) |
| **Waterfront Lifestyle** | `pillars.active_outdoors.breakdown.waterfront_lifestyle` | Component score (0-20) |
| **Park Count** | `pillars.active_outdoors.summary.local_parks.count` | Number of parks |
| **Playground Count** | `pillars.active_outdoors.summary.local_parks.playgrounds` | Number of playgrounds |
| **Park Area** | `pillars.active_outdoors.summary.local_parks.total_park_area_ha` | Total park area in hectares |
| **Closest Water Distance (km)** | `pillars.active_outdoors.summary.water.nearest_km` | Distance to nearest water feature |
| **Trails Within 5km** | `pillars.active_outdoors.summary.trails.count_within_5km` | Trail count within 5km |
| **Swimmable Count** | `pillars.active_outdoors.summary.water.features` | Total water features found |
| **Nearest Swimming km** | `pillars.active_outdoors.summary.water.nearest_km` | Same as "Closest Water Distance" |
| **Campsite Count** | `pillars.active_outdoors.summary.camping.sites` | Number of campsites |
| **Nearest Camping km** | `pillars.active_outdoors.summary.camping.nearest_km` | Distance to nearest campsite |
| **Tree Canopy 5km** | `pillars.active_outdoors.summary.environment.tree_canopy_pct_5km` | Tree canopy percentage |

## NEW: Additional Data Available (Optional)

With the recent changes, you can also extract:

| New Column | API Response Path | Description |
|-----------|------------------|-------------|
| **Recreational Facilities Count** | `pillars.active_outdoors.diagnostics.recreational_facilities` | ⚠️ **NOT YET EXPOSED** - needs to be added |
| **Parks 2km** | `pillars.active_outdoors.diagnostics.parks_2km` | Park count within 2km (if diagnostics=true) |
| **Playgrounds 2km** | `pillars.active_outdoors.diagnostics.playgrounds_2km` | Playground count within 2km (if diagnostics=true) |
| **Hiking Trails Total** | `pillars.active_outdoors.diagnostics.hiking_trails_total` | Total trail count (if diagnostics=true) |
| **Raw Total Score** | `pillars.active_outdoors.raw_total_v2` | Uncalibrated raw score before linear mapping |

## Example JSON Response Structure

```json
{
  "location": {
    "lat": 40.7851,
    "lon": -73.9683,
    "area_classification": {
      "area_type": "urban_core"
    }
  },
  "pillars": {
    "active_outdoors": {
      "score": 58.0,
      "breakdown": {
        "daily_urban_outdoors": 16.0,
        "wild_adventure": 5.3,
        "waterfront_lifestyle": 7.2
      },
      "summary": {
        "local_parks": {
          "count": 117,
          "playgrounds": 0,
          "total_park_area_ha": 227.47
        },
        "trails": {
          "count_total": 10,
          "count_within_5km": 5
        },
        "water": {
          "features": 50,
          "nearest_km": 0.56
        },
        "camping": {
          "sites": 0,
          "nearest_km": null
        },
        "environment": {
          "tree_canopy_pct_5km": 6.5
        }
      },
      "area_classification": {
        "area_type": "urban_core"
      }
    }
  },
  "diagnostics": {
    "active_outdoors": {
      "parks_2km": 117,
      "playgrounds_2km": 0,
      "hiking_trails_total": 10,
      "hiking_trails_within_5km": 5,
      "swimming_features": 50,
      "camp_sites": 0,
      "tree_canopy_pct_5km": 6.5
    }
  }
}
```

## Notes

1. **All your existing columns still work** - nothing has changed in the response structure for those fields.

2. **"Closest Water Distance" and "Nearest Swimming km"** are the same value (`summary.water.nearest_km`).

3. **Diagnostics require `diagnostics=true`** parameter in the API call to be included.

4. **Recreational Facilities** are now being captured and used in scoring, but are not yet exposed in the summary/diagnostics. This could be added if needed.

5. **Park Area** now excludes parks <0.1 ha from the calculation (data quality improvement), but the field name and location haven't changed.

## Quick Test

To verify your extraction paths, test with:

```bash
curl "http://localhost:8000/score?location=Central%20Park,%20New%20York%20NY&only=active_outdoors&diagnostics=true" | jq '.pillars.active_outdoors'
```

