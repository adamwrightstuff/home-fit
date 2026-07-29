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
    "neighborhood_beauty":  30,
    "built_environment":    30,
    "quality_education":    50,
    "community_safety":     50,
    "default":              70,
}

# Pillars where score=None is expected (no aggregate numeric score by design)
NO_SCORE_EXPECTED = {"political_lean"}

# Known OLD versions that should be flagged (scored under a superseded algorithm).
# None = pillar isn't versioned yet, handled separately.
OLD_VERSIONS: Dict[str, set] = {
    "public_transit_access": {"commuter_access_floor_fresh"},
    "social_fabric":         {"v14_two_morphology"},
}

# Latest version per pillar — presence of this version means the place is current.
# Absence means either unversioned (old) or on a known old version above.
LATEST_VERSIONS: Dict[str, str] = {
    "active_outdoors":        "active_outdoors_v2_component_sum",
    "air_travel_access":      "air_travel_commute_bands",
    "economic_security":      "econ_job_access_blend",
    "housing_value":          "housing_empty_tract_fix",
    "neighborhood_amenities": "amenities_v3_walkable_density",
    "public_transit_access":  "transit_v3_subway_commuter_split",
    "quality_education":      "education_weight_enabled",
    "social_fabric":          "v14_sf_two_morphology",
}

# Expected non-None breakdown subcomponents per pillar.
EXPECTED_BREAKDOWN: Dict[str, List[str]] = {
    "active_outdoors":        ["daily_urban_outdoors", "wild_adventure", "waterfront_lifestyle"],
    "neighborhood_amenities": ["home_walkability", "location_quality"],
    "public_transit_access":  ["heavy_rail", "bus", "commute_time"],
    "healthcare_access":      ["hospital_access", "primary_care", "pharmacies"],
    "economic_security":      ["density", "mobility", "ecosystem", "resilience"],
    "quality_education":      ["base_avg_rating"],
    "housing_value":          ["local_affordability", "space", "value_efficiency"],
    "climate_risk":           ["heat_exposure_pts", "air_quality_pts", "flood_zone_pts", "climate_trend_pts"],
    "social_fabric":          ["participation", "social_capital", "peer_civic", "rootedness"],
    "diversity":              ["race_entropy", "income_entropy", "age_entropy"],
    "community_safety":       ["violent_per_1k", "property_per_1k"],
    "neighborhood_beauty":    ["built_environment_score", "natural_beauty_score"],
}

NB_V9_KEYS = ["gvi_score", "water_score", "canopy_score", "topo_score", "landcover_score"]

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


def pillar_version(pillar: str, data: Dict[str, Any]) -> Optional[str]:
    if pillar == "natural_beauty":
        return data.get("scoring_version") or data.get("scoring_formula")
    return data.get("_rescore_version") or data.get("_version") or data.get("version")


def check_pillar(pillar: str, data: Dict[str, Any], show_unversioned: bool) -> List[str]:
    flags: List[str] = []

    score = data.get("score")
    if score is None and pillar not in NO_SCORE_EXPECTED:
        flags.append("score_null")

    dq = data.get("data_quality") or {}

    conf = dq.get("confidence")
    threshold = CONFIDENCE_THRESHOLDS.get(pillar, CONFIDENCE_THRESHOLDS["default"])
    # Some pillars (political_lean) store confidence on 0-1 scale — skip those
    if pillar in ZERO_ONE_CONFIDENCE_PILLARS:
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

    # natural_beauty v9_breakdown
    if pillar == "natural_beauty":
        v9 = data.get("v9_breakdown") or {}
        for key in NB_V9_KEYS:
            if v9.get(key) is None:
                flags.append(f"missing:v9.{key}")

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
        if stored_l is not None and lb:
            computed_l = recompute_longevity(lb)
            if computed_l is not None and abs(stored_l - computed_l) > 1.0:
                place_flags.append(f"longevity_drift:{stored_l:.1f}vs{computed_l:.1f}")

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
    low_conf:            Dict[str, List[Tuple[str,str]]] = defaultdict(list)
    degraded_issues:     Dict[str, List[str]] = defaultdict(list)
    warning_issues:      Dict[str, List[str]] = defaultdict(list)
    fallback_issues:     Dict[str, List[str]] = defaultdict(list)
    missing_sub:         Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    for name, _, pillar_flags, _ in results:
        for pillar, flags in pillar_flags.items():
            for f in flags:
                if f.startswith("OLD_VERSION:"):
                    old_version_issues[pillar].append(f"{name} ({f[12:]})")
                elif f in ("unversioned",) or f.startswith("version:"):
                    unversioned_issues[pillar].append(f"{name} ({f})")
                elif f == "score_null":
                    null_scores[pillar].append(name)
                elif f.startswith("conf_"):
                    low_conf[pillar].append((name, f))
                elif f == "degraded":
                    degraded_issues[pillar].append(name)
                elif f.startswith("warn:"):
                    warning_issues[pillar].append(f"{name}[{f[5:]}]")
                elif f == "fallback_used":
                    fallback_issues[pillar].append(name)
                elif f.startswith("missing:"):
                    missing_sub[pillar][f[8:]].append(name)

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

    # ── Section 8: Missing subcomponents ──────────────────────────────────
    if missing_sub:
        print("\n── MISSING SUBCOMPONENTS ──────────────────────────────────────────")
        for pillar in sorted(missing_sub):
            for sub, places in sorted(missing_sub[pillar].items()):
                truncated = ', '.join(places[:5]) + ('...' if len(places) > 5 else '')
                print(f"  {pillar}.{sub}: {len(places)} place(s) — {truncated}")

    # ── Section 9: Place metadata ──────────────────────────────────────────
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

    # ── Section 10: Per-place summary ─────────────────────────────────────
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
    print(f"  Low confidence          : {sum(len(v) for v in low_conf.values())}")
    print(f"  Degraded                : {sum(len(v) for v in degraded_issues.values())}")
    print(f"  Data warnings           : {sum(len(v) for v in warning_issues.values())}")
    print(f"  Fallback used           : {sum(len(v) for v in fallback_issues.values())}")
    print(f"  Missing subcomponents   : {sum(len(vv) for v in missing_sub.values() for vv in v.values())}")
    print(f"  Metadata issues         : {sum(len(pf) for _, pf, _, _ in results)}")
    lean_missing = sum(
        1 for row in rows
        if (row.get("score", {}).get("livability_pillars", {}).get("political_lean", {}).get("breakdown") or {}).get("lean_2024") is None
    )
    print(f"  Missing lean_2024       : {lean_missing} / {len(rows)} places (election data gap)")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
