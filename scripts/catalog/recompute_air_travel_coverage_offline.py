#!/usr/bin/env python3
"""
Offline: recompute air_travel_access for every catalog row under the nonstop-coverage model.

Drive minutes to the 6 nearest served airports come from data/airport_drive_minutes_catalog.json (routed once with
OSRM); a pin missing from that file falls back to the fitted line on distance and says so in the summary. The score,
airport blocks and summary are replaced and drive-time warnings added to data_quality; contribution and total_score are updated by the
delta method (2 decimals). Run recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 -I scripts/catalog/recompute_air_travel_coverage_offline.py                 # dry run
  PYTHONPATH=. python3 -I scripts/catalog/recompute_air_travel_coverage_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from pillars.air_travel_access import score_location  # noqa: E402

SLOW_KMH = 45.0  # routed trips slower than this (road-adjusted) are flagged; about the slowest 5% of catalog trips


def recompute(score: dict, routed: dict):
    pillar = (score.get("livability_pillars") or {}).get("air_travel_access")
    co = score.get("coordinates") or {}
    if not pillar or pillar.get("score") is None or co.get("lat") is None:
        return None
    old = pillar["score"]
    minutes = routed.get(f"{co['lat']},{co['lon']}")
    new, bd, nearby = score_location(co["lat"], co["lon"], minutes)
    # data_quality is kept as stored (it rates airport data availability, which did not change; recomputing it
    # costs about 2 seconds per place); only the drive-time warnings are updated.
    dq = pillar.get("data_quality") or {}
    warnings = [w for w in (dq.get("data_warnings") or []) if w not in ("drive_time_estimated_from_distance", "routed_drive_time_unusually_slow")]
    nearest = nearby[0] if nearby else None
    if minutes is None:
        warnings.append("drive_time_estimated_from_distance")
    elif nearest and nearest["distance_km"] >= 15 and nearest["drive_minutes"] > 0:
        if nearest["distance_km"] * 1.3 / (nearest["drive_minutes"] / 60.0) < SLOW_KMH:
            warnings.append("routed_drive_time_unusually_slow")
    dq["data_warnings"] = list(dict.fromkeys(warnings))
    for k in ("primary_airport", "nearest_airports", "summary", "method"):
        pillar[k] = bd[k]
    pillar["score"] = new
    pillar["data_quality"] = dq
    if isinstance(pillar.get("weight"), (int, float)):
        pillar["contribution"] = round(pillar["weight"] * new / 100.0, 4)
    return old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    ap.add_argument("--routed", default=str(ROOT / "data" / "airport_drive_minutes_catalog.json"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    routed = json.loads(Path(a.routed).read_text())["minutes"]
    changed, unrouted, dS, dT = 0, 0, [], []
    for path in sorted(glob.glob(a.glob)):
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
            pillar = P.get("air_travel_access")
            if not pillar:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(pillar))
            res = recompute(s, routed)
            if res is None:
                out.append(line)
                continue
            co = s["coordinates"]
            unrouted += f"{co['lat']},{co['lon']}" not in routed
            tb = (s.get("total_score_breakdown") or {}).get("air_travel_access")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = pillar["score"], pillar["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            dS.append(res[1] - res[0])
            changed += 1
            cat = rec.get("catalog")
            old_vals[f"{metro}|{(cat or {}).get('name') if isinstance(cat, dict) else s.get('input')}"] = {"air_travel_access": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            dst = b / os.path.basename(path)
            if not dst.exists():
                shutil.copy2(path, dst)
            (b / f"{metro}_old_air_travel_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print(f"rows {changed} | pins without routed minutes {unrouted}")
    if dS:
        print("air score delta mean %.2f min %.1f max %.1f | total_score delta mean %.3f min %.2f max %.2f" % (
            st.mean(dS), min(dS), max(dS), st.mean(dT or [0]), min(dT or [0]), max(dT or [0])))


if __name__ == "__main__":
    main()
