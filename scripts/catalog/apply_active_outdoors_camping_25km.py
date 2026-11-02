#!/usr/bin/env python3
"""
Apply a fresh 25 km (15.5 miles) camping read to the places that were read only to 15 km (urban and suburban area types),
so every place has the same camping window. Offline: reads stored catalog files and the fresh read JSON, no live call.

A place can only gain: its nearest camping becomes the nearer of the stored one (which may include Google Places sites)
and the fresh OSM one. Wild adventure is rescored from the stored trail counts with the absolute scale (the stored wild score
reproduces exactly from those fields), then the pillar score is rescaled. Water, daily and trails are untouched.
Writes new files and a diff CSV only.

  PYTHONPATH=. python3 scripts/catalog/apply_active_outdoors_camping_25km.py \
    --camping analysis/ao_camping_25km/camping_25km_A.json --camping analysis/ao_camping_25km/camping_25km_B.json \
    --out-dir analysis/ao_camping_25km/out_pillar
"""
from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.active_outdoors import _score_wild_adventure_v2, scale_active_outdoors  # noqa: E402

VERSION = "active_outdoors_camping_25km_2026-11-02"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camping", action="append", required=True)
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    fresh = {}
    for p in a.camping:
        fresh.update({k: v for k, v in json.load(open(p)).items() if v.get("outcome") in ("overpass_ok", "overpass_empty")})
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(glob.glob(a.glob)):
        with open(path) as fin, open(out_dir / Path(path).name, "w") as fout:
            for line in fin:
                row = json.loads(line)
                c = row["catalog"]
                ao = ((row.get("score") or {}).get("livability_pillars") or {}).get("active_outdoors")
                f = fresh.get(f"{c['name']}|{c['state_abbr']}")
                if ao and f and f["camping"]:
                    sm = ao["summary"]
                    tr, cs = sm["trails"], sm.get("camping") or {}
                    old_km = cs.get("nearest_km") if cs.get("sites") else None
                    new_m = min(q["distance_m"] for q in f["camping"])
                    if old_km is None or new_m < old_km * 1000.0 - 1.0:
                        tot, near = int(tr["count_total"]), int(tr.get("count_within_5km") or 0)
                        trails = [{"distance_m": 1000}] * near + [{"distance_m": 6000}] * max(0, tot - near)
                        wild = round(_score_wild_adventure_v2(trails, [{"distance_m": new_m}], "suburban"), 1)
                        bd = ao["breakdown"]
                        if wild > bd["wild_adventure"] + 0.04:
                            pts = {"daily_urban_outdoors": bd["daily_urban_outdoors"], "wild_adventure": wild,
                                   "waterfront_lifestyle": bd["waterfront_lifestyle"]}
                            new_score = round(scale_active_outdoors(pts)[0], 1)
                            pa = sm.get("places_ao") or {}
                            if pa.get("degraded_osm_substitute") and pa.get("osm_down_score_cap") is not None:
                                new_score = min(new_score, float(pa["osm_down_score_cap"]))
                            row = copy.deepcopy(row)
                            n = row["score"]["livability_pillars"]["active_outdoors"]
                            rows.append(dict(place=c["name"], state=c["state_abbr"], file=Path(path).name,
                                             stored_score=ao["score"], new_score=new_score, stored_wild=bd["wild_adventure"],
                                             new_wild=wild, stored_camp_km=old_km, new_camp_km=round(new_m / 1000.0, 2)))
                            n["score"] = new_score
                            if n.get("weight") is not None:
                                n["contribution"] = round(new_score * float(n["weight"]) / 100.0, 4)
                            n["breakdown"]["wild_adventure"] = wild
                            n["summary"]["camping"] = {"sites": max(int(cs.get("sites") or 0), len(f["camping"])),
                                                       "nearest_km": round(new_m / 1000.0, 2)}
                            n["camping_25km_read"] = {"version": VERSION, "stored_score": ao["score"],
                                                      "stored_wild": bd["wild_adventure"], "stored_nearest_km": old_km}
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(out_dir / "diff.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["none"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} places change; wrote {out_dir}")


if __name__ == "__main__":
    main()
