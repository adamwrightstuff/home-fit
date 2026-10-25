#!/usr/bin/env python3
"""
Offline: re-score active_outdoors with budgets scaled to 100 and failed Overpass reads left out.

Old: score = min(100, daily + wild + water), with budgets 35 + 50 + 25 = 110, so 15% of places sat at exactly 100, and a failed
Overpass read scored its component as zero without any flag. New (pillars.active_outdoors.scale_active_outdoors): points earned
over the budgets of the components that were read, scaled to 100; a failed read (error or timeout; an empty parks read in a
populated area) leaves its component out and marks the pillar degraded. The stored components are rounded to 0.1, so the new
score is exact to about 0.1. No API calls. The failed places keep their wrong component out until the read is retried.
Run recompute_catalog_composites.py --no-census on the rows afterwards.

  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_budget_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_active_outdoors_budget_offline.py --write --backup-dir <dir>
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
from pillars.active_outdoors import overpass_read_failed, scale_active_outdoors  # noqa: E402


def rescore(score: dict):
    ao = (score.get("livability_pillars") or {}).get("active_outdoors")
    if not ao or not isinstance(ao.get("score"), (int, float)):
        return None
    b, s = ao.get("breakdown") or {}, ao.get("summary") or {}
    o, places = s.get("overpass") or {}, s.get("places_ao") or {}
    area = (ao.get("area_classification") or {}).get("area_type")
    d, w, wt = b.get("daily_urban_outdoors"), b.get("wild_adventure"), b.get("waterfront_lifestyle")
    if not all(isinstance(x, (int, float)) for x in (d, w, wt)):
        return None
    old = ao["score"]
    old_formula = min(100.0, d + w + wt)
    reproduces = abs(old_formula - old) <= 0.16 or places.get("degraded_osm_substitute")
    local_f = overpass_read_failed(o.get("local"), area, empty_is_failure=True)
    trail_f, reg_f = overpass_read_failed(o.get("trail"), area), overpass_read_failed(o.get("regional"), area)
    if places.get("used"):
        local_f = trail_f = reg_f = False
    points = {"daily_urban_outdoors": None if local_f else d, "wild_adventure": None if (trail_f or reg_f) else w,
              "waterfront_lifestyle": None if reg_f else wt}
    new, missing = scale_active_outdoors(points)
    cap = places.get("osm_down_score_cap")
    if places.get("degraded_osm_substitute") and cap is not None:
        new = min(new, float(cap))
    new = round(new, 1)
    b.update({k: points[k] for k in points})
    s["components_missing"] = missing
    if missing:
        dq = ao.get("data_quality") or {}
        dq["degraded"] = True
        dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + [f"active_outdoors_missing_components: {', '.join(missing)} (Overpass read failed)"]))
        ao["data_quality"] = dq
    ao["breakdown"], ao["summary"], ao["score"] = b, s, new
    if isinstance(ao.get("weight"), (int, float)):
        ao["contribution"] = round(ao["weight"] * new / 100.0, 4)
    return old, new, bool(missing), reproduces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    n = nfail = nrepro = 0
    dA, dF, dT = [], [], []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            ao = P.get("active_outdoors")
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(ao)) if ao else None
            res = rescore(s) if ao else None
            if not res:
                out.append(line)
                continue
            old, new, failed, repro = res
            n += 1
            nfail += failed
            nrepro += bool(repro)
            (dF if failed else dA).append(new - old)
            tb = (s.get("total_score_breakdown") or {}).get("active_outdoors")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = ao["score"], ao["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            old_vals[f"{metro}|{cat.get('name')}"] = {"active_outdoors": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_active_outdoors_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| rows:", n, "| with a failed read:", nfail, "| old formula reproduces the stored score:", nrepro)
    print("score delta, rows with all reads ok: mean %.2f min %.1f max %.1f" % (st.mean(dA), min(dA), max(dA)))
    if dF:
        print("score delta, rows with a failed read: mean %.2f min %.1f max %.1f" % (st.mean(dF), min(dF), max(dF)))
    print("total_score delta mean %.3f min %.2f max %.2f" % (st.mean(dT), min(dT), max(dT)))


if __name__ == "__main__":
    main()
