#!/usr/bin/env python3
"""
Count catalog places with one or more livability pillars below a confidence threshold.

  python3 scripts/report_catalog_confidence_below.py --metro nyc --threshold 80
  python3 scripts/report_catalog_confidence_below.py --metro la --threshold 75
  python3 scripts/report_catalog_confidence_below.py --metro all --threshold 80

Default JSONL paths (repo data/):
  nyc: nyc_metro_place_catalog_scores_merged.jsonl
  la:  la_metro_place_catalog_scores_merged.jsonl

Use --jsonl PATH to analyze any file instead of --metro.

quality_education is skipped by default (often 0 with schools off).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]

PILLAR_ORDER: List[str] = [
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

DEFAULT_JSONL_BY_METRO: Dict[str, Path] = {
    "nyc": REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl",
    "la": REPO_ROOT / "data" / "la_metro_place_catalog_scores_merged.jsonl",
}


def catalog_key(cat: Dict[str, Any]) -> str:
    return f"{cat.get('name', '')}|{cat.get('county_borough', '')}|{cat.get('state_abbr', '')}"


def pillar_confidence(pillar: Any) -> Optional[float]:
    if not isinstance(pillar, dict):
        return None
    c = pillar.get("confidence")
    if c is None:
        dq = pillar.get("data_quality")
        if isinstance(dq, dict):
            c = dq.get("confidence")
    try:
        return float(c) if c is not None else None
    except (TypeError, ValueError):
        return None


def load_last_per_place(path: Path) -> Dict[str, Dict[str, Any]]:
    last: Dict[str, Dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            cat = obj.get("catalog")
            if isinstance(cat, dict):
                last[catalog_key(cat)] = obj
    return last


def report_one(
    label: str,
    path: Path,
    *,
    max_confidence: float,
    pillars: List[str],
) -> None:
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return

    last = load_last_per_place(path)
    total_ok_rows = 0
    places_with_any_low = 0
    pillar_low_counts: Dict[str, int] = defaultdict(int)

    for _place_key in sorted(last.keys()):
        obj = last[_place_key]
        if not obj.get("success"):
            continue
        score = obj.get("score")
        if not isinstance(score, dict):
            continue
        lp = score.get("livability_pillars")
        if not isinstance(lp, dict):
            continue

        total_ok_rows += 1
        low_pillars: List[str] = []
        for pname in pillars:
            conf = pillar_confidence(lp.get(pname))
            if conf is None or conf < max_confidence:
                low_pillars.append(pname)
                pillar_low_counts[pname] += 1

        if low_pillars:
            places_with_any_low += 1

    print(f"=== {label} ===")
    print(f"File: {path}")
    print(f"Successful rows (with livability_pillars): {total_ok_rows}")
    print(f"Threshold: pillar confidence < {max_confidence}")
    print()
    print(f"Places with at least one checked pillar below {max_confidence}: {places_with_any_low}")
    if total_ok_rows:
        pct = 100.0 * places_with_any_low / total_ok_rows
        print(f"  ({pct:.1f}% of successful rows)")
    print()
    print("Per-pillar: places where THIS pillar is below threshold")
    for pname in pillars:
        print(f"  {pname}: {pillar_low_counts.get(pname, 0)}")
    print()


def parse_skip_pillars(raw: str) -> Set[str]:
    out = {p.strip() for p in raw.replace(",", " ").split() if p.strip()}
    unknown = out - set(PILLAR_ORDER)
    if unknown:
        raise ValueError(f"Unknown pillar(s): {sorted(unknown)}. Valid: {PILLAR_ORDER}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Report catalog places with pillar confidence below a threshold."
    )
    ap.add_argument(
        "--metro",
        choices=["nyc", "la", "all"],
        default=None,
        help="Which default catalog JSONL to use (nyc / la / both). Ignored if --jsonl is set.",
    )
    ap.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Explicit JSONL path (overrides --metro).",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        metavar="N",
        help="Count pillar as 'low' if confidence is strictly below N (0-100). Default: 80",
    )
    ap.add_argument(
        "--skip-pillars",
        type=str,
        default="quality_education",
        help="Comma-separated pillar keys to exclude from checks. Default: quality_education",
    )
    args = ap.parse_args()

    if args.jsonl is not None:
        if not args.jsonl.is_file():
            print(f"File not found: {args.jsonl}", file=sys.stderr)
            return 1
        try:
            skip = parse_skip_pillars(args.skip_pillars)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        pillars = [p for p in PILLAR_ORDER if p not in skip]
        print("Pillar order (checked):", ", ".join(pillars))
        if skip:
            print("Skipped:", ", ".join(sorted(skip)))
        print()
        report_one("catalog", args.jsonl, max_confidence=args.threshold, pillars=pillars)
        return 0

    if args.metro is None:
        print("Specify --metro nyc|la|all or pass --jsonl PATH.", file=sys.stderr)
        return 1

    try:
        skip = parse_skip_pillars(args.skip_pillars)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    pillars = [p for p in PILLAR_ORDER if p not in skip]
    print("Pillar order (checked):", ", ".join(pillars))
    if skip:
        print("Skipped:", ", ".join(sorted(skip)))
    print()

    metros = ["nyc", "la"] if args.metro == "all" else [args.metro]
    for m in metros:
        path = DEFAULT_JSONL_BY_METRO[m]
        report_one(m.upper(), path, max_confidence=args.threshold, pillars=pillars)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
