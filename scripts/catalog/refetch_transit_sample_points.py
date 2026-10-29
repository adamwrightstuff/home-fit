#!/usr/bin/env python3
"""
Read Transitland route counts at nine sample points per catalog place (the pin plus eight points on the edge of the
1 km disk used for area type), at the sourced walking radii (bus 800 m, subway and light rail 1,200 m), so transit access
can be scored over the place instead of at one pin (DPv2 P3, P6). Commuter rail keeps its separate drive-distance
side file. Read-only on the catalog: one side JSONL line per place, resumable; failed reads are not written and are
retried on the next run.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/refetch_transit_sample_points.py --out analysis/transit_sample_points.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.catalog.refetch_transit_radii import BUS_M, RAIL_M, counts, places  # noqa: E402
from pillars.public_transit_access import _get_nearby_routes  # noqa: E402

EDGE_M = 1000.0
BEARINGS = range(0, 360, 45)


def sample_points(lat, lon):
    pts = [(lat, lon)]
    for b in BEARINGS:
        r = math.radians(b)
        pts.append((lat + EDGE_M * math.cos(r) / 111320.0, lon + EDGE_M * math.sin(r) / (111320.0 * math.cos(math.radians(lat)))))
    return pts


def work(item):
    key, lat, lon = item
    out = []
    try:
        for la, lo in sample_points(lat, lon):
            bus = counts(_get_nearby_routes(la, lo, radius_m=BUS_M))
            rail = counts(_get_nearby_routes(la, lo, radius_m=RAIL_M))
            out.append({"lat": round(la, 5), "lon": round(lo, 5), "bus": bus["bus"], "subway": rail["subway"],
                        "commuter_rail": rail["commuter_rail"], "light_rail": rail["light_rail"]})
            time.sleep(0.05)
    except Exception as e:
        return key, None, str(e)[:120]
    return key, out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    done = {json.loads(l)["key"] for l in open(out)} if out.exists() else set()
    todo = [p for p in places() if p[0] not in done]
    print(f"{len(done)} done, {len(todo)} to fetch ({len(todo) * 18} Transitland calls)")
    failed = 0
    with ThreadPoolExecutor(a.workers) as ex, open(out, "a") as fh:
        for i, (key, pts, err) in enumerate(ex.map(work, todo), 1):
            if pts is None:
                failed += 1
                print(f"FAILED {key}: {err}")
                continue
            fh.write(json.dumps({"key": key, "points": pts}) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(f"{i}/{len(todo)}")
    print(f"finished, {failed} failed (rerun the same command to retry them)")


if __name__ == "__main__":
    main()
