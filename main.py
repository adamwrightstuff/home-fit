from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# UPDATED IMPORTS - 8 Purpose-Driven Pillars
from data_sources.geocoding import geocode
from pillars.schools import get_school_data
from pillars.active_outdoors import get_active_outdoors_score
from pillars.neighborhood_beauty import get_neighborhood_beauty_score
from pillars.walkable_town import get_walkable_town_score
from pillars.air_travel_access import get_air_travel_score
from pillars.public_transit_access import get_public_transit_score
from pillars.healthcare_access import get_healthcare_access_score
from pillars.housing_value import get_housing_value_score

##########################
# CONFIGURATION FLAGS
##########################
ENABLE_SCHOOL_SCORING = False  # Set to True to enable school API calls

# Load environment variables
load_dotenv()

app = FastAPI(
    title="HomeFit API",
    description="Purpose-driven livability scoring API with 8 pillars",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "service": "HomeFit API",
        "status": "running",
        "version": "3.0.0",
        "pillars": [
            "active_outdoors",
            "neighborhood_beauty",
            "neighborhood_amenities",
            "air_travel_access",
            "public_transit_access",
            "healthcare_access",
            "quality_education",
            "housing_value"
        ],
        "endpoints": {
            "score": "/score?location=ADDRESS",
            "docs": "/docs"
        }
    }


@app.get("/score")
def get_livability_score(location: str):
    """
    Calculate livability score for a given address.

    Returns scores across 8 purpose-driven pillars:
    - Active Outdoors: Can I be active outside regularly?
    - Neighborhood Beauty: Is my environment beautiful and charming?
    - Neighborhood Amenities: Can I walk to great local spots?
    - Air Travel Access: How easily can I fly somewhere?
    - Public Transit Access: Can I get around without a car?
    - Healthcare Access: Can I get medical care when needed?
    - Quality Education: Can I raise kids with good schools?
    - Housing Value: Can I afford a spacious home here?

    Parameters:
        location: Address or ZIP code

    Returns:
        JSON with pillar scores and weighted total
    """
    print(f"\n{'='*60}")
    print(f"🏠 HomeFit Score Request: {location}")
    print(f"{'='*60}")

    # Step 1: Geocode the location
    geo_result = geocode(location)

    if not geo_result:
        raise HTTPException(
            status_code=400,
            detail="Could not geocode the provided location. Please check the address."
        )

    lat, lon, zip_code, state, city = geo_result
    print(f"✅ Coordinates: {lat}, {lon}")
    print(f"📮 Location: {city}, {state} {zip_code}\n")

    # Step 2: Calculate all pillar scores
    print("📊 Calculating pillar scores...\n")

    # Pillar 1: Active Outdoors
    active_outdoors_score, active_outdoors_details = get_active_outdoors_score(lat, lon, city=city)

    # Pillar 2: Neighborhood Beauty
    beauty_score, beauty_details = get_neighborhood_beauty_score(lat, lon, city=city)

    # Pillar 3: Neighborhood Amenities (walkable town)
    amenities_score, amenities_details = get_walkable_town_score(lat, lon)

    # Pillar 4: Air Travel Access
    air_travel_score, air_travel_details = get_air_travel_score(lat, lon)

    # Pillar 5: Public Transit Access
    transit_score, transit_details = get_public_transit_score(lat, lon)

    # Pillar 6: Healthcare Access
    healthcare_score, healthcare_details = get_healthcare_access_score(lat, lon)

    # Pillar 7: Quality Education (schools)
    if ENABLE_SCHOOL_SCORING:
        print("📚 Fetching school data from SchoolDigger API...")
        school_avg, schools_by_level = get_school_data(
            zip_code=zip_code,
            state=state,
            city=city
        )
    else:
        print("📚 School scoring disabled (preserving API quota)")
        school_avg = 50  # Neutral default
        schools_by_level = {
            "elementary": [],
            "middle": [],
            "high": []
        }

    # Pillar 8: Housing Value
    housing_score, housing_details = get_housing_value_score(lat, lon)

    # Step 3: Calculate weighted total (EQUAL WEIGHTS)
    default_weights = {
        "active_outdoors": 12.5,
        "neighborhood_beauty": 12.5,
        "neighborhood_amenities": 12.5,
        "air_travel_access": 12.5,
        "public_transit_access": 12.5,
        "healthcare_access": 12.5,
        "quality_education": 12.5,
        "housing_value": 12.5
    }

    total_score = (
        (active_outdoors_score * default_weights["active_outdoors"] / 100) +
        (beauty_score * default_weights["neighborhood_beauty"] / 100) +
        (amenities_score * default_weights["neighborhood_amenities"] / 100) +
        (air_travel_score * default_weights["air_travel_access"] / 100) +
        (transit_score * default_weights["public_transit_access"] / 100) +
        (healthcare_score * default_weights["healthcare_access"] / 100) +
        (school_avg * default_weights["quality_education"] / 100) +
        (housing_score * default_weights["housing_value"] / 100)
    )

    print(f"\n{'='*60}")
    print(f"🎯 Final Livability Score: {total_score:.1f}/100")
    print(f"{'='*60}")
    print(f"   🏃 Active Outdoors: {active_outdoors_score:.1f}/100")
    print(f"   ✨ Neighborhood Beauty: {beauty_score:.1f}/100")
    print(f"   🍽️  Neighborhood Amenities: {amenities_score:.1f}/100")
    print(f"   ✈️  Air Travel Access: {air_travel_score:.1f}/100")
    print(f"   🚇 Public Transit Access: {transit_score:.1f}/100")
    print(f"   🏥 Healthcare Access: {healthcare_score:.1f}/100")
    print(f"   🎓 Quality Education: {school_avg:.1f}/100")
    print(f"   🏠 Housing Value: {housing_score:.1f}/100")
    print(f"{'='*60}\n")

    # Count total schools
    total_schools = sum([
        len(schools_by_level.get("elementary", [])),
        len(schools_by_level.get("middle", [])),
        len(schools_by_level.get("high", []))
    ])

    # Build response
    response = {
        "input": location,
        "coordinates": {
            "lat": lat,
            "lon": lon
        },
        "location_info": {
            "city": city,
            "state": state,
            "zip": zip_code
        },
        "livability_pillars": {
            "active_outdoors": {
                "score": active_outdoors_score,
                "weight": default_weights["active_outdoors"],
                "contribution": round(active_outdoors_score * default_weights["active_outdoors"] / 100, 2),
                "breakdown": active_outdoors_details["breakdown"],
                "summary": active_outdoors_details["summary"]
            },
            "neighborhood_beauty": {
                "score": beauty_score,
                "weight": default_weights["neighborhood_beauty"],
                "contribution": round(beauty_score * default_weights["neighborhood_beauty"] / 100, 2),
                "breakdown": beauty_details["breakdown"],
                "summary": beauty_details["summary"],
                "scoring_note": beauty_details.get("scoring_note", "")
            },
            "neighborhood_amenities": {
                "score": amenities_score,
                "weight": default_weights["neighborhood_amenities"],
                "contribution": round(amenities_score * default_weights["neighborhood_amenities"] / 100, 2),
                "breakdown": amenities_details["breakdown"],
                "summary": amenities_details["summary"]
            },
            "air_travel_access": {
                "score": air_travel_score,
                "weight": default_weights["air_travel_access"],
                "contribution": round(air_travel_score * default_weights["air_travel_access"] / 100, 2),
                "primary_airport": air_travel_details.get("primary_airport"),
                "nearest_airports": air_travel_details.get("nearest_airports", []),
                "summary": air_travel_details.get("summary", {})
            },
            "public_transit_access": {
                "score": transit_score,
                "weight": default_weights["public_transit_access"],
                "contribution": round(transit_score * default_weights["public_transit_access"] / 100, 2),
                "breakdown": transit_details["breakdown"],
                "summary": transit_details["summary"]
            },
            "healthcare_access": {
                "score": healthcare_score,
                "weight": default_weights["healthcare_access"],
                "contribution": round(healthcare_score * default_weights["healthcare_access"] / 100, 2),
                "breakdown": healthcare_details["breakdown"],
                "summary": healthcare_details["summary"]
            },
            "quality_education": {
                "score": school_avg,
                "weight": default_weights["quality_education"],
                "contribution": round(school_avg * default_weights["quality_education"] / 100, 2),
                "by_level": {
                    "elementary": schools_by_level.get("elementary", []),
                    "middle": schools_by_level.get("middle", []),
                    "high": schools_by_level.get("high", [])
                },
                "total_schools_rated": total_schools
            },
            "housing_value": {
                "score": housing_score,
                "weight": default_weights["housing_value"],
                "contribution": round(housing_score * default_weights["housing_value"] / 100, 2),
                "breakdown": housing_details["breakdown"],
                "summary": housing_details["summary"]
            }
        },
        "total_score": round(total_score, 2),
        "default_weights": default_weights,
        "metadata": {
            "version": "3.0.0",
            "architecture": "8 Purpose-Driven Pillars",
            "pillars": {
                "active_outdoors": "Can I be active outside regularly? (Parks, beaches, trails, camping)",
                "neighborhood_beauty": "Is my environment beautiful? (Trees, green space, historic buildings, art)",
                "neighborhood_amenities": "Can I walk to great spots? (Indie cafes, restaurants, shops, culture)",
                "air_travel_access": "How easily can I fly? (Airport proximity and type)",
                "public_transit_access": "Can I move without a car? (Rail, light rail, bus access)",
                "healthcare_access": "Can I get medical care? (Hospitals, clinics, pharmacies)",
                "quality_education": "Can I raise kids well? (School ratings by level)",
                "housing_value": "Can I afford space? (Affordability relative to local income)"
            },
            "data_sources": [
                "Nominatim (geocoding)",
                "SchoolDigger API (schools)",
                "OpenStreetMap Overpass API (recreation, beauty, amenities, healthcare)",
                "Census Bureau ACS (housing, building age, tree canopy)",
                "NYC Open Data (street trees)",
                "OurAirports (airport database)",
                "Transitland API (public transit GTFS)"
            ],
            "note": "Total score = weighted average of 8 pillars. Equal weights by default (12.5% each). User can customize weights via token allocation system (future feature)."
        }
    }

    return response


@app.get("/health")
def health_check():
    """Detailed health check with API credential validation."""
    import os

    checks = {
        "geocoding": "✅ Nominatim (no credentials required)",
        "schools": "❌ SchoolDigger credentials missing",
        "osm": "✅ OpenStreetMap (no credentials required)",
        "census": "❌ Census API key missing",
        "nyc_trees": "✅ NYC Open Data (no credentials required)",
        "airports": "✅ OurAirports database (static data)",
        "transit": "✅ Transitland API (no credentials required)"
    }

    # Check SchoolDigger credentials
    if os.getenv("SCHOOLDIGGER_APPID") and os.getenv("SCHOOLDIGGER_APPKEY"):
        checks["schools"] = "✅ SchoolDigger credentials configured"

    # Check Census API key
    if os.getenv("CENSUS_API_KEY"):
        checks["census"] = "✅ Census API key configured"

    return {
        "status": "healthy",
        "checks": checks,
        "version": "3.0.0",
        "architecture": "8 Purpose-Driven Pillars",
        "pillars": [
            "active_outdoors",
            "neighborhood_beauty", 
            "neighborhood_amenities",
            "air_travel_access",
            "public_transit_access",
            "healthcare_access",
            "quality_education",
            "housing_value"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)