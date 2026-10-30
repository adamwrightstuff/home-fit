#!/usr/bin/env python3
"""
Latency test for scoring transit over nine sample points on a live request (18 Transitland route reads per place:
bus at 800 m and subway, light rail and commuter rail at 1,200 m, at each of nine points). For each pilot place it times
the 18 reads run one after another and then run in parallel (as a live request would), then repeats the parallel run
with several requests at once to show rate-limit and slowdown behavior. Reads only; changes nothing.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/latency_test_transit_area.py
  (options: --workers 9 --concurrent 4 --only Astoria)
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

from pillars.public_transit_access import _get_nearby_routes  # noqa: E402
from scripts.catalog.refetch_transit_radii import BUS_M, RAIL_M  # noqa: E402
from scripts.catalog.refetch_transit_sample_points import sample_points  # noqa: E402

logging.disable(logging.CRITICAL)
PILOT = [("Astoria", 40.7721, -73.9302), ("Bronxville", 40.9387, -73.8327), ("Harrison", 40.9759, -73.7129),
         ("Decatur", 33.7711, -84.2958), ("Hinsdale", 41.8025, -87.93)]


def one_call(args):
    lat, lon, radius = args
    t = time.time()
    try:
        _get_nearby_routes(lat, lon, radius_m=radius)
        return time.time() - t, None
    except Exception as e:
        return time.time() - t, type(e).__name__


def calls_for(lat, lon, jitter=0.0):
    pts = sample_points(lat + jitter, lon + jitter)
    return [(la, lo, r) for la, lo in pts for r in (BUS_M, RAIL_M)]


def run_place(lat, lon, workers, jitter=0.0):
    calls = calls_for(lat, lon, jitter)
    t = time.time()
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one_call, calls))
    return time.time() - t, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=9)
    ap.add_argument("--concurrent", type=int, default=4)
    ap.add_argument("--only")
    a = ap.parse_args()
    places = [p for p in PILOT if not a.only or p[0].startswith(a.only)]

    print("one place, 18 calls: sequential vs parallel, cold reads (each run uses shifted points so no cache hits)")
    seq_t, par_t, per_call, errs = [], [], [], []
    for i, (name, lat, lon) in enumerate(places):
        t0 = time.time()
        res_seq = [one_call(c) for c in calls_for(lat, lon, jitter=0.0003 * (i + 1))]
        seq = time.time() - t0
        par, res_par = run_place(lat, lon, a.workers, jitter=-0.0003 * (i + 1))
        seq_t.append(seq)
        par_t.append(par)
        per_call += [d for d, _ in res_seq + res_par]
        errs += [e for _, e in res_seq + res_par if e]
        print(f"  {name:11s} sequential {seq:5.1f}s   parallel({a.workers}) {par:5.1f}s")
    print(f"  per-call latency: median {st.median(per_call):.2f}s  p95 {sorted(per_call)[int(len(per_call) * .95)]:.2f}s  max {max(per_call):.2f}s")
    print(f"  sequential mean {st.mean(seq_t):.1f}s | parallel mean {st.mean(par_t):.1f}s | errors {len(errs)} {sorted(set(errs))}")

    print(f"\n{a.concurrent} requests at once (parallel {a.workers} each, {a.concurrent * 18} calls in flight at most)")
    t0 = time.time()
    with ThreadPoolExecutor(a.concurrent) as ex:
        futs = [ex.submit(run_place, lat, lon, a.workers, 0.0006 * (j + 1))
                for j, (_, lat, lon) in enumerate((places * a.concurrent)[:a.concurrent])]
        out = [f.result() for f in futs]
    walls = [w for w, _ in out]
    e2 = [e for _, res in out for _, e in res if e]
    print(f"  per-request wall time: mean {st.mean(walls):.1f}s  max {max(walls):.1f}s | total {time.time() - t0:.1f}s | errors {len(e2)} {sorted(set(e2))}")
    print("\nA live /score request today makes about 2 route reads for this pillar.")


if __name__ == "__main__":
    main()
