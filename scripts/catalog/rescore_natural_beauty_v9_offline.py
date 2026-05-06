#!/usr/bin/env python3
"""
Offline V9 rescore for natural beauty — no API calls, no GEE.

Reads stored tree_analysis data from each catalog JSONL row and applies
_apply_v9_formula directly. Updates natural_beauty.score and details in place,
then rewrites total_score.

Usage:
  PYTHONPATH=. python3 scripts/catalog/rescore_natural_beauty_v9_offline.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --output data/nyc_metro_place_catalog_scores_merged.jsonl

  PYTHONPATH=. python3 scripts/catalog/rescore_natural_beauty_v9_offline.py \
    --input data/la_metro_place_catalog_scores_merged.jsonl \
    --output data/la_metro_place_catalog_scores_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pillars import natural_beauty as nb_module


def _recompute_total(pillars: dict) -> float:
    total = weighted = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total += float(weight)
    return round(weighted / total, 4) if total > 0 else 0.0


def rescore_row(row: dict) -> tuple[bool, str]:
    score_doc = row.get("score")
    if not isinstance(score_doc, dict):
        return False, "no score doc"

    coords = score_doc.get("coordinates") or {}
    lat = coords.get("lat")
    lon = coords.get("lon")
    if lat is None or lon is None:
        return False, "no coordinates"

    pillars = score_doc.get("livability_pillars", {})
    nb = pillars.get("natural_beauty")
    if not nb:
        return False, "no natural_beauty pillar"

    det = nb.get("details") or {}
    tree_details = det.get("tree_analysis") or {}
    nc = tree_details.get("natural_context") or {}
    if not nc.get("component_scores"):
        return False, "no component_scores"

    try:
        v9_score, v9_breakdown = nb_module._apply_v9_formula(
            {}, tree_details, lat=lat, lon=lon
        )
    except Exception as e:
        return False, f"formula error: {e}"

    det["score_v9"] = round(float(v9_score), 2)
    det["score_v7"] = round(float(nb.get("score") or 0), 2)
    det["v9_breakdown"] = v9_breakdown
    det["scoring_formula"] = "v9" if nb_module.ENABLE_NATURAL_BEAUTY_V9 else "v7"
    nb["details"] = det

    if nb_module.ENABLE_NATURAL_BEAUTY_V9:
        nb["score"] = round(float(v9_score), 2)

    score_doc["total_score"] = _recompute_total(pillars)
    return True, "ok"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = [json.loads(l) for l in Path(args.input).read_text().splitlines() if l.strip()]
    ok = skip = err = 0
    reasons: dict[str, int] = {}

    for row in rows:
        success, reason = rescore_row(row)
        if success:
            ok += 1
        else:
            if reason == "no score doc" or "no coordinates" in reason:
                skip += 1
            else:
                err += 1
            reasons[reason] = reasons.get(reason, 0) + 1

    Path(args.output).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done: {ok} rescored, {skip} skipped, {err} errors")
    if reasons:
        for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {n:4d}  {r}")


if __name__ == "__main__":
    main()
