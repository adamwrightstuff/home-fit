#!/usr/bin/env python3
"""
Re-read Transitland route counts at the sourced walking radii (bus 800 m, rail and light rail 1,200 m) for every
catalog place, so the transit search radius (DPv2 P3) can be tested against the stored area-type radii. Read-only on
the catalog: results go to one side JSONL, one line per place, resumable (places already in the file are skipped,
failed reads are not written and are retried on the next run). Nothing is scored here.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 -I scripts/catalog/refetch_transit_radii.py --out analysis/transit_radii_refetch.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from pillars.public_transit_access import _get_nearby_routes  # noqa: E402

BUS_M, RAIL_M = 800, 1200
TYPES = {1: "subway", 2: "commuter_rail", 0: "light_rail", 3: "bus"}


def counts(routes):
    seen = {}
    for r in routes:
        seen[r.get("route_id") or id(r)] = r.get("route_type")
    return {name: sum(1 for v in seen.values() if v == t) for t, name in TYPES.items()}


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
        bus = counts(_get_nearby_routes(lat, lon, radius_m=BUS_M))
        rail = counts(_get_nearby_routes(lat, lon, radius_m=RAIL_M))
    except Exception as e:  # failed read is no data, retried next run
        return key, None, str(e)[:120]
    time.sleep(0.1)
    return key, {"bus": bus["bus"], "subway": rail["subway"], "commuter_rail": rail["commuter_rail"],
                 "light_rail": rail["light_rail"]}, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    done = set()
    if out.exists():
        done = {json.loads(l)["key"] for l in open(out)}
    todo = [p for p in places() if p[0] not in done]
    print(f"{len(done)} done, {len(todo)} to fetch ({len(todo) * 2} Transitland calls)")
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
