#!/usr/bin/env python3
"""
Verify 40-location calibration is in use and score Carroll Gardens + Larchmont
with full economic breakdown (to explain low scores).

1. Reads data/economic_baselines.json and reports n for "all"/"all" key metrics.
2. Calls API with diagnostics for Carroll Gardens Brooklyn NY and Larchmont NY,
   prints total_score, economic_security score, division/area_bucket, and raw
   economic summary (unemployment, employment ratio, dynamism, resilience, etc.).

Run from project root:
  PYTHONPATH=. python3 scripts/check_calibration_and_scores.py
  HOMEFIT_API_URL=https://your-app.railway.app python3 scripts/check_calibration_and_scores.py

Clear score cache first if you want to force use of latest baselines:
  curl -X POST "https://your-app.railway.app/cache/clear?cache_type=scores"
"""

from __future__ import annotations

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASELINES_PATH = os.path.join(ROOT, "data", "economic_baselines.json")

TARGET_LOCATIONS = [
    "Carroll Gardens Brooklyn NY",
    "Larchmont NY",
]


def check_baselines():
    if not os.path.isfile(BASELINES_PATH):
        print("ERROR: data/economic_baselines.json not found.")
        return False
    with open(BASELINES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    block = data.get("all", {}).get("all", {})
    if not block:
        print("ERROR: baselines have no 'all'/'all' block.")
        return False
    ns = set()
    for key, v in block.items():
        if isinstance(v, dict) and "n" in v:
            ns.add(v["n"])
    sample = list(block.items())[:5]
    n_vals = [v.get("n") for _, v in sample if isinstance(v, dict)]
    n = n_vals[0] if n_vals else None
    print("--- Baselines (data/economic_baselines.json) ---", flush=True)
    print(f"  'all'/'all' sample n values: {n_vals}", flush=True)
    print(f"  Unique 'n' in block: {ns}")
    if n == 40:
        print("  OK: 40-location calibration present in file.")
    else:
        print(f"  WARNING: expected n=40, got n={n}. Re-run scripts/build_economic_baselines.py with full locations.csv.")
    return True


def score_locations():
    try:
        import requests
    except ImportError:
        print("Install requests to use API: pip install requests")
        return
    base_url = os.environ.get("HOMEFIT_API_URL", "http://localhost:8000").rstrip("/")
    timeout = int(os.environ.get("HOMEFIT_TIMEOUT", "45"))
    print("\n--- Scoring (API with diagnostics) ---")
    print(f"  Base URL: {base_url}")
    for loc in TARGET_LOCATIONS:
        try:
            r = requests.get(
                f"{base_url}/score",
                params={"location": loc, "diagnostics": "true"},
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"\n  {loc}: API error — {e}")
            continue
        total = data.get("total_score")
        pillars = data.get("livability_pillars") or data.get("pillars") or {}
        econ = pillars.get("economic_security") or {}
        econ_score = econ.get("score")
        details = econ.get("details") or econ
        summary = details.get("summary") or {}
        breakdown = details.get("breakdown") or {}
        division = summary.get("division", "?")
        area_bucket = summary.get("area_bucket", "?")
        print(f"\n  Location: {loc}")
        print(f"  Total score: {total}")
        print(f"  Economic security score: {econ_score}")
        print(f"  Division / area_bucket: {division} / {area_bucket}")
        print("  Raw economic summary (used for normalization):")
        for k, v in summary.items():
            if k not in ("division", "area_bucket", "geo_level", "geo_name"):
                print(f"    {k}: {v}")
        comp = breakdown.get("component_scores") or breakdown
        if comp:
            print("  Component scores (0–100):")
            for k, v in comp.items():
                if isinstance(v, (int, float)):
                    print(f"    {k}: {v}")
    print()


def main():
    os.chdir(ROOT)
    check_baselines()
    score_locations()


if __name__ == "__main__":
    main()
