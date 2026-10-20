#!/usr/bin/env python3
"""
Offline: score the cost_of_living pillar for every place in the composites_recomputed
catalogs and write data/cost_of_living_scores.jsonl.  Does NOT modify any catalog file or
total_score.  Also writes what the total would be if the pillar entered at equal weight
(1/14), as an illustration only.

Inputs are state and city from the catalog; every place is priced for the same reference
household, so no API calls are needed.

Usage:  PYTHONPATH=. python3 scripts/catalog/compute_cost_of_living.py
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from pillars.cost_of_living import get_cost_of_living_score  # noqa: E402

# Catalog metro -> BEA metro (CBSA) code.  Connecticut places in the NYC catalog sit in
# the Bridgeport-Stamford-Danbury metro, which BEA prices separately.
METRO_CBSA = {
    "nyc": "35620", "la": "31080", "chicago": "16980", "dallas": "19100", "houston": "26420",
    "philadelphia": "37980", "sf": "41860", "seattle": "42660", "austin": "12420",
}
STATE_CBSA_OVERRIDE = {("nyc", "Connecticut"): "14860"}

OUT = os.path.join(ROOT, "data", "cost_of_living_scores.jsonl")


def main() -> None:
    n = degraded = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for path in sorted(glob.glob(os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
            metro = os.path.basename(path).split("_")[0]
            for line in open(path, encoding="utf-8"):
                s = json.loads(line)["score"]
                li = s["location_info"]
                cbsa = STATE_CBSA_OVERRIDE.get((metro, li["state"]), METRO_CBSA.get(metro))
                score, det = get_cost_of_living_score(li["state"], cbsa_code=cbsa, city=li["city"])
                old = s.get("total_score")
                new = round(old * 13 / 14 + score / 14, 2) if (score is not None and old is not None) else None
                n += 1
                degraded += score is None
                out.write(json.dumps({
                    "metro": metro, "input": s.get("input"), "city": li["city"], "state": li["state"],
                    "cost_of_living": score, "summary": det.get("summary"), "breakdown": det.get("breakdown"),
                    "confidence": det.get("confidence"), "total_score_current": old,
                    "total_score_if_added_equal_weight": new,
                }) + "\n")
    print(f"wrote {n} places ({degraded} without a score) to {OUT}")


if __name__ == "__main__":
    main()
