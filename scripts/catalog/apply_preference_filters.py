#!/usr/bin/env python3
"""
Apply a preference profile against the catalog JSONL and produce a ranked shortlist.

Decision levers:
  WIRED IN AGENT_RECOMMEND (pillar weights + political_preference param)
  OFFLINE ONLY (all filters below — not yet wired into the API endpoint)

Usage:
  python3 scripts/catalog/apply_preference_filters.py \
      --catalog data/nyc_metro_place_catalog_scores_merged.jsonl \
      [--catalog data/la_metro_place_catalog_scores_merged.jsonl] \
      --output /tmp/shortlist.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# LEVER DEFINITIONS — what exists in the catalog and what it maps to
# ---------------------------------------------------------------------------
#
# FULLY WIRED IN AGENT_RECOMMEND (agent_recommend.py priorities dict):
#   community_safety      → priorities["community_safety"]    (None/Low/Medium/High)
#   quality_education     → priorities["quality_education"]   (None/Low/Medium/High)
#   social_fabric         → priorities["social_fabric"]       (None/Low/Medium/High)
#   neighborhood_amenities→ priorities["neighborhood_amenities"]
#   natural_beauty        → priorities["natural_beauty"]
#   healthcare_access     → priorities["healthcare_access"]
#   active_outdoors       → priorities["active_outdoors"]
#   housing_value         → priorities["housing_value"]
#   public_transit_access → priorities["public_transit_access"]
#   political_preference  → separate param: "progressive" | "moderate" | "conservative"
#                           NOTE: only takes ONE value — "progressive+moderate" requires
#                           offline lean_2024 range filter (0.0–1.0 covers both).
#
# OFFLINE-ONLY FILTERS (catalog fields, not wired into agent_recommend.py):
#   class/archetype       → score.status_signal_breakdown.archetype
#                           values: "Elite" | "Affluent" | "Middle Class" | "Working Class" | "Struggling"
#   trajectory            → score.status_signal_breakdown.trajectory
#                           values: "Arrived" | "Stable" | "Declining" | "Up-and-Coming" | "Cooling"
#   local_scene           → score.local_scene_bucket
#                           values: "High" | "Some" | "Low"
#   built_form            → score.livability_pillars.built_environment.summary.built_form_label
#                           values: "Historic urban fabric" | "Suburban" | "Urban residential"
#                           "Urban Neighborhood" in UI → "Historic urban fabric" or "Urban residential"
#                           "Suburban" in UI → "Suburban"
#   housing_stock         → score.housing_stock.pct_low_density  (0.0–1.0)
#                           Single-Family/Townhouse → pct_low_density ≥ 0.50
#   political_lean_label  → score.livability_pillars.political_lean.breakdown.label
#                           Progressive → "strong_d" | "lean_d"
#                           Moderate    → "competitive"
#   natural_beauty_water  → score.livability_pillars.natural_beauty.v9_breakdown.inputs.water_type
#                           Ocean/Coast → "ocean"  |  Bays → "bay"
#   canopy_score          → score.livability_pillars.natural_beauty.v9_breakdown.canopy_score (0–100)
#   waterfront_type_ao    → score.livability_pillars.active_outdoors.breakdown.waterfront_breakdown
#                           Bays & Harbors → bay_harbor > 0
#                           CAVEAT: only Battery Park City has bay_harbor>0 in NYC catalog —
#                           treat as soft preference, not hard filter
#   ao_daily_parks        → score.livability_pillars.active_outdoors.breakdown.daily_urban_outdoors
#   ao_waterfront_score   → score.livability_pillars.active_outdoors.breakdown.waterfront_lifestyle
#
# NOT IN CATALOG (manual / unscored):
#   household_income      → no per-user income filter; wealth is area-level
#   commute_to_ESB        → not stored per destination; public_transit_access.breakdown.commute_time
#                           scores area-level Census commute, not to a specific address
#   low_traffic_streets   → no traffic volume metric; community_safety crime rate is closest proxy
#   schools_filter="Any"  → weight quality_education=0 to exclude it from ranking, or set to Low/High


PILLAR_WEIGHTS = {
    "community_safety": 100,       # High
    "quality_education": 100,      # High (Schools)
    "social_fabric": 100,          # High
    "neighborhood_amenities": 66,  # Medium (Daily Amenities)
    "natural_beauty": 66,          # Medium
    "healthcare_access": 33,       # Low
    "active_outdoors": 33,         # Low
    "housing_value": 33,           # Low (Home Price to Space)
    "public_transit_access": 33,   # Low
    # Not in user's preference → default 0 (excluded from ranking)
    "air_travel_access": 0,
    "economic_security": 0,
    "climate_risk": 0,
    "diversity": 0,
    "political_lean": 0,
    "built_environment": 0,
}

# Progressive OR moderate → lean_2024 range includes both
# lean_2024 is in [-1, 1]; progressive = positive (D lean), moderate = near 0.
# Excluding lean_r / strong_r is sufficient: require lean_2024 >= -0.15 (excludes strong R).
POLITICAL_LEAN_2024_MIN = -0.15

ALLOWED_ARCHETYPES = {"Elite", "Affluent"}
ALLOWED_TRAJECTORIES = {"Arrived"}
ALLOWED_LOCAL_SCENE = {"High"}
ALLOWED_BUILT_FORMS = {
    "Historic urban fabric",  # Urban Neighborhood (dense, pre-war)
    "Urban residential",      # Urban Neighborhood (newer apartment stock)
    "Suburban",               # Suburban
}
HOUSING_STOCK_MIN_PCT_LOW_DENSITY = 0.30  # Single-family/townhouse mix meaningful

# Scenery sub-preferences (mirrors Trovamo filter sheet)
NB_PREFERENCES = ["ocean", "canopy"]   # Ocean/Coast + Tree Canopy
AO_PREFERENCES = ["local_parks", "waterfront"]  # Local Parks + Waterfront

# OWA constants — mirrors frontend/lib/nbPreference.ts and aoPreference.ts
_V9_OWA_WEIGHTS = [0.62, 0.25, 0.10, 0.02, 0.01, 0.0]
_V9_COMPONENT_KEYS = ["gvi_score", "water_score", "canopy_score", "topo_score", "landcover_score", "bio_score"]
_PREFERENCE_V9_COMPONENTS: dict[str, list[str]] = {
    "mountains": ["topo_score"],
    "ocean": ["water_score"],
    "lakes_rivers": ["water_score"],
    "canopy": ["gvi_score"],
}

_AO_OWA_WEIGHTS = [0.62, 0.25, 0.13]
_AO_COMPONENT_MAX = {"daily_urban_outdoors": 35.0, "wild_adventure": 50.0, "waterfront_lifestyle": 25.0}
_PREFERENCE_AO_COMPONENTS = {
    "local_parks": "daily_urban_outdoors",
    "trails_regional": "wild_adventure",
    "waterfront": "waterfront_lifestyle",
}


def _apply_nb_preferences_v9(v9: dict, preferences: list) -> Optional[float]:
    if not v9 or not preferences:
        return None
    water_type = (v9.get("inputs") or {}).get("water_type", "") or ""
    effective: dict[str, float] = {}
    for key in _V9_COMPONENT_KEYS:
        val = v9.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            effective[key] = float(val)
    for pref in preferences:
        if pref in ("ocean", "lakes_rivers") and "water_score" in effective:
            import re as _re
            is_coastal = bool(_re.search(r"ocean|coast|bay|harbor|sea", water_type, _re.I))
            is_lake_river = bool(_re.search(r"lake|reservoir|river|stream|canal", water_type, _re.I))
            match = is_coastal if pref == "ocean" else is_lake_river
            if not match:
                effective["water_score"] *= 0.25
    targets: set[str] = set(c for p in preferences for c in _PREFERENCE_V9_COMPONENTS.get(p, []))
    pref_vals = [effective[t] for t in targets if t in effective]
    if not pref_vals:
        return None
    preferred = sum(pref_vals) / len(pref_vals)
    others = sorted([v for k, v in effective.items() if k not in targets], reverse=True)
    dynamic_lead = min(1.0, 0.62 + 0.38 * (preferred / 100))
    ranked = [preferred] + others
    weights = [dynamic_lead] + _V9_OWA_WEIGHTS[1:len(ranked)]
    tot = sum(weights) or 1
    return round(sum(w / tot * s for w, s in zip(weights, ranked)), 2)


def _apply_ao_preferences(ao_bd: dict, preferences: list) -> Optional[float]:
    if not ao_bd or not preferences:
        return None
    normalized: dict[str, float] = {}
    for key, cap in _AO_COMPONENT_MAX.items():
        raw = ao_bd.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            normalized[key] = min(100.0, (float(raw) / cap) * 100)
    targets: set[str] = {_PREFERENCE_AO_COMPONENTS[p] for p in preferences if p in _PREFERENCE_AO_COMPONENTS}
    pref_vals = [normalized[t] for t in targets if t in normalized]
    if not pref_vals:
        return None
    preferred = sum(pref_vals) / len(pref_vals)
    others = sorted([v for k, v in normalized.items() if k not in targets], reverse=True)
    dynamic_lead = min(1.0, 0.62 + 0.38 * (preferred / 100))
    ranked = [preferred] + others
    weights = [dynamic_lead] + _AO_OWA_WEIGHTS[1:len(ranked)]
    tot = sum(weights) or 1
    return round(sum(w / tot * s for w, s in zip(weights, ranked)), 2)


def _get(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    return d if d != {} else default


def _pillar_score(lp: dict, key: str) -> Optional[float]:
    p = lp.get(key, {})
    if not isinstance(p, dict):
        return None
    s = p.get("score")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    return None


def _weighted_score(lp: dict, nb_adjusted: Optional[float] = None, ao_adjusted: Optional[float] = None) -> float:
    total_weight = sum(PILLAR_WEIGHTS.values()) or 1
    total = 0.0
    for key, w in PILLAR_WEIGHTS.items():
        if key == "natural_beauty" and nb_adjusted is not None:
            s = nb_adjusted
        elif key == "active_outdoors" and ao_adjusted is not None:
            s = ao_adjusted
        else:
            s = _pillar_score(lp, key) or 0.0
        total += w * s
    return round(total / total_weight, 2)


def _passes_hard_filters(row: dict) -> tuple[bool, str]:
    score = row.get("score", {})
    lp = score.get("livability_pillars", {})

    # Archetype / class
    ss = score.get("status_signal_breakdown", {})
    arch = ss.get("archetype") if isinstance(ss, dict) else None
    if arch not in ALLOWED_ARCHETYPES:
        return False, f"archetype={arch}"

    # Trajectory
    traj = ss.get("trajectory") if isinstance(ss, dict) else None
    if traj not in ALLOWED_TRAJECTORIES:
        return False, f"trajectory={traj}"

    # Local scene
    ls = score.get("local_scene_bucket")
    if ls not in ALLOWED_LOCAL_SCENE:
        return False, f"local_scene={ls}"

    # Built form
    be_summary = lp.get("built_environment", {}).get("summary", {})
    built_form = be_summary.get("built_form_label") if isinstance(be_summary, dict) else None
    if built_form not in ALLOWED_BUILT_FORMS:
        return False, f"built_form={built_form}"

    # Political lean
    pl_bd = lp.get("political_lean", {}).get("breakdown", {})
    lean_2024 = pl_bd.get("lean_2024") if isinstance(pl_bd, dict) else None
    if lean_2024 is not None and lean_2024 < POLITICAL_LEAN_2024_MIN:
        label = pl_bd.get("label", "?")
        return False, f"pol_lean={label}({lean_2024:.2f})"

    # Housing stock
    hs = score.get("housing_stock", {})
    pct_ld = hs.get("pct_low_density") if isinstance(hs, dict) else None
    if pct_ld is not None and pct_ld < HOUSING_STOCK_MIN_PCT_LOW_DENSITY:
        return False, f"pct_low_density={pct_ld:.2f}"

    return True, "ok"


def _score_row(row: dict) -> dict:
    catalog = row.get("catalog", {})
    score = row.get("score", {})
    lp = score.get("livability_pillars", {})

    nb = lp.get("natural_beauty", {})
    v9 = nb.get("v9_breakdown", {}) if isinstance(nb, dict) else {}
    nb_inp = v9.get("inputs", {}) if isinstance(v9, dict) else {}
    water_type = nb_inp.get("water_type") if isinstance(nb_inp, dict) else None
    canopy_score = v9.get("canopy_score") if isinstance(v9, dict) else None

    ao_bd = lp.get("active_outdoors", {}).get("breakdown", {})
    waterfront_bd = ao_bd.get("waterfront_breakdown", {}) if isinstance(ao_bd, dict) else {}
    bay_harbor = waterfront_bd.get("bay_harbor", 0.0) if isinstance(waterfront_bd, dict) else 0.0
    daily_urban = ao_bd.get("daily_urban_outdoors", 0.0) if isinstance(ao_bd, dict) else 0.0
    waterfront_lifestyle = ao_bd.get("waterfront_lifestyle", 0.0) if isinstance(ao_bd, dict) else 0.0

    nb_adjusted = _apply_nb_preferences_v9(v9 if isinstance(v9, dict) else {}, NB_PREFERENCES)
    ao_adjusted = _apply_ao_preferences(ao_bd if isinstance(ao_bd, dict) else {}, AO_PREFERENCES)

    weighted = _weighted_score(lp, nb_adjusted=nb_adjusted, ao_adjusted=ao_adjusted)
    final_score = weighted

    ss = score.get("status_signal_breakdown", {})
    pl_bd = lp.get("political_lean", {}).get("breakdown", {})
    hs = score.get("housing_stock", {})

    return {
        "name": catalog.get("name", "?"),
        "state": catalog.get("state_abbr", "?"),
        "final_score": final_score,
        "weighted_pillar_score": weighted,
        "nb_adjusted": round(nb_adjusted, 1) if nb_adjusted is not None else None,
        "ao_adjusted": round(ao_adjusted, 1) if ao_adjusted is not None else None,
        "archetype": ss.get("archetype") if isinstance(ss, dict) else None,
        "trajectory": ss.get("trajectory") if isinstance(ss, dict) else None,
        "local_scene": score.get("local_scene_bucket"),
        "built_form": lp.get("built_environment", {}).get("summary", {}).get("built_form_label") if isinstance(lp.get("built_environment", {}).get("summary", {}), dict) else None,
        "pct_low_density": hs.get("pct_low_density") if isinstance(hs, dict) else None,
        "water_type": water_type,
        "canopy_score": round(canopy_score, 1) if canopy_score else None,
        "bay_harbor": bay_harbor,
        "ao_daily_parks": round(daily_urban, 1),
        "ao_waterfront": round(waterfront_lifestyle, 1),
        "pol_label": pl_bd.get("label") if isinstance(pl_bd, dict) else None,
        "lean_2024": round(pl_bd.get("lean_2024", 0), 3) if isinstance(pl_bd, dict) else None,
        "pillar_scores": {
            k: round(_pillar_score(lp, k), 1) if _pillar_score(lp, k) is not None else None
            for k in ["community_safety", "quality_education", "social_fabric",
                      "neighborhood_amenities", "natural_beauty", "healthcare_access",
                      "active_outdoors", "housing_value", "public_transit_access"]
        },
        "manual_must_haves": {
            "commute_ESB_45min": "NOT SCORED — check manually (LIRR/Metro-North/subway to Midtown)",
            "quiet_streets_kids_bike": "NOT SCORED — proxy: low violent_per_1k + suburban built_form",
            "violent_per_1k": lp.get("community_safety", {}).get("breakdown", {}).get("violent_per_1k")
                              if isinstance(lp.get("community_safety", {}).get("breakdown", {}), dict) else None,
        },
    }


def process_catalog(path: Path, results: list) -> tuple[int, int]:
    passed = failed = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("success", True):
                continue
            ok, reason = _passes_hard_filters(row)
            if ok:
                results.append(_score_row(row))
                passed += 1
            else:
                failed += 1
    return passed, failed


def main():
    parser = argparse.ArgumentParser(description="Apply preference filters to catalog JSONL.")
    parser.add_argument("--catalog", action="append", required=True,
                        help="Path to catalog JSONL (repeat for multiple metros)")
    parser.add_argument("--output", default=None, help="Write JSON shortlist to file")
    parser.add_argument("--top", type=int, default=30, help="Print top N results")
    args = parser.parse_args()

    results = []
    for p in args.catalog:
        path = Path(p)
        if not path.exists():
            print(f"WARN: {path} not found, skipping")
            continue
        passed, failed = process_catalog(path, results)
        print(f"{path.name}: {passed} passed filters, {failed} excluded")

    results.sort(key=lambda x: x["final_score"], reverse=True)

    print(f"\n=== TOP {min(args.top, len(results))} of {len(results)} passing hard filters ===")
    print(f"{'Rank':<5} {'Name':<28} {'St':<4} {'Score':>6} {'Arch':<10} {'Built Form':<22} "
          f"{'Water':<6} {'Canopy':>7} {'CS':>5} {'EDU':>5} {'SF':>5} {'NA':>5} {'NB':>5} {'pct_ld':>7}")
    print("-" * 145)
    for i, r in enumerate(results[:args.top], 1):
        ps = r["pillar_scores"]
        print(
            f"{i:<5} {r['name']:<28} {r['state']:<4} {r['final_score']:>6.1f} "
            f"{(r['archetype'] or '?'):<10} {(r['built_form'] or '?'):<22} "
            f"{(r['water_type'] or 'none'):<6} {(r['canopy_score'] or 0):>7.1f} "
            f"{(ps.get('community_safety') or 0):>5.1f} {(ps.get('quality_education') or 0):>5.1f} "
            f"{(ps.get('social_fabric') or 0):>5.1f} {(ps.get('neighborhood_amenities') or 0):>5.1f} "
            f"{(ps.get('natural_beauty') or 0):>5.1f} {(r['pct_low_density'] or 0):>7.2f}"
        )

    print(f"\nManual must-haves NOT scored (verify per place):")
    print("  1. Commute to Empire State Building ~45 min")
    print("     → check LIRR, Metro-North, or subway travel time from each place")
    print("  2. Quiet, low-traffic streets safe for kids to bike")
    print("     → proxy: violent_per_1k < 0.5 + suburban/historic built form + low density area")
    print()
    print("Political note: 'Progressive + Moderate' applied as lean_2024 >= -0.15 (excludes strong R).")
    print("Bay & Harbor AO waterfront: only Battery Park City has bay_harbor>0 in NYC — treated as soft bonus.")

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nWrote {len(results)} results to {out_path}")


if __name__ == "__main__":
    main()
