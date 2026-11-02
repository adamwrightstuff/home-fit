#!/usr/bin/env python3
"""
Apply fresh 2,000 m park reads to places that were scored with an empty park read (daily outdoors = 0).

Offline: reads the stored catalog file and the fresh read JSON, no live call. For each place whose fresh read is
overpass_ok with parks, the park, playground and nearest-park terms are computed exactly as the pillar does (density-peer
baseline, decayed counts, 2,000 m nearest park). The facilities term (0 to 3) cannot be computed (the count is not in the
fresh read), so it stays at 0 and the daily value is a LOWER BOUND by up to 3 points. Water and wild are untouched.
A place whose fresh read is still empty keeps its stored values. Writes a new file only.

  PYTHONPATH=. python3 scripts/catalog/apply_active_outdoors_empty_park_reread.py \
    --input data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl \
    --parks analysis/ao_reread_four/parks_fresh_CA.json --output analysis/ao_reread_four/out/sf_....jsonl
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_sources.surrounding_density import surrounding_stats  # noqa: E402
from pillars.active_outdoors import (  # noqa: E402
    expected_parks_for_activity, expected_playgrounds_for_activity, scale_active_outdoors, weighted_park_count,
)

VERSION = "active_outdoors_empty_park_reread_2026-11-02"


def _sat(x, target, mx):
    return mx * (1.0 - math.exp(-x / target))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--parks", action="append", required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    fresh = {}
    for p in a.parks:
        fresh.update(json.load(open(p)))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    changed = []
    with open(a.input) as fin, open(a.output, "w") as fout:
        for line in fin:
            row = json.loads(line)
            c = row["catalog"]
            key = f"{c['name']}|{c['state_abbr']}"
            f = fresh.get(key)
            ao = ((row.get("score") or {}).get("livability_pillars") or {}).get("active_outdoors")
            if f and f.get("outcome") == "overpass_ok" and f.get("parks") and ao and ao["summary"]["overpass"]["local"] == "overpass_empty":
                s = surrounding_stats(float(c["lat"]), float(c["lon"]), tract_geoid=None)
                act = None if s is None else s.activity_per_acre
                pb, gb = expected_parks_for_activity(act), expected_playgrounds_for_activity(act)
                if pb is None or gb is None:
                    print("no density for", key, file=sys.stderr)
                else:
                    parks = f["parks"]
                    near = [p["distance_m"] for p in parks if p["distance_m"] <= 2000 and (p.get("area_sqm") or 0) / 1e4 >= 0.5]
                    s_near = 8.0 * math.exp(-0.0012 * min(near)) if near else 0.0
                    s_p = _sat(weighted_park_count(parks, pb[1]), pb[0], 22.0)
                    s_g = _sat(weighted_park_count(f["playgrounds"], gb[1]), gb[0], 5.0)
                    daily = round(min(35.0, s_p + s_near + s_g), 1)
                    bd = ao["breakdown"]
                    pts = {"daily_urban_outdoors": daily, "wild_adventure": bd["wild_adventure"],
                           "waterfront_lifestyle": bd["waterfront_lifestyle"]}
                    new_score = round(scale_active_outdoors(pts)[0], 1)
                    old = ao["score"]
                    row = copy.deepcopy(row)
                    n = row["score"]["livability_pillars"]["active_outdoors"]
                    n["score"] = new_score
                    if n.get("weight") is not None:
                        n["contribution"] = round(new_score * float(n["weight"]) / 100.0, 4)
                    n["breakdown"]["daily_urban_outdoors"] = daily
                    n["summary"]["overpass"]["local"] = "overpass_ok"
                    n["summary"]["local_parks"] = {
                        "count": len(parks), "playgrounds": len(f["playgrounds"]),
                        "total_park_area_ha": round(sum((p.get("area_sqm") or 0) for p in parks) / 1e4, 2),
                    }
                    n["empty_park_reread"] = {"version": VERSION, "stored_score": old, "stored_daily": bd["daily_urban_outdoors"],
                                              "activity_per_acre": act, "terms": {"parks": round(s_p, 2), "nearest": round(s_near, 2),
                                              "playgrounds": round(s_g, 2), "facilities": "not computed (0)"}}
                    changed.append((key, old, new_score, bd["daily_urban_outdoors"], daily, round(s_p, 1), round(s_near, 1), round(s_g, 1)))
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
    for ch in changed:
        print("changed", ch)


if __name__ == "__main__":
    main()
