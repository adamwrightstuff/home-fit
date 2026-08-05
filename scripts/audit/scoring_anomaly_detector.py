#!/usr/bin/env python3
"""
Empirical scoring anomaly detector.

Loads all scored catalogs, groups by area_type, and flags places where any
pillar score is an outlier relative to peers — catching the class of bugs
that static code review misses (e.g. Pelham Bay AO=3.8 with a huge park).

Also runs pattern-based checks for known failure modes: overpass errors that
produced low scores, all-zero sub-components, and cross-pillar contradictions.

Usage:
    python3 scripts/audit/scoring_anomaly_detector.py [--sigma 2.0] [--min-score-to-flag 40]
"""

import json
import math
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Any

ROOT = Path(__file__).parent.parent.parent

CATALOGS = [
    ("nyc",     ROOT / "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl", "score"),
    ("la",      ROOT / "data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl",  "score"),
    ("vacation",ROOT / "data/vacation_destinations_scores.jsonl",                                 "score_data"),
]

PILLARS = [
    "active_outdoors",
    "natural_beauty",
    "built_environment",
    "neighborhood_amenities",
    "air_travel_access",
    "public_transit_access",
    "healthcare_access",
    "economic_opportunity",
    "quality_education",
    "housing_value",
    "climate_risk",
    "social_fabric",
    "diversity",
    "community_safety",
]

# Sub-breakdown fields to check for all-zero when pillar score is non-trivial
BREAKDOWN_CHECKS = {
    "active_outdoors": ["daily_urban_outdoors", "wild_adventure", "waterfront_lifestyle"],
    "natural_beauty":  ["tree_canopy", "water_proximity", "terrain_variety", "open_space"],
}

# Cross-pillar pairs where low+high together is suspicious
# (low_pillar, high_pillar, note)
CROSS_PILLAR_CHECKS = [
    ("active_outdoors",      "natural_beauty",       50, 70,
     "natural_beauty high but active_outdoors low — outdoor access should track scenic quality"),
    ("neighborhood_amenities","public_transit_access", 20, 65,
     "transit high but amenities very low — dense transit areas usually have services"),
    ("public_transit_access", "neighborhood_amenities", 20, 65,
     "amenities high but transit very low — walkable areas usually have transit"),
]


def load_records() -> list[dict]:
    records = []
    for catalog_id, path, score_key in CATALOGS:
        if not path.exists():
            print(f"[SKIP] {path.name} not found", file=sys.stderr)
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not raw.get("success", True):
                    continue

                score_data = raw.get(score_key, {})
                if not score_data:
                    continue

                pillars_data = score_data.get("livability_pillars", {})
                if not pillars_data:
                    continue

                name = (
                    raw.get("catalog", {}).get("name")
                    or raw.get("location")
                    or score_data.get("input", "unknown")
                )
                state = (
                    raw.get("catalog", {}).get("state_abbr", "")
                    or raw.get("catalog", {}).get("state_full", "")
                    or ""
                )
                label = f"{name}, {state}".rstrip(", ")

                area_type = (
                    score_data.get("data_quality_summary", {})
                    .get("area_classification", {})
                    .get("area_type")
                    or _pillar_area_type(pillars_data)
                    or "unknown"
                )

                records.append({
                    "label":      label,
                    "catalog":    catalog_id,
                    "area_type":  area_type,
                    "total_score": score_data.get("total_score"),
                    "pillars":    pillars_data,
                    "raw":        raw,
                    "score_data": score_data,
                })
    return records


def _pillar_area_type(pillars_data: dict) -> str | None:
    for p in pillars_data.values():
        if isinstance(p, dict):
            at = p.get("area_classification", {}).get("area_type")
            if at:
                return at
    return None


# ── Statistical anomaly detection ────────────────────────────────────────────

def compute_stats(records: list[dict]) -> dict:
    """Returns {area_type: {pillar: (mean, std, [scores])}}"""
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        at = rec["area_type"]
        for pillar, pdata in rec["pillars"].items():
            if isinstance(pdata, dict) and pdata.get("score") is not None:
                buckets[at][pillar].append(float(pdata["score"]))

    stats = {}
    for at, pillar_map in buckets.items():
        stats[at] = {}
        for pillar, scores in pillar_map.items():
            if len(scores) < 3:
                continue
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std = math.sqrt(variance)
            stats[at][pillar] = (mean, std, scores)
    return stats


def flag_statistical_outliers(records: list[dict], stats: dict, sigma: float) -> list[dict]:
    flags = []
    for rec in records:
        at = rec["area_type"]
        if at not in stats:
            continue
        for pillar, pdata in rec["pillars"].items():
            if not isinstance(pdata, dict) or pdata.get("score") is None:
                continue
            score = float(pdata["score"])
            if pillar not in stats[at]:
                continue
            mean, std, _ = stats[at][pillar]
            if std < 1.0:
                continue  # pillar is nearly constant for this area type — skip
            z = (score - mean) / std
            if z < -sigma:
                flags.append({
                    "place":   rec["label"],
                    "catalog": rec["catalog"],
                    "area_type": at,
                    "category": "statistical_low",
                    "pillar":  pillar,
                    "score":   score,
                    "peer_mean": round(mean, 1),
                    "peer_std":  round(std, 1),
                    "z":       round(z, 2),
                    "severity": abs(z),
                    "note": f"{pillar}={score:.1f} is {abs(z):.1f}σ below {at} mean ({mean:.1f}±{std:.1f})",
                })
    return flags


# ── Pattern-based checks ─────────────────────────────────────────────────────

def flag_overpass_errors_with_low_scores(records: list[dict]) -> list[dict]:
    flags = []
    for rec in records:
        for pillar, pdata in rec["pillars"].items():
            if not isinstance(pdata, dict):
                continue
            score = pdata.get("score")
            if score is None or score >= 40:
                continue
            summary = pdata.get("summary", {})
            overpass = summary.get("overpass", {})
            if not overpass:
                continue
            errors = [k for k, v in overpass.items()
                      if isinstance(v, str) and ("error" in v or "empty" in v)]
            if errors:
                flags.append({
                    "place":    rec["label"],
                    "catalog":  rec["catalog"],
                    "area_type": rec["area_type"],
                    "category": "overpass_error_low_score",
                    "pillar":   pillar,
                    "score":    score,
                    "severity": (40 - score) / 10,
                    "note": f"{pillar}={score:.1f} with overpass errors: {errors}",
                })
    return flags


def flag_all_zero_breakdowns(records: list[dict]) -> list[dict]:
    flags = []
    for rec in records:
        for pillar, sub_fields in BREAKDOWN_CHECKS.items():
            pdata = rec["pillars"].get(pillar)
            if not isinstance(pdata, dict):
                continue
            score = pdata.get("score", 0)
            if score < 5:
                continue  # genuinely low — not surprising all sub-fields are zero
            breakdown = pdata.get("breakdown", {})
            if not breakdown:
                continue
            zero_fields = [f for f in sub_fields if f in breakdown and breakdown[f] == 0]
            if len(zero_fields) == len([f for f in sub_fields if f in breakdown]) and zero_fields:
                flags.append({
                    "place":    rec["label"],
                    "catalog":  rec["catalog"],
                    "area_type": rec["area_type"],
                    "category": "all_sub_components_zero",
                    "pillar":   pillar,
                    "score":    score,
                    "severity": score / 10,
                    "note": f"{pillar}={score:.1f} but all breakdown sub-fields are 0: {zero_fields}",
                })
    return flags


def flag_cross_pillar_contradictions(records: list[dict]) -> list[dict]:
    flags = []
    for rec in records:
        for low_p, high_p, low_thresh, high_thresh, msg in CROSS_PILLAR_CHECKS:
            low_data  = rec["pillars"].get(low_p)
            high_data = rec["pillars"].get(high_p)
            if not isinstance(low_data, dict) or not isinstance(high_data, dict):
                continue
            low_score  = low_data.get("score")
            high_score = high_data.get("score")
            if low_score is None or high_score is None:
                continue
            if low_score < low_thresh and high_score > high_thresh:
                flags.append({
                    "place":    rec["label"],
                    "catalog":  rec["catalog"],
                    "area_type": rec["area_type"],
                    "category": "cross_pillar_contradiction",
                    "pillar":   f"{low_p} vs {high_p}",
                    "score":    low_score,
                    "severity": (high_score - high_thresh) / 10 + (low_thresh - low_score) / 10,
                    "note": f"{msg} ({low_p}={low_score:.1f}, {high_p}={high_score:.1f})",
                })
    return flags


def flag_suspiciously_missing_pillars(records: list[dict]) -> list[dict]:
    """Flag places missing expected pillars entirely (None or absent)."""
    flags = []
    # vacation catalog intentionally has fewer pillars — skip it
    for rec in records:
        if rec["catalog"] == "vacation":
            continue
        for pillar in ["active_outdoors", "natural_beauty", "neighborhood_amenities",
                       "public_transit_access", "healthcare_access"]:
            pdata = rec["pillars"].get(pillar)
            if pdata is None or (isinstance(pdata, dict) and pdata.get("score") is None):
                flags.append({
                    "place":    rec["label"],
                    "catalog":  rec["catalog"],
                    "area_type": rec["area_type"],
                    "category": "missing_pillar",
                    "pillar":   pillar,
                    "score":    None,
                    "severity": 3.0,
                    "note": f"{pillar} is absent or unscored",
                })
    return flags


# ── Formatting ────────────────────────────────────────────────────────────────

CATEGORY_LABEL = {
    "statistical_low":            "STAT LOW",
    "overpass_error_low_score":   "OVERPASS ERR",
    "all_sub_components_zero":    "ALL ZERO BREAKDOWN",
    "cross_pillar_contradiction":  "CROSS-PILLAR",
    "missing_pillar":             "MISSING PILLAR",
}

def print_report(all_flags: list[dict], stats: dict) -> None:
    # Sort by severity descending
    all_flags.sort(key=lambda f: -f["severity"])

    # Dedup: one entry per (place, pillar, category)
    seen = set()
    deduped = []
    for f in all_flags:
        key = (f["place"], f["pillar"], f["category"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    print("\n" + "=" * 80)
    print("  HOMEFIT SCORING ANOMALY REPORT")
    print("=" * 80)

    # Summary by category
    by_cat: dict[str, list] = defaultdict(list)
    for f in deduped:
        by_cat[f["category"]].append(f)

    print(f"\n{'Category':<28}  Count")
    print("-" * 40)
    total = 0
    for cat, items in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {CATEGORY_LABEL.get(cat, cat):<26}  {len(items)}")
        total += len(items)
    print(f"  {'TOTAL':<26}  {total}")

    # Per-area-type pillar distributions
    print("\n" + "─" * 80)
    print("  PILLAR SCORE DISTRIBUTIONS BY AREA TYPE")
    print("─" * 80)
    for at in sorted(stats.keys()):
        print(f"\n  {at.upper()}")
        print(f"    {'Pillar':<30}  {'Mean':>6}  {'Std':>5}  {'Min':>5}  {'Max':>5}  N")
        print(f"    {'-'*30}  {'------':>6}  {'-----':>5}  {'-----':>5}  {'-----':>5}  -")
        for pillar in PILLARS:
            if pillar not in stats.get(at, {}):
                continue
            mean, std, scores = stats[at][pillar]
            print(f"    {pillar:<30}  {mean:>6.1f}  {std:>5.1f}  {min(scores):>5.1f}  {max(scores):>5.1f}  {len(scores)}")

    # Flagged places ranked by severity
    print("\n" + "─" * 80)
    print("  FLAGGED PLACES (ranked by severity)")
    print("─" * 80)

    prev_sev_band = None
    for f in deduped:
        sev_band = "HIGH" if f["severity"] >= 3 else ("MED" if f["severity"] >= 1.5 else "LOW")
        if sev_band != prev_sev_band:
            print(f"\n  ── {sev_band} ──")
            prev_sev_band = sev_band
        cat_label = CATEGORY_LABEL.get(f["category"], f["category"])
        score_str = f"{f['score']:.1f}" if f["score"] is not None else "N/A"
        print(f"  [{cat_label}]  {f['place']}  ({f['area_type']})")
        print(f"    {f['note']}")

    print("\n" + "=" * 80 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HomeFit scoring anomaly detector")
    parser.add_argument("--sigma", type=float, default=2.0,
                        help="Z-score threshold for statistical outliers (default: 2.0)")
    args = parser.parse_args()

    print("Loading catalogs...", file=sys.stderr)
    records = load_records()
    print(f"Loaded {len(records)} scored records", file=sys.stderr)

    print("Computing area-type distributions...", file=sys.stderr)
    stats = compute_stats(records)

    print("Running anomaly checks...", file=sys.stderr)
    all_flags = []
    all_flags += flag_statistical_outliers(records, stats, sigma=args.sigma)
    all_flags += flag_overpass_errors_with_low_scores(records)
    all_flags += flag_all_zero_breakdowns(records)
    all_flags += flag_cross_pillar_contradictions(records)
    all_flags += flag_suspiciously_missing_pillars(records)

    print_report(all_flags, stats)


if __name__ == "__main__":
    main()
