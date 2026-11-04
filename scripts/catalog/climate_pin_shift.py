#!/usr/bin/env python3
"""
Pin-shift sensitivity for climate_risk (DPv2 principle 6). Reads fresh FEMA flood zones (and optionally GEE heat and
Census tracts for PM2.5) at points shifted north, east, south and west of each sampled place, rescoring the climate pillar
with everything else held at its stored value.

Sample: --per-type places from each area type, chosen with a fixed seed from the recomputed catalog files in --catalog-dir.
Reads: FEMA = places x 4 directions x len(distances). Heat (GEE) = same count when --heat is on. PM2.5 uses the Census
geocoder and is off unless --pm25 is given. The warming trend (5 km circle, 4 km pixels) is not re-read.

Results append to <out-dir>/reads.jsonl, so an interrupted run resumes where it stopped. --out-dir must be new or hold only
a previous run of this script. --summarize prints the result and writes <out-dir>/summary.md without any reads.

  cd /Users/adamwright/Dev/home-fit/.claude/worktrees/dpv2-climate-risk
  PYTHONPATH=. python3 scripts/catalog/climate_pin_shift.py --out-dir analysis/climate_pin_shift_2026-11-03 --heat
  PYTHONPATH=. python3 scripts/catalog/climate_pin_shift.py --out-dir analysis/climate_pin_shift_2026-11-03 --summarize
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import statistics as st
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

DIRS = {"N": (1, 0), "E": (0, 1), "S": (-1, 0), "W": (0, -1)}
MAX_PTS = {"heat": 25.0, "air": 20.0, "flood": 30.0, "trend": 25.0}
SEED = 20261103


def load_sample(catalog_dir: str, per_type: int):
    by_type: dict = {}
    for path in sorted(glob.glob(os.path.join(catalog_dir, "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            sc = r.get("score") or {}
            cr = (sc.get("livability_pillars") or {}).get("climate_risk")
            c = sc.get("coordinates") or {}
            if not cr or not isinstance(cr.get("score"), (int, float)) or "lat" not in c:
                continue
            at = (cr.get("area_classification") or {}).get("area_type") or "unknown"
            if at == "unknown":
                continue
            b = cr.get("breakdown") or {}
            by_type.setdefault(at, []).append({
                "name": (r.get("catalog") or {}).get("name"), "state": (r.get("catalog") or {}).get("state_abbr"),
                "area_type": at, "lat": c["lat"], "lon": c["lon"], "stored_score": cr["score"],
                "pts": {"heat": b.get("heat_exposure_pts"), "air": b.get("air_quality_pts"),
                        "flood": b.get("flood_zone_pts"), "trend": b.get("climate_trend_pts")},
            })
    rng = random.Random(SEED)
    sample = []
    for at in sorted(by_type):
        pool = sorted(by_type[at], key=lambda p: (p["state"] or "", p["name"] or ""))
        sample += rng.sample(pool, min(per_type, len(pool)))
    return sample


def shifted(lat: float, lon: float, d: str, meters: float):
    n, e = DIRS[d]
    return lat + n * meters / 111320.0, lon + e * meters / (111320.0 * math.cos(math.radians(lat)))


def score_from(pts: dict) -> float | None:
    present = [k for k, v in pts.items() if v is not None]
    if len(present) < 3:
        return None
    return round(min(100.0, sum(pts[k] for k in present) / sum(MAX_PTS[k] for k in present) * 100.0), 1)


def run(args) -> int:
    from data_sources.fema_flood import FLOOD_MAX_PTS_DEFAULT, fetch_flood_features, flood_zone_from_features
    if args.heat:
        from pillars.climate_risk import HEAT_MIN_LAND_FRACTION, LST_PLAUSIBLE_MAX_C, LST_PLAUSIBLE_MIN_C, heat_points
        from data_sources.gee_api import get_heat_exposure_lst
    if args.pm25:
        from data_sources.air_quality_pm25 import get_pm25
        from pillars.climate_risk import air_quality_points
    os.makedirs(args.out_dir, exist_ok=True)
    reads_path = os.path.join(args.out_dir, "reads.jsonl")
    done = set()
    if os.path.exists(reads_path):
        for line in open(reads_path, encoding="utf-8"):
            r = json.loads(line)
            done.add((r["name"], r["state"], r["dir"], r["meters"]))
    sample = load_sample(args.catalog_dir, args.per_type)
    json.dump(sample, open(os.path.join(args.out_dir, "sample.json"), "w"), indent=1)
    total = len(sample) * 4 * len(args.meters)
    print(f"{len(sample)} places, {total} shifted points; heat={'on' if args.heat else 'off'} pm25={'on' if args.pm25 else 'off'}", flush=True)
    n = 0
    with open(reads_path, "a", encoding="utf-8") as out:
        for p in sample:
            for meters in args.meters:
                for d in DIRS:
                    n += 1
                    if (p["name"], p["state"], d, meters) in done:
                        continue
                    lat, lon = shifted(p["lat"], p["lon"], d, meters)
                    pts = dict(p["pts"])
                    rec = {"name": p["name"], "state": p["state"], "area_type": p["area_type"], "dir": d, "meters": meters,
                           "stored_score": p["stored_score"], "flood_failed": False, "heat_failed": False}
                    feats = fetch_flood_features(lat, lon)
                    fl = flood_zone_from_features(feats, FLOOD_MAX_PTS_DEFAULT)
                    if fl is None:
                        rec["flood_failed"] = True  # a failed read is excluded from the summary, not scored
                    else:
                        pts["flood"] = fl["flood_zone_pts"]
                        rec["flood_tier"] = fl["risk_tier"]
                    if args.heat:
                        h = get_heat_exposure_lst(lat, lon)
                        lst = (h or {}).get("local_lst_c")
                        if h is None or lst is None:
                            rec["heat_failed"] = True
                        elif LST_PLAUSIBLE_MIN_C <= float(lst) <= LST_PLAUSIBLE_MAX_C and h.get("land_pixel_fraction", 1.0) >= HEAT_MIN_LAND_FRACTION:
                            pts["heat"] = heat_points(float(lst))
                            rec["lst_c"] = float(lst)
                        else:
                            pts["heat"] = None
                    if args.pm25:
                        from data_sources.census_api import get_census_tract
                        a = get_pm25(lat, lon, census_tract=get_census_tract(lat, lon))
                        if a is not None:
                            pts["air"] = air_quality_points(a["pm25_ugm3"])
                    rec["pts"] = pts
                    rec["score"] = score_from(pts)
                    out.write(json.dumps(rec) + "\n")
                    out.flush()
                    time.sleep(args.sleep)
                    if n % 20 == 0:
                        print(f"  {n}/{total}", flush=True)
    print("reads done; run again with --summarize", flush=True)
    return 0


def summarize(out_dir: str) -> int:
    recs = [json.loads(line) for line in open(os.path.join(out_dir, "reads.jsonl"), encoding="utf-8")]
    ok = [r for r in recs if not r["flood_failed"] and not r["heat_failed"] and r["score"] is not None]
    lines = [f"# Climate pin-shift summary", "", f"Reads: {len(recs)}; scored: {len(ok)}; failed reads excluded: {len(recs) - len(ok)}", ""]

    def p95(v):
        v = sorted(v)
        return v[min(len(v) - 1, int(math.ceil(0.95 * len(v))) - 1)]

    def block(label, rows):
        for m in sorted({r["meters"] for r in rows}):
            d = [abs(r["score"] - r["stored_score"]) for r in rows if r["meters"] == m]
            if d:
                lines.append(f"| {label} | {m} m | {len(d)} | {st.median(d):.1f} | {p95(d):.1f} | {100 * sum(1 for x in d if x > 10) / len(d):.1f}% |")

    lines += ["| group | shift | n | median change | 95th percentile | share over 10 |", "|---|---|---|---|---|---|"]
    block("all", ok)
    for at in sorted({r["area_type"] for r in ok}):
        block(at, [r for r in ok if r["area_type"] == at])
    flips = [r for r in ok if r.get("flood_tier") is not None]
    tiers = {}
    for r in flips:
        tiers.setdefault((r["name"], r["state"], r["meters"]), set()).add(r["flood_tier"])
    changed = sum(1 for v in tiers.values() if len(v) > 1)
    lines += ["", f"Flood tier differs among the four shifted points of a place: {changed} of {len(tiers)} place-distances."]
    open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--catalog-dir", default=os.path.join(ROOT, "analysis", "climate_dpv2_2026-11-03"))
    ap.add_argument("--per-type", type=int, default=12)
    ap.add_argument("--meters", type=float, nargs="+", default=[500.0, 1000.0])
    ap.add_argument("--heat", action="store_true", help="also re-read GEE heat at each shifted point (slow)")
    ap.add_argument("--pm25", action="store_true", help="also look up the Census tract and PM2.5 at each shifted point")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args()
    return summarize(a.out_dir) if a.summarize else run(a)


if __name__ == "__main__":
    sys.exit(main())
