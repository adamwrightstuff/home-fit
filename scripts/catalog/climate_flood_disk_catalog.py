#!/usr/bin/env python3
"""
Catalog run of the 800 m disk flood measure (docs/PILLAR_CLIMATE_RISK.md, flood disk pilot). Two steps.

  fetch  One FEMA NFHL polygon query per place (about 1,476, radius 800 m around the scored pin), then the area-weighted mean of
         the flood points over the disk (mapped part only; zone D and unmapped area are no data). Saves one small result per place to
         <out-dir>/disk_flood.json after every 25 places, so an interrupted run resumes. A place whose query fails is skipped and
         counted; run the same command again to retry only those. Polygons are not kept.
  apply  Reads disk_flood.json and the post-option-B catalog files, replaces each place's flood points with the disk value, and
         carries the climate score, total score and longevity into NEW files in <apply-dir> (the inputs are never modified).
         Then run recompute_happiness_only.py on those files. No FEMA call.

  cd /Users/adamwright/Dev/home-fit/.claude/worktrees/dpv2-climate-risk
  python3 scripts/catalog/climate_flood_disk_catalog.py fetch --out-dir analysis/climate_flood_disk_2026-11-03
  PYTHONPATH=. python3 scripts/catalog/climate_flood_disk_catalog.py apply --out-dir analysis/climate_flood_disk_2026-11-03 --apply-dir analysis/climate_dpv2_disk_2026-11-03
  PYTHONPATH=. python3 scripts/catalog/recompute_happiness_only.py analysis/climate_dpv2_disk_2026-11-03/*.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "catalog"))

import climate_flood_disk_pilot as pilot  # noqa: E402
from data_sources.fema_flood import _classify_zone  # noqa: E402

CATALOG_DIR = os.path.join(ROOT, "analysis", "climate_dpv2_2026-11-03")
GLOB = "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def place_key(lat, lon):
    return f"{float(lat):.5f},{float(lon):.5f}"


def pins():
    out = {}
    for path in sorted(glob.glob(os.path.join(CATALOG_DIR, GLOB))):
        for line in open(path, encoding="utf-8"):
            c = (json.loads(line).get("score") or {}).get("coordinates") or {}
            if "lat" in c and "lon" in c:
                out[place_key(c["lat"], c["lon"])] = (float(c["lat"]), float(c["lon"]))
    return out


def fetch(a) -> int:
    os.makedirs(a.out_dir, exist_ok=True)
    path = os.path.join(a.out_dir, "disk_flood.json")
    done = json.load(open(path)) if os.path.exists(path) else {}
    todo = [(k, v) for k, v in pins().items() if k not in done]
    print(f"{len(done)} places already done, {len(todo)} to fetch (one FEMA query each)", flush=True)
    failed = 0
    for i, (k, (lat, lon)) in enumerate(todo, 1):
        try:
            feats = pilot.query(lat, lon, fetch_m=pilot.RADIUS_M + 50)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAILED {k}: {str(e)[:120]}", flush=True)
            continue
        zones = []
        for f in feats:
            at = f.get("attributes") or {}
            g = pilot.to_geom(f, lat, lon)
            if g is not None and not g.is_empty:
                zones.append((_classify_zone(at.get("FLD_ZONE"), at.get("SFHA_TF"), at.get("ZONE_SUBTY")), g))
        pts, mapped, shares = pilot.disk_flood(zones, 0.0, 0.0)
        done[k] = {"pts": None if pts is None else round(pts, 2), "mapped": round(mapped, 3),
                   "shares": {t: round(s, 4) for t, s in shares.items()}, "polygons": len(feats)}
        if i % 25 == 0 or i == len(todo):
            json.dump(done, open(path, "w"))
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(a.sleep)
    json.dump(done, open(path, "w"))
    print(f"done: {len(done)} places saved, {failed} failed this run" + ("; run the same command again to retry them" if failed else ""), flush=True)
    return 0


def apply(a) -> int:
    from scripts.catalog.recompute_flood_offline import MAX_PTS, MIN_COMPONENTS, _BD_KEYS, _num, update_composites

    disk = json.load(open(os.path.join(a.out_dir, "disk_flood.json")))
    if os.path.isdir(a.apply_dir) and os.listdir(a.apply_dir):
        sys.exit(f"{a.apply_dir} is not empty; new files only")
    os.makedirs(a.apply_dir, exist_ok=True)
    recs, missing = [], 0
    for path in sorted(glob.glob(os.path.join(CATALOG_DIR, GLOB))):
        out = []
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score") or {}
            cr = (sc.get("livability_pillars") or {}).get("climate_risk")
            c = sc.get("coordinates") or {}
            if cr and isinstance(cr.get("score"), (int, float)) and "lat" in c:
                d = disk.get(place_key(c["lat"], c["lon"]))
                if d is None:
                    missing += 1
                else:
                    before, total_before = cr["score"], sc.get("total_score")
                    bd = cr.get("breakdown") or {}
                    pts = {k: _num(bd.get(v)) for k, v in _BD_KEYS.items()}
                    pts["flood"] = d["pts"]
                    present = [k for k, v in pts.items() if v is not None]
                    if len(present) >= MIN_COMPONENTS:
                        flood_100 = None if d["pts"] is None else round(d["pts"] / MAX_PTS["flood"] * 100.0, 1)
                        bd["flood_zone_pts"], bd["flood_zone_score_0_100"] = d["pts"], flood_100
                        cr["breakdown"] = bd
                        s = cr.get("summary") or {}
                        s.update({"flood_zone_score": flood_100, "flood_method": "disk_800m_mean", "flood_zone_shares": d["shares"],
                                  "flood_mapped_fraction": d["mapped"], "components_missing": [k for k in MAX_PTS if k not in present]})
                        cr["summary"] = s
                        dq = cr.get("data_quality") or {}
                        reasons = [r for r in (dq.get("degraded_reasons") or []) if not str(r).startswith(("flood_", "climate_risk_missing_components: flood"))]
                        if d["pts"] is None:
                            reasons += ["climate_risk_missing_components: flood", "flood_no_mapped_polygon_in_disk"]
                        dq["degraded_reasons"] = list(dict.fromkeys(reasons))
                        dq["degraded"] = bool(dq["degraded_reasons"])
                        cr["data_quality"] = dq
                        cr["score"] = round(min(100.0, sum(pts[k] for k in present) / sum(MAX_PTS[k] for k in present) * 100.0), 1)
                        if isinstance(cr.get("weight"), (int, float)):
                            cr["contribution"] = round(cr["weight"] * cr["score"] / 100.0, 4)
                        update_composites(sc)
                        recs.append({"name": (row.get("catalog") or {}).get("name"), "file": os.path.basename(path), "climate_before": before,
                                     "climate_after": cr["score"], "total_before": total_before, "total_after": sc.get("total_score"),
                                     "disk_flood_pts": d["pts"], "mapped_fraction": d["mapped"]})
            out.append(json.dumps(row, ensure_ascii=False))
        with open(os.path.join(a.apply_dir, os.path.basename(path)), "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    with open(os.path.join(a.apply_dir, "diff.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)
    print(f"{sum(1 for r in recs if r['climate_after'] != r['climate_before'])} of {len(recs)} places changed; {missing} places had no saved disk value and are unchanged; wrote {a.apply_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "apply"])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--apply-dir")
    ap.add_argument("--sleep", type=float, default=0.5)
    a = ap.parse_args()
    if a.step == "apply" and not a.apply_dir:
        sys.exit("apply needs --apply-dir")
    return fetch(a) if a.step == "fetch" else apply(a)


if __name__ == "__main__":
    sys.exit(main())
