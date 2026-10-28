#!/usr/bin/env python3
"""
Offline active outdoors recompute for the density-based baselines (design principles v2).

Applies the three new terms to the stored catalog without any live call:
  - parks and playgrounds: distance-decayed counts from a fresh 2 km read, judged against the density-peer baseline
  - trails (wild adventure): the absolute scale, from the stored trail counts and nearest camping distance
The nearest-park and facilities terms and the water term keep their stored values.

The old park and playground terms are recomputed from the stored counts and the stored area type's table and
subtracted from the stored daily score, so nothing else in the daily score moves.

Writes new files only (never the input). Usage, from the repo root:
  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_dpv2_offline.py \
    --parks analysis/parks_requery_all.json --parks analysis/ao_fresh_parks_uncovered/parks_fresh.json \
    --out-dir analysis/ao_recompute_2026-10-28
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

from data_sources.regional_baselines import get_contextual_expectations
from data_sources.surrounding_density import surrounding_stats
from pillars.active_outdoors import (
    _score_wild_adventure_v2,
    expected_parks_for_activity,
    expected_playgrounds_for_activity,
    scale_active_outdoors,
    weighted_park_count,
)

VERSION = "active_outdoors_dpv2_offline_2026-10-28"


def _sat(x: float, target: float, mx: float) -> float:
    return 0.0 if target <= 0 else mx * (1.0 - math.exp(-x / target))


def _table(area_type: str, key: str, default: float) -> float:
    return max(1.0, (get_contextual_expectations(area_type, "active_outdoors") or {}).get(key, default))


def old_terms(area_type: str, parks: int, plays: int, daily: float):
    """Old park and playground terms from the stored counts. Falls back to the exurban table when the remainder
    (nearest-park plus facilities, 0 to 11) is out of range, which is how the pillar's trail override behaved."""
    def terms(t):
        return (_sat(parks, _table(t, "expected_parks_within_1km", 8.0), 22.0),
                _sat(plays, _table(t, "expected_playgrounds_within_1km", 2.0), 5.0))
    p, g = terms(area_type)
    if -0.5 <= daily - p - g <= 11.5:
        return p, g, ""
    p2, g2 = terms("exurban")
    if -0.5 <= daily - p2 - g2 <= 11.5:
        return p2, g2, "exurban_override"
    return p, g, "old_terms_unreproduced"


def recompute(row: dict, fresh: dict, act_cache: dict):
    """Returns (new_row, csv_record) or (row, None) when the place has no scored active outdoors."""
    score = row.get("score") or {}
    ao = (score.get("livability_pillars") or {}).get("active_outdoors")
    if not ao or ao.get("score") is None:
        return row, None
    cat = row["catalog"]
    key = f"{cat['name']}|{cat['state_abbr']}"
    sm, bd = ao["summary"], ao["breakdown"]
    area_type = (ao.get("area_classification") or {}).get("area_type", "suburban")
    ov = sm.get("overpass") or {}
    daily0, wild0, water0 = bd.get("daily_urban_outdoors"), bd.get("wild_adventure"), bd.get("waterfront_lifestyle")
    notes = []

    # trails
    wild1 = wild0
    tr = sm.get("trails") or {}
    if wild0 is not None and ov.get("trail") == "overpass_ok" and tr.get("count_total") is not None and tr.get("count_within_5km") is not None:
        total, near = int(tr["count_total"]), int(tr["count_within_5km"])
        trails = [{"distance_m": 1000}] * near + [{"distance_m": 6000}] * max(0, total - near)
        cs = sm.get("camping") or {}
        nearest_km, sites = cs.get("nearest_km"), int(cs.get("sites") or 0)
        camping = [{"distance_m": float(nearest_km) * 1000.0}] * max(1, sites) if nearest_km is not None and sites else []
        wild1 = round(_score_wild_adventure_v2(trails, camping, area_type), 1)
    elif wild0 is not None:
        notes.append("trails_unchanged_no_ok_read")

    # parks and playgrounds
    daily1 = daily0
    f = fresh.get(key)
    old_p = old_g = new_p = new_g = None
    act = None
    if daily0 is not None and f and f.get("outcome") == "overpass_ok" and ov.get("local") == "overpass_ok":
        if key not in act_cache:
            s = surrounding_stats(float(cat["lat"]), float(cat["lon"]), tract_geoid=None)
            act_cache[key] = None if s is None else s.activity_per_acre
        act = act_cache[key]
        pb, gb = expected_parks_for_activity(act), expected_playgrounds_for_activity(act)
        if pb is not None and gb is not None:
            lp = sm.get("local_parks") or {}
            old_p, old_g, note = old_terms(area_type, int(lp.get("count") or 0), int(lp.get("playgrounds") or 0), daily0)
            if note:
                notes.append(note)
            new_p = _sat(weighted_park_count(f["parks"], pb[1]), pb[0], 22.0)
            new_g = _sat(weighted_park_count(f["playgrounds"], gb[1]), gb[0], 5.0)
            daily1 = round(max(0.0, min(35.0, daily0 - old_p - old_g + new_p + new_g)), 1)
        else:
            notes.append("parks_unchanged_no_density")
    elif daily0 is not None:
        notes.append("parks_unchanged_no_fresh_read")

    points = {"daily_urban_outdoors": daily1, "wild_adventure": wild1, "waterfront_lifestyle": water0}
    new_score, _ = scale_active_outdoors(points)
    cap = (sm.get("places_ao") or {}).get("osm_down_score_cap")
    if (sm.get("places_ao") or {}).get("degraded_osm_substitute") and cap is not None:
        new_score = min(new_score, float(cap))
    new_score = round(new_score, 1)

    out = copy.deepcopy(row)
    nao = out["score"]["livability_pillars"]["active_outdoors"]
    nao["score"] = new_score
    if nao.get("weight") is not None:
        # total_score is the sum of stored pillar contributions (score x weight / 100), so keep it in step
        nao["contribution"] = round(new_score * float(nao["weight"]) / 100.0, 4)
    nao["breakdown"]["daily_urban_outdoors"] = daily1
    nao["breakdown"]["wild_adventure"] = wild1
    nao["dpv2_recompute"] = {
        "version": VERSION, "stored_score": ao["score"], "stored_daily": daily0, "stored_wild": wild0,
        "activity_per_acre": act, "notes": notes,
    }
    rec = dict(
        place=cat["name"], state=cat["state_abbr"], area_type=area_type, act=None if act is None else round(act, 1),
        stored_score=ao["score"], new_score=new_score, delta=round(new_score - ao["score"], 1),
        stored_daily=daily0, new_daily=daily1, stored_wild=wild0, new_wild=wild1,
        old_park_term=None if old_p is None else round(old_p, 2), new_park_term=None if new_p is None else round(new_p, 2),
        old_play_term=None if old_g is None else round(old_g, 2), new_play_term=None if new_g is None else round(new_g, 2),
        notes=";".join(notes),
    )
    return out, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parks", action="append", required=True, help="fresh park read JSON keyed 'name|state' (repeatable)")
    ap.add_argument("--glob", default=str(REPO_ROOT / "data" / "*_merged.composites_recomputed.jsonl"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    fresh = {}
    for p in args.parks:
        fresh.update({k: v for k, v in json.load(open(p)).items() if v.get("outcome") == "overpass_ok"})
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    act_cache, records = {}, []
    for path in sorted(glob.glob(args.glob)):
        with open(path) as fin, open(out_dir / Path(path).name, "w") as fout:
            for line in fin:
                row = json.loads(line)
                try:
                    new_row, rec = recompute(row, fresh, act_cache)
                except Exception as e:  # keep the row, say why
                    new_row, rec = row, None
                    print("skip", (row.get("catalog") or {}).get("name"), type(e).__name__, e, file=sys.stderr)
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
