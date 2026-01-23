#!/usr/bin/env python3
"""
Built Beauty diagnostics CLI.

Prints a stable JSON breakdown using the existing Built Beauty pipeline.

Examples:
  python scripts/debug_built_beauty.py --lat 42.3588 --lon -71.0707 --name "Beacon Hill"

  python scripts/debug_built_beauty.py --compare \
    "Beacon Hill,42.3588,-71.0707" \
    "StripMall,33.9137,-118.4064"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


def _parse_compare_arg(value: str) -> Tuple[str, float, float]:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid --compare value {value!r}. Expected format: Name,lat,lon")
    name = parts[0]
    lat = float(parts[1])
    lon = float(parts[2])
    return name, lat, lon


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_one(lat: float, lon: float, name: Optional[str] = None) -> Dict[str, Any]:
    # Ensure repo root is importable (matches existing scripts style).
    sys.path.insert(0, _project_root())

    from pillars.built_beauty import calculate_built_beauty  # type: ignore

    result: Dict[str, Any] = calculate_built_beauty(
        lat,
        lon,
        location_name=name,
    )

    # Keep output stable and focused. Everything else is nested under `result`.
    return {
        "input": {"name": name, "lat": lat, "lon": lon},
        "score": result.get("score"),
        "score_before_normalization": result.get("score_before_normalization"),
        "effective_area_type": result.get("effective_area_type"),
        "result": result,
    }


def _run_compare(items: List[Tuple[str, float, float]]) -> Dict[str, Any]:
    runs = [_run_one(lat, lon, name=name) for (name, lat, lon) in items]
    summary = [
        {
            "name": r["input"]["name"],
            "lat": r["input"]["lat"],
            "lon": r["input"]["lon"],
            "score": r.get("score"),
            "score_before_normalization": r.get("score_before_normalization"),
            "effective_area_type": r.get("effective_area_type"),
        }
        for r in runs
    ]
    return {"summary": summary, "runs": runs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Built Beauty diagnostics (JSON).")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--lat", type=float, help="Latitude for a single run")
    mode.add_argument(
        "--compare",
        nargs="+",
        help='One or more "Name,lat,lon" entries to compare',
    )

    parser.add_argument("--lon", type=float, help="Longitude for a single run (required with --lat)")
    parser.add_argument("--name", type=str, default=None, help="Optional name for a single run")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    args = parser.parse_args()

    if args.lat is not None:
        if args.lon is None:
            parser.error("--lon is required when using --lat")
        payload = _run_one(args.lat, args.lon, name=args.name)
    else:
        compare_items = [_parse_compare_arg(x) for x in (args.compare or [])]
        payload = _run_compare(compare_items)

    indent = 2 if args.pretty else None
    print(json.dumps(payload, indent=indent, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

