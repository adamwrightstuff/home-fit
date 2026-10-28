"""
Build data/active_outdoors_trails_scale.json: the one scale the wild adventure trail terms use for every place.

Expected values are catalog medians (trails within 15 km and within 5 km of the pin) over places whose trail read was
clean, so the scale is "relative to the places we score", not a published standard. The point budgets, the camping
distance limit and its decay are NOT sourced (TODO: ground them in research or revealed-preference data).

Usage:
  PYTHONPATH=. python3 scripts/baselines/build_active_outdoors_trails_scale.py
"""
import argparse
import glob
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "active_outdoors_trails_scale.json")
DEFAULT_GLOB = os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog-glob", default=DEFAULT_GLOB)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    total, near = [], []
    for f in sorted(glob.glob(args.catalog_glob)):
        for line in open(f):
            try:
                summary = json.loads(line)["score"]["livability_pillars"]["active_outdoors"]["summary"]
                if summary["overpass"]["trail"] != "overpass_ok":
                    continue
                t, n = summary["trails"]["count_total"], summary["trails"]["count_within_5km"]
            except (KeyError, TypeError, ValueError):
                continue
            if t is not None and n is not None:
                total.append(t)
                near.append(n)

    doc = {
        "measure": "trail routes within 15 km and within 5 km of the pin",
        "expected_trails_15km": statistics.median(total),
        "expected_trails_5km": statistics.median(near),
        "budget_trails_15km": 25.0,   # TODO unsourced
        "budget_trails_5km": 15.0,    # TODO unsourced
        "budget_camping": 10.0,       # TODO unsourced
        "camping_full_within_m": 25000,   # TODO unsourced
        "camping_decay_per_m": 0.00005,   # TODO unsourced
        "n_places": len(total),
        "status": "expected values are catalog medians, not a published standard; budgets and camping limits unsourced",
    }
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main()
