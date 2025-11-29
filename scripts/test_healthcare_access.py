#!/usr/bin/env python3
"""
Test script for healthcare access pillar.

Usage:
    python scripts/test_healthcare_access.py "1600 Pennsylvania Avenue NW, Washington, DC"
    python scripts/test_healthcare_access.py "40.7128,-74.0060"  # lat,lon format
    python scripts/test_healthcare_access.py "40.7128,-74.0060" --area-type urban_core --location-scope neighborhood
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.geocoding import geocode_with_full_result
from data_sources.data_quality import detect_area_type, detect_location_scope
from data_sources import census_api
from pillars.healthcare_access import get_healthcare_access_score


def parse_location(location_str: str):
    """Parse location string - either address or lat,lon coordinates."""
    if ',' in location_str and not any(c.isalpha() for c in location_str.split(',')[0]):
        # Looks like coordinates
        try:
            lat, lon = map(float, location_str.split(','))
            return lat, lon, None
        except ValueError:
            raise ValueError(f"Invalid coordinate format: {location_str}")
    else:
        # Assume it's an address
        geo_result = geocode_with_full_result(location_str)
        if not geo_result:
            raise ValueError(f"Could not geocode: {location_str}")
        lat, lon, zip_code, state, city, geocode_data = geo_result
        return lat, lon, geocode_data


def get_area_type_and_scope(lat: float, lon: float, geocode_data=None):
    """Get area_type and location_scope for a location."""
    # Get population density (needed for area_type detection)
    density = census_api.get_population_density(lat, lon) or 0.0
    
    # Detect area type
    area_type = detect_area_type(lat, lon, density=density)
    
    # Detect location scope
    location_scope = detect_location_scope(lat, lon, geocode_data)
    
    return area_type, location_scope


def test_healthcare_access(location: str, area_type: str = None, location_scope: str = None):
    """
    Test healthcare access pillar for a given location.
    
    Args:
        location: Address string or "lat,lon" coordinates
        area_type: Optional area type (urban_core, suburban, exurban, rural)
                   If not provided, will be auto-detected
        location_scope: Optional location scope (neighborhood, city, etc.)
                       If not provided, will be auto-detected
    """
    print(f"📍 Testing healthcare access for: {location}\n")
    
    # Parse location
    lat, lon, geocode_data = parse_location(location)
    print(f"   Coordinates: {lat}, {lon}")
    
    # Get area_type and location_scope if not provided
    if area_type is None or location_scope is None:
        detected_area_type, detected_location_scope = get_area_type_and_scope(lat, lon, geocode_data)
        if area_type is None:
            area_type = detected_area_type
        if location_scope is None:
            location_scope = detected_location_scope
    
    print(f"   Area type: {area_type}")
    print(f"   Location scope: {location_scope}\n")
    
    # Call healthcare access pillar
    print("=" * 60)
    score, breakdown = get_healthcare_access_score(
        lat=lat,
        lon=lon,
        area_type=area_type,
        location_scope=location_scope
    )
    print("=" * 60)
    
    # Display results
    print(f"\n🏥 Healthcare Access Score: {score:.1f}/100\n")
    print("Breakdown:")
    print(f"  Hospital Access: {breakdown.get('hospital_score', 0):.1f}/35")
    print(f"  Primary Care: {breakdown.get('primary_care_score', 0):.1f}/25")
    print(f"  Specialized Care: {breakdown.get('specialty_score', 0):.1f}/15")
    print(f"  Emergency Services: {breakdown.get('emergency_score', 0):.1f}/10")
    print(f"  Pharmacies: {breakdown.get('pharmacy_score', 0):.1f}/15")
    
    if 'bonus_score' in breakdown:
        print(f"  Bonus: {breakdown.get('bonus_score', 0):.1f}")
    
    # Show facility counts if available
    if 'facilities' in breakdown:
        facilities = breakdown['facilities']
        print(f"\nFacilities Found:")
        print(f"  Hospitals: {len(facilities.get('hospitals', []))}")
        print(f"  Urgent Care: {len(facilities.get('urgent_care', []))}")
        print(f"  Clinics: {len(facilities.get('clinics', []))}")
        print(f"  Doctors: {len(facilities.get('doctors', []))}")
        print(f"  Pharmacies: {len(facilities.get('pharmacies', []))}")
    
    # Show nearest hospital if available
    if 'nearest_hospital' in breakdown and breakdown['nearest_hospital']:
        nearest = breakdown['nearest_hospital']
        print(f"\nNearest Hospital:")
        print(f"  Name: {nearest.get('name', 'Unknown')}")
        print(f"  Distance: {nearest.get('distance_km', 0):.1f} km")
    
    return score, breakdown


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test healthcare access pillar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with address (auto-detect area_type and location_scope)
  python scripts/test_healthcare_access.py "1600 Pennsylvania Avenue NW, Washington, DC"
  
  # Test with coordinates
  python scripts/test_healthcare_access.py "40.7128,-74.0060"
  
  # Test with explicit area_type and location_scope
  python scripts/test_healthcare_access.py "40.7128,-74.0060" --area-type urban_core --location-scope neighborhood
        """
    )
    
    parser.add_argument(
        "location",
        help="Address or coordinates (lat,lon format)"
    )
    parser.add_argument(
        "--area-type",
        choices=["urban_core", "suburban", "exurban", "rural"],
        help="Area type (if not provided, will be auto-detected)"
    )
    parser.add_argument(
        "--location-scope",
        help="Location scope (if not provided, will be auto-detected)"
    )
    
    args = parser.parse_args()
    
    try:
        test_healthcare_access(
            args.location,
            area_type=args.area_type,
            location_scope=args.location_scope
        )
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

