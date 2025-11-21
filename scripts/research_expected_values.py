#!/usr/bin/env python3
"""
Research Data Collection Script for Expected Values

This script samples locations across area types and queries OSM/Census data
to calculate research-backed expected values for all HomeFit pillars.

Usage:
    python scripts/research_expected_values.py [--sample-size N] [--output-dir DIR]
"""

import sys
import os
import csv
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources import geocoding, osm_api
from data_sources.data_quality import detect_area_type
from data_sources.census_api import get_population_density
from pillars.public_transit_access import get_public_transit_score

# Sample locations by area type (from test cases + known benchmarks)
SAMPLE_LOCATIONS = {
    'urban_core': [
        "Park Slope Brooklyn NY",
        "Williamsburg Brooklyn NY",
        "West Village Manhattan NY",
        "North Beach San Francisco CA",
        "Old Town Pasadena CA",
        "Downtown Boulder CO",
        "Pearl District Portland OR",
        "Downtown Santa Monica CA",
        "Gaslamp Quarter San Diego CA",
        "Downtown Charleston SC",
        "Downtown Savannah GA",
        "Downtown Asheville NC",
        "Old Town Alexandria VA",
        "Downtown Annapolis MD",
        "Downtown Burlington VT",
        "Downtown Madison WI",
        "Downtown Greenville SC",
        "Upper West Side New York NY",
        "Times Square NY",
        "Downtown Phoenix AZ",
    ],
    'suburban': [
        "Main Street Bozeman MT",
        "Downtown Traverse City MI",
        "Downtown Bend OR",
        "Main Street Park City UT",
        "Downtown Durango CO",
        "Downtown Jackson WY",
        "Downtown Telluride CO",
        "Downtown Sun Valley ID",
        "Downtown Aspen CO",
        "Downtown Carmel CA",
        "Downtown Sausalito CA",
        "Downtown Healdsburg CA",
        "Downtown St Helena CA",
        "Downtown Sonoma CA",
        "Downtown Napa CA",
        "Downtown Monterey CA",
        "Downtown Ojai CA",
        "Downtown Sedona AZ",
        "Downtown Taos NM",
        "Downtown Key West FL",
        "Downtown Marblehead MA",
        "Downtown Newport RI",
        "Downtown Bar Harbor ME",
        "Downtown Camden ME",
        "Downtown Edgartown MA",
        "Downtown Las Vegas NV",
    ],
    'exurban': [
        "Park City UT",
        "Healdsburg CA",
        "Carson City NV",
        "Augusta ME",
        "Bismarck ND",
        "Carmel-by-the-Sea CA",
        "Aspen CO",
        "Telluride CO",
        "Cody WY",
        "Pierre SD",
        "Montpelier VT",
    ],
    'rural': [
        "Bar Harbor ME",
        "Cody WY",
        "Pierre SD",
        "Montpelier VT",
        "Juneau AK",
        "Carson City NV",
        "Bismarck ND",
        "Augusta ME",
        "Telluride CO",
        "Jackson WY",
    ]
}


def geocode_location(location: str) -> Optional[Tuple[float, float, str]]:
    """Geocode a location and return (lat, lon, city)."""
    try:
        result = geocoding.geocode_with_full_result(location)
        if result and isinstance(result, tuple) and len(result) >= 6:
            # geocode_with_full_result returns: (lat, lon, zip_code, state, city, full_result)
            lat, lon, zip_code, state, city, full_result = result
            if lat and lon:
                return (
                    lat,
                    lon,
                    city or location.split(',')[0] if ',' in location else location
                )
        elif result and isinstance(result, dict):
            # Fallback for dict format (shouldn't happen but handle it)
            if result.get('lat') and result.get('lon'):
                return (
                    result['lat'],
                    result['lon'],
                    result.get('city', location.split(',')[0] if ',' in location else location)
                )
    except Exception as e:
        print(f"  ⚠️  Geocoding failed for {location}: {e}")
    return None


def collect_active_outdoors_data(lat: float, lon: float, area_type: str) -> Dict:
    """Collect Active Outdoors pillar data."""
    data = {
        'parks_1km': 0,
        'playgrounds_1km': 0,
        'park_area_hectares': 0.0,
        'trails_15km': 0,
        'water_15km': 0,
        'camping_15km': 0,
        'closest_water_km': None,
    }
    
    try:
        # Query parks within 1km
        green_spaces = osm_api.query_green_spaces(lat, lon, radius_m=1000)
        if green_spaces:
            parks = green_spaces.get('parks', [])
            playgrounds = green_spaces.get('playgrounds', [])
            data['parks_1km'] = len(parks)
            data['playgrounds_1km'] = len(playgrounds)
            
            # Calculate total park area
            total_area_sqm = sum(p.get('area_sqm', 0) for p in parks)
            data['park_area_hectares'] = total_area_sqm / 10000
        
        # Query nature features within 15km
        nature_features = osm_api.query_nature_features(lat, lon, radius_m=15000)
        if nature_features:
            data['trails_15km'] = len(nature_features.get('hiking', []))
            data['water_15km'] = len(nature_features.get('swimming', []))
            data['camping_15km'] = len(nature_features.get('camping', []))
            
            # Find closest water
            swimming = nature_features.get('swimming', [])
            if swimming:
                closest = min(swimming, key=lambda x: x.get('distance_m', float('inf')))
                data['closest_water_km'] = closest.get('distance_m', 0) / 1000
        
    except Exception as e:
        print(f"    ⚠️  Active Outdoors query failed: {e}")
    
    return data


def collect_healthcare_data(lat: float, lon: float, area_type: str) -> Dict:
    """Collect Healthcare Access pillar data."""
    data = {
        # Use radii that match healthcare_access expectations:
        # - expected_hospitals_within_10km
        # - expected_urgent_care_within_5km
        # - expected_pharmacies_within_2km
        "hospitals_10km": 0,
        "urgent_care_5km": 0,
        "pharmacies_2km": 0,
        "clinics_5km": 0,
        "doctors_5km": 0,
        "closest_hospital_km": None,
    }
    
    try:
        # Query healthcare facilities (20km radius, then filter by distance_km)
        # This matches how the healthcare pillar uses distance_km in scoring.
        healthcare = osm_api.query_healthcare_facilities(lat, lon, radius_m=20000)
        if healthcare:
            hospitals = healthcare.get("hospitals", [])
            urgent_care = healthcare.get("urgent_care", [])
            pharmacies = healthcare.get("pharmacies", [])
            clinics = healthcare.get("clinics", [])
            doctors = healthcare.get("doctors", [])

            # Filter by distance to match pillar expectations
            data["hospitals_10km"] = len([h for h in hospitals if h.get("distance_km", 999) <= 10])
            data["urgent_care_5km"] = len([u for u in urgent_care if u.get("distance_km", 999) <= 5])
            data["pharmacies_2km"] = len([p for p in pharmacies if p.get("distance_km", 999) <= 2])
            data["clinics_5km"] = len([c for c in clinics if c.get("distance_km", 999) <= 5])
            data["doctors_5km"] = len([d for d in doctors if d.get("distance_km", 999) <= 5])

            # Find closest hospital
            if hospitals:
                closest = min(hospitals, key=lambda x: x.get("distance_km", float("inf")))
                data["closest_hospital_km"] = closest.get("distance_km")
        
    except Exception as e:
        print(f"    ⚠️  Healthcare query failed: {e}")
    
    return data


def collect_amenities_data(lat: float, lon: float, area_type: str) -> Dict:
    """Collect Neighborhood Amenities pillar data."""
    data = {
        'businesses_1km': 0,
        'business_types': 0,
        'restaurants_1km': 0,
        'median_distance_m': None,
    }
    
    try:
        # Query businesses within 1km
        business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
        if business_data:
            all_businesses = (
                business_data.get('tier1_daily', []) +
                business_data.get('tier2_social', []) +
                business_data.get('tier3_culture', []) +
                business_data.get('tier4_services', [])
            )
            
            data['businesses_1km'] = len(all_businesses)
            
            # Count unique business types
            business_types = set()
            for biz in all_businesses:
                biz_type = biz.get('type') or biz.get('amenity') or biz.get('shop')
                if biz_type:
                    business_types.add(biz_type)
            data['business_types'] = len(business_types)
            
            # Count restaurants (cafe, restaurant, fast_food, etc.)
            restaurants = [
                b for b in all_businesses
                if any(keyword in str(b.get('type', '')).lower() or 
                       keyword in str(b.get('amenity', '')).lower()
                       for keyword in ['restaurant', 'cafe', 'food', 'dining'])
            ]
            data['restaurants_1km'] = len(restaurants)
            
            # Calculate median distance
            distances = [b.get('distance_m', 0) for b in all_businesses if b.get('distance_m')]
            if distances:
                data['median_distance_m'] = statistics.median(distances)
        
    except Exception as e:
        print(f"    ⚠️  Amenities query failed: {e}")
    
    return data


def collect_transit_data(lat: float, lon: float, area_type: str, city: Optional[str]) -> Dict:
    """Collect Public Transit Access pillar data using the existing pillar logic.

    This is research-only and does not change scoring; it just records the
    same raw metrics the pillar already exposes (counts and subscores).
    """
    data: Dict[str, Optional[float]] = {
        "transit_score": None,
        "heavy_rail_score": None,
        "light_rail_score": None,
        "bus_score": None,
        "commute_time_score": None,
        "total_stops": None,
        "heavy_rail_stops": None,
        "light_rail_stops": None,
        "bus_stops": None,
        "mean_commute_minutes": None,
        "transit_modes_count": None,
    }

    try:
        score, breakdown = get_public_transit_score(
            lat,
            lon,
            area_type=area_type,
            location_scope="city",
            city=city,
        )
        data["transit_score"] = score

        bd = breakdown.get("breakdown", {}) if isinstance(breakdown, dict) else {}
        sm = breakdown.get("summary", {}) if isinstance(breakdown, dict) else {}

        data["heavy_rail_score"] = bd.get("heavy_rail")
        data["light_rail_score"] = bd.get("light_rail")
        data["bus_score"] = bd.get("bus")
        data["commute_time_score"] = bd.get("commute_time")

        data["total_stops"] = sm.get("total_stops")
        data["heavy_rail_stops"] = sm.get("heavy_rail_stops")
        data["light_rail_stops"] = sm.get("light_rail_stops")
        data["bus_stops"] = sm.get("bus_stops")

        # Commute minutes are logged in summary if available
        data["mean_commute_minutes"] = sm.get("mean_commute_minutes")

        modes = sm.get("transit_modes_available") or []
        if isinstance(modes, list):
            data["transit_modes_count"] = len(modes)
        else:
            data["transit_modes_count"] = None
    except Exception as e:
        print(f"    ⚠️  Transit data collection failed: {e}")

    return data


def collect_location_data(location: str, area_type: str, pillars: List[str]) -> Optional[Dict]:
    """Collect all data for a single location for the requested pillars."""
    print(f"\n📍 Processing: {location} ({area_type})")
    
    # Geocode
    geocode_result = geocode_location(location)
    if not geocode_result:
        return None
    
    lat, lon, city = geocode_result
    print(f"   Coordinates: {lat}, {lon}")
    
    # Verify area type (optional - use provided or detect)
    detected_type = detect_area_type(lat, lon, city=city)
    if detected_type != area_type:
        print(f"   ⚠️  Area type mismatch: provided={area_type}, detected={detected_type}")
    
    # Get population density
    density = get_population_density(lat, lon)
    
    # Collect data for each requested pillar
    active_outdoors = None
    healthcare = None
    amenities = None
    transit = None

    if "active_outdoors" in pillars or "all" in pillars:
        print(f"   🏞️  Collecting Active Outdoors data...")
        active_outdoors = collect_active_outdoors_data(lat, lon, area_type)
        time.sleep(3)  # Rate limiting - longer delay for OSM

    if "healthcare" in pillars or "all" in pillars:
        print(f"   🏥 Collecting Healthcare data...")
        healthcare = collect_healthcare_data(lat, lon, area_type)
        time.sleep(3)  # Rate limiting

    if "amenities" in pillars or "all" in pillars:
        print(f"   🍽️  Collecting Amenities data...")
        amenities = collect_amenities_data(lat, lon, area_type)
        time.sleep(3)  # Rate limiting

    if "transit" in pillars or "all" in pillars:
        print(f"   🚇 Collecting Transit data...")
        transit = collect_transit_data(lat, lon, area_type, city)
        # Transitland / Census are separate APIs; keep same pacing to be safe
        time.sleep(3)

    return {
        "location": location,
        "city": city,
        "lat": lat,
        "lon": lon,
        "area_type": area_type,
        "detected_area_type": detected_type,
        "density": density,
        "active_outdoors": active_outdoors,
        "healthcare": healthcare,
        "amenities": amenities,
        "transit": transit,
    }


def calculate_statistics(data_by_area_type: Dict[str, List[Dict]]) -> Dict:
    """Calculate medians and percentiles for each area type."""
    stats = {}
    
    for area_type, locations in data_by_area_type.items():
        if not locations:
            continue
        
        print(f"\n📊 Calculating statistics for {area_type} (n={len(locations)})")
        
        # Active Outdoors stats (only for locations where we collected that pillar)
        ao_locations = [l for l in locations if l.get("active_outdoors")]
        parks_1km = [l["active_outdoors"]["parks_1km"] for l in ao_locations]
        playgrounds_1km = [l["active_outdoors"]["playgrounds_1km"] for l in ao_locations]
        park_area = [l["active_outdoors"]["park_area_hectares"] for l in ao_locations]
        trails_15km = [l["active_outdoors"]["trails_15km"] for l in ao_locations]
        water_15km = [l["active_outdoors"]["water_15km"] for l in ao_locations]
        camping_15km = [l["active_outdoors"]["camping_15km"] for l in ao_locations]
        closest_water = [
            l["active_outdoors"]["closest_water_km"]
            for l in ao_locations
            if l["active_outdoors"]["closest_water_km"] is not None
        ]

        # Healthcare stats (for locations where we collected that pillar)
        hc_locations = [l for l in locations if l.get("healthcare")]
        hospitals_10km = [l["healthcare"]["hospitals_10km"] for l in hc_locations]
        pharmacies_2km = [l["healthcare"]["pharmacies_2km"] for l in hc_locations]
        clinics_5km = [l["healthcare"]["clinics_5km"] for l in hc_locations]
        closest_hospital = [
            l["healthcare"]["closest_hospital_km"]
            for l in hc_locations
            if l["healthcare"]["closest_hospital_km"] is not None
        ]

        # Amenities stats (for locations where we collected that pillar)
        am_locations = [l for l in locations if l.get("amenities")]
        businesses_1km = [l["amenities"]["businesses_1km"] for l in am_locations]
        business_types = [l["amenities"]["business_types"] for l in am_locations]
        restaurants_1km = [l["amenities"]["restaurants_1km"] for l in am_locations]
        median_distance = [
            l["amenities"]["median_distance_m"]
            for l in am_locations
            if l["amenities"]["median_distance_m"] is not None
        ]

        # Public Transit stats (for locations where we collected that pillar)
        tr_locations = [l for l in locations if l.get("transit")]
        transit_scores = [l["transit"]["transit_score"] for l in tr_locations if l["transit"]["transit_score"] is not None]
        heavy_scores = [l["transit"]["heavy_rail_score"] for l in tr_locations if l["transit"]["heavy_rail_score"] is not None]
        light_scores = [l["transit"]["light_rail_score"] for l in tr_locations if l["transit"]["light_rail_score"] is not None]
        bus_scores = [l["transit"]["bus_score"] for l in tr_locations if l["transit"]["bus_score"] is not None]
        commute_scores = [
            l["transit"]["commute_time_score"]
            for l in tr_locations
            if l["transit"]["commute_time_score"] is not None
        ]
        total_stops = [l["transit"]["total_stops"] for l in tr_locations if l["transit"]["total_stops"] is not None]
        heavy_stops = [l["transit"]["heavy_rail_stops"] for l in tr_locations if l["transit"]["heavy_rail_stops"] is not None]
        light_stops = [l["transit"]["light_rail_stops"] for l in tr_locations if l["transit"]["light_rail_stops"] is not None]
        bus_stops = [l["transit"]["bus_stops"] for l in tr_locations if l["transit"]["bus_stops"] is not None]
        commute_minutes = [
            l["transit"]["mean_commute_minutes"]
            for l in tr_locations
            if l["transit"]["mean_commute_minutes"] is not None
        ]
        modes_count = [
            l["transit"]["transit_modes_count"]
            for l in tr_locations
            if l["transit"]["transit_modes_count"] is not None
        ]
        
        def calc_stats(values):
            if not values:
                return None
            return {
                'median': statistics.median(values),
                'p25': statistics.quantiles(values, n=4)[0] if len(values) > 1 else values[0],
                'p75': statistics.quantiles(values, n=4)[2] if len(values) > 1 else values[0],
                'min': min(values),
                'max': max(values),
                'count': len(values),
            }
        
        stats[area_type] = {
            "sample_size": len(locations),
            "active_outdoors": {
                "parks_1km": calc_stats(parks_1km),
                "playgrounds_1km": calc_stats(playgrounds_1km),
                "park_area_hectares": calc_stats(park_area),
                "trails_15km": calc_stats(trails_15km),
                "water_15km": calc_stats(water_15km),
                "camping_15km": calc_stats(camping_15km),
                "closest_water_km": calc_stats(closest_water),
            },
            "healthcare": {
                "hospitals_10km": calc_stats(hospitals_10km),
                "pharmacies_2km": calc_stats(pharmacies_2km),
                "clinics_5km": calc_stats(clinics_5km),
                "closest_hospital_km": calc_stats(closest_hospital),
            },
            "amenities": {
                "businesses_1km": calc_stats(businesses_1km),
                "business_types": calc_stats(business_types),
                "restaurants_1km": calc_stats(restaurants_1km),
                "median_distance_m": calc_stats(median_distance),
            },
            "transit": {
                "transit_score": calc_stats(transit_scores),
                "heavy_rail_score": calc_stats(heavy_scores),
                "light_rail_score": calc_stats(light_scores),
                "bus_score": calc_stats(bus_scores),
                "commute_time_score": calc_stats(commute_scores),
                "total_stops": calc_stats(total_stops),
                "heavy_rail_stops": calc_stats(heavy_stops),
                "light_rail_stops": calc_stats(light_stops),
                "bus_stops": calc_stats(bus_stops),
                "mean_commute_minutes": calc_stats(commute_minutes),
                "transit_modes_count": calc_stats(modes_count),
            },
        }
    
    return stats


def export_results(stats: Dict, raw_data: Dict, output_dir: Path):
    """Export results to JSON and CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export statistics
    stats_file = output_dir / 'expected_values_statistics.json'
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\n✅ Exported statistics to {stats_file}")
    
    # Export raw data
    raw_file = output_dir / 'expected_values_raw_data.json'
    with open(raw_file, 'w') as f:
        json.dump(raw_data, f, indent=2)
    print(f"✅ Exported raw data to {raw_file}")
    
    # Export summary CSV
    csv_file = output_dir / 'expected_values_summary.csv'
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Area Type", "Metric", "Median", "P25", "P75", "Min", "Max", "Sample Size"]
        )
        
        for area_type, area_stats in stats.items():
            # Active Outdoors
            for metric, values in area_stats["active_outdoors"].items():
                if values:
                    writer.writerow([
                        area_type, f'active_outdoors.{metric}',
                        values['median'], values['p25'], values['p75'],
                        values['min'], values['max'], values['count']
                    ])
            
            # Healthcare
            for metric, values in area_stats["healthcare"].items():
                if values:
                    writer.writerow([
                        area_type, f'healthcare.{metric}',
                        values['median'], values['p25'], values['p75'],
                        values['min'], values['max'], values['count']
                    ])
            
            # Amenities
            for metric, values in area_stats["amenities"].items():
                if values:
                    writer.writerow([
                        area_type, f'amenities.{metric}',
                        values['median'], values['p25'], values['p75'],
                        values['min'], values['max'], values['count']
                    ])

            # Transit
            for metric, values in area_stats.get("transit", {}).items():
                if values:
                    writer.writerow([
                        area_type, f"transit.{metric}",
                        values['median'], values['p25'], values['p75'],
                        values['min'], values['max'], values['count']
                    ])
    
    print(f"✅ Exported summary CSV to {csv_file}")


def main():
    parser = argparse.ArgumentParser(description="Research expected values for HomeFit pillars")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Limit sample size per area type (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="analysis/research_data",
        help="Output directory for results",
    )
    parser.add_argument(
        "--area-types",
        nargs="+",
        default=None,
        help="Specific area types to process (default: all)",
    )
    parser.add_argument(
        "--pillars",
        nargs="+",
        choices=["active_outdoors", "healthcare", "amenities", "transit", "all"],
        default=["active_outdoors", "healthcare", "amenities"],
        help=(
            "Which pillars to collect research data for. "
            "Default: active_outdoors healthcare amenities. "
            "Use 'transit' to collect Public Transit metrics, or 'all' for every pillar."
        ),
    )
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔬 HomeFit Expected Values Research")
    print("=" * 60)
    
    # Collect data for each area type
    data_by_area_type = defaultdict(list)
    all_raw_data = []

    area_types = args.area_types or SAMPLE_LOCATIONS.keys()
    
    for area_type in area_types:
        if area_type not in SAMPLE_LOCATIONS:
            print(f"⚠️  No sample locations for {area_type}")
            continue
        
        locations = SAMPLE_LOCATIONS[area_type]
        if args.sample_size:
            locations = locations[: args.sample_size]

        print(f"\n{'='*60}")
        print(f"Processing {area_type} ({len(locations)} locations)")
        print(f"{'='*60}")

        for location in locations:
            data = collect_location_data(location, area_type, args.pillars)
            if data:
                data_by_area_type[area_type].append(data)
                all_raw_data.append(data)

            # Rate limiting - longer delay between locations
            time.sleep(5)
    
    # Calculate statistics
    print(f"\n{'='*60}")
    print("Calculating Statistics")
    print(f"{'='*60}")
    
    stats = calculate_statistics(data_by_area_type)
    
    # Export results
    print(f"\n{'='*60}")
    print("Exporting Results")
    print(f"{'='*60}")
    
    export_results(stats, {
        'raw_data': all_raw_data,
        'statistics': stats,
        'sample_locations': SAMPLE_LOCATIONS,
    }, output_dir)
    
    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    
    for area_type, area_stats in stats.items():
        print(f"\n{area_type.upper()} (n={area_stats['sample_size']}):")

        ao = area_stats.get("active_outdoors", {})
        if ao.get("parks_1km"):
            print(
                f"  Parks (1km): median={ao['parks_1km']['median']:.1f}, "
                f"range=[{ao['parks_1km']['p25']:.1f}, {ao['parks_1km']['p75']:.1f}]"
            )

        hc = area_stats.get("healthcare", {})
        if hc.get("hospitals_10km"):
            print(f"  Hospitals (10km): median={hc['hospitals_10km']['median']:.1f}")

        am = area_stats.get("amenities", {})
        if am.get("businesses_1km"):
            print(f"  Businesses (1km): median={am['businesses_1km']['median']:.1f}")

        tr = area_stats.get("transit", {})
        if tr.get("total_stops"):
            print(
                f"  Transit routes (radius profile): median={tr['total_stops']['median']:.1f}"
            )
        if tr.get("transit_score"):
            print(
                f"  Transit score: median={tr['transit_score']['median']:.1f}, "
                f"p75={tr['transit_score']['p75']:.1f}"
            )
    
    print(f"\n✅ Research complete! Results saved to {output_dir}")


if __name__ == '__main__':
    main()
