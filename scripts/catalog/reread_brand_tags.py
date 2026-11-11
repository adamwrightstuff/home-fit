#!/usr/bin/env python3
"""
Re-read the social and cultural venues around every catalog place from the PRIVATE Overpass server, keeping the OSM
brand tags the stored business lists dropped (docs/LOCAL_SCENE.md). Only OpenStreetMap data is read: no Census, Earth
Engine or Google calls, and no pillar is rescored. Output is one JSON line per place in
data/local_scene_brand_reads.jsonl (untracked). Resumable: places already in the output (keyed by coordinates) are skipped.

The public Overpass servers refuse scripts, so this only ever talks to the two private tunnels:
  port A (default 12345): NY NJ CT CA WA TX IL IN PA DE MD
  port B (default 12346): AZ CO FL GA MA NC NV
A state outside both lists is skipped and reported, never sent to a public server.

  PYTHONPATH=. python3 scripts/catalog/reread_brand_tags.py --dry-run          # counts only, no network
  PYTHONPATH=. python3 scripts/catalog/reread_brand_tags.py --limit 5          # small trial
  PYTHONPATH=. caffeinate -i python3 scripts/catalog/reread_brand_tags.py      # the full run (about 75 minutes)
"""
from __future__ import annotations

import argparse
import glob
import inspect
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

STATES_A = {"NY", "NJ", "CT", "CA", "WA", "TX", "IL", "IN", "PA", "DE", "MD"}
STATES_B = {"AZ", "CO", "FL", "GA", "MA", "NC", "NV"}
RADIUS_M = 1500  # widest amenities radius; each venue keeps distance_m so it can be trimmed to the pillar radius later


def coord_key(lat, lon) -> str:
    return f"{float(lat):.5f},{float(lon):.5f}"


def load_places():
    places = []
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = Path(path).name.split("_metro_")[0]
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("success"):
                continue
            c = r["catalog"]
            places.append({"metro": metro, "name": c["name"], "state": c.get("state_abbr"),
                           "lat": float(c["lat"]), "lon": float(c["lon"])})
    return places


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port-a", type=int, default=12345)
    ap.add_argument("--port-b", type=int, default=12346)
    ap.add_argument("--out", default=str(REPO / "data" / "local_scene_brand_reads.jsonl"))
    ap.add_argument("--limit", type=int, default=None, help="read at most this many new places")
    ap.add_argument("--dry-run", action="store_true", help="count places and ports, no network")
    args = ap.parse_args()

    places = load_places()
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in open(out, encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["key"])
    todo, skipped_states = [], {}
    for p in places:
        if coord_key(p["lat"], p["lon"]) in done:
            continue
        if p["state"] in STATES_A:
            p["port"] = args.port_a
        elif p["state"] in STATES_B:
            p["port"] = args.port_b
        else:
            skipped_states[p["state"]] = skipped_states.get(p["state"], 0) + 1
            continue
        todo.append(p)
    print(f"places {len(places)}, already read {len(done)}, to read {len(todo)}, skipped (state not on the private server) {skipped_states}")
    if args.dry_run:
        return 0
    if args.limit:
        todo = todo[: args.limit]

    from data_sources import osm_api
    from pillars.local_scene_v2 import VENUE_TYPES

    fn = inspect.unwrap(osm_api.query_local_businesses)  # bypass the disk cache, which holds results without brand tags
    t0 = time.time()
    fails = 0
    with open(out, "a", encoding="utf-8") as fh:
        for n, p in enumerate(todo, 1):
            osm_api.OVERPASS_URLS = [f"http://localhost:{p['port']}/api/interpreter"]  # private server only, no public fallbacks
            res, secs = None, 0.0
            for attempt in range(3):
                t = time.time()
                try:
                    res = fn(p["lat"], p["lon"], radius_m=RADIUS_M, include_chains=True)
                except Exception as e:  # keep going; the place is retried on the next run
                    print(f"  {p['name']}: attempt {attempt + 1} failed: {e}")
                    res = None
                secs = time.time() - t
                if res:
                    break
                time.sleep(3)
            if not res:
                fails += 1
                print(f"  {p['name']} ({p['state']}): no result, will be retried next run")
                continue
            venues = [
                {k: b.get(k) for k in ("name", "type", "distance_m", "lat", "lon", "osm_id", "brand", "brand_wikidata")}
                for tier in ("tier1_daily", "tier2_social", "tier3_culture", "tier4_services")
                for b in (res.get(tier) or [])
                if b.get("type") in VENUE_TYPES and (b.get("name") or "").strip()
            ]
            fh.write(json.dumps({"key": coord_key(p["lat"], p["lon"]), "metro": p["metro"], "name": p["name"],
                                 "state": p["state"], "lat": p["lat"], "lon": p["lon"], "radius_m": RADIUS_M,
                                 "secs": round(secs, 1), "venues": venues}, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 25 == 0 or n == len(todo):
                el = time.time() - t0
                print(f"{n}/{len(todo)} read, {fails} failed, {el / 60:.1f} min elapsed, about {el / n * (len(todo) - n) / 60:.0f} min left")
    print(f"done: {len(todo) - fails} read, {fails} failed (rerun to retry the failures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
