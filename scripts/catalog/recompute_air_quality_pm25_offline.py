#!/usr/bin/env python3
"""
Offline: replace the climate_risk air-quality component in catalog rows with measured tract PM2.5.

Uses data/pm25_tract_annual.json (scripts/baselines/build_pm25_tract_table.py) and the same
pillars.climate_risk.air_quality_points curve as the live pillar (20 points at 5 ug/m3 down to 0 at 35). Each
place's census tract comes from its stored coordinates (cached Census geocoder calls). The other three components
are taken as stored; a place with no tract value gets air quality as no data, the score is built from the
remaining components (degraded flag), and fewer than three components makes the pillar no data. Run
recompute_catalog_composites.py --no-census on the changed rows afterwards (happiness, longevity, aura).

  PYTHONPATH=. python3 scripts/catalog/recompute_air_quality_pm25_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_air_quality_pm25_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import statistics as st
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from data_sources import census_api  # noqa: E402
from data_sources.air_quality_pm25 import get_pm25_for_point  # noqa: E402
from pillars.climate_risk import AIR_MAX_PTS, FLOOD_MAX_PTS, HEAT_MAX_PTS, MIN_COMPONENTS, TREND_MAX_PTS, air_quality_points  # noqa: E402

MAXES = {"heat_exposure_pts": HEAT_MAX_PTS, "air_quality_pts": AIR_MAX_PTS, "flood_zone_pts": FLOOD_MAX_PTS, "climate_trend_pts": TREND_MAX_PTS}


def tract_geoid(lat, lon):
    for _ in range(3):
        try:
            t = census_api.get_census_tract(lat, lon)
            if t and t.get("geoid"):
                return t["geoid"]
        except Exception:
            pass
        time.sleep(1)
    return None


def recompute(score: dict, pm: dict | None):
    cr = (score.get("livability_pillars") or {}).get("climate_risk")
    if not cr or not isinstance(cr.get("score"), (int, float)):
        return None
    b, s = cr.get("breakdown") or {}, cr.get("summary") or {}
    old = cr["score"]
    pts = {k: b.get(k) for k in MAXES}
    pts["air_quality_pts"] = air_quality_points(pm["pm25_ugm3"]) if pm else None
    present = {k: v for k, v in pts.items() if isinstance(v, (int, float))}
    missing = [k for k in MAXES if k not in present]
    b.update({k: pts[k] for k in MAXES})
    b["aqi_score"] = round(pts["air_quality_pts"] / AIR_MAX_PTS * 100.0, 1) if pts["air_quality_pts"] is not None else None
    for k in ("pm25_proxy_ugm3", "aer_ai_mean"):
        s.pop(k, None)
    s["pm25_ugm3"] = round(pm["pm25_ugm3"], 2) if pm else None
    s["pm25_years"] = pm.get("years") if pm else None
    s["pm25_source"] = pm.get("source") if pm else None
    s["pm25_match"] = pm.get("match") if pm else None
    s["pm25_match_km"] = pm.get("match_km") if pm else None
    s["components_missing"] = [m.replace("_pts", "") for m in missing]
    dq = cr.get("data_quality") or {}
    if pm and pm.get("match") == "nearest_centroid":
        dq["data_warnings"] = list(dict.fromkeys(list(dq.get("data_warnings") or []) + [f"pm25_nearest_tract_centroid_{pm.get('match_km')}km"]))
    if "air_quality_pts" in missing:
        dq["degraded"] = True
        dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + ["climate_risk_missing_components: air_quality"]))
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
    files = sorted(glob.glob(a.glob))
    coords = []
    for path in files:
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if line.strip():
                try:
                    co = (json.loads(line).get("score") or {}).get("coordinates") or {}
                except Exception:
                    continue
                if co.get("lat") is not None:
                    coords.append((co["lat"], co["lon"]))
    with ThreadPoolExecutor(8) as ex:
        geoids = dict(zip(coords, ex.map(lambda c: tract_geoid(*c), coords)))
    changed, missing_pm, nodata = 0, 0, 0
    dC, dT = [], []
    for path in files:
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
            co = s.get("coordinates") or {}
            if not cr or co.get("lat") is None:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(cr))
            pm = get_pm25_for_point(geoids.get((co["lat"], co["lon"])), co["lat"], co["lon"])
            res = recompute(s, pm)
            if res is None:
                out.append(line)
                continue
            missing_pm += pm is None
            nodata += res[1] is None
            tb = (s.get("total_score_breakdown") or {}).get("climate_risk")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = cr["score"], cr["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            changed += 1
            if res[1] is not None:
                dC.append(res[1] - res[0])
            cat = rec.get("catalog")
            old_vals[f"{metro}|{(cat or {}).get('name') if isinstance(cat, dict) else s.get('input')}"] = {"climate_risk": snap, "total_score": old_total}
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
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print(f"rows {changed} | no PM2.5 for tract {missing_pm} | pillar no data {nodata}")
    if dC:
        print("climate score delta mean %.2f min %.1f max %.1f | total_score delta mean %.3f min %.2f max %.2f | |delta|>3: %d" % (
            st.mean(dC), min(dC), max(dC), st.mean(dT), min(dT), max(dT), sum(abs(x) > 3 for x in dC)))


if __name__ == "__main__":
    main()
