"""Quick prototype to explore enhanced natural beauty signals using GEE."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from data_sources.gee_api import (  # noqa: E402
    GEE_AVAILABLE,
    get_tree_canopy_gee,
    get_urban_greenness_gee,
    get_topography_context,
    get_landcover_context_gee,
)


def analyze_location(name: str, lat: float, lon: float) -> dict:
    """Run prototype analyses for a single location."""
    print(f"\n=== {name} ({lat}, {lon}) ===")

    tree_canopy = get_tree_canopy_gee(lat, lon, radius_m=1000)
    greenness = get_urban_greenness_gee(lat, lon, radius_m=1000)
    topo = get_topography_context(lat, lon, radius_m=5000)
    landcover = get_landcover_context_gee(lat, lon, radius_m=3000)

    return {
        "name": name,
        "lat": lat,
        "lon": lon,
        "tree_canopy_pct": tree_canopy,
        "greenness": greenness,
        "topography": topo,
        "landcover": landcover,
    }


def main():
    if not GEE_AVAILABLE:
        raise SystemExit("Google Earth Engine is not available. Check credentials.")

    locations = [
        ("Old Town Alexandria VA", 38.80653, -77.06105),
        ("Montclair NJ", 40.81645, -74.22106),
        ("Telluride CO", 37.93749, -107.81229),
        ("Carmel-by-the-Sea CA", 36.55524, -121.92329),
        ("Venice Beach CA", 33.9850, -118.4695),
    ]

    results = [analyze_location(name, lat, lon) for name, lat, lon in locations]

    print("\n=== JSON Output ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

