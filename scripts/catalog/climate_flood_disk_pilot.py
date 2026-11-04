#!/usr/bin/env python3
"""
Pilot: score flood as the average of the flood points over an 800 m disk instead of at the single pin (DPv2 principles 3 and 6).

Reads the 60-place sample of climate_pin_shift.py. For each place it asks FEMA NFHL once for every flood polygon within
RADIUS_M + 1,000 m of the pin (1,800 m), saves the polygons, then computes locally, with no further reads:
  - the disk-average flood points at the pin, and at each of the eight shifted centres of the pin-shift test (N, E, S, W at
    500 m and 1,000 m), so the disk measure is tested on exactly the points the pin measure failed on;
  - the climate score with the disk flood value and the shifted heat read already in reads.jsonl (air and trend as stored).
Disk average: points of each zone weighted by the area of the disk it covers; the mapped part only (zone D and unmapped area are
no data and are left out, as in the pillar). Overlapping polygons are resolved worst tier first.
FEMA reads: one query per place (more only if the service pages the answer). Nothing is changed in the catalog.

  cd /Users/adamwright/Dev/home-fit/.claude/worktrees/dpv2-climate-risk
  python3 scripts/catalog/climate_flood_disk_pilot.py --shift-dir analysis/climate_pin_shift_2026-11-03 --out-dir analysis/climate_flood_disk_pilot_2026-11-03
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from data_sources import fema_flood as fema  # noqa: E402
from data_sources.fema_flood import _classify_zone  # noqa: E402

RADIUS_M = fema.FLOOD_DISK_RADIUS_M
FETCH_M = 1800.0
MAX_PTS = {"heat": 25.0, "air": 20.0, "flood": 30.0, "trend": 25.0}
DIRS = {"N": (1, 0), "E": (0, 1), "S": (-1, 0), "W": (0, -1)}


def query(lat, lon, fetch_m=FETCH_M):
    return fema.fetch_flood_polygons(lat, lon, fetch_m)


def to_geom(feature, lat0, lon0):
    return fema.polygon_to_geom(feature, lat0, lon0)


def disk_flood(zones, cx, cy):
    """zones: [(tier, geom)] in metres around the pin. Returns (mean points over mapped area or None, mapped fraction, tier shares)."""
    return fema.disk_flood_points(zones, cx, cy, RADIUS_M)


def score_from(pts):
    present = [k for k, v in pts.items() if v is not None]
    if len(present) < 3:
        return None
    return round(min(100.0, sum(pts[k] for k in present) / sum(MAX_PTS[k] for k in present) * 100.0), 1)


def p95(v):
    v = sorted(v)
    return v[min(len(v) - 1, int(math.ceil(0.95 * len(v))) - 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shift-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sleep", type=float, default=1.0)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    sample = json.load(open(os.path.join(a.shift_dir, "sample.json")))
    reads = [json.loads(l) for l in open(os.path.join(a.shift_dir, "reads.jsonl"))]
    by_place = {}
    for r in reads:
        by_place.setdefault((r["name"], r["state"]), []).append(r)
    raw_path = os.path.join(a.out_dir, "polygons.json")
    raw = json.load(open(raw_path)) if os.path.exists(raw_path) else {}
    n_queries = 0
    for p in sample:
        key = f"{p['name']}|{p['state']}"
        if key in raw:
            continue
        raw[key] = query(p["lat"], p["lon"])
        n_queries += 1
        json.dump(raw, open(raw_path, "w"))
        print(f"  {n_queries}: {key} {len(raw[key])} polygons", flush=True)
        time.sleep(a.sleep)
    print(f"{n_queries} place queries made this run", flush=True)

    rows, pin_rows = [], []
    for p in sample:
        key = f"{p['name']}|{p['state']}"
        zones = []
        for f in raw[key]:
            at = f.get("attributes") or {}
            g = to_geom(f, p["lat"], p["lon"])
            if g is not None and not g.is_empty:
                zones.append((_classify_zone(at.get("FLD_ZONE"), at.get("SFHA_TF"), at.get("ZONE_SUBTY")), g))
        kx = 111320.0 * math.cos(math.radians(p["lat"]))
        d0, mapped0, sh0 = disk_flood(zones, 0.0, 0.0)
        pts0 = dict(p["pts"])
        pts0["flood"] = None if d0 is None else round(d0, 2)
        base = score_from(pts0)
        pin_rows.append({"name": p["name"], "state": p["state"], "area_type": p["area_type"], "stored_score": p["stored_score"],
                         "disk_score": base, "disk_flood_pts": pts0["flood"], "pin_flood_pts": p["pts"]["flood"], "mapped_fraction": round(mapped0, 3)})
        for r in by_place.get((p["name"], p["state"]), []):
            if r["flood_failed"] or r["heat_failed"]:
                continue
            n, e = DIRS[r["dir"]]
            dx, dy = e * r["meters"], n * r["meters"]
            d, mapped, _ = disk_flood(zones, dx, dy)
            pts = dict(r["pts"])  # shifted heat read, stored air and trend
            pts["flood"] = None if d is None else round(d, 2)
            s = score_from(pts)
            if s is None or base is None:
                continue
            rows.append({"area_type": p["area_type"], "meters": r["meters"], "change": abs(s - base), "pin_change": abs(r["score"] - r["stored_score"]) if r["score"] is not None else None})
    json.dump({"pins": pin_rows, "shifts": rows}, open(os.path.join(a.out_dir, "results.json"), "w"), indent=1)

    out = ["# Flood disk pilot (800 m disk average)", "", f"Places: {len(pin_rows)}; shifted points scored: {len(rows)}", "",
           "| group | shift | n | median change | 95th percentile | share over 10 | pin measure 95th |", "|---|---|---|---|---|---|---|"]

    def block(label, rs):
        for m in sorted({r["meters"] for r in rs}):
            c = [r["change"] for r in rs if r["meters"] == m]
            pc = [r["pin_change"] for r in rs if r["meters"] == m and r["pin_change"] is not None]
            if c:
                out.append(f"| {label} | {m:.0f} m | {len(c)} | {st.median(c):.1f} | {p95(c):.1f} | {100 * sum(1 for x in c if x > 10) / len(c):.1f}% | {p95(pc):.1f} |")

    block("all", rows)
    for at in sorted({r["area_type"] for r in rows}):
        block(at, [r for r in rows if r["area_type"] == at])
    diff = [abs(r["disk_score"] - r["stored_score"]) for r in pin_rows if r["disk_score"] is not None]
    mf = [r["mapped_fraction"] for r in pin_rows]
    out += ["", f"Disk score against stored pin score at the pin: median difference {st.median(diff):.1f}, 95th percentile {p95(diff):.1f}, "
            f"{sum(1 for x in diff if x > 5)} of {len(diff)} places differ by more than 5.",
            f"Places with no flood component under the disk measure: {sum(1 for r in pin_rows if r['disk_flood_pts'] is None)}.",
            f"Mapped fraction of the disk: median {st.median(mf):.2f}, minimum {min(mf):.2f}, places under 0.5: {sum(1 for x in mf if x < 0.5)}."]
    open(os.path.join(a.out_dir, "summary.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
