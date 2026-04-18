#!/usr/bin/env python3
"""
Score one location via the API and print Status Signal and its breakdown (wealth, education, occupation, brand).
Run from project root with backend at http://localhost:8000:

  PYTHONPATH=. python3 scripts/score_status_signal.py "Tribeca, NY"
  PYTHONPATH=. python3 scripts/score_status_signal.py "Seattle, WA"
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    import requests
    from data_sources import census_api as _ca
    from pillars.status_signal import compute_status_signal_with_breakdown

    location = (sys.argv[1:] or ["Tribeca, NY"])[0].strip()
    base_url = os.environ.get("HOMEFIT_API_URL", "http://localhost:8000")
    timeout = int(os.environ.get("HOMEFIT_TIMEOUT", "120"))

    only = "housing_value,social_fabric,economic_security,neighborhood_amenities"
    print(f"Scoring: {location} (Status Signal pillars only)", flush=True)
    try:
        r = requests.get(
            f"{base_url}/score",
            params={"location": location, "only": only},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Error: {e}", flush=True)
        sys.exit(1)

    total = data.get("total_score")
    status_signal = data.get("status_signal")
    print(f"Total score: {total}")
    print(f"Status Signal (from API): {status_signal}")

    pillars = data.get("livability_pillars") or {}
    housing = pillars.get("housing_value")
    social = pillars.get("social_fabric")
    economic = pillars.get("economic_security")
    amenities = pillars.get("neighborhood_amenities")
    business_list = []
    if amenities:
        business_list = (amenities.get("breakdown") or {}).get("business_list") or amenities.get("business_list") or []

    coords = data.get("coordinates") or {}
    lat, lon = coords.get("lat"), coords.get("lon")
    loc = data.get("location_info") or {}
    state = loc.get("state")
    city = loc.get("city")

    if not housing or not social or not economic:
        print("Missing pillar details; cannot compute breakdown.")
        sys.exit(0)

    census_tract = None
    if lat is not None and lon is not None:
        try:
            census_tract = _ca.get_census_tract(lat, lon)
        except Exception:
            pass

    score, breakdown = compute_status_signal_with_breakdown(
        housing,
        social,
        economic,
        business_list,
        census_tract,
        state,
        city=city,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
    )
    print(f"Status Signal (recomputed): {score}")
    print("Breakdown (0–100 each, or label for wealth_character):")
    for k, v in breakdown.items():
        if v is None:
            val = "—"
        elif isinstance(v, str):
            val = v
        elif isinstance(v, dict):
            val = json.dumps(v, indent=2)[:500] + ("..." if len(json.dumps(v)) > 500 else "")
        elif isinstance(v, (int, float)):
            val = f"{v:.1f}"
        else:
            val = str(v)
        print(f"  {k}: {val}")


if __name__ == "__main__":
    main()
