#!/usr/bin/env python3
"""
Compare Status Signal and its four pillars (wealth, education, occupation, brand)
for two locations. Run from project root with backend at http://localhost:8000:

  PYTHONPATH=. python3 scripts/compare_status_signal.py "Tribeca, NY 40.7154, -74.0093" "Carroll Gardens, Brooklyn NY 40.678420, -73.994802"
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def fetch_and_breakdown(location: str, base_url: str, timeout: int):
    import requests
    from data_sources import census_api as _ca
    from pillars.status_signal import compute_status_signal_with_breakdown

    only = "housing_value,social_fabric,economic_security,neighborhood_amenities"
    r = requests.get(
        f"{base_url}/score",
        params={"location": location, "only": only},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()

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
    # Raw inputs for interpretation
    summary = (housing or {}).get("summary") or (housing or {})
    edu = (social or {}).get("education_attainment") or {}
    industry = (economic or {}).get("industry_shares_pct") or {}
    return {
        "location": location,
        "status_signal": data.get("status_signal"),
        "recomputed": score,
        "breakdown": breakdown,
        "mean_hh_income": summary.get("mean_household_income") or summary.get("median_household_income"),
        "median_hh_income": summary.get("median_household_income"),
        "grad_pct": edu.get("grad_pct"),
        "bachelor_pct": edu.get("bachelor_pct"),
        "self_employed_pct": (social or {}).get("self_employed_pct"),
        "finance_realestate": industry.get("finance_realestate"),
        "leisure_hospitality": industry.get("leisure_hospitality"),
        "business_count": len(business_list),
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: compare_status_signal.py <location1> <location2>")
        print('  e.g. compare_status_signal.py "Tribeca, NY 40.7154, -74.0093" "Carroll Gardens, Brooklyn NY 40.678420, -73.994802"')
        sys.exit(1)
    loc_a, loc_b = sys.argv[1].strip(), sys.argv[2].strip()
    base_url = os.environ.get("HOMEFIT_API_URL", "http://localhost:8000")
    timeout = int(os.environ.get("HOMEFIT_TIMEOUT", "120"))

    print(f"Fetching: {loc_a}", flush=True)
    try:
        a = fetch_and_breakdown(loc_a, base_url, timeout)
    except Exception as e:
        print(f"Error for {loc_a}: {e}")
        sys.exit(1)
    print(f"Fetching: {loc_b}", flush=True)
    try:
        b = fetch_and_breakdown(loc_b, base_url, timeout)
    except Exception as e:
        print(f"Error for {loc_b}: {e}")
        sys.exit(1)

    print()
    print("=" * 70)
    print("STATUS SIGNAL COMPARISON (Wealth 25% | Education 20% | Occupation 20% | Brand 35%)")
    print("=" * 70)
    print(f"{'Metric':<22} {loc_a[:24]:<26} {loc_b[:24]:<26} Winner")
    print("-" * 70)
    sa, sb = a["recomputed"], b["recomputed"]
    print(f"{'Status Signal (0-100)':<22} {sa if sa is not None else '—':<26} {sb if sb is not None else '—':<26} {'A' if (sa or 0) > (sb or 0) else 'B' if (sb or 0) > (sa or 0) else '—'}")
    for key in ["wealth", "education", "occupation", "brand"]:
        va = a["breakdown"].get(key)
        vb = b["breakdown"].get(key)
        va_s = f"{va:.1f}" if va is not None else "—"
        vb_s = f"{vb:.1f}" if vb is not None else "—"
        winner = "A" if (va or 0) > (vb or 0) else "B" if (vb or 0) > (va or 0) else "—"
        print(f"  {key:<20} {va_s:<26} {vb_s:<26} {winner}")
    print("-" * 70)
    print(f"{'Businesses in list':<22} {a['business_count']:<26} {b['business_count']:<26}")
    print(f"{'Median HH income':<22} {a['median_hh_income'] or '—':<26} {b['median_hh_income'] or '—':<26}")
    print(f"{'Grad % (edu)':<22} {a['grad_pct'] if a['grad_pct'] is not None else '—':<26} {b['grad_pct'] if b['grad_pct'] is not None else '—':<26}")
    print(f"{'Bachelor % (edu)':<22} {a['bachelor_pct'] if a['bachelor_pct'] is not None else '—':<26} {b['bachelor_pct'] if b['bachelor_pct'] is not None else '—':<26}")
    print("=" * 70)


if __name__ == "__main__":
    main()
