#!/usr/bin/env python3
"""
Offline: recompute public_transit_access for every catalog row as an area average (DPv2 P3).

Each place is scored at nine points (the pin plus eight on the edge of the 1 km disk used for area type) from
refetch_transit_sample_points.py: bus routes within 800 m, subway and light rail within 1,200 m, per route weights
bus 0.7, subway 3, light rail 2, commuter rail 3. Commuter rail with no route within 1,200 m of a point earns 3 x a
drive-distance credit from the pin to the nearest station (refetch_commuter_rail_distance.py): 1.0 within 1,200 m
falling linearly through 0.5 at 2.79 mi, 0.25 at 4.93 mi to 0 at 6.2 mi (median, 75th and 85th percentile driving
distance, Vijayakumar, El-Geneidy and Patterson, TRR 2219, 2011, Montreal n=432; the decay and the 6.2 mi cutoff are
modeling choices, not paper findings). Point scores use the log supply curve and are averaged; stored schedule bonuses
are added and the result is capped at 100.

The anchor (weighted routes that score 100) is a judgment: the data cannot identify it (rank correlation is the same
at anchors 30, 60 and 120). It is chosen by bisection so the catalog mean transit score equals --target-mean (default:
the mean of the stored scores), a continuity choice. Run recompute_catalog_composites.py --no-census afterwards.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/recompute_transit_v3_area_offline.py                     # dry run
  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/recompute_transit_v3_area_offline.py --write --backup-dir analysis/backup_transit_v3
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import shutil
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "transit_v3_area_average_2026-10-29"
BONUS_KEYS = ("frequency_bonus", "weekend_service_bonus", "hub_connectivity_bonus", "destination_diversity_bonus")
CREDIT = [(1200, 1.0), (4490, 0.5), (7930, 0.25), (9980, 0.0)]  # metres, credit
W_BUS, W_SUBWAY, W_COMMUTER_RAIL, W_LIGHT_RAIL = 0.7, 3.0, 3.0, 2.0


def credit(d):
    if d <= CREDIT[0][0]:
        return 1.0
    for (a, fa), (b, fb) in zip(CREDIT, CREDIT[1:]):
        if d <= b:
            return fa + (fb - fa) * (d - a) / (b - a)
    return 0.0


def supply(w, anchor):
    return 0.0 if w <= 0 else 100.0 * min(1.0, math.log(1.0 + w) / math.log(1.0 + anchor))


def load(p):
    return {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / p)}


def point_weights(points, d):
    out = []
    for p in points:
        rail = W_COMMUTER_RAIL * p["commuter_rail"] if p["commuter_rail"] > 0 else (0.0 if d is None else W_COMMUTER_RAIL * credit(d))
        out.append(W_SUBWAY * p["subway"] + W_LIGHT_RAIL * p["light_rail"] + W_BUS * p["bus"] + rail)
    return out


def area_score(ws, bonus, anchor):
    return round(min(100.0, st.mean(supply(w, anchor) for w in ws) + bonus), 1)


def row_key(path, rec):
    s, c = rec.get("score") or {}, rec.get("catalog") or {}
    co = s.get("coordinates") or {}
    if co.get("lat") is None:
        return None
    return f"{os.path.basename(path).split('_')[0]}|{c.get('name')}|{co['lat']:.4f},{co['lon']:.4f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--target-mean", type=float)
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    sp, cr = load("analysis/transit_sample_points.jsonl"), load("analysis/commuter_rail_distance.jsonl")

    paths = sorted(glob.glob(a.glob))
    rows = []  # (ws, bonus, old)
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            rec = json.loads(line)
            t = ((rec.get("score") or {}).get("livability_pillars") or {}).get("public_transit_access")
            k = row_key(path, rec)
            if not t or t.get("score") is None or k not in sp or k not in cr:
                continue
            near = cr[k]["nearest"]
            bonus = sum((t.get("breakdown") or {}).get(x) or 0 for x in BONUS_KEYS)
            rows.append((point_weights(sp[k]["points"], near[0]["m"] if near else None), bonus, t["score"]))
    target = a.target_mean if a.target_mean is not None else st.mean(r[2] for r in rows)
    lo, hi = 5.0, 500.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if st.mean(area_score(w, b, mid) for w, b, _ in rows) > target:
            lo = mid
        else:
            hi = mid
    anchor = round((lo + hi) / 2, 2)
    mean_new = st.mean(area_score(w, b, anchor) for w, b, _ in rows)
    print(f"rows {len(rows)} | target mean {target:.2f} | anchor {anchor} | resulting mean {mean_new:.2f}")

    n, dS, dT = 0, [], []
    for path in paths:
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            t = P.get("public_transit_access")
            k = row_key(path, rec)
            if not t or t.get("score") is None or k not in sp or k not in cr:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(t))
            near = cr[k]["nearest"]
            ws = point_weights(sp[k]["points"], near[0]["m"] if near else None)
            br = t.get("breakdown") or {}
            br.pop("commute_bonus", None)
            t["breakdown"] = br
            new = area_score(ws, sum(br.get(x) or 0 for x in BONUS_KEYS), anchor)
            t["area_sample"] = {"points": 9, "mean_weighted_routes": round(st.mean(ws), 2), "anchor": anchor,
                                "nearest_commuter_rail_m": near[0]["m"] if near else None}
            t["_rescore_version"] = VERSION
            old = t["score"]
            t["score"] = new
            if isinstance(t.get("weight"), (int, float)):
                t["contribution"] = round(t["weight"] * new / 100.0, 4)
            tb = (s.get("total_score_breakdown") or {}).get("public_transit_access")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = t["score"], t["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            else:
                dT.append(0.0)
            dS.append(new - old)
            n += 1
            old_vals[k] = {"public_transit_access": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            dst = b / os.path.basename(path)
            if not dst.exists():
                shutil.copy2(path, dst)
            (b / f"{metro}_old_transit_v3_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print(f"rows {n} | transit score delta mean {st.mean(dS):.2f} min {min(dS):.1f} max {max(dS):.1f} | total_score delta mean {st.mean(dT):.3f} min {min(dT):.2f} max {max(dT):.2f}")
    print(f"places moving more than 5 transit points: {sum(abs(x) > 5 for x in dS)} | more than 15: {sum(abs(x) > 15 for x in dS)}")


if __name__ == "__main__":
    main()
