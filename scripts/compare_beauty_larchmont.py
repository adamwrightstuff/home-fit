#!/usr/bin/env python3
"""
Compare built beauty and natural beauty scores for two locations that should
be in the same area: a town name vs a specific address in that town.

Example: "Larchmont NY" vs "2 Springdale Dr Larchmont NY"

Reasons they can differ:
- Different (lat, lon): town center vs address → different 1–2 km radius data
- Different location_scope: address may be "neighborhood", town "city" → different tree radius (1 km vs 2 km)
- Different area_type: density/built coverage at the point → different expectations/normalization

Run from project root:
  PYTHONPATH=. python3 scripts/compare_beauty_larchmont.py
"""

from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def geocode_and_scope(location: str):
    from data_sources.geocoding import geocode_with_full_result
    from data_sources.data_quality import detect_location_scope

    geo = geocode_with_full_result(location)
    if not geo:
        return None
    lat, lon, zip_code, state, city, geocode_data = geo
    scope = detect_location_scope(lat, lon, geocode_data)
    return {
        "location": location,
        "lat": lat,
        "lon": lon,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "geocode_data": geocode_data,
        "location_scope": scope,
    }


def get_shared_data(lat: float, lon: float, city: str | None, location: str):
    from concurrent.futures import ThreadPoolExecutor
    from data_sources import census_api, data_quality, osm_api
    from data_sources.arch_diversity import compute_arch_diversity
    from data_sources.regional_baselines import RegionalBaselineManager

    def _census_tract():
        try:
            return census_api.get_census_tract(lat, lon)
        except Exception:
            return None

    def _density(tract):
        try:
            return census_api.get_population_density(lat, lon, tract=tract) or 0.0
        except Exception:
            return 0.0

    def _business_count():
        try:
            data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
            if data:
                all_b = (
                    data.get("tier1_daily", [])
                    + data.get("tier2_social", [])
                    + data.get("tier3_culture", [])
                    + data.get("tier4_services", [])
                )
                return len(all_b)
            return 0
        except Exception:
            return 0

    def _arch_diversity():
        try:
            return compute_arch_diversity(lat, lon, radius_m=2000)
        except Exception:
            return None

    def _metro_distance():
        try:
            mgr = RegionalBaselineManager()
            return mgr.get_distance_to_principal_city(lat, lon, city=city)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as ex:
        f_tract = ex.submit(_census_tract)
        f_business = ex.submit(_business_count)
        f_metro = ex.submit(_metro_distance)
        f_arch = ex.submit(_arch_diversity)
        census_tract = f_tract.result()
        density = ex.submit(_density, census_tract).result()
        business_count = f_business.result()
        metro_distance_km = f_metro.result()
        arch_diversity_data = f_arch.result()

    built_coverage = arch_diversity_data.get("built_coverage_ratio") if arch_diversity_data else None
    area_type = data_quality.detect_area_type(
        lat, lon,
        density=density,
        city=city,
        location_input=location,
        business_count=business_count,
        built_coverage=built_coverage,
        metro_distance_km=metro_distance_km,
    )

    tree_canopy_5km = None
    try:
        from data_sources.gee_api import get_tree_canopy_gee
        tree_canopy_5km = get_tree_canopy_gee(lat, lon, radius_m=5000, area_type=area_type)
    except Exception:
        pass

    form_context = None
    try:
        from data_sources.data_quality import get_form_context
        if arch_diversity_data:
            levels_entropy = arch_diversity_data.get("levels_entropy")
            building_type_diversity = arch_diversity_data.get("building_type_diversity")
            built_coverage_ratio = arch_diversity_data.get("built_coverage_ratio")
            footprint_area_cv = arch_diversity_data.get("footprint_area_cv")
            material_profile = arch_diversity_data.get("material_profile")
        else:
            levels_entropy = building_type_diversity = built_coverage_ratio = footprint_area_cv = material_profile = None
        charm_data = osm_api.query_charm_features(lat, lon, radius_m=1000)
        historic_landmarks = len(charm_data.get("historic", [])) if charm_data else 0
        year_built_data = census_api.get_year_built_data(lat, lon) if census_api else None
        median_year_built = year_built_data.get("median_year_built") if year_built_data else None
        pre_1940_pct = year_built_data.get("pre_1940_pct") if year_built_data else None
        form_context = get_form_context(
            area_type=area_type,
            density=density,
            levels_entropy=levels_entropy,
            building_type_diversity=building_type_diversity,
            historic_landmarks=historic_landmarks,
            median_year_built=median_year_built,
            built_coverage_ratio=built_coverage_ratio,
            footprint_area_cv=footprint_area_cv,
            pre_1940_pct=pre_1940_pct,
            material_profile=material_profile,
            use_multinomial=True,
        )
    except Exception:
        pass

    return {
        "density": density,
        "area_type": area_type,
        "arch_diversity_data": arch_diversity_data,
        "tree_canopy_5km": tree_canopy_5km,
        "form_context": form_context,
    }


def main():
    # Town-level vs address-level in same area. (2 Springdale Dr doesn't geocode with current
    # Nominatim/Census pipeline; using another Larchmont address to demonstrate the same effect.)
    loc_a = "Larchmont NY"
    loc_b = "1 Palmer Avenue Larchmont NY"  # specific address in Larchmont (2 Springdale Dr fails geocode)

    print("Geocoding and scope...")
    a = geocode_and_scope(loc_a)
    b = geocode_and_scope(loc_b)
    if not a:
        print(f"Geocoding failed for: {loc_a}")
        sys.exit(1)
    if not b:
        print(f"Geocoding failed for: {loc_b}")
        sys.exit(1)

    print(f"\n--- Location A: {a['location']} ---")
    print(f"  lat, lon: {a['lat']:.5f}, {a['lon']:.5f}")
    print(f"  location_scope: {a['location_scope']}")

    print(f"\n--- Location B: {b['location']} ---")
    print(f"  lat, lon: {b['lat']:.5f}, {b['lon']:.5f}")
    print(f"  location_scope: {b['location_scope']}")

    print("\nComputing shared data and beauty scores (this may take a moment)...")
    shared_a = get_shared_data(a["lat"], a["lon"], a["city"], a["location"])
    shared_b = get_shared_data(b["lat"], b["lon"], b["city"], b["location"])

    print(f"\n  A area_type: {shared_a['area_type']}")
    print(f"  B area_type: {shared_b['area_type']}")

    from pillars import built_beauty, natural_beauty
    from data_sources.radius_profiles import get_radius_profile

    def beauty_radius_info(area_type, location_scope):
        rp_b = get_radius_profile("built_beauty", area_type, location_scope)
        rp_n = get_radius_profile("natural_beauty", area_type, location_scope)
        return {
            "arch_radius_m": rp_b.get("architectural_diversity_radius_m", 2000),
            "tree_radius_m": rp_n.get("tree_canopy_radius_m", 1000),
        }

    rad_a = beauty_radius_info(shared_a["area_type"], a["location_scope"])
    rad_b = beauty_radius_info(shared_b["area_type"], b["location_scope"])
    print(f"\n  A radii: arch={rad_a['arch_radius_m']}m, tree={rad_a['tree_radius_m']}m")
    print(f"  B radii: arch={rad_b['arch_radius_m']}m, tree={rad_b['tree_radius_m']}m")

    built_a = built_beauty.calculate_built_beauty(
        a["lat"], a["lon"],
        city=a["city"],
        area_type=shared_a["area_type"],
        location_scope=a["location_scope"],
        location_name=a["location"],
        precomputed_arch_diversity=shared_a["arch_diversity_data"],
        density=shared_a["density"],
        form_context=shared_a["form_context"],
    )
    built_b = built_beauty.calculate_built_beauty(
        b["lat"], b["lon"],
        city=b["city"],
        area_type=shared_b["area_type"],
        location_scope=b["location_scope"],
        location_name=b["location"],
        precomputed_arch_diversity=shared_b["arch_diversity_data"],
        density=shared_b["density"],
        form_context=shared_b["form_context"],
    )

    natural_a = natural_beauty.calculate_natural_beauty(
        a["lat"], a["lon"],
        city=a["city"],
        area_type=shared_a["area_type"],
        location_scope=a["location_scope"],
        location_name=a["location"],
        precomputed_tree_canopy_5km=shared_a["tree_canopy_5km"],
        form_context=shared_a["form_context"],
    )
    natural_b = natural_beauty.calculate_natural_beauty(
        b["lat"], b["lon"],
        city=b["city"],
        area_type=shared_b["area_type"],
        location_scope=b["location_scope"],
        location_name=b["location"],
        precomputed_tree_canopy_5km=shared_b["tree_canopy_5km"],
        form_context=shared_b["form_context"],
    )

    def beauty_score(d):
        return d.get("score") if isinstance(d.get("score"), (int, float)) else None

    built_score_a = beauty_score(built_a)
    built_score_b = beauty_score(built_b)
    natural_score_a = beauty_score(natural_a)
    natural_score_b = beauty_score(natural_b)

    print("=" * 66)
    print("BEAUTY SCORE COMPARISON")
    print("=" * 66)
    print(f"{'Metric':<30} {'Larchmont NY':>14} {'Address in Larchmont':>20}")
    print("-" * 66)
    print(f"{'Built beauty score':<30} {built_score_a:>14.1f} {built_score_b:>20.1f}")
    print(f"{'Natural beauty score':<30} {natural_score_a:>14.1f} {natural_score_b:>20.1f}")
    print()

    print("Why they differ:")
    print("1. Different coordinates: town center vs address → different buildings/trees in the radius.")
    print("2. location_scope: affects tree_canopy_radius_m (neighborhood=1000m, city=2000m for suburban).")
    print("3. area_type at each point: density/built_coverage can differ → different normalization/expectations.")
    print("4. Built beauty uses a 2km radius around the point; natural beauty uses 1–2km depending on scope/area type.")


if __name__ == "__main__":
    main()
