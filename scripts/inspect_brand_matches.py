#!/usr/bin/env python3
"""
Inspect which businesses matched each status-signal brand category per location.

Reads saved score JSON (from save_score_json.py). Requires the JSON to include
business_list (in livability_pillars.neighborhood_amenities.breakdown.business_list).
Re-run save_score_json after the app includes business_list in the response.

Usage (from project root):
  PYTHONPATH=. python3 scripts/inspect_brand_matches.py tribeca_status_signal.json
  PYTHONPATH=. python3 scripts/inspect_brand_matches.py tribeca_status_signal.json carroll_gardens_status_signal.json
  PYTHONPATH=. python3 scripts/inspect_brand_matches.py tribeca_status_signal.json -o brand_matches.json
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pillars.status_signal import compute_brand, _brand_matches_for_business_list


def get_business_list(data: dict) -> list:
    """Extract business_list from saved score JSON."""
    pillars = data.get("livability_pillars") or {}
    na = pillars.get("neighborhood_amenities") or {}
    breakdown = na.get("breakdown") or {}
    return breakdown.get("business_list") or na.get("business_list") or []


def inspect(path: str) -> dict:
    """Load JSON, get business_list, return brand score and per-category matches."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    business_list = get_business_list(data)
    if not business_list:
        return {
            "path": path,
            "input": data.get("input", path),
            "status_signal": data.get("status_signal"),
            "error": "No business_list in this file. Re-run save_score_json.py after the app includes business_list in the response.",
            "brand_score": None,
            "brand_matches": [],
        }
    brand_score = compute_brand(business_list)
    brand_matches = _brand_matches_for_business_list(business_list)
    return {
        "path": path,
        "input": data.get("input", path),
        "status_signal": data.get("status_signal"),
        "brand_score": round(brand_score, 1),
        "business_count": len(business_list),
        "brand_matches": brand_matches,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    out_path = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "-o" and i + 2 <= len(sys.argv):
            out_path = sys.argv[i + 2]
            break
    if not args:
        print("Usage: python3 scripts/inspect_brand_matches.py <score_json> [<score_json> ...] [-o out.json]", file=sys.stderr)
        sys.exit(1)

    results = []
    for path in args:
        if not os.path.isfile(path):
            print(f"Skip (not found): {path}", file=sys.stderr)
            continue
        results.append(inspect(path))

    # Print human-readable summary
    for r in results:
        print(f"\n--- {r.get('input', r['path'])} ---")
        print(f"  status_signal (from JSON): {r.get('status_signal')}")
        print(f"  brand_score (computed):    {r.get('brand_score')}")
        if r.get("error"):
            print(f"  {r['error']}")
            continue
        print(f"  businesses in list:        {r.get('business_count', 0)}")
        for m in r.get("brand_matches", []):
            names = m.get("matched_names", [])
            if names:
                print(f"  [{m['category']}] weight={m['weight']} score={m['cat_score']}: {names}")
            else:
                print(f"  [{m['category']}] weight={m['weight']} score={m['cat_score']}: (none)")

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
