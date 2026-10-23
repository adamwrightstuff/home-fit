#!/usr/bin/env python3
"""
Fetch FEMA NFHL flood zones for every catalog place into data/fema_flood_zones_catalog.json.

The snapshot is the raw source data for recompute_flood_offline.py, so flood scores can be recomputed
offline and repeatably (the same pattern as the school snapshot).  Only places missing from the snapshot
(or whose last request failed) are queried; pass --refresh to query everything again.  Free public API,
no key; about 0.6 s per place at 6 parallel requests.

  cd /Users/adamwright/Dev/home-fit
  PYTHONPATH=. python3 scripts/catalog/fetch_fema_flood_snapshot.py
  PYTHONPATH=. python3 scripts/catalog/fetch_fema_flood_snapshot.py --refresh
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from data_sources.fema_flood import FEMA_NFHL_QUERY_URL, FEMA_OUT_FIELDS, fetch_flood_features  # noqa: E402

SNAPSHOT = os.path.join(ROOT, "data", "fema_flood_zones_catalog.json")


def place_key(lat: float, lon: float) -> str:
    return f"{lat:.5f},{lon:.5f}"


def catalog_points() -> dict:
    pts = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(path, encoding="utf-8"):
            c = (json.loads(line).get("score") or {}).get("coordinates") or {}
            if isinstance(c.get("lat"), (int, float)) and isinstance(c.get("lon"), (int, float)):
                pts[place_key(c["lat"], c["lon"])] = (c["lat"], c["lon"])
    return pts


def _query(latlon):
    for attempt in range(4):
        feats = fetch_flood_features(*latlon)
        if feats is not None:
            return feats
        time.sleep(1.5 * (attempt + 1))
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-query every place")
    args = ap.parse_args()

    snap = {"_meta": {}, "places": {}}
    if os.path.isfile(SNAPSHOT):
        snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    places = snap.setdefault("places", {})
    pts = catalog_points()
    todo = [k for k in pts if args.refresh or places.get(k) is None]
    print(f"{len(pts)} catalog places, {len(todo)} to query")
    if todo:
        with ThreadPoolExecutor(6) as ex:
            for k, feats in zip(todo, ex.map(_query, [pts[k] for k in todo])):
                places[k] = feats
        snap["_meta"] = {
            "source": FEMA_NFHL_QUERY_URL,
            "out_fields": FEMA_OUT_FIELDS,
            "last_updated": datetime.date.today().isoformat(),
            "note": "value is the list of FEMA zones at the point; [] = no mapped polygon; null = request failed (scored neutral)",
        }
        with open(SNAPSHOT, "w", encoding="utf-8") as f:
            json.dump({"_meta": snap["_meta"], "places": dict(sorted(places.items()))}, f, separators=(",", ":"))
    failed = [k for k in pts if places.get(k) is None]
    print(f"snapshot has {sum(1 for k in pts if k in places)} of {len(pts)} places; {len(failed)} still failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
