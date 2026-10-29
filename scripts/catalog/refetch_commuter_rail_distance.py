#!/usr/bin/env python3
"""
Read the distance from every catalog place to its nearest commuter rail stations (GTFS route type 2) within 10 km
(6.2 miles, the 85th percentile of park-and-ride driving distance in Vijayakumar, El-Geneidy and Patterson, TRR 2219,
2011), so commuter rail credit can fall with distance (DPv2 P3). Read-only on the catalog: results go to one side
JSONL, one line per place, resumable; failed reads are not written and are retried on the next run.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/refetch_commuter_rail_distance.py --out analysis/commuter_rail_distance.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from data_sources.transitland_api import TRANSITLAND_BASE_URL  # noqa: E402
from data_sources.utils import haversine_distance  # noqa: E402

RADIUS_M = 10000
KEEP = 10


def places():
    for f in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            c, s = r.get("catalog") or {}, r.get("score") or {}
            co = s.get("coordinates") or {}
            if co.get("lat") is None:
                continue
            yield f"{Path(f).name.split('_')[0]}|{c.get('name')}|{co['lat']:.4f},{co['lon']:.4f}", co["lat"], co["lon"]


def work(item):
    key, lat, lon = item
    try:
        r = None
        for _ in range(2):
            r = requests.get(
                f"{TRANSITLAND_BASE_URL}/rest/stops",
                params={"lat": lat, "lon": lon, "radius": RADIUS_M, "served_by_route_type": 2, "limit": 100,
                        "apikey": os.getenv("TRANSITLAND_API_KEY")},
                timeout=30,
            )
            if r.status_code == 200:
                break
        if r is None or r.status_code != 200:
            return key, None, f"HTTP {getattr(r, 'status_code', None)}"
        stops = r.json().get("stops", [])
        ds = sorted(
            (haversine_distance(lat, lon, s["geometry"]["coordinates"][1], s["geometry"]["coordinates"][0]),
             s.get("stop_name"))
            for s in stops if s.get("geometry")
        )
        time.sleep(0.1)
        return key, {"stops_found": len(stops), "limit_hit": len(stops) >= 100,
                     "nearest": [{"m": round(m), "name": n} for m, n in ds[:KEEP]]}, None
    except Exception as e:
        return key, None, str(e)[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    done = {json.loads(l)["key"] for l in open(out)} if out.exists() else set()
    todo = [p for p in places() if p[0] not in done]
    print(f"{len(done)} done, {len(todo)} to fetch")
    failed = 0
    with ThreadPoolExecutor(a.workers) as ex, open(out, "a") as fh:
        for i, (key, res, err) in enumerate(ex.map(work, todo), 1):
            if res is None:
                failed += 1
                print(f"FAILED {key}: {err}")
                continue
            fh.write(json.dumps({"key": key, **res}) + "\n")
            fh.flush()
            if i % 100 == 0:
                print(f"{i}/{len(todo)}")
    print(f"finished, {failed} failed (rerun the same command to retry them)")


if __name__ == "__main__":
    main()
