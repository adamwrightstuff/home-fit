#!/usr/bin/env python3
"""
Active outdoors Level 2, check 1 (pin-shift) on the current code. Method as fixed in docs/ACTIVE_OUTDOORS_LEVEL2_BRIEF.md
and run before in analysis/ao_level2_rerun6_check1_pin_shift.csv: the same 60 places (analysis/ao_level2_check1_pin_shift.csv,
seed 20261102), each pin shifted 500 m and 1,000 m north, east, south and west, plus a fresh unshifted read of the same place.
Tree canopy passed as 0, the catalog's current stored area type held fixed (places retyped since the sample was drawn are noted), density context recomputed at each shifted pin from the local tables
(surrounding_factors). The change is measured against the fresh unshifted score. Private Overpass server only, no paid call.

The earlier runner was not saved in the repo; this is a rewrite of the same method.

  OVERPASS_URL=http://localhost:12345/api/interpreter HOMEFIT_DISK_CACHE_DIR=<new empty dir> \
  HOMEFIT_PLACES_AO_FALLBACK_ENABLED=false PYTHONPATH=. python3 scripts/qa/active_outdoors_pin_shift.py \
    --out analysis/ao_level2_rerun7_check1_pin_shift.csv [--limit N] [--workers 4]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

BEARINGS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}  # (north, east) unit steps


def shifted(lat, lon, dist_m, bearing):
    n, e = BEARINGS[bearing]
    dlat = n * dist_m / 111320.0
    dlon = e * dist_m / (111320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def load_sample(path):
    seen, out = set(), []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            k = (r["place"], r["state"], r["area"])
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


def load_catalog():
    rows = {}
    for p in glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
        metro = Path(p).name.split("_metro_")[0]
        for line in open(p):
            if not line.strip():
                continue
            d = json.loads(line)
            c = d["catalog"]
            ao = d["score"]["livability_pillars"].get("active_outdoors", {})
            area = (ao.get("area_classification") or {}).get("area_type")
            rows.setdefault((c["name"], c["state_abbr"]), []).append(
                (metro, float(c["lat"]), float(c["lon"]), ao.get("score"), area))
    return rows


def score_at(lat, lon, area):
    from data_sources.place_context import PlaceContext, surrounding_factors
    from pillars.active_outdoors import get_active_outdoors_score_v2
    ctx = PlaceContext(lat=lat, lon=lon, city=None, area_type=area, density=None, area_type_source="catalog_stored",
                       **surrounding_factors(lat, lon))
    s, details = get_active_outdoors_score_v2(lat, lon, city=None, area_type=area, precomputed_tree_canopy_5km=0,
                                              place_context=ctx)
    b = (details or {}).get("breakdown", {}) or {}
    return s, b.get("daily_urban_outdoors"), b.get("wild_adventure"), b.get("waterfront_lifestyle"), details


def read_status(details):
    d = details or {}
    probs = []
    for k in ("data_quality", "warnings", "error"):
        v = d.get(k)
        if v:
            probs.append(f"{k}={str(v)[:80]}")
    return ";".join(probs)


def run_place(job):
    place, state, area, lat, lon, stored = job
    rows = []
    plan = [(0, 0)] + [(m, b) for m in (500, 1000) for b in (0, 90, 180, 270)]
    base = None
    for dist, brg in plan:
        la, lo = (lat, lon) if dist == 0 else shifted(lat, lon, dist, brg)
        try:
            s, daily, wild, water, det = score_at(la, lo, area)
            err, prob = "", read_status(det)
        except Exception as e:  # recorded, never hidden
            s = daily = wild = water = None
            err, prob = f"{type(e).__name__}: {str(e)[:120]}", ""
        if dist == 0:
            base = s
        rows.append({"place": place, "state": state, "area": area, "shift_m": dist, "bearing": brg,
                     "total": None if s is None else round(s, 1), "daily": daily, "wild": wild, "water": water,
                     "err": err,
                     "change_vs_unshifted_fresh": ("" if dist == 0 or s is None or base is None else round(abs(s - base), 1)),
                     "read_problem": prob, "stored_total": stored})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=str(REPO / "analysis" / "ao_level2_check1_pin_shift.csv"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if "localhost" not in os.environ.get("OVERPASS_URL", ""):
        sys.exit("OVERPASS_URL must point at the private server tunnel (localhost). Refusing to run.")
    if not os.environ.get("HOMEFIT_DISK_CACHE_DIR"):
        sys.exit("Set HOMEFIT_DISK_CACHE_DIR to a new empty directory so no stored read is reused.")
    cat = load_catalog()
    jobs = []
    for place, state, area in load_sample(a.sample):
        c = cat.get((place, state))
        if not c:
            sys.exit(f"no catalog row for {place} {state}")
        if len(c) > 1:
            same = [r for r in c if r[4] == area]
            print(f"note: {len(c)} catalog rows for {place} {state}; using the one typed {area if same else c[0][4]}", file=sys.stderr)
            c = same or c
        _, lat, lon, stored, cur_area = c[0]
        if cur_area != area:
            print(f"note: {place} {state} was {area} in the 2026-11-02 sample and is {cur_area} in the catalog now; holding {cur_area}", file=sys.stderr)
        jobs.append((place, state, cur_area, lat, lon, stored))
    if a.limit:
        jobs = jobs[: a.limit]
    fields = ["place", "state", "area", "shift_m", "bearing", "total", "daily", "wild", "water", "local", "trail",
              "regional", "err", "change_vs_unshifted_fresh", "read_problem", "stored_total"]
    with open(a.out, "w", newline="") as f, ThreadPoolExecutor(max_workers=a.workers) as ex:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for i, rows in enumerate(ex.map(run_place, jobs), 1):
            for r in rows:
                w.writerow(r)
            f.flush()
            print(f"{i}/{len(jobs)} {rows[0]['place']} {rows[0]['state']}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
