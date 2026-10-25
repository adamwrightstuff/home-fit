#!/usr/bin/env python3
"""
Offline: mark implausible summer land-surface temperatures as no data for the climate_risk heat component.

A June-August surface temperature outside pillars.climate_risk.LST_PLAUSIBLE_MIN_C..MAX_C is a bad pixel (cloud, water),
not heat; the old code gave such places full heat points. The heat component becomes None, the score is rebuilt from the
remaining components (same arithmetic as the pillar), and the pillar is marked degraded. No API calls. Run
recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 scripts/catalog/recompute_climate_lst_guard_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_climate_lst_guard_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pillars.climate_risk import (AIR_MAX_PTS, FLOOD_MAX_PTS, HEAT_MAX_PTS, LST_PLAUSIBLE_MAX_C, LST_PLAUSIBLE_MIN_C,  # noqa: E402
                                  MIN_COMPONENTS, TREND_MAX_PTS)

MAXES = {"heat_exposure_pts": HEAT_MAX_PTS, "air_quality_pts": AIR_MAX_PTS, "flood_zone_pts": FLOOD_MAX_PTS, "climate_trend_pts": TREND_MAX_PTS}


def apply_guard(score: dict):
    cr = (score.get("livability_pillars") or {}).get("climate_risk")
    if not cr or not isinstance(cr.get("score"), (int, float)):
        return None
    b, s = cr.get("breakdown") or {}, cr.get("summary") or {}
    lst = s.get("local_lst_c")
    if not isinstance(lst, (int, float)) or LST_PLAUSIBLE_MIN_C <= lst <= LST_PLAUSIBLE_MAX_C:
        return None
    old = cr["score"]
    b["heat_exposure_pts"], b["lst_score"] = None, None
    s["heat_status"], s["local_lst_rejected_c"], s["local_lst_c"] = "implausible_lst", lst, None
    present = {k: b.get(k) for k in MAXES if isinstance(b.get(k), (int, float))}
    s["components_missing"] = sorted(set((s.get("components_missing") or []) + ["heat"]))
    dq = cr.get("data_quality") or {}
    dq["degraded"] = True
    dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + ["climate_risk_missing_components: heat (implausible land-surface temperature)"]))
    cr["breakdown"], cr["summary"], cr["data_quality"] = b, s, dq
    if len(present) < MIN_COMPONENTS:
        cr["score"], cr["contribution"], cr["confidence"], cr["status"] = None, 0.0, 0, "no_data"
        return old, None
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
    hits = []
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
            res = apply_guard(s) if cr else None
            if not res:
                out.append(line)
                continue
            tb = (s.get("total_score_breakdown") or {}).get("climate_risk")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = cr["score"], cr["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            hits.append((metro, cat.get("name"), snap["summary"].get("local_lst_c"), res[0], res[1]))
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
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places:", len(hits))
    for h in hits:
        print(f"   {h[0]:10s} {str(h[1]):22s} LST {h[2]:7.2f} C  climate score {h[3]} -> {h[4]}")


if __name__ == "__main__":
    main()
