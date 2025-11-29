# Testing Active Outdoors Pillar

## Quick Test via API

### Using the Test Script

```bash
# Test with default location (Central Park, NYC)
python3 test_active_outdoors_api.py

# Test with custom location
python3 test_active_outdoors_api.py "Miami Beach FL"

# Test with custom API URL (if running on different port/host)
python3 test_active_outdoors_api.py "Boulder CO" "http://localhost:8000"
```

### Using cURL

```bash
# Test Active Outdoors only
curl "http://localhost:8000/score?location=Central%20Park,%20New%20York%20NY&only=active_outdoors&diagnostics=true"

# Test with different location
curl "http://localhost:8000/score?location=Miami%20Beach%20FL&only=active_outdoors&diagnostics=true"
```

### Using Python Requests

```python
import requests

response = requests.get("http://localhost:8000/score", params={
    "location": "Central Park, New York NY",
    "only": "active_outdoors",  # Only test this pillar
    "diagnostics": "true"  # Include detailed diagnostics
})

data = response.json()
score = data["pillars"]["active_outdoors"]["score"]
breakdown = data["pillars"]["active_outdoors"]["breakdown"]
print(f"Score: {score}/100")
print(f"Daily Urban: {breakdown['daily_urban_outdoors']}/30")
print(f"Wild Adventure: {breakdown['wild_adventure']}/50")
print(f"Waterfront: {breakdown['waterfront_lifestyle']}/20")
```

## What Gets Tested

The Active Outdoors pillar measures:

1. **Daily Urban Outdoors (0-30)**
   - Parks and green spaces (filtered: parks <0.1 ha excluded from area calc)
   - Playgrounds
   - **Recreational facilities** (tennis courts, baseball fields, dog parks, etc.)

2. **Wild Adventure (0-50)**
   - Hiking trails (filtered: urban paths excluded)
   - Camping sites
   - Tree canopy coverage

3. **Waterfront Lifestyle (0-20)**
   - Beaches (swimmable, filtered: private/rocky excluded)
   - Swimming areas
   - Lakes (filtered: ornamental water excluded)
   - Coastline (filtered: short segments <100m excluded)

## Recent Improvements

- ✅ **Recreational facilities** now captured separately (tennis courts, baseball fields, dog parks)
- ✅ **Small parks** (<0.1 ha) filtered from area calculations but still counted for density
- ✅ **Beach classification** improved (distinguishes swimmable beaches from rocky/private)
- ✅ **Ornamental water** filtered (fountains, decorative ponds, small lakes)
- ✅ **Coastline fragments** filtered (segments <100m excluded)

## Expected Response Structure

```json
{
  "pillars": {
    "active_outdoors": {
      "score": 58.0,
      "breakdown": {
        "daily_urban_outdoors": 16.0,
        "wild_adventure": 5.3,
        "waterfront_lifestyle": 7.2
      },
      "summary": {
        "parks": 117,
        "playgrounds": 0,
        "hiking_trails": 10,
        "swimming_features": 50
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

## Running the API Server

```bash
# Start the FastAPI server
uvicorn main:app --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

