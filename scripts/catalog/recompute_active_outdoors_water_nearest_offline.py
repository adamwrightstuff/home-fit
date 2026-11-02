#!/usr/bin/env python3
"""
Offline active outdoors recompute for two approved DPv2 audit steps (2026-11-02), no live call:
  1. water: the area-type multipliers (0.9 / 0.95 on lake, coastline and swim area for suburban and urban residential) are gone.
     The stored category bests carry the multiplier, so they are divided by it. Exact for a category whose features all
     share one multiplier; for the lake/river category (lake 0.95, swim area 0.9, beach-as-swim-area 1.0) the winning
     feature's type is used when it wins, otherwise the factor is 1.0, so the result is a LOWER BOUND (a feature that
     stored as second-best could overtake). Not applied to places with no breakdown.
  2. nearest park: judged on the 2,000 m list for every place instead of the area type's own radius, using the stored fresh
     park lists (distance and area). The daily value changes by (new nearest term - old nearest term), clipped at 35.
Everything else keeps its stored value. Writes new files only (never the input).

  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_water_nearest_offline.py \
    --parks analysis/ao_fresh_parks_uncovered/parks_fresh_covered_states.json \
    --parks analysis/ao_fresh_parks_uncovered/parks_fresh.json --out-dir analysis/ao_recompute_2026-11-02
"""
from __future__ import annotations

import argparse
import copy
import csv
import glob
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pillars.active_outdoors import scale_active_outdoors  # noqa: E402

VERSION = "active_outdoors_water_nearest_offline_2026-11-02"
OLD_RADIUS = {"urban_core": 800, "urban_residential": 1000, "suburban": 1500, "exurban": 2000, "rural": 2000}
MULT_TYPES = {"suburban", "urban_residential"}   # the only types left in the catalog that carried a multiplier
FACTOR_BY_TYPE = {"lake": 0.95, "swimming_area": 0.9, "coastline": 0.9, "coastline_rocky": 0.9}
CATEGORY_FACTOR = {"ocean_beach": 1.0, "bay_harbor": 1.0, "waterfront_access": 0.9, "lake_river": 1.0}


def nearest_term(parks, radius_m):
    ds = [p["distance_m"] for p in parks if p["distance_m"] <= radius_m and (p.get("area_sqm") or 0) / 1e4 >= 0.5]
    return 8.0 * math.exp(-0.0012 * min(ds)) if ds else 0.0


def new_water(ao, area_type):
    """(new water points, note). Lower bound, see module docstring."""
    old = ao["breakdown"]["waterfront_lifestyle"]
    wb = ao["breakdown"].get("waterfront_breakdown")
    if old is None or not wb or area_type not in MULT_TYPES:
        return old, ""
    win = wb.get("winning_feature") or {}
    wtype = win.get("type")
    best = old
    for cat, f in CATEGORY_FACTOR.items():
        v = wb.get(cat)
        if v is None:
            continue
        factor = f
        if cat == "lake_river" and wtype in ("lake", "swimming_area") and abs(v / 100.0 * 25.0 - old) < 0.06:
            factor = FACTOR_BY_TYPE[wtype]
        best = max(best, min(25.0, v / 100.0 * 25.0 / factor))
    return round(best, 1), ""


def recompute(row, fresh):
    ao = ((row.get("score") or {}).get("livability_pillars") or {}).get("active_outdoors")
    if not ao or ao.get("score") is None:
        return row, None
    cat = row["catalog"]
    key = f"{cat['name']}|{cat['state_abbr']}"
    sm, bd = ao["summary"], ao["breakdown"]
    area_type = (ao.get("area_classification") or {}).get("area_type", "suburban")
    notes = []
    daily0, wild0, water0 = bd.get("daily_urban_outdoors"), bd.get("wild_adventure"), bd.get("waterfront_lifestyle")

    daily1, d_nearest = daily0, 0.0
    f = fresh.get(key)
    if daily0 is not None and f and (sm.get("overpass") or {}).get("local") == "overpass_ok" and (f.get("parks")):
        old_r = OLD_RADIUS.get(area_type, 2000)
        d_nearest = nearest_term(f["parks"], 2000) - nearest_term(f["parks"], old_r)
        daily1 = round(max(0.0, min(35.0, daily0 + d_nearest)), 1)
    elif daily0 is not None:
        notes.append("nearest_unchanged_no_fresh_read")

    if "exurban_override" in ((ao.get("dpv2_recompute") or {}).get("notes") or []):
        # These were scored under the old mountain-town override (exurban), which carried no water multiplier.
        water1, wnote = water0, "water_unchanged_exurban_override"
    else:
        water1, wnote = new_water(ao, area_type)
    if wnote:
        notes.append(wnote)

    points = {"daily_urban_outdoors": daily1, "wild_adventure": wild0, "waterfront_lifestyle": water1}
    new_score, _ = scale_active_outdoors(points)
    pa = sm.get("places_ao") or {}
    if pa.get("degraded_osm_substitute") and pa.get("osm_down_score_cap") is not None:
        new_score = min(new_score, float(pa["osm_down_score_cap"]))
    new_score = round(new_score, 1)

    out = copy.deepcopy(row)
    nao = out["score"]["livability_pillars"]["active_outdoors"]
    nao["score"] = new_score
    if nao.get("weight") is not None:
        nao["contribution"] = round(new_score * float(nao["weight"]) / 100.0, 4)
    nao["breakdown"]["daily_urban_outdoors"] = daily1
    nao["breakdown"]["waterfront_lifestyle"] = water1
    nao["dpv2_recompute_2026_11_02"] = {
        "version": VERSION, "stored_score": ao["score"], "stored_daily": daily0, "stored_water": water0, "notes": notes,
    }
    rec = dict(
        place=cat["name"], state=cat["state_abbr"], area_type=area_type, stored_score=ao["score"], new_score=new_score,
        delta=round(new_score - ao["score"], 1), stored_daily=daily0, new_daily=daily1,
        stored_water=water0, new_water=water1, notes=";".join(notes),
    )
    return out, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parks", action="append", required=True)
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    fresh = {}
    for p in args.parks:
        fresh.update({k: v for k, v in json.load(open(p)).items() if v.get("outcome") == "overpass_ok"})
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(glob.glob(args.glob)):
        with open(path) as fin, open(out_dir / Path(path).name, "w") as fout:
            for line in fin:
                new_row, rec = recompute(json.loads(line), fresh)
                if rec:
                    rec["file"] = Path(path).name
                    records.append(rec)
                fout.write(json.dumps(new_row, ensure_ascii=False) + "\n")
    with open(out_dir / "diff.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(f"wrote {len(records)} place records to {out_dir}")


if __name__ == "__main__":
    main()
