#!/usr/bin/env python3
"""Offline: add political_lean.breakdown.data_vintage to catalog JSONL files from the stored lean_2024_estimated flag.

    PYTHONPATH=. python3 scripts/catalog/backfill_lean_vintage.py data/chicago_metro_place_catalog_scores_merged.composites_recomputed.jsonl [...]
"""
import json
import sys

ESTIMATED = "2020 results (2024 precinct results are not available for this area; the 2024 fields repeat 2020)"


def patch(path: str) -> int:
    rows, n = [], 0
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        bd = (((r.get("score") or {}).get("livability_pillars") or {}).get("political_lean") or {}).get("breakdown")
        if isinstance(bd, dict) and bd.get("lean_2024") is not None:
            want = ESTIMATED if bd.get("lean_2024_estimated") else "2024 results"
            if bd.get("data_vintage") != want:
                bd["data_vintage"] = want
                n += 1
        rows.append(r)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return n


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"{p}: {patch(p)} places updated")
