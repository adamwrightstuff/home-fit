from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import time
import asyncio
from typing import Dict, Optional

# UPDATED IMPORTS - 8 Purpose-Driven Pillars
from logging_config import setup_logging, get_logger, log_api_call, log_pillar_calculation, log_error, log_performance
from data_sources.async_geocoding import geocode_async
from data_sources.cache import clear_cache, get_cache_stats, cleanup_expired_cache
from data_sources.error_handling import check_api_credentials, get_fallback_score
from data_sources.telemetry import record_request_metrics, record_error, get_telemetry_stats
from pillars.schools import get_school_data
from pillars.active_outdoors import get_active_outdoors_score
from pillars.neighborhood_beauty import get_neighborhood_beauty_score
from pillars.neighborhood_beauty_enhanced import get_enhanced_neighborhood_beauty_score
from pillars.walkable_town import get_walkable_town_score
from pillars.air_travel_access import get_air_travel_score
from pillars.public_transit_access import get_public_transit_score
from pillars.healthcare_access import get_healthcare_access_score
from pillars.housing_value import get_housing_value_score

##########################
# CONFIGURATION FLAGS
##########################
ENABLE_SCHOOL_SCORING = False  # Set to True to enable school API calls
ENABLE_ENHANCED_BEAUTY = True  # Set to True to use enhanced neighborhood beauty scoring

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(level="INFO", json_format=True)
logger = get_logger(__name__)

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
async def get_livability_score(location: str):
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
    start_time = time.time()
    request_id = f"req_{int(start_time * 1000)}"
    
    logger.info(f"Starting livability score request", extra={
        "request_id": request_id,
        "location": location
    })

    # Step 1: Geocode the location
    geo_result = await geocode_async(location)

    if not geo_result:
        logger.error(f"Geocoding failed for location: {location}", extra={
            "request_id": request_id,
            "location": location
        })
        raise HTTPException(
            status_code=400,
            detail="Could not geocode the provided location. Please check the address."
        )

    lat, lon, zip_code, state, city = geo_result
    logger.info(f"Location geocoded successfully", extra={
        "request_id": request_id,
        "lat": lat,
        "lon": lon,
        "city": city,
        "state": state,
        "zip_code": zip_code
    })

    # Step 2: Calculate all pillar scores in parallel
    logger.info("Starting parallel pillar score calculations", extra={
        "request_id": request_id
    })

    # Create tasks for parallel execution
    tasks = [
        _calculate_pillar_score("active_outdoors", get_active_outdoors_score, lat, lon, city),
        _calculate_pillar_score("neighborhood_beauty", 
                               get_enhanced_neighborhood_beauty_score if ENABLE_ENHANCED_BEAUTY else get_neighborhood_beauty_score, 
                               lat, lon, city),
        _calculate_pillar_score("neighborhood_amenities", get_walkable_town_score, lat, lon),
        _calculate_pillar_score("air_travel_access", get_air_travel_score, lat, lon),
        _calculate_pillar_score("public_transit_access", get_public_transit_score, lat, lon),
        _calculate_pillar_score("healthcare_access", get_healthcare_access_score, lat, lon),
        _calculate_pillar_score("housing_value", get_housing_value_score, lat, lon),
    ]

    # Add school scoring task if enabled
    if ENABLE_SCHOOL_SCORING:
        tasks.append(_calculate_school_score(zip_code, state, city))
    else:
        # Use fallback for schools
        tasks.append(asyncio.create_task(_get_fallback_school_score()))

    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    pillar_scores = {}
    pillar_details = {}
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Pillar calculation failed: {result}", extra={
                "request_id": request_id,
                "pillar_index": i
            })
            # Use fallback score
            pillar_name = ["active_outdoors", "neighborhood_beauty", "neighborhood_amenities", 
                          "air_travel_access", "public_transit_access", "healthcare_access", 
                          "housing_value", "quality_education"][i]
            fallback_score, fallback_details = get_fallback_score(pillar_name, "Calculation error")
            pillar_scores[pillar_name] = fallback_score
            pillar_details[pillar_name] = fallback_details
        else:
            pillar_name, score, details = result
            pillar_scores[pillar_name] = score
            pillar_details[pillar_name] = details

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

    total_score = sum(
        pillar_scores.get(pillar, 0) * default_weights[pillar] / 100 
        for pillar in default_weights.keys()
    )

    response_time = time.time() - start_time
    
    logger.info(f"Livability score calculated", extra={
        "request_id": request_id,
        "total_score": round(total_score, 2),
        "response_time": round(response_time, 2),
        "pillar_scores": pillar_scores
    })

    # Build response with enhanced metadata
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
        "livability_pillars": _build_pillar_response(pillar_scores, pillar_details, default_weights),
        "total_score": round(total_score, 2),
        "default_weights": default_weights,
        "overall_confidence": _calculate_overall_confidence(_build_pillar_response(pillar_scores, pillar_details, default_weights)),
        "data_quality_summary": _calculate_data_quality_summary(_build_pillar_response(pillar_scores, pillar_details, default_weights)),
        "metadata": {
            "version": "3.0.0",
            "architecture": "8 Purpose-Driven Pillars",
            "request_id": request_id,
            "response_time_seconds": round(response_time, 2),
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

    # Record telemetry metrics
    try:
        record_request_metrics(location, lat, lon, response, response_time)
    except Exception as e:
        logger.error(f"Failed to record telemetry: {e}", extra={
            "request_id": request_id
        })

    return response


async def _calculate_pillar_score(pillar_name: str, score_func, *args):
    """Calculate score for a single pillar with error handling."""
    try:
        if asyncio.iscoroutinefunction(score_func):
            score, details = await score_func(*args)
        else:
            score, details = score_func(*args)
        return pillar_name, score, details
    except Exception as e:
        logger.error(f"Error calculating {pillar_name}: {e}")
        raise


async def _calculate_school_score(zip_code: str, state: str, city: str):
    """Calculate school score with async handling."""
    try:
        logger.info("Fetching school data from SchoolDigger API...")
        school_avg, schools_by_level = get_school_data(
            zip_code=zip_code,
            state=state,
            city=city
        )
        return "quality_education", school_avg, {
            "by_level": schools_by_level,
            "total_schools_rated": sum(len(schools_by_level.get(level, [])) for level in schools_by_level)
        }
    except Exception as e:
        logger.error(f"Error calculating school score: {e}")
        raise


async def _get_fallback_school_score():
    """Get fallback school score when school scoring is disabled."""
    logger.info("School scoring disabled (preserving API quota)")
    return "quality_education", 50, {
        "by_level": {
            "elementary": [],
            "middle": [],
            "high": []
        },
        "total_schools_rated": 0,
        "fallback_used": True,
        "reason": "School scoring disabled"
    }


def _build_pillar_response(pillar_scores: Dict, pillar_details: Dict, default_weights: Dict) -> Dict:
    """Build the livability_pillars response structure."""
    pillars = {}
    
    for pillar_name in default_weights.keys():
        score = pillar_scores.get(pillar_name, 0)
        details = pillar_details.get(pillar_name, {})
        weight = default_weights[pillar_name]
        
        pillars[pillar_name] = {
            "score": score,
            "weight": weight,
            "contribution": round(score * weight / 100, 2),
            "breakdown": details.get("breakdown", {}),
            "summary": details.get("summary", {}),
            "confidence": details.get("data_quality", {}).get("confidence", 0),
            "data_quality": details.get("data_quality", {}),
            "area_classification": details.get("area_classification", {})
        }
        
        # Add pillar-specific fields
        if pillar_name == "quality_education":
            pillars[pillar_name]["by_level"] = details.get("by_level", {})
            pillars[pillar_name]["total_schools_rated"] = details.get("total_schools_rated", 0)
        elif pillar_name == "air_travel_access":
            pillars[pillar_name]["primary_airport"] = details.get("primary_airport")
            pillars[pillar_name]["nearest_airports"] = details.get("nearest_airports", [])
        elif pillar_name == "neighborhood_beauty":
            pillars[pillar_name]["enhanced"] = ENABLE_ENHANCED_BEAUTY
            pillars[pillar_name]["scoring_note"] = details.get("scoring_note", "")
    
    return pillars


def _calculate_overall_confidence(pillars: dict) -> dict:
    """Calculate overall confidence metrics for the response."""
    confidences = []
    fallback_count = 0
    quality_tiers = []
    
    for pillar_name, pillar_data in pillars.items():
        confidence = pillar_data.get("confidence", 0)
        confidences.append(confidence)
        
        data_quality = pillar_data.get("data_quality", {})
        if data_quality.get("fallback_used", False):
            fallback_count += 1
        
        quality_tier = data_quality.get("quality_tier", "unknown")
        quality_tiers.append(quality_tier)
    
    # Calculate overall metrics
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    fallback_percentage = (fallback_count / len(pillars)) * 100
    
    # Quality tier distribution
    tier_counts = {}
    for tier in quality_tiers:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    return {
        "average_confidence": round(avg_confidence, 1),
        "pillars_using_fallback": fallback_count,
        "fallback_percentage": round(fallback_percentage, 1),
        "quality_tier_distribution": tier_counts,
        "overall_quality": "excellent" if avg_confidence >= 85 else "good" if avg_confidence >= 70 else "fair" if avg_confidence >= 50 else "poor"
    }


def _calculate_data_quality_summary(pillars: dict) -> dict:
    """Calculate data quality summary for the response."""
    data_sources_used = set()
    area_classifications = []
    
    for pillar_name, pillar_data in pillars.items():
        data_quality = pillar_data.get("data_quality", {})
        area_classification = pillar_data.get("area_classification", {})
        
        # Collect data sources
        sources = data_quality.get("data_sources", [])
        data_sources_used.update(sources)
        
        # Collect area classifications
        if area_classification:
            area_classifications.append(area_classification)
    
    # Get most common area classification
    if area_classifications:
        area_types = [ac.get("area_type", "unknown") for ac in area_classifications]
        most_common_area = max(set(area_types), key=area_types.count)
        metro_name = area_classifications[0].get("metro_name") if area_classifications else None
    else:
        most_common_area = "unknown"
        metro_name = None
    
    return {
        "data_sources_used": list(data_sources_used),
        "area_classification": {
            "type": most_common_area,
            "metro_name": metro_name
        },
        "total_pillars": len(pillars),
        "data_completeness": "high" if len(data_sources_used) >= 3 else "medium" if len(data_sources_used) >= 2 else "low"
    }


@app.get("/health")
def health_check():
    """Detailed health check with API credential validation."""
    credentials = check_api_credentials()
    cache_stats = get_cache_stats()
    
    # Clean up expired cache entries
    cleanup_expired_cache()
    
    checks = {
        "geocoding": "✅ Nominatim (no credentials required)",
        "schools": "✅ SchoolDigger credentials configured" if credentials["schools"] else "❌ SchoolDigger credentials missing",
        "osm": "✅ OpenStreetMap (no credentials required)",
        "census": "✅ Census API key configured" if credentials["census"] else "❌ Census API key missing",
        "nyc_trees": "✅ NYC Open Data (no credentials required)",
        "airports": "✅ OurAirports database (static data)",
        "transit": "✅ Transitland API (no credentials required)"
    }

    return {
        "status": "healthy",
        "checks": checks,
        "cache_stats": cache_stats,
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


@app.post("/cache/clear")
def clear_cache_endpoint(cache_type: str = None):
    """Clear cache entries."""
    try:
        clear_cache(cache_type)
        return {
            "status": "success",
            "message": f"Cache cleared for {cache_type or 'all'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {e}")


@app.get("/cache/stats")
def cache_stats_endpoint():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache stats failed: {e}")


@app.get("/telemetry")
def telemetry_endpoint():
    """Get telemetry and analytics data."""
    try:
        stats = get_telemetry_stats()
        return {
            "status": "success",
            "telemetry": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telemetry failed: {e}")


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize async resources on startup."""
    logger.info("Starting HomeFit API server")
    # Initialize any async resources here if needed


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up async resources on shutdown."""
    logger.info("Shutting down HomeFit API server")
    # Close async sessions
    from data_sources.async_geocoding import close_session as close_geocoding_session
    from data_sources.async_osm_api import close_session as close_osm_session
    from data_sources.async_census_api import close_session as close_census_session
    
    await close_geocoding_session()
    await close_osm_session()
    await close_census_session()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
