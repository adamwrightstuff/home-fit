#!/usr/bin/env python3
"""
Map each catalog place (lat/lon) to its 2010 census tract via TIGERweb point-in-polygon, then join CDC
USALEEP tract life expectancy (data/usaleep/US_A.CSV). USALEEP uses 2010 tract codes.

Output: data/usaleep/catalog_tract_map.json  {metro|name|lat|lon: {geoid, e0, se, flag}}
Resumable (skips keys already mapped). Only free Census TIGERweb calls; no scorer, Overpass or GEE.

  PYTHONPATH=. python3 scripts/catalog/map_catalog_to_usaleep.py
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2010/MapServer/14/query"
OUT = ROOT / "data/usaleep/catalog_tract_map.json"
METROS = ["nyc", "la", "sf", "seattle"]


def main() -> int:
    le = {r["Tract ID"].zfill(11): r for r in csv.DictReader(open(ROOT / "data/usaleep/US_A.CSV"))}
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    s = requests.Session()
    n = 0
    for m in METROS:
        f = ROOT / f"data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
        for ln in f.read_text().splitlines():
            if not ln.strip():
                continue
            c = json.loads(ln)["catalog"]
            key = f"{m}|{c['name']}|{c['lat']}|{c['lon']}"
            if key in done and done[key].get("geoid"):
                continue
            geoid = None
            for attempt in range(3):
                try:
                    q = s.get(URL, params={"geometry": f"{c['lon']},{c['lat']}", "geometryType": "esriGeometryPoint",
                                           "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                                           "outFields": "GEOID", "returnGeometry": "false", "f": "json"}, timeout=60).json()
                    feats = q.get("features") or []
                    geoid = feats[0]["attributes"]["GEOID"] if feats else None
                    break
                except Exception:
                    time.sleep(2)
            rec = {"geoid": geoid}
            r = le.get(geoid or "")
            if r and r["e(0)"]:
                rec.update(e0=float(r["e(0)"]), se=float(r["se(e(0))"] or 0), flag=r["Abridged life table flag"])
            done[key] = rec
            n += 1
            if n % 50 == 0:
                OUT.write_text(json.dumps(done))
                print(n, flush=True)
    OUT.write_text(json.dumps(done))
    got = sum(1 for v in done.values() if "e0" in v)
    print(f"mapped {len(done)} places, {got} with USALEEP life expectancy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
