#!/usr/bin/env python3
"""
Recompute community_safety scores in catalog JSONL files using stored crime
rates and the current community_safety_baselines.json.

No API calls — all raw data (violent_per_1k, property_per_1k, area_type) is
already stored in the catalog breakdown. Only the scoring curve changes.

Usage (from project root):
  PYTHONPATH=. python3 scripts/catalog/recompute_community_safety_scores.py
  PYTHONPATH=. python3 scripts/catalog/recompute_community_safety_scores.py --dry-run
  PYTHONPATH=. python3 scripts/catalog/recompute_community_safety_scores.py \
      --inputs data/nyc_metro_place_catalog_scores_merged.jsonl \
               data/la_metro_place_catalog_scores_merged.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, ROOT)

import math

from pillars.community_safety import _score_rates, _trend_delta, _get_baselines

DEFAULT_INPUTS = [
    os.path.join(ROOT, "data", "nyc_metro_place_catalog_scores_merged.jsonl"),
    os.path.join(ROOT, "data", "la_metro_place_catalog_scores_merged.jsonl"),
]


def _get_area_type(score: dict) -> str | None:
    try:
        return score["livability_pillars"]["active_outdoors"]["area_classification"]["area_type"]
    except (KeyError, TypeError):
        return None


def recompute_record(score: dict) -> tuple[float | None, float | None, str]:
    """Return (old_score, new_score, name) or (None, None, reason) if skipped."""
    pillars = score.get("livability_pillars", {})
    safety = pillars.get("community_safety")
    if not isinstance(safety, dict):
        return None, None, "no community_safety pillar"

    bd = safety.get("breakdown", {})
    precision = bd.get("precision_level", "")
    if precision == "DEGRADED":
        return None, None, "DEGRADED"

    # Use pre-boost residential rates as canonical input; fall back to stored rates.
    v_raw = bd.get("violent_per_1k_residential_radius", bd.get("violent_per_1k"))
    p_raw = bd.get("property_per_1k_residential_radius", bd.get("property_per_1k"))
    if not isinstance(v_raw, (int, float)) or not isinstance(p_raw, (int, float)):
        return None, None, "missing rates"

    area_type = _get_area_type(score)
    trend_pct = bd.get("trend_pct")

    # Re-apply commuter multiplier from stored wrr_jobs (no H3 re-lookup — avoids
    # coordinate drift between scoring time and recompute time).
    _MIN_WRR = 5.0
    _POP_MULT_CAP = 3.5
    commuter_ctx = bd.get("commuter_context", {})
    wrr = commuter_ctx.get("wrr_jobs") if commuter_ctx else None
    if isinstance(wrr, (int, float)) and wrr > _MIN_WRR:
        commuter_mult = float(min(_POP_MULT_CAP, max(1.0, 1.0 + math.log10(max(1.0, wrr)))))
        commuter_meta = dict(commuter_ctx)
        commuter_meta["commuter_denominator_boost"] = True
        commuter_meta["effective_pop_multiplier"] = round(commuter_mult, 4)
    else:
        commuter_mult = 1.0
        commuter_meta = dict(commuter_ctx) if commuter_ctx else {}

    v_adj = float(v_raw) / commuter_mult
    p_adj = float(p_raw) / commuter_mult

    v_slot, p_slot, raw, _ = _score_rates(v_adj, p_adj, area_type)
    td = _trend_delta(trend_pct)
    new_score = round(max(0.0, min(100.0, raw + td)), 1)

    old_score = safety.get("score")

    # Update breakdown with new adjusted rates, slot values, and commuter context.
    bd["violent_per_1k"] = round(v_adj, 3)
    bd["property_per_1k"] = round(p_adj, 3)
    bd["violent_slot"] = round(v_slot, 1)
    bd["property_slot"] = round(p_slot, 1)
    bd["raw_score"] = round(raw, 1)
    bd["trend_delta"] = td
    bl = _get_baselines(area_type)
    bd["area_type_baseline"] = {
        "violent_mean": bl.get("violent_mean"),
        "violent_std": bl.get("violent_std"),
        "property_mean": bl.get("property_mean"),
        "property_std": bl.get("property_std"),
    }
    if commuter_meta:
        bd["commuter_context"] = commuter_meta

    safety["score"] = new_score

    # Recompute pillar contribution using stored weight.
    weight = safety.get("weight")
    if isinstance(weight, (int, float)):
        safety["contribution"] = round(new_score * weight / 100, 2)

    return old_score, new_score, "ok"


def process_file(path: str, dry_run: bool) -> None:
    if not os.path.isfile(path):
        print(f"  skipping {path} (not found)")
        return

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated = 0
    skipped = 0
    diffs: list[tuple[str, float, float]] = []

    out_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            out_lines.append("")
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue

        old, new, reason = recompute_record(d.get("score", {}))
        if new is None:
            skipped += 1
        else:
            updated += 1
            if old != new:
                diffs.append((d.get("catalog", {}).get("name", "?"), old, new))

        out_lines.append(json.dumps(d, separators=(",", ":")))

    print(f"  {os.path.basename(path)}: {updated} recomputed, {skipped} skipped, {len(diffs)} changed")

    if diffs:
        diffs.sort(key=lambda x: abs((x[2] or 0) - (x[1] or 0)), reverse=True)
        print(f"  largest changes (top 10):")
        for name, old, new in diffs[:10]:
            direction = "↑" if (new or 0) > (old or 0) else "↓"
            print(f"    {direction} {name}: {old} → {new}  (Δ{(new or 0)-(old or 0):+.1f})")

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines))
            if not out_lines[-1]:
                pass
            else:
                f.write("\n")
        print(f"  wrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Recompute community_safety scores from stored rates")
    ap.add_argument("--inputs", nargs="+", default=DEFAULT_INPUTS)
    ap.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = ap.parse_args()

    for path in args.inputs:
        print(f"\nProcessing {os.path.basename(path)}...")
        process_file(path, args.dry_run)

    if args.dry_run:
        print("\n[dry-run] no files written")


if __name__ == "__main__":
    main()
