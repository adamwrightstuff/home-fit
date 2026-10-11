#!/usr/bin/env python3
"""
Build data/austin_block_groups.json: simplified Census block-group polygons around Austin.

Austin PD's public Crime Reports dataset carries no coordinates, only the 10-digit
block-group code (county + tract + BG, no state prefix).  crime_api.py apportions a
block group's incidents to a neighborhood circle by polygon overlap, so it needs the
polygons.  Counties: Travis 453, Williamson 491, Hays 209.

Usage (project root):
    PYTHONPATH=. python3 scripts/baselines/build_austin_block_groups.py [--tiger-zip path]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import urllib.request
import zipfile
import tempfile

import geopandas as gpd

TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2020/BG/tl_2020_48_bg.zip"
COUNTIES = {"453", "491", "209"}
# Rough box around the City of Austin and its ETJ, to drop far-off block groups.
BBOX = (30.05, -98.10, 30.70, -97.35)  # lat_min, lon_min, lat_max, lon_max
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "data", "austin_block_groups.json")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tiger-zip", help="Local tl_2020_48_bg.zip (downloaded if omitted)")
    args = p.parse_args()

    tmp = tempfile.mkdtemp()
    zpath = args.tiger_zip
    if not zpath:
        zpath = os.path.join(tmp, "bg48.zip")
        req = urllib.request.Request(TIGER_URL, headers={"User-Agent": "homefit-data-fetcher/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as f:
            f.write(r.read())
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(tmp)
    shp = next(os.path.join(tmp, n) for n in os.listdir(tmp) if n.endswith(".shp"))
    g = gpd.read_file(shp)
    g = g[g["COUNTYFP"].isin(COUNTIES)].to_crs(epsg=4326)
    g = g.cx[BBOX[1]:BBOX[3], BBOX[0]:BBOX[2]]
    g["geometry"] = g.geometry.simplify(0.0002, preserve_topology=True)
    out = {}
    for _, row in g.iterrows():
        geom = row.geometry
        polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        out[row["GEOID"][2:]] = [
            [[round(x, 5), round(y, 5)] for x, y in poly.exterior.coords] for poly in polys
        ]
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Wrote {len(out)} block groups to {OUT} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
