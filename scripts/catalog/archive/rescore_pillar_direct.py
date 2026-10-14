#!/usr/bin/env python3
"""
Targeted in-process pillar subscorer — makes only the specific OSM/API queries
needed for the broken subcomponent(s), then patches those values in-place.
No HTTP, no full 13-pillar overhead, no wasteful re-scoring of pillars that
already scored correctly.

Supported modes
---------------
active_outdoors --fix daily_urban_outdoors
    Re-runs the local parks Overpass query (1 km radius) and recomputes
    daily_urban_outdoors. wild_adventure and waterfront_lifestyle are kept
    from the stored catalog. If both trail and regional queries also failed,
    pass --fix wild_adventure to re-run those too.

active_outdoors --fix wild_adventure
    Re-runs the trail (15 km) and regional (50 km) Overpass queries and
    recomputes wild_adventure. daily_urban_outdoors and waterfront_lifestyle
    kept from stored values.

Usage
-----
PYTHONPATH=. python3 scripts/catalog/rescore_pillar_direct.py \\
    --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
    --pillar active_outdoors --fix daily_urban_outdoors \\
    --names "Bed-Stuy,Gowanus" \\
    --in-place
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional


def fix_ao_daily_urban_outdoors(lat: float, lon: float, area_type: str, location_scope: Optional[str]) -> dict:
    """Re-run local parks query only; return {new_score, new_outcome, parks_debug}."""
    from data_sources import osm_api
    from data_sources.osm_api import coerce_green_spaces_response
    from data_sources.radius_profiles import get_radius_profile
    from data_sources.regional_baselines import get_contextual_expectations
    from pillars.active_outdoors import _score_daily_urban_outdoors_v2

    profile = get_radius_profile("active_outdoors", area_type, location_scope)
    local_radius = int(profile.get("local_radius_m", 2000))

    raw = osm_api.query_green_spaces(lat, lon, radius_m=local_radius)
    local = coerce_green_spaces_response(raw) or {}
    outcome = local.get("_overpass_outcome", "overpass_empty")

    parks               = local.get("parks", []) or []
    playgrounds         = local.get("playgrounds", []) or []
    recreational_facs   = local.get("recreational_facilities", []) or []

    expectations = get_contextual_expectations(area_type, "active_outdoors") or {}
    score = _score_daily_urban_outdoors_v2(parks, playgrounds, recreational_facs, area_type, expectations)

    return {
        "score": score,
        "outcome": outcome,
        "parks_count": len(parks),
        "playgrounds_count": len(playgrounds),
    }


def fix_ao_wild_adventure(lat: float, lon: float, area_type: str, location_scope: Optional[str], canopy_pct: Optional[float]) -> dict:
    """Re-run trail + regional queries only; return {new_score, trail_outcome, reg_outcome}."""
    from data_sources import osm_api
    from data_sources.osm_api import coerce_nature_features_response
    from data_sources.radius_profiles import get_radius_profile
    from pillars.active_outdoors import _score_wild_adventure_v2

    profile = get_radius_profile("active_outdoors", area_type, location_scope)
    trail_radius    = int(profile.get("trail_radius_m", 15000))
    regional_radius = int(profile.get("regional_radius_m", 50000))

    raw_trail    = osm_api.query_nature_features(lat, lon, radius_m=trail_radius)
    raw_regional = osm_api.query_nature_features(lat, lon, radius_m=regional_radius, include_hiking=False)
    nature_trail    = coerce_nature_features_response(raw_trail)    or {}
    nature_regional = coerce_nature_features_response(raw_regional) or {}

    trail_outcome = nature_trail.get("_overpass_outcome", "overpass_empty")
    reg_outcome   = nature_regional.get("_overpass_outcome", "overpass_empty")

    hiking_trails = nature_trail.get("hiking_trails", []) or []
    camping       = nature_regional.get("camping", []) or []

    score = _score_wild_adventure_v2(hiking_trails, camping, canopy_pct or 0.0, area_type)

    return {
        "score": score,
        "trail_outcome": trail_outcome,
        "reg_outcome": reg_outcome,
        "trail_count": len(hiking_trails),
    }


def rescore_natural_beauty(lat: float, lon: float, area_type: str, city: Optional[str]) -> dict:
    """Full natural_beauty rescore via direct pillar call — GEE + OSM, no other pillars."""
    from pillars.natural_beauty import get_natural_beauty_score
    score, data = get_natural_beauty_score(lat, lon, city=city, area_type=area_type)
    return {"score": score, "data": data}


def rescore_healthcare(lat: float, lon: float, area_type: str, city: Optional[str]) -> dict:
    """Full healthcare_access rescore via direct pillar call — OSM only, no other pillars."""
    from pillars.healthcare_access import get_healthcare_access_score
    score, data = get_healthcare_access_score(lat, lon, area_type=area_type, city=city)
    return {"score": score, "data": data}


FULL_RESCORE_FUNCTIONS = {
    "natural_beauty":    rescore_natural_beauty,
    "healthcare_access": rescore_healthcare,
}

PILLAR_KEY_MAP = {
    "natural_beauty":    "natural_beauty",
    "healthcare_access": "healthcare_access",
}

FIX_FUNCTIONS = {
    ("active_outdoors", "daily_urban_outdoors"): fix_ao_daily_urban_outdoors,
    ("active_outdoors", "wild_adventure"):       fix_ao_wild_adventure,
}


def main():
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",   required=True)
    ap.add_argument("--pillar",  required=True, choices=["active_outdoors", "natural_beauty", "healthcare_access"])
    ap.add_argument("--fix",     default=None,  choices=["daily_urban_outdoors", "wild_adventure"])
    ap.add_argument("--names",   default="")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--output")
    ap.add_argument("--delay",   type=float, default=2.0)
    args = ap.parse_args()

    is_full_rescore = args.pillar in FULL_RESCORE_FUNCTIONS and args.fix is None
    if is_full_rescore:
        rescore_fn = FULL_RESCORE_FUNCTIONS[args.pillar]
        pillar_key = PILLAR_KEY_MAP[args.pillar]
    else:
        key = (args.pillar, args.fix)
        if key not in FIX_FUNCTIONS:
            print(f"ERROR: No fix function for {key}"); sys.exit(1)
        fix_fn = FIX_FUNCTIONS[key]

    target_names = {n.strip() for n in args.names.split(",") if n.strip()} if args.names else None

    path = Path(args.input)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(rows)} rows from {path.name}")

    to_fix = []
    for i, row in enumerate(rows):
        cat = row.get("catalog", {})
        name = cat.get("place_name") or cat.get("name", "")
        if target_names and name not in target_names:
            continue
        to_fix.append((i, name))

    mode = pillar_key if is_full_rescore else f"{args.pillar}.{args.fix}"
    print(f"Rows selected: {len(to_fix)}  mode={mode}")
    if not to_fix:
        print("Nothing to do."); return

    ok = 0
    for idx, (row_i, name) in enumerate(to_fix):
        print(f"[{idx+1}/{len(to_fix)}] {name} …", flush=True)
        row = rows[row_i]
        cat = row.get("catalog", {})
        lat = float(cat["lat"])
        lon = float(cat["lon"])
        # Prefer geocoded city (location_info.city) over catalog name for NPI lookups;
        # neighborhood names like "Almaden Valley" aren't valid NPPES city names.
        geocoded_city = (row.get("score", {}).get("location_info", {}) or {}).get("city")
        city = geocoded_city or cat.get("name")

        if is_full_rescore:
            pillars = (row.get("score", {}).get("livability_pillars", {}) or {})
            old = pillars.get(pillar_key, {})
            area_type = (old.get("area_classification") or {}).get("area_type") or "suburban"
            try:
                res = rescore_fn(lat, lon, area_type, city)
                new_score = res["score"]
                new_data  = res["data"]
                new_data["score"] = new_score
                old_score = old.get("score", 0)
                print(f"  score: {old_score:.1f}→{new_score:.1f}")
                rows[row_i]["score"]["livability_pillars"][pillar_key] = new_data
                ok += 1
            except Exception as e:
                print(f"  FAIL: {e}")
                import traceback; traceback.print_exc()
        else:
            ao = (row.get("score", {}).get("livability_pillars", {}) or {}).get("active_outdoors", {})
            area_type     = (ao.get("area_classification") or {}).get("area_type") or "suburban"
            location_scope = ao.get("location_scope")
            bd = ao.get("breakdown") or {}
            dq = ao.get("data_quality") or {}

            stored_duo = bd.get("daily_urban_outdoors", 0.0)
            stored_wa  = bd.get("wild_adventure", 0.0)
            stored_wl  = bd.get("waterfront_lifestyle", 0.0)

            try:
                if args.fix == "daily_urban_outdoors":
                    res = fix_fn(lat, lon, area_type, location_scope)
                    new_duo = res["score"]
                    new_score = min(100.0, new_duo + stored_wa + stored_wl)
                    bd["daily_urban_outdoors"] = round(new_duo, 1)
                    dq["overpass_local_outcome"] = res["outcome"]
                    print(f"  duo: {stored_duo:.1f}→{new_duo:.1f}  (parks={res['parks_count']})  score: {ao.get('score', 0):.1f}→{new_score:.1f}")
                elif args.fix == "wild_adventure":
                    canopy = dq.get("canopy_pct_5km")
                    res = fix_fn(lat, lon, area_type, location_scope, canopy)
                    new_wa = res["score"]
                    new_score = min(100.0, stored_duo + new_wa + stored_wl)
                    bd["wild_adventure"] = round(new_wa, 1)
                    dq["overpass_trail_outcome"]    = res["trail_outcome"]
                    dq["overpass_regional_outcome"] = res["reg_outcome"]
                    print(f"  wa: {stored_wa:.1f}→{new_wa:.1f}  (trails={res['trail_count']})  score: {ao.get('score', 0):.1f}→{new_score:.1f}")
                else:
                    raise ValueError(f"Unknown fix: {args.fix}")

                ao["score"]       = round(new_score, 1)
                ao["breakdown"]   = bd
                ao["data_quality"] = dq
                # sync degraded flag to current overpass outcomes
                local_ok = dq.get("overpass_local_outcome")   not in ("overpass_error",)
                trail_ok = dq.get("overpass_trail_outcome")   not in ("overpass_error",)
                reg_ok   = dq.get("overpass_regional_outcome") not in ("overpass_error",)
                area_t   = area_type or ""
                if not local_ok and area_t in {"urban_core", "urban_residential", "suburban"}:
                    dq["degraded"] = True
                    reasons = list(dq.get("degraded_reasons") or [])
                    if "overpass_local_failure" not in reasons:
                        reasons.append("overpass_local_failure")
                    dq["degraded_reasons"] = reasons
                elif local_ok and trail_ok and reg_ok:
                    dq["degraded"] = False
                    dq.pop("degraded_reasons", None)

                rows[row_i]["score"]["livability_pillars"]["active_outdoors"] = ao
                ok += 1

            except Exception as e:
                print(f"  FAIL: {e}")
                import traceback; traceback.print_exc()

        if idx < len(to_fix) - 1:
            time.sleep(args.delay)

    out_path = path if args.in_place else Path(args.output or str(path).replace(".jsonl", ".rescored.jsonl"))
    if args.in_place:
        bak = path.with_suffix(f".bak.{time.strftime('%Y%m%d-%H%M%S')}")
        path.rename(bak)
        print(f"Backup: {bak}")

    out_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Wrote {len(rows)} lines to {out_path} ({ok} merged OK, {len(to_fix)-ok} errors)")


if __name__ == "__main__":
    main()
