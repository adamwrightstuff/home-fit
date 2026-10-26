#!/usr/bin/env python3
"""
Offline: recompute public_transit_access for every catalog row under the supply-only model.

Removed from the score (2026-10-26): the legacy suburban layer, the ridership-weighted commuter floor, the 5% commute
blend and the +5 commute bonus. What remains is the documented supply formula on the stored route counts
(per route: subway 3, commuter rail 3, light rail 2, bus 0.7; log curve, anchor 120; validated against tract transit share and no-vehicle households) plus the schedule-based bonuses that were
actually computed for the place (frequency, weekend service, hub connectivity, destination diversity), capped at 100.
Commute minutes and score stay in the pillar as informational fields (weight 0) because the frontend uses them as the
area-average commute fallback. The area type from the row's central classification is stored on the pillar. Run
recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 -I scripts/catalog/recompute_transit_v2_offline.py                  # dry run
  PYTHONPATH=. python3 -I scripts/catalog/recompute_transit_v2_offline.py --write --backup-dir <dir>
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
ANCHOR = 120.0
W_BUS, W_SUBWAY, W_COMMUTER_RAIL, W_LIGHT_RAIL = 0.7, 3.0, 3.0, 2.0  # mirrors pillars/public_transit_access.py
BONUS_KEYS = ("frequency_bonus", "weekend_service_bonus", "hub_connectivity_bonus", "destination_diversity_bonus")
VERSION = "transit_v2_supply_only_2026-10-26"


def supply(weighted_routes: float) -> float:
    if weighted_routes <= 0:
        return 0.0
    return 100.0 * min(1.0, math.log(1.0 + weighted_routes) / math.log(1.0 + ANCHOR))


def recompute(score: dict):
    t = (score.get("livability_pillars") or {}).get("public_transit_access")
    if not t or t.get("score") is None:
        return None
    sm, br = t.get("summary") or {}, t.get("breakdown") or {}
    w = (W_SUBWAY * (sm.get("subway_routes") or 0) + W_COMMUTER_RAIL * (sm.get("commuter_rail_routes") or 0)
         + W_LIGHT_RAIL * (sm.get("light_rail_routes") or 0) + W_BUS * (sm.get("bus_routes") or 0))
    bonuses = sum(br.get(k) or 0 for k in BONUS_KEYS)
    new = round(min(100.0, supply(w) + bonuses), 1)
    old = t["score"]
    br.pop("commute_bonus", None)
    t["breakdown"] = br
    ct = (t.get("details") or {}).get("commute_time")
    if isinstance(ct, dict):
        ct["weight"] = 0.0
        ct["note"] = "Mean commute time (ACS), informational only; not part of the transit score"
    ac = (score.get("data_quality_summary") or {}).get("area_classification") or {}
    t["area_classification"] = {"area_type": ac.get("area_type"), "density": ac.get("density")}
    t["_rescore_version"] = VERSION
    t["score"] = new
    if isinstance(t.get("weight"), (int, float)):
        t["contribution"] = round(t["weight"] * new / 100.0, 4)
    return old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    n, dS, dT = 0, [], []
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
            t = P.get("public_transit_access")
            if not t or t.get("score") is None:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(t))
            res = recompute(s)
            tb = (s.get("total_score_breakdown") or {}).get("public_transit_access")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = t["score"], t["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            else:
                dT.append(0.0)
            dS.append(res[1] - res[0])
            n += 1
            cat = rec.get("catalog")
            old_vals[f"{metro}|{(cat or {}).get('name') if isinstance(cat, dict) else s.get('input')}"] = {"public_transit_access": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            dst = b / os.path.basename(path)
            if not dst.exists():
                shutil.copy2(path, dst)
            (b / f"{metro}_old_transit_v2_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print(f"rows {n} | transit score delta mean {st.mean(dS):.2f} min {min(dS):.1f} max {max(dS):.1f} | total_score delta mean {st.mean(dT):.3f} min {min(dT):.2f} max {max(dT):.2f}")
    print(f"places moving more than 5 transit points: {sum(abs(x) > 5 for x in dS)} | more than 15: {sum(abs(x) > 15 for x in dS)}")


if __name__ == "__main__":
    main()
