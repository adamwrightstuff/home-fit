from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# UPDATED IMPORTS - New pillar structure
from data_sources.geocoding import geocode
from pillars.schools import get_school_data
from pillars.recreation_outdoors import get_recreation_outdoors_score
from pillars.neighborhood_charm import get_neighborhood_charm_score
from pillars.walkable_town import get_walkable_town_score
from pillars.housing_value import get_housing_value_score

##########################
# CONFIGURATION FLAGS
##########################
ENABLE_SCHOOL_SCORING = False  # Set to True to enable school API calls
ENABLE_RECREATION_OUTDOORS = True
ENABLE_NEIGHBORHOOD_CHARM = True
ENABLE_WALKABLE_TOWN = True
ENABLE_HOUSING_VALUE = True

# Load environment variables
load_dotenv()

app = FastAPI(
    title="HomeFit API",
    description="Geospatial livability scoring API with multiple pillars",
    version="2.0.0"
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
        "version": "2.0.0",
        "pillars": ["schools", "recreation_outdoors", "neighborhood_charm", "walkable_town", "housing_value"],
        "endpoints": {
            "score": "/score?location=ADDRESS",
            "docs": "/docs"
        }
    }


@app.get("/score")
def get_livability_score(location: str):
    """
    Calculate livability score for a given address.

    Returns scores across multiple pillars:
    - Schools: Quality and variety of nearby schools
    - Recreation & Outdoors: Parks, beaches, trails, outdoor activities
    - Neighborhood Charm: Tree canopy, historic architecture, public art
    - Walkable Town: Indie businesses, downtown walkability
    - Housing Value: Affordability and space relative to local income

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

    # Schools pillar
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

    # Recreation & Outdoors pillar (merged green_neighborhood + nature_access)
    recreation_score, recreation_details = get_recreation_outdoors_score(lat, lon, city=city)

    # Neighborhood Charm pillar (NEW - aesthetic appeal)
    charm_score, charm_details = get_neighborhood_charm_score(lat, lon, city=city)

    # Walkable Town pillar
    walkable_score, walkable_details = get_walkable_town_score(lat, lon)

    # Housing Value pillar
    housing_score, housing_details = get_housing_value_score(lat, lon)

    # Step 3: Calculate weighted total (default weights)
    default_weights = {
        "schools": 30,
        "recreation_outdoors": 20,
        "neighborhood_charm": 10,
        "walkable_town": 20,
        "housing_value": 20
    }

    total_score = (
        (school_avg * default_weights["schools"] / 100) +
        (recreation_score * default_weights["recreation_outdoors"] / 100) +
        (charm_score * default_weights["neighborhood_charm"] / 100) +
        (walkable_score * default_weights["walkable_town"] / 100) +
        (housing_score * default_weights["housing_value"] / 100)
    )

    print(f"\n{'='*60}")
    print(f"🎯 Final Livability Score: {total_score:.1f}/100")
    print(f"{'='*60}")
    print(f"   🎓 Schools: {school_avg:.1f}/100 (weight: {default_weights['schools']}%)")
    print(f"   🌳 Recreation & Outdoors: {recreation_score:.1f}/100 (weight: {default_weights['recreation_outdoors']}%)")
    print(f"   ✨ Neighborhood Charm: {charm_score:.1f}/100 (weight: {default_weights['neighborhood_charm']}%)")
    print(f"   🚶 Walkable Town: {walkable_score:.1f}/100 (weight: {default_weights['walkable_town']}%)")
    print(f"   🏠 Housing Value: {housing_score:.1f}/100 (weight: {default_weights['housing_value']}%)")
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
            "schools": {
                "score": school_avg,
                "weight": default_weights["schools"],
                "contribution": round(school_avg * default_weights["schools"] / 100, 2),
                "by_level": {
                    "elementary": schools_by_level.get("elementary", []),
                    "middle": schools_by_level.get("middle", []),
                    "high": schools_by_level.get("high", [])
                },
                "total_schools_rated": total_schools
            },
            "recreation_outdoors": {
                "score": recreation_score,
                "weight": default_weights["recreation_outdoors"],
                "contribution": round(recreation_score * default_weights["recreation_outdoors"] / 100, 2),
                "breakdown": recreation_details["breakdown"],
                "summary": recreation_details["summary"]
            },
            "neighborhood_charm": {
                "score": charm_score,
                "weight": default_weights["neighborhood_charm"],
                "contribution": round(charm_score * default_weights["neighborhood_charm"] / 100, 2),
                "breakdown": charm_details["breakdown"],
                "summary": charm_details["summary"]
            },
            "walkable_town": {
                "score": walkable_score,
                "weight": default_weights["walkable_town"],
                "contribution": round(walkable_score * default_weights["walkable_town"] / 100, 2),
                "breakdown": walkable_details["breakdown"],
                "summary": walkable_details["summary"]
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
            "version": "2.0.0",
            "architecture": "Refactored pillars: Recreation & Outdoors + Neighborhood Charm",
            "pillars": {
                "schools": "Quality and variety of nearby schools (Elementary, Middle, High)",
                "recreation_outdoors": "Parks, playgrounds, beaches, trails, and outdoor activities",
                "neighborhood_charm": "Tree canopy, historic architecture, and public art",
                "walkable_town": "Indie businesses, downtown walkability, and local character",
                "housing_value": "Housing affordability and space relative to local income"
            },
            "data_sources": [
                "Nominatim (geocoding)",
                "SchoolDigger API (schools)",
                "OpenStreetMap Overpass API (recreation, charm, walkability)",
                "Census Bureau (tree canopy, housing)",
                "NYC Open Data (street trees)"
            ],
            "note": "Total score = weighted average of pillars. Weights can be customized in scoring layer."
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
        "recreation": "✅ OpenStreetMap (no credentials required)",
        "charm": "✅ OpenStreetMap (no credentials required)",
        "census": "❌ Census API key missing",
        "nyc_trees": "✅ NYC Open Data (no credentials required)"
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
        "version": "2.0.0",
        "architecture": "Refactored: Recreation & Outdoors + Neighborhood Charm pillars",
        "pillars": ["schools", "recreation_outdoors", "neighborhood_charm", "walkable_town", "housing_value"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)