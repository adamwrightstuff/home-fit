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

from shapely.geometry import Point, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from data_sources.fema_flood import FEMA_NFHL_QUERY_URL, FLOOD_MAX_PTS_DEFAULT, _classify_zone, _flood_risk_to_points  # noqa: E402

RADIUS_M = 800.0
FETCH_M = 1800.0
TIER_ORDER = ["floodway", "sfha", "x_500yr", "d", "minimal"]  # worst first
MAX_PTS = {"heat": 25.0, "air": 20.0, "flood": 30.0, "trend": 25.0}
DIRS = {"N": (1, 0), "E": (0, 1), "S": (-1, 0), "W": (0, -1)}


def circle_rings(lat, lon, meters, n=64):
    dlat = meters / 111320.0
    dlon = meters / (111320.0 * math.cos(math.radians(lat)))
    ring = [[lon + dlon * math.cos(2 * math.pi * i / n), lat + dlat * math.sin(2 * math.pi * i / n)] for i in range(n)]
    ring.append(ring[0])
    return [ring]


def query(lat, lon, fetch_m=FETCH_M):
    feats, offset = [], 0
    while True:
        body = urllib.parse.urlencode({
            "where": "1=1", "geometry": json.dumps({"rings": circle_rings(lat, lon, fetch_m), "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPolygon", "inSR": "4326", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true", "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF", "f": "json",
            "maxAllowableOffset": 0.00002,  # about 2 m of vertex generalization: lighter answers, no visible effect on an 800 m disk
            "resultOffset": offset, "resultRecordCount": 100,
        }).encode()
        for attempt in range(4):  # the service sometimes answers a transient 500; retry with a pause, then fail loudly
            try:
                with urllib.request.urlopen(urllib.request.Request(FEMA_NFHL_QUERY_URL, data=body, method="POST"), timeout=90) as r:
                    data = json.loads(r.read().decode())
            except Exception as e:  # noqa: BLE001
                data = {"error": str(e)}
            if "features" in data:
                break
            time.sleep(5 * (attempt + 1))
        if "features" not in data:
            raise RuntimeError(f"FEMA answer without features: {str(data)[:200]}")
        feats += data["features"]
        if not data.get("exceededTransferLimit"):
            return feats
        offset += len(data["features"])


def to_geom(feature, lat0, lon0):
    """Esri rings (lon, lat) to a shapely geometry in metres east/north of (lat0, lon0)."""
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 111320.0
    ext, holes = [], []
    for ring in (feature.get("geometry") or {}).get("rings") or []:
        pts = [((x - lon0) * kx, (y - lat0) * ky) for x, y in ring]
        if len(pts) < 4:
            continue
        area2 = sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1))
        (ext if area2 < 0 else holes).append(Polygon(pts).buffer(0))  # Esri: clockwise rings are outer rings
    if not ext:
        return None
    g = unary_union(ext)
    return g.difference(unary_union(holes)) if holes else g


def disk_flood(zones, cx, cy):
    """zones: [(tier, geom)] in metres around the pin. Returns (mean points over mapped area or None, mapped fraction, tier shares)."""
    disk = Point(cx, cy).buffer(RADIUS_M, 64)
    taken, shares = None, {}
    for tier in TIER_ORDER:
        gs = [g for t, g in zones if t == tier]
        if not gs:
            continue
        part = unary_union(gs).intersection(disk)
        if taken is not None:
            part = part.difference(taken)
        if part.is_empty:
            continue
        shares[tier] = part.area / disk.area
        taken = part if taken is None else taken.union(part)
    mapped = sum(shares.values())
    scored = {t: s for t, s in shares.items() if _flood_risk_to_points(t, FLOOD_MAX_PTS_DEFAULT) is not None}
    denom = sum(scored.values())
    if denom <= 0:
        return None, mapped, shares
    pts = sum(_flood_risk_to_points(t, FLOOD_MAX_PTS_DEFAULT) * s for t, s in scored.items()) / denom
    return pts, mapped, shares


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
