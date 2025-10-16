from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Optional
import os

from modules.geoclient import geocode
from modules.schools import get_school_data
from modules.green_neighborhood import get_green_neighborhood_score
from modules.nature_access import get_nature_access_score

# Load environment variables
load_dotenv()

app = FastAPI(
    title="HomeFit API",
    description="Geospatial livability scoring API with multiple pillars",
    version="1.0.0"
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
        "version": "1.0.0",
        "pillars": ["schools", "green_neighborhood", "nature_access"],
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
    - Green Neighborhood: Parks, playgrounds, daily green space
    - Nature Access: Wilderness, water, outdoor recreation
    
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
    school_avg, schools_by_level = get_school_data(
        zip_code=zip_code,
        state=state,
        city=city
    )
    
    # Green Neighborhood pillar
    green_score, green_details = get_green_neighborhood_score(lat, lon)
    
    # Nature Access pillar
    nature_score, nature_details = get_nature_access_score(lat, lon)
    
    # Step 3: Calculate weighted total (default weights)
    default_weights = {
        "schools": 50,
        "green_neighborhood": 30,
        "nature_access": 20
    }
    
    total_score = (
        (school_avg * default_weights["schools"] / 100) +
        (green_score * default_weights["green_neighborhood"] / 100) +
        (nature_score * default_weights["nature_access"] / 100)
    )
    
    print(f"\n{'='*60}")
    print(f"🎯 Final Livability Score: {total_score:.1f}/100")
    print(f"{'='*60}")
    print(f"   🎓 Schools: {school_avg:.1f}/100 (weight: {default_weights['schools']}%)")
    print(f"   🏘️  Green Neighborhood: {green_score:.1f}/100 (weight: {default_weights['green_neighborhood']}%)")
    print(f"   🏔️  Nature Access: {nature_score:.1f}/100 (weight: {default_weights['nature_access']}%)")
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
            "green_neighborhood": {
                "score": green_score,
                "weight": default_weights["green_neighborhood"],
                "contribution": round(green_score * default_weights["green_neighborhood"] / 100, 2),
                "breakdown": green_details["breakdown"],
                "summary": green_details["summary"]
            },
            "nature_access": {
                "score": nature_score,
                "weight": default_weights["nature_access"],
                "contribution": round(nature_score * default_weights["nature_access"] / 100, 2),
                "breakdown": nature_details["breakdown"],
                "summary": nature_details["summary"]
            }
        },
        "total_score": round(total_score, 2),
        "default_weights": default_weights,
        "metadata": {
            "version": "1.0.0",
            "pillars": {
                "schools": "Quality and variety of nearby schools (Elementary, Middle, High)",
                "green_neighborhood": "Parks, playgrounds, and green spaces within walking distance (1km)",
                "nature_access": "Wilderness, water, and outdoor recreation within day-trip distance (10km)"
            },
            "data_sources": [
                "Nominatim (geocoding)",
                "SchoolDigger API (schools)",
                "OpenStreetMap Overpass API (green spaces & nature)"
            ],
            "note": "Total score = weighted average of pillars. Default weights: Schools 50%, Green Neighborhood 30%, Nature Access 20%"
        }
    }
    
    return response


@app.get("/health")
def health_check():
    """Detailed health check with API credential validation."""
    checks = {
        "geocoding": "✅ Nominatim (no credentials required)",
        "schools": "❌ SchoolDigger credentials missing",
        "green_spaces": "✅ OpenStreetMap (no credentials required)",
        "nature": "✅ OpenStreetMap (no credentials required)"
    }
    
    # Check SchoolDigger credentials
    if os.getenv("SCHOOLDIGGER_APPID") and os.getenv("SCHOOLDIGGER_APPKEY"):
        checks["schools"] = "✅ SchoolDigger credentials configured"
    
    return {
        "status": "healthy",
        "checks": checks,
        "version": "1.0.0",
        "pillars": ["schools", "green_neighborhood", "nature_access"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)