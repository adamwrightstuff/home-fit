#!/usr/bin/env python3
"""
Debug the climate_risk pillar for a location. Prints raw GEE outputs and final score.

Usage:
  python scripts/debug_climate_risk.py "Larchmont, NY"
  python scripts/debug_climate_risk.py 40.9279 -73.7518
"""
import os
import sys

# Run from repo root so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_climate_risk.py <location>")
        print("   or: python scripts/debug_climate_risk.py <lat> <lon>")
        sys.exit(1)

    if len(sys.argv) >= 3:
        try:
            lat = float(sys.argv[1])
            lon = float(sys.argv[2])
            label = f"{lat},{lon}"
        except ValueError:
            print("Lat/lon must be numbers")
            sys.exit(1)
    else:
        location = sys.argv[1]
        from data_sources.geocoding import geocode
        result = geocode(location)
        if not result:
            print(f"No geocode result for: {location}")
            sys.exit(1)
        lat, lon, zip_code, state, city = result
        label = f"{city}, {state}" if (city or state) else location
        print(f"Geocoded: {label} -> {lat}, {lon}\n")

    print("GEE_AVAILABLE:", "GOOGLE_APPLICATION_CREDENTIALS set" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") else ("GOOGLE_APPLICATION_CREDENTIALS_JSON set" if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON") else "not set"))
    from data_sources.gee_api import GEE_AVAILABLE, get_heat_exposure_lst, get_air_quality_aer_ai
    print("GEE_AVAILABLE =", GEE_AVAILABLE)
    print()

    print("--- get_heat_exposure_lst(lat, lon) ---")
    heat = get_heat_exposure_lst(lat, lon)
    print("heat_data:", heat)
    print()

    print("--- get_air_quality_aer_ai(lat, lon) ---")
    air = get_air_quality_aer_ai(lat, lon)
    print("air_data:", air)
    print()

    print("--- get_climate_risk_score(lat, lon) ---")
    from pillars.climate_risk import get_climate_risk_score
    score, details = get_climate_risk_score(lat, lon)
    print("score:", score)
    print("summary:", details.get("summary"))
    print("breakdown:", details.get("breakdown"))
    print("data_quality:", details.get("data_quality"))
    print()
    print("Done. If score is 0, check heat_data/air_data above and server logs for 'Climate risk score 0 with data'.")


if __name__ == "__main__":
    main()
