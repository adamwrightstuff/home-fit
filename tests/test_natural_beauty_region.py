"""Natural-beauty region lookup (California polygon, desert and Great Basin boxes) and the offline recompute."""

import importlib.util
import os

import pytest

from pillars import natural_beauty as NB

_spec = importlib.util.spec_from_file_location(
    "recompute_nb", os.path.join(os.path.dirname(__file__), "..", "scripts", "catalog", "recompute_natural_beauty_region_offline.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


@pytest.mark.parametrize("name,lat,lon,region", [
    ("Las Vegas", 36.17, -115.14, "southwest_arid"), ("Henderson NV", 36.04, -114.98, "southwest_arid"),
    ("Mesquite NV", 36.81, -114.07, "southwest_arid"), ("Laughlin NV", 35.17, -114.57, "southwest_arid"),
    ("Pahrump NV", 36.21, -115.98, "southwest_arid"), ("Yuma AZ", 32.69, -114.62, "southwest_arid"),
    ("Bullhead City AZ", 35.15, -114.57, "southwest_arid"), ("Phoenix", 33.45, -112.07, "southwest_arid"),
    ("Reno", 39.53, -119.81, "mountain_west"), ("Denver", 39.74, -104.99, "mountain_west"),
    ("Boise", 43.62, -116.20, "mountain_west"), ("Seattle", 47.61, -122.33, "pacific_northwest"),
])
def test_places_outside_california_get_their_own_regions(name, lat, lon, region):
    assert NB._get_nb_region(lat, lon) == region, name


@pytest.mark.parametrize("name,lat,lon", [
    ("Los Angeles", 34.05, -118.24), ("San Diego", 32.72, -117.16), ("San Francisco", 37.77, -122.42),
    ("Sacramento", 38.58, -121.49), ("Palm Springs", 33.83, -116.55), ("El Centro", 32.79, -115.56),
    ("South Lake Tahoe", 38.94, -119.98), ("Truckee", 39.33, -120.18), ("Redding", 40.59, -122.39),
])
def test_california_places_stay_california(name, lat, lon):
    assert NB._get_nb_region(lat, lon) == "california", name


def test_unknown_coordinates_fall_back_to_international():
    assert NB._get_nb_region(None, None) == "international"
    assert NB._get_nb_region(48.8, 2.3) == "international"  # Paris


def _place(region, lat, lon, canopy=1.5, gvi=7.6):
    tree = {"green_view_index": gvi, "gee_canopy_pct": canopy,
            "natural_context": {"component_scores": {"topography_raw": 3.8, "landcover_raw": 0.1}, "debug_breakdown": {}}}
    return {"coordinates": {"lat": lat, "lon": lon}, "livability_pillars": {"natural_beauty": {
        "score": 26.9, "weight": 7.6923076923, "contribution": 2.0692,
        "details": {"tree_analysis": tree, "v9_breakdown": {"region": region}}}}}


def test_recompute_updates_only_places_whose_region_changed():
    moved = _place("california", 36.17, -115.14)
    info = _mod.recompute_place(moved)
    assert info and info["region_before"] == "california" and info["region_after"] == "southwest_arid"
    nb = moved["livability_pillars"]["natural_beauty"]
    assert nb["details"]["v9_breakdown"]["region"] == "southwest_arid" and nb["score"] == nb["details"]["score_v9"]
    assert nb["contribution"] == pytest.approx(7.6923076923 * nb["score"] / 100, abs=1e-4)
    same = _place("southwest_arid", 33.45, -112.07)
    assert _mod.recompute_place(same) is None and same["livability_pillars"]["natural_beauty"]["score"] == 26.9


def test_arid_region_lifts_the_normalized_green_view_for_the_same_raw_greenery():
    assert NB._v9_regional_normalize(7.6, "gvi", "southwest_arid") > NB._v9_regional_normalize(7.6, "gvi", "california")
