#!/usr/bin/env python3
"""
Export one wide CSV row per catalog location: catalog fields, pillar scores, composite indices.

Reads merged batch JSONL (success + catalog + score per line).

Usage:

  PYTHONPATH=. python3 scripts/catalog/export_catalog_scores_csv.py \\
    --jsonl data/nyc_metro_place_catalog_scores_merged.jsonl \\
    --output data/nyc_metro_catalog_locations_pillar_scores_indices.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

# Match frontend/lib/pillars.ts PILLAR_ORDER (column order for pillar scores).
PILLAR_KEYS: List[str] = [
    "quality_education",
    "neighborhood_amenities",
    "economic_security",
    "climate_risk",
    "active_outdoors",
    "natural_beauty",
    "diversity",
    "social_fabric",
    "built_beauty",
    "healthcare_access",
    "public_transit_access",
    "air_travel_access",
    "housing_value",
]

LONGEVITY_CONTRIB_KEYS = [
    "social_fabric",
    "neighborhood_amenities",
    "active_outdoors",
    "natural_beauty",
    "climate_risk",
    "quality_education",
]


def _default_jsonl() -> Path:
    raw = os.getenv("HOMEFIT_AGENT_CATALOG_JSONL", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pillar_score(lp: Dict[str, Any], key: str) -> Optional[float]:
    po = lp.get(key)
    if not isinstance(po, dict):
        return None
    return _num(po.get("score"))


def _pillar_status(lp: Dict[str, Any], key: str) -> str:
    po = lp.get(key)
    if not isinstance(po, dict):
        return ""
    s = po.get("status")
    return s if isinstance(s, str) else ""


def build_row(cat: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    lp = score.get("livability_pillars") or {}
    if not isinstance(lp, dict):
        lp = {}

    md = score.get("metadata") or {}
    iv = md.get("indices_version") if isinstance(md, dict) else None
    if not isinstance(iv, dict):
        iv = {}

    lic = score.get("longevity_index_contributions")
    if not isinstance(lic, dict):
        lic = {}

    row: Dict[str, Any] = {
        "name": cat.get("name", ""),
        "type": cat.get("type", ""),
        "county_borough": cat.get("county_borough", ""),
        "state_abbr": cat.get("state_abbr", ""),
        "state_full": cat.get("state_full", ""),
        "lat": cat.get("lat", ""),
        "lon": cat.get("lon", ""),
        "search_query": cat.get("search_query", ""),
        "total_score": _num(score.get("total_score")),
        "longevity_index": _num(score.get("longevity_index")),
        "happiness_index": _num(score.get("happiness_index")),
        "status_signal": _num(score.get("status_signal")),
        "overall_confidence": _num(score.get("overall_confidence")),
        "indices_version_longevity": iv.get("longevity", ""),
        "indices_version_status_signal": iv.get("status_signal", ""),
        "indices_version_happiness": iv.get("happiness", ""),
    }

    for pk in PILLAR_KEYS:
        row[f"pillar_{pk}_score"] = _pillar_score(lp, pk)
        row[f"pillar_{pk}_status"] = _pillar_status(lp, pk)

    for lk in LONGEVITY_CONTRIB_KEYS:
        row[f"longevity_contrib_{lk}"] = _num(lic.get(lk))

    return row


def fieldnames() -> List[str]:
    base = [
        "name",
        "type",
        "county_borough",
        "state_abbr",
        "state_full",
        "lat",
        "lon",
        "search_query",
        "total_score",
        "longevity_index",
        "happiness_index",
        "status_signal",
        "overall_confidence",
        "indices_version_longevity",
        "indices_version_status_signal",
        "indices_version_happiness",
    ]
    for pk in PILLAR_KEYS:
        base.append(f"pillar_{pk}_score")
        base.append(f"pillar_{pk}_status")
    for lk in LONGEVITY_CONTRIB_KEYS:
        base.append(f"longevity_contrib_{lk}")
    return base


def main() -> None:
    ap = argparse.ArgumentParser(description="Export catalog JSONL to wide CSV.")
    ap.add_argument("--jsonl", type=Path, default=_default_jsonl(), help="Input JSONL path")
    ap.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "nyc_metro_catalog_locations_pillar_scores_indices.csv",
        help="Output CSV path",
    )
    args = ap.parse_args()

    if not args.jsonl.is_file():
        print(f"ERROR: file not found: {args.jsonl}", file=sys.stderr)
        sys.exit(1)

    fn = fieldnames()
    n_in = 0
    n_out = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.jsonl, "r", encoding="utf-8") as f, open(
        args.output, "w", encoding="utf-8", newline=""
    ) as out:
        w = csv.DictWriter(out, fieldnames=fn, extrasaction="ignore")
        w.writeheader()
        for line in f:
            n_in += 1
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not obj.get("success"):
                continue
            cat = obj.get("catalog")
            score = obj.get("score")
            if not isinstance(cat, dict) or not isinstance(score, dict):
                continue
            w.writerow(build_row(cat, score))
            n_out += 1

    print(f"Wrote {n_out} rows to {args.output} (read {n_in} non-empty lines).")


if __name__ == "__main__":
    main()
