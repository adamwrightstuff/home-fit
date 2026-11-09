#!/usr/bin/env python3
"""
Offline: apply the heat plausibility screen (data_sources/heat_screen.py) to the catalog. New files only.

For each place, samples the PRISM 1991-2020 June, July and August mean daily maximum temperature normals (800 m GeoTIFFs the
owner downloaded, see docs/PILLAR_CLIMATE_RISK.md Level 2 status) at the scored pin. When the stored land-surface temperature
(local_lst_c) is more than HEAT_MAX_BELOW_AIR_C below that air normal, the heat component becomes no data: the climate score
is rebuilt over the remaining components, the pillar is marked degraded, and total score follows
(recompute_flood_offline.update_composites). The happiness index is recomputed afterwards with recompute_happiness_only.py.
The live pillar uses the same function with the TerraClimate 4 km normal instead of PRISM, so a place near the margin can
differ between catalog and live. No API, Earth Engine, Census or Overpass call. Inputs are never modified.

Two steps, because reading the GeoTIFFs needs rasterio (not in requirements; use a throwaway virtual environment that has only
rasterio and numpy) and the apply step needs the project's own packages.

  cd /Users/adamwright/Dev/home-fit/.claude/worktrees/dpv2-climate-risk
  PYTHONPATH=. <venv>/bin/python3 scripts/catalog/climate_heat_screen_catalog.py sample --prism-dir analysis/climate_level2_prism_2026-11-03 --air-ref analysis/climate_heat_screen_air_ref_2026-11-03.json
  PYTHONPATH=. python3 scripts/catalog/climate_heat_screen_catalog.py apply --air-ref analysis/climate_heat_screen_air_ref_2026-11-03.json --out-dir analysis/climate_heat_screen_2026-11-03
  PYTHONPATH=. python3 scripts/catalog/recompute_happiness_only.py analysis/climate_heat_screen_2026-11-03/*.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

GLOB = "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def place_key(lat, lon):
    return f"{float(lat):.5f},{float(lon):.5f}"


def sample(a) -> int:
    import rasterio

    src = [rasterio.open(os.path.join(a.prism_dir, f"prism_tmax_us_30s_2020{m}_avg_30y.tif")) for m in ("06", "07", "08")]
    ref = {}
    for path in sorted(glob.glob(os.path.join(a.catalog_dir, GLOB))):
        for line in open(path, encoding="utf-8"):
            c = ((json.loads(line).get("score") or {}).get("coordinates")) or {}
            if "lat" in c and "lon" in c:
                vals = [float(next(x.sample([(c["lon"], c["lat"])]))[0]) for x in src]
                if all(v > -9000 for v in vals):
                    ref[place_key(c["lat"], c["lon"])] = round(sum(vals) / 3.0, 2)
    json.dump(ref, open(a.air_ref, "w"))
    print(f"{len(ref)} places sampled; wrote {a.air_ref}")
    return 0


def apply(a) -> int:
    from data_sources.heat_screen import HEAT_MAX_BELOW_AIR_C, lst_implausible_vs_air
    from scripts.catalog.recompute_flood_offline import MAX_PTS, MIN_COMPONENTS, _BD_KEYS, _num, update_composites

    ref = json.load(open(a.air_ref))
    if os.path.isdir(a.out_dir) and os.listdir(a.out_dir):
        sys.exit(f"{a.out_dir} is not empty; new files only")
    os.makedirs(a.out_dir, exist_ok=True)
    recs, checked = [], 0
    for path in sorted(glob.glob(os.path.join(a.catalog_dir, GLOB))):
        out = []
        for line in open(path, encoding="utf-8"):
            row = json.loads(line)
            sc = row.get("score") or {}
            cr = (sc.get("livability_pillars") or {}).get("climate_risk")
            c = sc.get("coordinates") or {}
            s = (cr or {}).get("summary") or {}
            air_ref = ref.get(place_key(c["lat"], c["lon"])) if "lat" in c and "lon" in c else None
            if cr and isinstance(cr.get("score"), (int, float)) and s.get("local_lst_c") is not None and air_ref is not None:
                checked += 1
                s["air_tmax_jja_normal_c"] = air_ref
                cr["summary"] = s
                if lst_implausible_vs_air(s["local_lst_c"], air_ref) and _num((cr.get("breakdown") or {}).get(_BD_KEYS["heat"])) is not None:
                    before, total_before = cr["score"], sc.get("total_score")
                    bd = cr["breakdown"]
                    pts = {k: _num(bd.get(v)) for k, v in _BD_KEYS.items()}
                    pts["flood"] = _num(bd.get("flood_zone_pts"))
                    pts["heat"] = None
                    present = [k for k, v in pts.items() if v is not None]
                    if len(present) >= MIN_COMPONENTS:
                        bd[_BD_KEYS["heat"]], bd["lst_score"] = None, None
                        s.update({"heat_status": "implausible_vs_air_temperature", "local_lst_rejected_c": s["local_lst_c"],
                                  "components_missing": [k for k in MAX_PTS if k not in present]})
                        dq = cr.get("data_quality") or {}
                        reasons = [r for r in (dq.get("degraded_reasons") or []) if not str(r).startswith("climate_risk_missing_components")]
                        reasons += [f"climate_risk_missing_components: {', '.join(s['components_missing'])}", "heat_reading_implausible_vs_air_temperature"]
                        dq["degraded_reasons"] = list(dict.fromkeys(reasons))
                        dq["degraded"] = True
                        cr["data_quality"] = dq
                        cr["score"] = round(min(100.0, sum(pts[k] for k in present) / sum(MAX_PTS[k] for k in present) * 100.0), 1)
                        if isinstance(cr.get("weight"), (int, float)):
                            cr["contribution"] = round(cr["weight"] * cr["score"] / 100.0, 4)
                        update_composites(sc)
                        recs.append({"name": (row.get("catalog") or {}).get("name"), "file": os.path.basename(path),
                                     "lst_c": s["local_lst_c"], "air_tmax_jja_normal_c": air_ref,
                                     "climate_before": before, "climate_after": cr["score"],
                                     "total_before": total_before, "total_after": sc.get("total_score")})
            out.append(json.dumps(row, ensure_ascii=False))
        with open(os.path.join(a.out_dir, os.path.basename(path)), "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    with open(os.path.join(a.out_dir, "diff.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "file", "lst_c", "air_tmax_jja_normal_c", "climate_before", "climate_after", "total_before", "total_after"])
        w.writeheader()
        w.writerows(recs)
    print(f"{checked} places checked against PRISM; {len(recs)} heat readings screened out (margin {HEAT_MAX_BELOW_AIR_C} C); wrote {a.out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["sample", "apply"])
    ap.add_argument("--prism-dir")
    ap.add_argument("--air-ref", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--catalog-dir", default=os.path.join(ROOT, "data"))
    a = ap.parse_args()
    if a.step == "sample":
        if not a.prism_dir:
            sys.exit("sample needs --prism-dir")
        return sample(a)
    if not a.out_dir:
        sys.exit("apply needs --out-dir")
    return apply(a)


if __name__ == "__main__":
    sys.exit(main())
