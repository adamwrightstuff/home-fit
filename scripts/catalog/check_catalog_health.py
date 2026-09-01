#!/usr/bin/env python3
"""
Catalog health check — per-place, per-pillar diagnostics on the scored JSONL.

Checks:
  1. Pillar scoring version — on a known OLD version (not just unversioned)?
  2. Unversioned pillars — scored before version tracking was added?
  3. Missing/null pillar scores
  4. Low confidence — below per-pillar threshold
  5. Degraded pillars — data_quality.degraded=True
  6. Data warnings — non-empty data_quality.data_warnings
  7. Fallback scoring used — data_quality.fallback_metadata.fallback_used=True
  8. Missing subcomponents — expected breakdown keys absent or None
  8b. Zero subcomponents — breakdown key present but =0 when that indicates data failure
  9. Missing catalog metadata — null lat/lon, empty search_query, null lean_2024
 10. No area type — area_classification empty and score.area_type null
 11. Composite drift — stored happiness/longevity vs recomputed from breakdown

Usage:
  PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py
  PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --csv > health.csv
  PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --pillar public_transit_access
  PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --min-flags 3
  PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --no-unversioned   # hide unversioned noise
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"

# Per-pillar confidence thresholds. Pillars with structurally low confidence
# (healthcare, air travel) get a lower bar so they don't flood the report.
CONFIDENCE_THRESHOLDS: Dict[str, int] = {
    "healthcare_access":    30,
    "air_travel_access":    50,
    "built_environment":    30,
    "quality_education":    50,
    "community_safety":     50,
    "default":              70,
}

# Pillars where score=None is expected (no aggregate numeric score by design)
NO_SCORE_EXPECTED = {"political_lean"}

# Pillars that must be present and scored in every catalog row.
# Absence of the key entirely (not just null score) is flagged as pillar_absent.
EXPECTED_PILLARS = {
    "active_outdoors", "natural_beauty", "neighborhood_amenities",
    "air_travel_access", "public_transit_access", "healthcare_access",
    "economic_opportunity", "quality_education", "housing_value",
    "climate_risk", "social_fabric", "diversity", "community_safety",
}

# Known OLD versions that should be flagged (scored under a superseded algorithm).
# None = pillar isn't versioned yet, handled separately.
OLD_VERSIONS: Dict[str, set] = {
    "public_transit_access": {"commuter_access_floor_fresh"},
    "social_fabric":         {"v14_two_morphology", "v14_sf_two_morphology"},
}

# Latest version per pillar — presence of this version means the place is current.
# Absence means either unversioned (old) or on a known old version above.
# NOTE: transit has two valid terminal versions depending on place type:
#   commuter_access_floor_ridership — commuter-rail towns (floor applied on top of v3)
#   transit_v3_subway_commuter_split — subway towns (floor is a no-op; v3 is terminal)
# The transit-specific check below handles this; LATEST_VERSIONS holds the floor version
# so unversioned places surface correctly.
LATEST_VERSIONS: Dict[str, str] = {
    "active_outdoors":        "active_outdoors_v2_component_sum",
    "air_travel_access":      "air_travel_commute_bands",
    # economic_opportunity: live scorer computes job_access natively; no migration stamp expected
    "housing_value":          "housing_empty_tract_fix",
    "neighborhood_amenities": "amenities_v3_walkable_density",
    "public_transit_access":  "commuter_access_floor_ridership",
    "quality_education":      "education_weight_enabled",
    "social_fabric":          "v16b_sf_with_rootedness",
}

# Expected non-None breakdown subcomponents per pillar.
EXPECTED_BREAKDOWN: Dict[str, List[str]] = {
    "active_outdoors":        ["daily_urban_outdoors", "wild_adventure", "waterfront_lifestyle"],
    "neighborhood_amenities": ["home_walkability", "location_quality"],
    "public_transit_access":  ["heavy_rail", "bus", "commute_time"],
    "healthcare_access":      ["hospital_access", "primary_care", "pharmacies"],
    "economic_opportunity":      ["density", "mobility", "ecosystem", "resilience"],
    "quality_education":      ["base_avg_rating"],
    "housing_value":          ["local_affordability", "space", "value_efficiency"],
    "climate_risk":           ["heat_exposure_pts", "air_quality_pts", "flood_zone_pts", "climate_trend_pts"],
    "social_fabric":          ["participation", "social_capital", "peer_civic", "rootedness"],
    "diversity":              ["race_entropy", "income_entropy", "age_entropy"],
    "community_safety":       ["violent_per_1k", "property_per_1k"],
}

NB_V9_KEYS = ["gvi_score", "water_score", "canopy_score", "topo_score", "landcover_score"]

# Subcomponents where a stored value of exactly 0 is suspicious — it indicates a data
# failure (Overpass timeout, GEE API error, missing source data) rather than a true zero.
# Legitimate zeros (crime trend flat = 0, no elite schools = 0, no waterfront = 0) are
# NOT listed here.
#
# Values are either "always" (zero is implausible regardless of geography) or a set of
# area_type strings (zero is only suspicious in those geographies).
ZERO_SUSPICIOUS_SUBCOMPONENTS: Dict[str, Dict[str, Any]] = {
    "active_outdoors": {
        # Every urban/suburban place has some parks or green space; 0 means Overpass failed
        "daily_urban_outdoors": {"urban_core", "urban_residential", "suburban"},
    },
    "natural_beauty": {
        # Satellite land-cover is available everywhere on Earth; 0 = GEE call failed
        "landcover_score": "always",
    },
    "healthcare_access": {
        # Any populated place has at least some hospitals/clinics within range; 0 = API error
        "specialized_care": "always",
        "emergency_services": "always",
    },
}

HAPPINESS_COMPONENT_WEIGHTS = {
    "social":       0.30,
    "safety":       0.20,
    "commute":      0.15,
    "neighborhood": 0.05,
    "home_space":   0.10,
    "green":        0.12,
    "education":    0.08,
}

# Pillars that store confidence on 0-1 scale instead of 0-100
ZERO_ONE_CONFIDENCE_PILLARS = {"political_lean"}

# Pillars where confidence is structurally undefined in residential catalog mode
# and should not be flagged (built_environment is vacation/road_trip only)
SKIP_CONFIDENCE_PILLARS = {"built_environment"}


def pillar_version(pillar: str, data: Dict[str, Any]) -> Optional[str]:
    if pillar == "natural_beauty":
        # Older batch runs (NYC/LA) store scoring_formula at pillar root.
        # Newer batch runs (SF) store it inside details. Check both; prefer scoring_formula.
        details = data.get("details") or {}
        return (details.get("scoring_formula") or details.get("scoring_version") or
                data.get("scoring_formula") or data.get("scoring_version"))
    return data.get("_rescore_version") or data.get("_version") or data.get("version")


def check_pillar(pillar: str, data: Dict[str, Any], show_unversioned: bool) -> List[str]:
    flags: List[str] = []

    score = data.get("score")
    status = data.get("status")
    if score is None and pillar not in NO_SCORE_EXPECTED:
        # built_environment is preference-gated: top-level score is null when no user
        # preference is set (catalog mode), but the quality score is in details.
        # Check that instead so we don't false-flag preference-gated nulls as data gaps.
        if pillar == "built_environment" and (data.get("details") or {}).get("built_environment_score"):
            pass
        else:
            flags.append("score_null")
    # fallback with score=0 is a data gap (e.g. education where SchoolDigger returned nothing)
    elif status == "fallback" and score == 0 and pillar not in NO_SCORE_EXPECTED:
        flags.append("fallback_zero")

    dq = data.get("data_quality") or {}

    conf = dq.get("confidence")
    threshold = CONFIDENCE_THRESHOLDS.get(pillar, CONFIDENCE_THRESHOLDS["default"])
    # Some pillars store confidence on 0-1 scale or are structurally unscored in catalog mode
    if pillar in ZERO_ONE_CONFIDENCE_PILLARS or pillar in SKIP_CONFIDENCE_PILLARS:
        conf = None
    if isinstance(conf, (int, float)) and conf < threshold:
        flags.append(f"conf_{int(conf)}")

    if dq.get("degraded") is True:
        flags.append("degraded")

    warnings = dq.get("data_warnings") or []
    if warnings:
        short = ",".join(str(w)[:20] for w in warnings[:2])
        flags.append(f"warn:{short}")

    fb = (dq.get("fallback_metadata") or {})
    if fb.get("fallback_used") is True:
        flags.append("fallback_used")

    # Version checks
    got = pillar_version(pillar, data)
    old = OLD_VERSIONS.get(pillar, set())
    latest = LATEST_VERSIONS.get(pillar)

    if got and old and got in old:
        flags.append(f"OLD_VERSION:{got}")
    elif latest and got != latest and show_unversioned:
        flags.append(f"unversioned" if not got else f"version:{got}")

    # Missing subcomponents
    breakdown = data.get("breakdown") or {}
    for key in EXPECTED_BREAKDOWN.get(pillar, []):
        val = breakdown.get(key)
        if val is None:
            flags.append(f"missing:{key}")

    # Zero subcomponents — present but =0 when that signals data failure, not true zero
    area_type = (data.get("area_classification") or {}).get("area_type") or ""
    for key, condition in (ZERO_SUSPICIOUS_SUBCOMPONENTS.get(pillar) or {}).items():
        val = breakdown.get(key)
        if val is not None and val == 0:
            if condition == "always" or area_type in condition:
                flags.append(f"zero:{key}")

    # natural_beauty v9_breakdown — stored at pillar root in older batches (NYC/LA),
    # inside details in newer batches (SF). Check both locations.
    if pillar == "natural_beauty" and got == "v9":
        v9 = data.get("v9_breakdown") or (data.get("details") or {}).get("v9_breakdown") or {}
        for key in NB_V9_KEYS:
            if v9.get(key) is None:
                flags.append(f"missing:v9.{key}")

    # Transit: check if Transitland API was unavailable and score fell back to commute-time only
    if pillar == "public_transit_access":
        summary = data.get("summary") or {}
        if summary.get("fallback_applied") is True:
            flags.append("transit_api_fallback")

    # Transit has two valid terminal versions: commuter_access_floor_ridership for
    # commuter-rail towns, transit_v3_subway_commuter_split for subway towns.
    # Override the generic version flag accordingly.
    if pillar == "public_transit_access" and got == "transit_v3_subway_commuter_split":
        summary = data.get("summary") or {}
        modes = summary.get("transit_modes_available") or []
        commuter_routes = summary.get("commuter_rail_routes") or 0
        if "Subway/Metro" in modes:
            # Subway town — v3 is the correct terminal; clear any spurious version: flag
            flags = [f for f in flags if not f.startswith("version:")]
        elif commuter_routes > 0:
            # Has commuter rail — floor should have been applied (or checked); flag it
            flags = [f for f in flags if not f.startswith("version:")]
            flags.append("OLD_VERSION:floor_not_applied")
        else:
            # Bus-only / no rail — v3 is the correct terminal state; clear version: flag
            flags = [f for f in flags if not f.startswith("version:")]

    return flags


def recompute_happiness(breakdown: Dict[str, Any]) -> Optional[float]:
    """Recompute happiness from stored component scores and weights."""
    weights = breakdown.get("component_weights") or HAPPINESS_COMPONENT_WEIGHTS
    total = 0.0
    for key, w in weights.items():
        val = breakdown.get(key)
        if val is None:
            return None
        total += val * w
    return round(total, 2)


def recompute_longevity(breakdown: Dict[str, Any]) -> Optional[float]:
    """Longevity breakdown stores pre-weighted contributions — just sum them."""
    if not breakdown:
        return None
    total = sum(v for v in breakdown.values() if isinstance(v, (int, float)))
    return round(total, 2) if total else None


def compute_outliers(
    rows: List[Dict[str, Any]],
    pillar_filter: Optional[str] = None,
    min_group: int = 8,
    low_z: float = -2.0,
    high_z: float = 2.5,
) -> Dict[Tuple[str, str], Tuple[float, float, float, str, str]]:
    """Return {(name, pillar): (z, mean, sd, area_type, 'low'|'high')} for outliers.

    Groups by (pillar, area_type). Groups smaller than min_group are skipped.
    """
    groups: Dict[Tuple[str, str], List[Tuple[str, float]]] = defaultdict(list)

    for row in rows:
        if not row.get("success"):
            continue
        cat = row.get("catalog") or {}
        name = cat.get("name") or cat.get("search_query") or "?"
        sc = row.get("score") or {}
        lp = sc.get("livability_pillars") or {}
        for pillar, pdata in lp.items():
            if pillar_filter and pillar != pillar_filter:
                continue
            if not isinstance(pdata, dict):
                continue
            if pillar in NO_SCORE_EXPECTED:
                continue
            score_val = pdata.get("score")
            if not isinstance(score_val, (int, float)):
                continue
            ac = pdata.get("area_classification") or {}
            area_type = ac.get("area_type") or "unknown"
            groups[(pillar, area_type)].append((name, score_val))

    outliers: Dict[Tuple[str, str], Tuple[float, float, float, str, str]] = {}
    for (pillar, area_type), entries in groups.items():
        if len(entries) < min_group:
            continue
        scores = [s for _, s in entries]
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)
        sd = math.sqrt(variance) if variance > 0 else 0.0
        if sd < 1.0:
            continue
        for name, score_val in entries:
            z = (score_val - mean) / sd
            if z < low_z:
                outliers[(name, pillar)] = (z, mean, sd, area_type, "low")
            elif z > high_z:
                outliers[(name, pillar)] = (z, mean, sd, area_type, "high")

    return outliers


def check_row(
    row: Dict[str, Any], pillar_filter: Optional[str], show_unversioned: bool
) -> Tuple[str, List[str], Dict[str, List[str]]]:
    cat = row.get("catalog") or {}
    name = cat.get("name") or cat.get("search_query") or "?"
    place_flags: List[str] = []
    pillar_flags: Dict[str, List[str]] = {}

    # Catalog metadata
    if not cat.get("lat") or not cat.get("lon"):
        place_flags.append("missing:lat_lon")
    if not (cat.get("search_query") or "").strip():
        place_flags.append("missing:search_query")
    # lean_2024 tracked in summary only — too many places genuinely lack election data
    # to be useful as a per-place flag

    sc = row.get("score") or {}
    if not (sc.get("location_info") or {}).get("zip", "").strip():
        place_flags.append("missing:zip")
    lp_any = sc.get("livability_pillars") or {}

    # Area type — check inside any pillar's area_classification (stored per-pillar, not top-level)
    def _has_area_type() -> bool:
        if sc.get("area_type"):
            return True
        for pdata in lp_any.values():
            if isinstance(pdata, dict):
                ac = pdata.get("area_classification") or {}
                if ac.get("area_type"):
                    return True
        return False

    if not _has_area_type():
        place_flags.append("no_area_type")

    lp = lp_any
    for pillar, data in lp.items():
        if pillar_filter and pillar != pillar_filter:
            continue
        if not isinstance(data, dict):
            continue
        flags = check_pillar(pillar, data, show_unversioned)
        if flags:
            pillar_flags[pillar] = flags

    # Check for expected pillars entirely absent from the JSONL
    for pillar in EXPECTED_PILLARS:
        if pillar_filter and pillar != pillar_filter:
            continue
        if pillar not in lp:
            pillar_flags.setdefault(pillar, []).append("pillar_absent")

    # Composite drift — recompute from stored breakdown components
    if not pillar_filter:
        stored_h = sc.get("happiness_index")
        hb = sc.get("happiness_index_breakdown") or {}
        if stored_h is not None and hb:
            computed_h = recompute_happiness(hb)
            if computed_h is not None and abs(stored_h - computed_h) > 1.0:
                place_flags.append(f"happiness_drift:{stored_h:.1f}vs{computed_h:.1f}")

        stored_l = sc.get("longevity_index")
        lb = sc.get("longevity_index_breakdown") or {}
        if stored_l is None:
            place_flags.append("missing:longevity_index")
        elif lb:
            computed_l = recompute_longevity(lb)
            if computed_l is not None and abs(stored_l - computed_l) > 1.0:
                place_flags.append(f"longevity_drift:{stored_l:.1f}vs{computed_l:.1f}")

        # status_signal drift — breakdown.composite_score should match top-level
        stored_ss = sc.get("status_signal")
        ssb = sc.get("status_signal_breakdown") or {}
        if stored_ss is None:
            place_flags.append("missing:status_signal")
        elif ssb:
            comp_ss = ssb.get("composite_score")
            if comp_ss is not None and abs(stored_ss - comp_ss) > 0.5:
                place_flags.append(f"status_signal_drift:{stored_ss:.1f}vs{comp_ss:.1f}")

        # total_score drift — recompute from stored contributions + token_allocation fallback.
        # False-positive patterns excluded:
        #   1. contribution=None pillars get recomputed from token_allocation at runtime;
        #      health check must do the same or it under-counts and flags false drift.
        #   2. SF-style high-scoring places: uncapped contribution sum > 100 but stored total
        #      is correctly min(100, sum) — compare after applying the same cap.
        #   3. Stored data-gap pillars (score=None, contribution=0.0, weight>0): recompute
        #      applies a gap scale (100 / (100 - gap_w)) to avoid penalising the place for
        #      a missing pillar.  Health check must mirror this or it flags correct totals.
        stored_t = sc.get("total_score")
        token_alloc = sc.get("token_allocation") or {}
        pillars_for_drift = sc.get("livability_pillars") or {}
        if stored_t is None:
            place_flags.append("missing:total_score")
        elif pillars_for_drift:
            _s_total = 0.0
            _r_weights: Dict[str, float] = {}
            _gap_w = 0.0
            for _pname, _pdata in pillars_for_drift.items():
                if not isinstance(_pdata, dict):
                    continue
                _contrib = _pdata.get("contribution")
                _stored_w = _pdata.get("weight")
                _pillar_w = float(_stored_w) if isinstance(_stored_w, (int, float)) else float(token_alloc.get(_pname) or 0)
                _is_gap = (_contrib == 0.0 and _pdata.get("score") is None and _pillar_w > 0)
                if _is_gap:
                    _gap_w += _pillar_w
                elif isinstance(_contrib, (int, float)):
                    _s_total += float(_contrib)
                else:
                    _w = _stored_w
                    if not isinstance(_w, (int, float)):
                        _w = token_alloc.get(_pname)
                    _r_weights[_pname] = float(_w) if isinstance(_w, (int, float)) else 0.0
            _r_total = sum(
                float((pillars_for_drift.get(_p) or {}).get("score") or 0.0) * _w / 100.0
                for _p, _w in _r_weights.items()
                if isinstance((pillars_for_drift.get(_p) or {}).get("score"), (int, float)) and _w > 0
            )
            _gap_scale = (100.0 / (100.0 - _gap_w)) if _gap_w > 0 else 1.0
            computed_t = round(min(100.0, (_s_total + _r_total) * _gap_scale), 2)
            if abs(stored_t - computed_t) > 1.0:
                place_flags.append(f"total_score_drift:{stored_t:.1f}vs{computed_t:.1f}")

        # happiness null check (drift already handled above)
        if sc.get("happiness_index") is None:
            place_flags.append("missing:happiness_index")

        # lean_2024 per-place (political_lean.breakdown.lean_2024)
        pl_bd = (lp_any.get("political_lean") or {}).get("breakdown") or {}
        if pl_bd.get("lean_2024") is None:
            place_flags.append("missing:lean_2024")

    return name, place_flags, pillar_flags


def load_last(path: Path) -> List[Dict[str, Any]]:
    last: Dict[str, Any] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            cat = obj.get("catalog") or {}
            key = cat.get("search_query") or cat.get("name") or ""
            if key:
                last[key] = obj
    return [last[k] for k in sorted(last)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Catalog health check")
    ap.add_argument("--input", type=Path, default=JSONL)
    ap.add_argument("--pillar", default=None, help="Focus on one pillar")
    ap.add_argument("--min-flags", type=int, default=0, help="Only show places with >= N total flags")
    ap.add_argument("--csv", action="store_true", help="Output CSV")
    ap.add_argument("--no-unversioned", action="store_true", help="Suppress unversioned/version: flags (reduce noise)")
    args = ap.parse_args()

    show_unversioned = not args.no_unversioned
    rows = load_last(args.input)

    results = []
    for row in rows:
        if not row.get("success"):
            continue
        name, place_flags, pillar_flags = check_row(row, args.pillar, show_unversioned)
        total_flags = len(place_flags) + sum(len(v) for v in pillar_flags.values())
        results.append((name, place_flags, pillar_flags, total_flags))

    results.sort(key=lambda x: -x[3])

    if args.csv:
        all_pillars = sorted({p for _, _, pf, _ in results for p in pf} |
                             {p for _, _, pf, _ in results for p in pf})
        all_pillars = sorted(EXPECTED_BREAKDOWN.keys())
        header = ["name", "total_flags", "place_flags"] + all_pillars
        print(",".join(header))
        for name, place_flags, pillar_flags, total in results:
            if total < args.min_flags:
                continue
            row_vals = [
                name, str(total), "|".join(place_flags),
            ] + ["|".join(pillar_flags.get(p, [])) for p in all_pillars]
            print(",".join(f'"{v}"' for v in row_vals))
        return 0

    # ── Text report ─────────────────────────────────────────────────────────
    print("=" * 72)
    print(f"CATALOG HEALTH CHECK  —  {args.input.name}  ({len(results)} places)")
    if not show_unversioned:
        print("  (--no-unversioned active: unversioned/version: flags suppressed)")
    print("=" * 72)

    # Bucket all flags by type
    old_version_issues:  Dict[str, List[str]] = defaultdict(list)
    unversioned_issues:  Dict[str, List[str]] = defaultdict(list)
    null_scores:         Dict[str, List[str]] = defaultdict(list)
    fallback_zeros:      Dict[str, List[str]] = defaultdict(list)
    absent_pillars:      Dict[str, List[str]] = defaultdict(list)
    composite_drifts:    Dict[str, List[str]] = defaultdict(list)
    missing_composites:  Dict[str, List[str]] = defaultdict(list)
    low_conf:            Dict[str, List[Tuple[str,str]]] = defaultdict(list)
    degraded_issues:     Dict[str, List[str]] = defaultdict(list)
    warning_issues:      Dict[str, List[str]] = defaultdict(list)
    fallback_issues:     Dict[str, List[str]] = defaultdict(list)
    transit_api_fallbacks: Dict[str, List[str]] = defaultdict(list)
    missing_sub:         Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    zero_sub:            Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    for name, _, pillar_flags, _ in results:
        for pillar, flags in pillar_flags.items():
            for f in flags:
                if f.startswith("OLD_VERSION:"):
                    old_version_issues[pillar].append(f"{name} ({f[12:]})")
                elif f in ("unversioned",) or f.startswith("version:"):
                    unversioned_issues[pillar].append(f"{name} ({f})")
                elif f == "score_null":
                    null_scores[pillar].append(name)
                elif f == "fallback_zero":
                    fallback_zeros[pillar].append(name)
                elif f == "pillar_absent":
                    absent_pillars[pillar].append(name)
                elif f.startswith("conf_"):
                    low_conf[pillar].append((name, f))
                elif f == "degraded":
                    degraded_issues[pillar].append(name)
                elif f.startswith("warn:"):
                    warning_issues[pillar].append(f"{name}[{f[5:]}]")
                elif f == "fallback_used":
                    fallback_issues[pillar].append(name)
                elif f == "transit_api_fallback":
                    transit_api_fallbacks[pillar].append(name)
                elif f.startswith("missing:"):
                    missing_sub[pillar][f[8:]].append(name)
                elif f.startswith("zero:"):
                    zero_sub[pillar][f[5:]].append(name)

    for name, place_flags, _, _ in results:
        for f in place_flags:
            if f.endswith("_drift") or "_drift:" in f:
                key = f.split(":")[0]
                composite_drifts[key].append(f"{name} ({f.split(':',1)[1]})")
            elif f.startswith("missing:") and f[8:] in (
                "total_score", "status_signal", "happiness_index",
                "longevity_index", "lean_2024",
            ):
                missing_composites[f[8:]].append(name)

    place_meta_issues = [(n, pf) for n, pf, _, _ in results if pf]

    # ── Section 1: Known old versions (highest priority) ──────────────────
    if old_version_issues:
        print("\n── KNOWN OLD VERSION (needs rescore) ──────────────────────────────")
        for pillar in sorted(old_version_issues):
            latest = LATEST_VERSIONS.get(pillar, "?")
            places = old_version_issues[pillar]
            print(f"\n  {pillar}  →  latest: {latest}  ({len(places)} place(s)):")
            for p in places:
                print(f"    • {p}")
    else:
        print("\n  ✓ No known old-version pillars found.")

    # ── Section 2: Unversioned pillars ────────────────────────────────────
    if unversioned_issues and show_unversioned:
        print("\n── UNVERSIONED (scored before version tracking) ───────────────────")
        for pillar in sorted(unversioned_issues):
            places = unversioned_issues[pillar]
            print(f"  {pillar}: {len(places)} place(s)  (first 5: {', '.join(p.split(' (')[0] for p in places[:5])}{'...' if len(places) > 5 else ''})")

    # ── Section 3: Null scores ─────────────────────────────────────────────
    if null_scores:
        print("\n── NULL SCORES ────────────────────────────────────────────────────")
        for pillar in sorted(null_scores):
            print(f"  {pillar}: {', '.join(null_scores[pillar])}")

    # ── Section 3b: Absent pillars (key not in JSONL at all) ──────────────
    if absent_pillars:
        print("\n── ABSENT PILLARS (never scored — key missing from JSONL) ─────────")
        for pillar in sorted(absent_pillars):
            places = absent_pillars[pillar]
            truncated = ', '.join(places[:6]) + (f' +{len(places)-6} more' if len(places) > 6 else '')
            print(f"  {pillar}: {len(places)} place(s) — {truncated}")

    # ── Section 3c: Fallback zeros (status=fallback, score=0 — no real data) ──
    if fallback_zeros:
        print("\n── FALLBACK ZEROS (status=fallback, score=0 — treat as missing) ───")
        for pillar in sorted(fallback_zeros):
            places = fallback_zeros[pillar]
            truncated = ', '.join(places[:6]) + (f' +{len(places)-6} more' if len(places) > 6 else '')
            print(f"  {pillar}: {len(places)} place(s) — {truncated}")

    # ── Section 4: Low confidence ──────────────────────────────────────────
    if low_conf:
        print("\n── LOW CONFIDENCE ─────────────────────────────────────────────────")
        for pillar in sorted(low_conf):
            threshold = CONFIDENCE_THRESHOLDS.get(pillar, CONFIDENCE_THRESHOLDS["default"])
            entries = ", ".join(f"{n}[{f}]" for n, f in low_conf[pillar][:8])
            suffix = f" +{len(low_conf[pillar])-8} more" if len(low_conf[pillar]) > 8 else ""
            print(f"  {pillar} (threshold {threshold}): {entries}{suffix}")

    # ── Section 5: Degraded ────────────────────────────────────────────────
    if degraded_issues:
        print("\n── DEGRADED PILLARS ───────────────────────────────────────────────")
        for pillar in sorted(degraded_issues):
            places = degraded_issues[pillar]
            print(f"  {pillar}: {len(places)} — {', '.join(places[:8])}{'...' if len(places)>8 else ''}")

    # ── Section 6: Data warnings ───────────────────────────────────────────
    if warning_issues:
        print("\n── DATA WARNINGS ──────────────────────────────────────────────────")
        for pillar in sorted(warning_issues):
            print(f"  {pillar}: {', '.join(warning_issues[pillar][:6])}{'...' if len(warning_issues[pillar])>6 else ''}")

    # ── Section 7: Fallback ────────────────────────────────────────────────
    if fallback_issues:
        print("\n── FALLBACK SCORING ───────────────────────────────────────────────")
        for pillar in sorted(fallback_issues):
            print(f"  {pillar}: {', '.join(fallback_issues[pillar])}")

    # ── Section 7b: Transit API fallback ──────────────────────────────────
    if transit_api_fallbacks:
        print("\n── TRANSIT API FALLBACK (Transitland unavailable — commute-time only) ─")
        for pillar in sorted(transit_api_fallbacks):
            places = transit_api_fallbacks[pillar]
            truncated = ', '.join(places[:6]) + (f' +{len(places)-6} more' if len(places) > 6 else '')
            print(f"  {pillar}: {len(places)} place(s) — {truncated}")

    # ── Section 7c: Composite drift / missing composites ─────────────────
    if composite_drifts or missing_composites:
        print("\n── COMPOSITE DRIFT / MISSING (total_score, status_signal, happiness, longevity) ─")
        for key in sorted(missing_composites):
            places = missing_composites[key]
            truncated = ', '.join(places[:6]) + (f' +{len(places)-6} more' if len(places) > 6 else '')
            print(f"  missing:{key}: {len(places)} place(s) — {truncated}")
        for key in sorted(composite_drifts):
            entries = composite_drifts[key]
            truncated = ', '.join(entries[:4]) + (f' +{len(entries)-4} more' if len(entries) > 4 else '')
            print(f"  {key}: {len(entries)} place(s) — {truncated}")

    # ── Section 8: Missing subcomponents ──────────────────────────────────
    if missing_sub:
        print("\n── MISSING SUBCOMPONENTS ──────────────────────────────────────────")
        for pillar in sorted(missing_sub):
            for sub, places in sorted(missing_sub[pillar].items()):
                truncated = ', '.join(places[:5]) + ('...' if len(places) > 5 else '')
                print(f"  {pillar}.{sub}: {len(places)} place(s) — {truncated}")

    # ── Section 8b: Zero subcomponents ────────────────────────────────────
    if zero_sub:
        print("\n── ZERO SUBCOMPONENTS (present=0 — likely data failure, not true zero) ─")
        for pillar in sorted(zero_sub):
            for sub, places in sorted(zero_sub[pillar].items()):
                truncated = ', '.join(places[:5]) + (f' +{len(places)-5} more' if len(places) > 5 else '')
                print(f"  {pillar}.{sub}: {len(places)} place(s) — {truncated}")

    # ── Section 9: Plausibility outliers ──────────────────────────────────
    # Build name→row lookup for score retrieval
    name_to_row: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cat = row.get("catalog") or {}
        n = cat.get("name") or cat.get("search_query") or "?"
        name_to_row[n] = row

    outliers = compute_outliers(rows, pillar_filter=args.pillar)
    if outliers:
        print("\n── PLAUSIBILITY OUTLIERS (z < -2.0 low  /  z > +2.5 high) ────────")
        by_pillar: Dict[str, list] = defaultdict(list)
        for (name, pillar), (z, mean, sd, area_type, direction) in outliers.items():
            by_pillar[pillar].append((name, z, mean, sd, area_type, direction))
        for pillar in sorted(by_pillar):
            entries_sorted = sorted(by_pillar[pillar], key=lambda t: t[1])
            print(f"\n  {pillar}:")
            for name, z, mean, sd, area_type, direction in entries_sorted:
                row2 = name_to_row.get(name) or {}
                lp2 = (row2.get("score") or {}).get("livability_pillars") or {}
                score_val = (lp2.get(pillar) or {}).get("score")
                score_str = f"{score_val:.1f}" if isinstance(score_val, (int, float)) else "?"
                tag = "LOW" if direction == "low" else "HIGH"
                print(f"    • {name:<32} score={score_str:<6} z={z:+.2f}  ({area_type}: mean={mean:.1f} sd={sd:.1f})  {tag}")
    else:
        print("\n  ✓ No plausibility outliers detected.")

    # ── Section 10: Place metadata ─────────────────────────────────────────
    if place_meta_issues:
        print("\n── PLACE METADATA ISSUES ──────────────────────────────────────────")
        # Group by flag type
        by_flag: Dict[str, List[str]] = defaultdict(list)
        for name, flags in place_meta_issues:
            for f in flags:
                by_flag[f].append(name)
        for flag, places in sorted(by_flag.items()):
            truncated = ', '.join(places[:6]) + ('...' if len(places) > 6 else '')
            print(f"  {flag}: {len(places)} place(s) — {truncated}")

    # ── Section 11: Per-place summary ─────────────────────────────────────
    print("\n── PER-PLACE FLAG SUMMARY ─────────────────────────────────────────")
    shown = 0
    for name, place_flags, pillar_flags, total in results:
        if total < max(args.min_flags, 1):
            continue
        top = sorted(pillar_flags, key=lambda p: -len(pillar_flags[p]))[:4]
        pil_str = "  ".join(f"{p}({len(pillar_flags[p])})" for p in top)
        meta_str = f"  meta:[{','.join(place_flags)}]" if place_flags else ""
        print(f"  {name:<30}  {total:2d}  {pil_str}{meta_str}")
        shown += 1

    clean = len(results) - shown
    print(f"\n  {shown} flagged / {clean} clean / {len(results)} total")

    # ── Summary stats ─────────────────────────────────────────────────────
    print("\n── SUMMARY ────────────────────────────────────────────────────────")
    print(f"  Known old versions      : {sum(len(v) for v in old_version_issues.values())}")
    print(f"  Unversioned pillars     : {sum(len(v) for v in unversioned_issues.values())}")
    print(f"  Null scores             : {sum(len(v) for v in null_scores.values())}")
    print(f"  Absent pillars          : {sum(len(v) for v in absent_pillars.values())}")
    print(f"  Fallback zeros          : {sum(len(v) for v in fallback_zeros.values())}")
    print(f"  Low confidence          : {sum(len(v) for v in low_conf.values())}")
    print(f"  Degraded                : {sum(len(v) for v in degraded_issues.values())}")
    print(f"  Data warnings           : {sum(len(v) for v in warning_issues.values())}")
    print(f"  Fallback used           : {sum(len(v) for v in fallback_issues.values())}")
    print(f"  Transit API fallback    : {sum(len(v) for v in transit_api_fallbacks.values())}")
    print(f"  Missing subcomponents   : {sum(len(vv) for v in missing_sub.values() for vv in v.values())}")
    print(f"  Zero subcomponents      : {sum(len(vv) for v in zero_sub.values() for vv in v.values())}")
    print(f"  Metadata issues         : {sum(len(pf) for _, pf, _, _ in results)}")
    n_low = sum(1 for v in outliers.values() if v[4] == "low")
    n_high = sum(1 for v in outliers.values() if v[4] == "high")
    print(f"  Plausibility outliers   : {len(outliers)} ({n_low} low / {n_high} high)")
    n_composite_drift  = sum(len(v) for v in composite_drifts.values())
    n_missing_composite = sum(len(v) for v in missing_composites.values())
    print(f"  Composite drift         : {n_composite_drift}")
    print(f"  Missing composites      : {n_missing_composite}")
    lean_missing = len(missing_composites.get("lean_2024", []))
    print(f"  Missing lean_2024       : {lean_missing} / {len(results)} places (election data gap)")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
