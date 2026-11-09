#!/usr/bin/env python3
"""
Offline active outdoors recompute for the owner-approved removal of hiking routes from the trail destination count
(2026-11-10, regional bias audit; see docs/PILLAR_ACTIVE_OUTDOORS.md). No live call.

Input: a saved Overpass read of every place (one JSON line per place: {"k": "<metro>|<name>|<state>", "outcome": ...,
"d": [{"type": "hiking_route" | "trail_area", "name", "distance_m"}]}), produced with osm_api.query_trail_destinations at
15 km. The count becomes the number of trail_area destinations within 15 km and within 5 km.

For each place whose trail read was ok and whose wild score is stored:
  camping points = stored wild - old 15 km points - old 5 km points (old scale: expected 24 and 4, budgets 25 and 15),
  new wild = new 15 km points + new 5 km points + camping points, clipped to 0..50, on the refit scale (catalog medians of
  the new counts over places with an ok trail read, same rule as scripts/baselines/build_active_outdoors_trails_scale.py),
  active outdoors score = pillars.active_outdoors.scale_active_outdoors over daily, new wild and water (stored values).
Everything else keeps its stored value. The old counts, wild and score are kept on the row under
active_outdoors.trail_routes_removed_2026_11_10. Writes new files only (never the input).

  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_routes_removed_offline.py \
    --reads analysis/regional_bias_reread_a_2026-11-10.jsonl --reads analysis/regional_bias_reread_b_2026-11-10.jsonl \
    --out-dir analysis/ao_routes_removed_2026-11-10
Then copy the files over data/, run scripts/baselines/build_active_outdoors_trails_scale.py (it must print the same
medians this script reports), and scripts/catalog/recompute_catalog_composites.py --no-census --in-place per file.
"""
from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import math
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.active_outdoors import scale_active_outdoors  # noqa: E402

VERSION = "active_outdoors_routes_removed_offline_2026-11-10"
OLD = {"e15": 24.0, "e5": 4.0, "b15": 25.0, "b5": 15.0}
NEAR_M = 5000


def sat(x, target, budget):
    return budget * (1.0 - math.exp(-x / target)) if target > 0 else 0.0


def key_of(path, row):
    metro = Path(path).name.split("_metro_")[0]
    c = row["catalog"]
    return f"{metro}|{c['name']}|{c['state_abbr']}"


def counts(read):
    areas = [d for d in read["d"] if d["type"] == "trail_area"]
    return len(areas), sum(1 for d in areas if d["distance_m"] <= NEAR_M), len(read["d"]) - len(areas)


def eligible(row):
    ao = ((row.get("score") or {}).get("livability_pillars") or {}).get("active_outdoors")
    if not ao or ao.get("score") is None:
        return None
    try:
        if ao["summary"]["overpass"]["trail"] != "overpass_ok":
            return None
        if ao["breakdown"].get("wild_adventure") is None:
            return None
        if ao["summary"]["trails"]["count_total"] is None or ao["summary"]["trails"]["count_within_5km"] is None:
            return None
    except (KeyError, TypeError):
        return None
    return ao


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reads", action="append", required=True)
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    reads = {}
    for p in args.reads:
        for line in open(p):
            d = json.loads(line)
            if d.get("outcome") == "overpass_ok":
                reads[d["k"]] = d

    paths = sorted(glob.glob(args.glob))
    rows_by_path = {p: [json.loads(l) for l in open(p)] for p in paths}

    # Pass 1: refit scale (catalog medians of the new counts over places with an ok trail read).
    n15, n5 = [], []
    for p, rows in rows_by_path.items():
        for row in rows:
            if eligible(row) is None or key_of(p, row) not in reads:
                continue
            a15, a5, _ = counts(reads[key_of(p, row)])
            n15.append(a15)
            n5.append(a5)
    e15, e5 = statistics.median(n15), statistics.median(n5)
    print(f"refit scale over {len(n15)} places: expected 15 km {e15}, expected 5 km {e5} (was {OLD['e15']}, {OLD['e5']})")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records, missing = [], 0
    for p, rows in rows_by_path.items():
        with open(out_dir / Path(p).name, "w") as fout:
            for row in rows:
                ao = eligible(row)
                k = key_of(p, row)
                if ao is None or k not in reads:
                    if ao is not None:
                        missing += 1
                    fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                a15, a5, routes15 = counts(reads[k])
                tr = ao["summary"]["trails"]
                bd = ao["breakdown"]
                wild0 = bd["wild_adventure"]
                camp = wild0 - sat(tr["count_total"], OLD["e15"], OLD["b15"]) - sat(tr["count_within_5km"], OLD["e5"], OLD["b5"])
                camp = max(0.0, min(10.0, camp))
                wild1 = round(max(0.0, min(50.0, sat(a15, e15, 25.0) + sat(a5, e5, 15.0) + camp)), 1)
                points = {"daily_urban_outdoors": bd.get("daily_urban_outdoors"), "wild_adventure": wild1,
                          "waterfront_lifestyle": bd.get("waterfront_lifestyle")}
                new_score, _ = scale_active_outdoors(points)
                pa = ao["summary"].get("places_ao") or {}
                if pa.get("degraded_osm_substitute") and pa.get("osm_down_score_cap") is not None:
                    new_score = min(new_score, float(pa["osm_down_score_cap"]))
                new_score = round(new_score, 1)

                out = copy.deepcopy(row)
                nao = out["score"]["livability_pillars"]["active_outdoors"]
                nao["trail_routes_removed_2026_11_10"] = {
                    "version": VERSION, "stored_score": ao["score"], "stored_wild": wild0,
                    "stored_count_total": tr["count_total"], "stored_count_within_5km": tr["count_within_5km"],
                    "routes_within_15km_removed": routes15,
                }
                nao["score"] = new_score
                if nao.get("weight") is not None:
                    nao["contribution"] = round(new_score * float(nao["weight"]) / 100.0, 4)
                nao["breakdown"]["wild_adventure"] = wild1
                nao["summary"]["trails"]["count_total"] = a15
                nao["summary"]["trails"]["count_within_5km"] = a5
                records.append(dict(file=Path(p).name, place=row["catalog"]["name"], state=row["catalog"]["state_abbr"],
                                    stored_score=ao["score"], new_score=new_score, delta=round(new_score - ao["score"], 1),
                                    stored_wild=wild0, new_wild=wild1, stored_count=tr["count_total"], new_count=a15,
                                    routes_removed=routes15))
                fout.write(json.dumps(out, ensure_ascii=False) + "\n")
    with open(out_dir / "diff.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(f"wrote {len(records)} place records to {out_dir}; eligible places with no read: {missing}")


if __name__ == "__main__":
    main()
