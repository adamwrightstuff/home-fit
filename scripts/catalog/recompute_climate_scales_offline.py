#!/usr/bin/env python3
"""
Offline: re-score the climate_risk heat and warming-trend components with the current scales.

Reads the stored summary.local_lst_c and summary.trend_c_per_decade and applies pillars.climate_risk.heat_points and
trend_points (heat 30 C full to 60 C zero, trend 0 full to 0.8 C per decade zero, both judgments; see the module comment).
Air quality and flood points are taken as stored; a component that is None stays None and the score is rebuilt from the
rest with the pillar's arithmetic. No API calls. Run recompute_catalog_composites.py --no-census on the rows afterwards.

  PYTHONPATH=. python3 scripts/catalog/recompute_climate_scales_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_climate_scales_offline.py --write --backup-dir <dir>
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
from pillars.climate_risk import (AIR_MAX_PTS, FLOOD_MAX_PTS, HEAT_MAX_PTS, MIN_COMPONENTS, TREND_MAX_PTS,  # noqa: E402
                                  heat_points, trend_points)

MAXES = {"heat_exposure_pts": HEAT_MAX_PTS, "air_quality_pts": AIR_MAX_PTS, "flood_zone_pts": FLOOD_MAX_PTS, "climate_trend_pts": TREND_MAX_PTS}


def rescore(score: dict):
    cr = (score.get("livability_pillars") or {}).get("climate_risk")
    if not cr or not isinstance(cr.get("score"), (int, float)):
        return None
    b, s = cr.get("breakdown") or {}, cr.get("summary") or {}
    old = cr["score"]
    lst, tr = s.get("local_lst_c"), s.get("trend_c_per_decade")
    if isinstance(lst, (int, float)):
        b["heat_exposure_pts"] = heat_points(lst)
        b["lst_score"] = round(b["heat_exposure_pts"] / HEAT_MAX_PTS * 100.0, 1)
    if isinstance(tr, (int, float)):
        b["climate_trend_pts"] = trend_points(tr)
        b["climate_trend_score_0_100"] = round(b["climate_trend_pts"] / TREND_MAX_PTS * 100.0, 1)
        s["climate_trend_score"] = b["climate_trend_score_0_100"]
    present = {k: b.get(k) for k in MAXES if isinstance(b.get(k), (int, float))}
    cr["breakdown"], cr["summary"] = b, s
    if len(present) < MIN_COMPONENTS:
        return old, old
    new = round(min(100.0, sum(present.values()) / sum(MAXES[k] for k in present) * 100.0), 1)
    cr["score"] = new
    if isinstance(cr.get("weight"), (int, float)):
        cr["contribution"] = round(cr["weight"] * new / 100.0, 4)
    return old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    n, dC, dT = 0, [], []
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
            cr = P.get("climate_risk")
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(cr)) if cr else None
            res = rescore(s) if cr else None
            if not res:
                out.append(line)
                continue
            tb = (s.get("total_score_breakdown") or {}).get("climate_risk")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = cr["score"], cr["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            n += 1
            dC.append(res[1] - res[0])
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            old_vals[f"{metro}|{cat.get('name')}"] = {"climate_risk": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_climate_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| rows:", n)
    print("climate score delta mean %.2f min %.1f max %.1f | total_score delta mean %.3f min %.2f max %.2f" % (
        st.mean(dC), min(dC), max(dC), st.mean(dT), min(dT), max(dT)))


if __name__ == "__main__":
    main()
