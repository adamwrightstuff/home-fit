#!/usr/bin/env python3
"""
Carroll Gardens (and any location) Built Beauty preference-permutation investigation.

Runs the same pipeline as the API: resolve location → shared data (area_type, density,
arch_diversity, form_context) → calculate_built_beauty for each preference pair.
Prints actual data returned and how the score is derived for each permutation.

Usage:
  python scripts/investigate_built_beauty_preferences.py
  python scripts/investigate_built_beauty_preferences.py --location "Carroll Gardens Brooklyn NY"
  python scripts/investigate_built_beauty_preferences.py --lat 40.679 --lon -73.991 --name "Carroll Gardens"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Preference permutations we care about: (built_character_preference, built_density_preference)
PREFERENCE_PERMUTATIONS: List[Tuple[Optional[str], Optional[str]]] = [
    ("historic", "spread_out_residential"),
    ("contemporary", "walkable_residential"),
    ("historic", "walkable_residential"),
]

# Maps density preference → area_type_for_scoring (used inside built_beauty)
DENSITY_TO_AREA_TYPE: Dict[str, str] = {
    "spread_out_residential": "exurban",
    "walkable_residential": "suburban",
    "dense_urban_living": "urban_core",
}


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _ensure_path() -> None:
    root = _project_root()
    if root not in sys.path:
        sys.path.insert(0, root)


def _fetch_shared_data(lat: float, lon: float, location_name: Optional[str]) -> Dict[str, Any]:
    """Replicate main.py shared pre-pillar data (no Redis)."""
    _ensure_path()
    from data_sources import census_api as _ca
    from data_sources import data_quality as _dq
    from data_sources import osm_api
    from data_sources.arch_diversity import compute_arch_diversity

    census_tract = None
    try:
        census_tract = _ca.get_census_tract(lat, lon)
    except Exception as e:
        print(f"  Census tract failed: {e}", file=sys.stderr)

    density = 0.0
    try:
        density = _ca.get_population_density(lat, lon, tract=census_tract) or 0.0
    except Exception as e:
        print(f"  Density failed: {e}", file=sys.stderr)

    arch_diversity_data = None
    try:
        arch_diversity_data = compute_arch_diversity(lat, lon, radius_m=2000)
    except Exception as e:
        print(f"  Arch diversity failed: {e}", file=sys.stderr)

    built_coverage = arch_diversity_data.get("built_coverage_ratio") if arch_diversity_data else None
    business_count = 0
    try:
        business_data = osm_api.query_local_businesses(lat, lon, radius_m=1000)
        if business_data:
            all_b = (
                business_data.get("tier1_daily", [])
                + business_data.get("tier2_social", [])
                + business_data.get("tier3_culture", [])
                + business_data.get("tier4_services", [])
            )
            business_count = len(all_b)
    except Exception as e:
        print(f"  Business count failed: {e}", file=sys.stderr)

    city = None
    try:
        from data_sources import geocoding
        city = geocoding.reverse_geocode(lat, lon)
    except Exception as e:
        print(f"  Geocode failed: {e}", file=sys.stderr)

    area_type = "unknown"
    try:
        area_type = _dq.detect_area_type(
            lat,
            lon,
            density=density,
            city=city,
            location_input=location_name or "",
            business_count=business_count,
            built_coverage=built_coverage,
            metro_distance_km=None,
        )
    except Exception as e:
        print(f"  detect_area_type failed: {e}", file=sys.stderr)

    form_context = None
    if arch_diversity_data:
        try:
            from data_sources import census_api
            from data_sources.data_quality import get_form_context
            levels_entropy = arch_diversity_data.get("levels_entropy")
            building_type_diversity = arch_diversity_data.get("building_type_diversity")
            built_coverage_ratio = arch_diversity_data.get("built_coverage_ratio")
            footprint_area_cv = arch_diversity_data.get("footprint_area_cv")
            material_profile = arch_diversity_data.get("material_profile")
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
        except Exception as e:
            print(f"  get_form_context failed: {e}", file=sys.stderr)

    return {
        "area_type": area_type,
        "density": density,
        "arch_diversity_data": arch_diversity_data,
        "form_context": form_context,
        "city": city,
    }


def _run_built_beauty(
    lat: float,
    lon: float,
    shared: Dict[str, Any],
    location_name: Optional[str],
    built_character_preference: Optional[str],
    built_density_preference: Optional[str],
) -> Dict[str, Any]:
    _ensure_path()
    from pillars.built_beauty import calculate_built_beauty

    result = calculate_built_beauty(
        lat,
        lon,
        city=shared.get("city"),
        area_type=shared.get("area_type"),
        location_name=location_name,
        precomputed_arch_diversity=shared.get("arch_diversity_data"),
        density=shared.get("density"),
        form_context=shared.get("form_context"),
        built_character_preference=built_character_preference,
        built_density_preference=built_density_preference,
    )
    return result


def _summarize_one(
    perm: Tuple[Optional[str], Optional[str]],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    char_pref, dens_pref = perm
    area_type_for_scoring = DENSITY_TO_AREA_TYPE.get(dens_pref or "", "(none)")
    effective = result.get("effective_area_type") or ""
    score_before_norm = result.get("score_before_normalization")
    comp_0_50 = result.get("component_score_0_50")
    final_score = result.get("score")

    # Character penalty: -8 if (contemporary + historic_urban) or (historic + not historic_urban)
    CHARACTER_MISMATCH_PENALTY = 8.0
    is_historic_place = effective == "historic_urban"
    penalty_applied = False
    if char_pref and effective:
        pref = (char_pref or "").strip().lower()
        if pref == "historic" and not is_historic_place:
            penalty_applied = True
        elif pref == "contemporary" and is_historic_place:
            penalty_applied = True

    inferred_raw_before_penalty = score_before_norm
    if penalty_applied:
        inferred_raw_before_penalty = score_before_norm + CHARACTER_MISMATCH_PENALTY

    return {
        "built_character_preference": char_pref,
        "built_density_preference": dens_pref,
        "area_type_for_scoring": area_type_for_scoring,
        "effective_area_type": effective,
        "arch_component_0_50": comp_0_50,
        "inferred_raw_before_penalty": round(inferred_raw_before_penalty, 2) if inferred_raw_before_penalty is not None else None,
        "score_before_normalization": round(score_before_norm, 2) if score_before_norm is not None else None,
        "character_penalty_applied": penalty_applied,
        "final_score": round(final_score, 2) if final_score is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Investigate Built Beauty scoring across preference permutations (Carroll Gardens or custom location)."
    )
    parser.add_argument("--lat", type=float, default=40.679, help="Latitude (default: Carroll Gardens)")
    parser.add_argument("--lon", type=float, default=-73.991, help="Longitude (default: Carroll Gardens)")
    parser.add_argument("--name", type=str, default="Carroll Gardens", help="Location name for display and form_context")
    parser.add_argument("--location", type=str, default=None, help="Geocode this string to lat,lon (overrides --lat/--lon/--name)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON only")
    parser.add_argument("--save", type=str, metavar="PATH", help="Write JSON output to this file (implies --json)")
    args = parser.parse_args()
    if getattr(args, "save", None):
        args.json = True

    lat, lon, name = args.lat, args.lon, args.name
    if args.location:
        _ensure_path()
        try:
            from data_sources import geocoding
            geocoded = geocoding.geocode(args.location)
            if not geocoded:
                print(f"Geocode failed for: {args.location}", file=sys.stderr)
                return 1
            lat = geocoded["lat"]
            lon = geocoded["lon"]
            name = args.location
        except Exception as e:
            print(f"Geocode error: {e}", file=sys.stderr)
            return 1

    if not args.json:
        print(f"Location: {name} ({lat}, {lon})")
        print("Fetching shared data (area_type, density, arch_diversity, form_context)...")
    shared = _fetch_shared_data(lat, lon, name)
    if not args.json:
        print(f"  area_type (detected): {shared['area_type']}")
        print(f"  form_context (effective for classification): {shared['form_context']}")
        print(f"  density: {shared['density']}")
        print()

    runs: List[Dict[str, Any]] = []
    for perm in PREFERENCE_PERMUTATIONS:
        char_pref, dens_pref = perm
        result = _run_built_beauty(
            lat, lon, shared, name,
            built_character_preference=char_pref,
            built_density_preference=dens_pref,
        )
        summary = _summarize_one(perm, result)
        summary["details_keys"] = list(result.get("details", {}).keys())
        runs.append({"permutation": list(perm), "summary": summary, "full_result": result})

    if args.json:
        out = {
            "location": {"name": name, "lat": lat, "lon": lon},
            "shared": {
                "area_type": shared["area_type"],
                "form_context": shared["form_context"],
                "density": shared["density"],
            },
            "runs": [
                {
                    "permutation": r["permutation"],
                    "summary": r["summary"],
                }
                for r in runs
            ],
        }
        json_str = json.dumps(out, indent=2, default=str)
        save_path = getattr(args, "save", None)
        if save_path:
            with open(save_path, "w") as f:
                f.write(json_str)
            print(f"Wrote {len(json_str)} chars to {save_path}", file=sys.stderr)
        else:
            print(json_str)
        return 0

    # Human-readable table
    print("Permutation summaries (how Built Beauty is calculated per preference):")
    print("-" * 100)
    for r in runs:
        s = r["summary"]
        print(
            f"  {s['built_character_preference'] or 'none'} + {s['built_density_preference'] or 'none'}"
        )
        print(f"    area_type_for_scoring: {s['area_type_for_scoring']} (from density preference)")
        print(f"    effective_area_type:   {s['effective_area_type']} (from form_context / multinomial)")
        print(f"    arch_component (0-50): {s['arch_component_0_50']}")
        print(f"    raw before penalty:   {s['inferred_raw_before_penalty']}  (×2 + enhancers → 0-100)")
        print(f"    character penalty:    {'-8 (mismatch)' if s['character_penalty_applied'] else 'none'}")
        print(f"    score_before_norm:    {s['score_before_normalization']}")
        print(f"    final_score:          {s['final_score']}")
        print()
    print("Expected order if logic is correct: historic+walkable ≥ contemporary+walkable (same raw, historic has no penalty).")
    print("historic+spread_out can be highest because exurban targets are more forgiving for uniform historic areas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
