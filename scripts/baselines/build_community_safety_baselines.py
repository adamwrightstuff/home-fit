#!/usr/bin/env python3
"""
Build data/community_safety_baselines.json from scored catalog JSONL files.

Extracts violent_per_1k and property_per_1k from the community_safety breakdown
of each scored place, groups by area_type, removes outliers via IQR fencing, and
computes mean + std for each group.

Usage (from project root):
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_baselines.py
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_baselines.py --dry-run
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_baselines.py \
      --inputs data/nyc_metro_place_catalog_scores_merged.jsonl \
               data/la_metro_place_catalog_scores_merged.jsonl \
      --output data/community_safety_baselines.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

DEFAULT_INPUTS = [
    os.path.join(ROOT, "data", "nyc_metro_place_catalog_scores_merged.jsonl"),
    os.path.join(ROOT, "data", "la_metro_place_catalog_scores_merged.jsonl"),
]
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "community_safety_baselines.json")

# Precision levels to include; DEGRADED is always excluded (no reliable data).
# PRECINCT_PROXY is excluded from baseline computation — precinct averages blur
# hyper-local variance and would drag suburban/exurban stds upward.
ACCEPTED_PRECISION = {"HYPER_LOCAL", "AGENCY_VERIFIED"}

# IQR fence multiplier for outlier removal.
# 3.0 is conservative (catches only extreme outliers like bad population denominators).
IQR_FENCE = 3.0

# Minimum clean samples to emit a baseline for a given area_type.
MIN_SAMPLES = 5


def _iqr_bounds(values: List[float]) -> Tuple[float, float]:
    s = sorted(values)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    iqr = q3 - q1
    return q1 - IQR_FENCE * iqr, q3 + IQR_FENCE * iqr


def _mean_std(values: List[float]) -> Tuple[float, float]:
    mean = statistics.mean(values)
    std = statistics.pstdev(values) if len(values) < 3 else statistics.stdev(values)
    return mean, std


def _get_area_type(score: dict) -> Optional[str]:
    try:
        return (
            score["livability_pillars"]["active_outdoors"]
            ["area_classification"]["area_type"]
        )
    except (KeyError, TypeError):
        return None


def _get_rates(score: dict) -> Optional[dict]:
    try:
        bd = score["livability_pillars"]["community_safety"]["breakdown"]
    except (KeyError, TypeError):
        return None
    if bd.get("precision_level") not in ACCEPTED_PRECISION:
        return None
    v = bd.get("violent_per_1k")
    p = bd.get("property_per_1k")
    if not isinstance(v, (int, float)) or not isinstance(p, (int, float)):
        return None
    return {"violent": float(v), "property": float(p), "source": bd.get("source", "")}


def load_records(paths: List[str]) -> List[dict]:
    records = []
    for path in paths:
        if not os.path.isfile(path):
            print(f"  skipping {path} (not found)")
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                score = d.get("score", {})
                area_type = _get_area_type(score)
                rates = _get_rates(score)
                if area_type and rates:
                    records.append({
                        "name": d.get("catalog", {}).get("name", "?"),
                        "area_type": area_type,
                        **rates,
                    })
        print(f"  loaded {path}")
    return records


def compute_baselines(
    records: List[dict],
    dry_run: bool = False,
) -> Dict[str, Dict[str, float]]:
    by_type: Dict[str, List[dict]] = defaultdict(list)
    for r in records:
        by_type[r["area_type"]].append(r)

    baselines: Dict[str, Dict[str, float]] = {}

    for area_type, items in sorted(by_type.items()):
        vs = [r["violent"] for r in items]
        ps = [r["property"] for r in items]

        # Outlier removal on violent rate (primary signal).
        if len(vs) >= 4:
            lo, hi = _iqr_bounds(vs)
            outliers = [r for r in items if r["violent"] < lo or r["violent"] > hi]
            clean = [r for r in items if lo <= r["violent"] <= hi]
        else:
            outliers = []
            clean = items

        if dry_run and outliers:
            print(f"  [{area_type}] removing {len(outliers)} outlier(s):")
            for o in outliers:
                print(f"    {o['name']}: violent={o['violent']:.1f}/1k")

        if len(clean) < MIN_SAMPLES:
            print(
                f"  [{area_type}] only {len(clean)} clean samples (need {MIN_SAMPLES}) — skipping"
            )
            continue

        v_vals = [r["violent"] for r in clean]
        p_vals = [r["property"] for r in clean]
        v_mean, v_std = _mean_std(v_vals)
        p_mean, p_std = _mean_std(p_vals)

        # Floor std at 0.5 to avoid division-by-zero in downstream z-scoring.
        v_std = max(0.5, round(v_std, 2))
        p_std = max(0.5, round(p_std, 2))

        baselines[area_type] = {
            "violent_mean": round(v_mean, 2),
            "violent_std": v_std,
            "property_mean": round(p_mean, 2),
            "property_std": p_std,
            "_n": len(clean),
            "_n_excluded": len(outliers),
            "_v_median": round(statistics.median(v_vals), 2),
            "_p_median": round(statistics.median(p_vals), 2),
        }

        if dry_run:
            old_v_mean = {"urban_core": 4.5, "urban_residential": 3.0, "suburban": 2.0,
                          "exurban": 1.5, "rural": 1.8}.get(area_type, "?")
            old_v_std = {"urban_core": 5.0, "urban_residential": 3.5, "suburban": 1.5,
                         "exurban": 1.2, "rural": 1.0}.get(area_type, "?")
            print(
                f"  [{area_type}] n={len(clean)} "
                f"v_mean {old_v_mean}→{v_mean:.2f}  "
                f"v_std {old_v_std}→{v_std:.2f}  "
                f"p_mean {p_mean:.2f}  p_std {p_std:.2f}"
            )

    # urban_core: no places in catalog classify this way; use urban_residential.
    if "urban_residential" in baselines and "urban_core" not in baselines:
        baselines["urban_core"] = dict(baselines["urban_residential"])
        if dry_run:
            print("  [urban_core] no catalog places → copied from urban_residential")

    # exurban: too few samples; blend suburban and rural by sample count.
    if "exurban" not in baselines and "suburban" in baselines and "rural" in baselines:
        sb = baselines["suburban"]
        ru = baselines["rural"]
        ns, nr = sb["_n"], ru["_n"]
        total = ns + nr
        blended = {
            "violent_mean": round((sb["violent_mean"] * ns + ru["violent_mean"] * nr) / total, 2),
            "violent_std": round((sb["violent_std"] * ns + ru["violent_std"] * nr) / total, 2),
            "property_mean": round((sb["property_mean"] * ns + ru["property_mean"] * nr) / total, 2),
            "property_std": round((sb["property_std"] * ns + ru["property_std"] * nr) / total, 2),
            "_n": 0,
            "_n_excluded": 0,
            "_blended_from": "suburban+rural",
        }
        baselines["exurban"] = blended
        if dry_run:
            print(
                f"  [exurban] blended suburban(n={ns}) + rural(n={nr}) → "
                f"v_mean={blended['violent_mean']} v_std={blended['violent_std']}"
            )

    # default: use urban_residential as the general fallback.
    if "urban_residential" in baselines:
        baselines["default"] = dict(baselines["urban_residential"])
        if dry_run:
            print("  [default] set to urban_residential values")

    return baselines


def main() -> None:
    ap = argparse.ArgumentParser(description="Build community_safety_baselines.json from catalog JSONL")
    ap.add_argument("--inputs", nargs="+", default=DEFAULT_INPUTS)
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--dry-run", action="store_true", help="Print results without writing")
    args = ap.parse_args()

    print("Loading records...")
    records = load_records(args.inputs)
    print(f"  {len(records)} valid records with accepted precision\n")

    print("Computing baselines...")
    baselines = compute_baselines(records, dry_run=args.dry_run)

    # Strip internal diagnostic keys before writing.
    output: Dict[str, object] = {
        "_meta": {
            "description": "Mean and std of violent_per_1k and property_per_1k crime rates by area type.",
            "sources": [os.path.basename(p) for p in args.inputs],
            "notes": [
                "violent_per_1k: (assault + robbery + homicide) per 1,000 residents in scored radius",
                "property_per_1k: (burglary + theft + vehicle theft) per 1,000 residents in scored radius",
                f"Outlier removal: IQR fence ×{IQR_FENCE} on violent rate before computing stats",
                f"Min samples per area_type: {MIN_SAMPLES}",
                "Rebuild: PYTHONPATH=. python3 scripts/baselines/build_community_safety_baselines.py",
            ],
        }
    }
    for at, bl in baselines.items():
        output[at] = {k: v for k, v in bl.items() if not k.startswith("_")}

    if args.dry_run:
        print("\n[dry-run] would write:")
        print(json.dumps(output, indent=2))
        return

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {args.output} ({len(baselines)} area types)")

    # Sanity check: show what Carroll Gardens and Coney Island would score.
    print("\nSpot-check (Carroll Gardens vs Coney Island):")
    ur = baselines.get("urban_residential", {})
    if ur:
        clip = 2.5
        for name, v in [("Carroll Gardens", 1.677), ("Coney Island", 4.109)]:
            v_mean = ur["violent_mean"]
            v_std = ur["violent_std"]
            z = (v - v_mean) / v_std
            z_inv = max(-clip, min(clip, -z))
            slot = ((z_inv + clip) / (2 * clip)) * 100
            print(f"  {name}: {v}/1k → violent_slot {slot:.1f}")


if __name__ == "__main__":
    main()
