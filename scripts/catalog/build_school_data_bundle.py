#!/usr/bin/env python3
"""
Build the slim school geography bundle (data/school_geo/) that production reads.

Raw downloads (data_cache/tiger_sd_2024, tiger_place_2024, zone_maps, nces_ccd_2324) are about 200 MB; the bundle keeps
only the columns the scorer uses, simplifies outlines to about 10 m and drops places too large to matter. Re-run it when
a raw layer is refreshed, then commit data/school_geo/.

  PYTHONPATH=. python3 scripts/catalog/build_school_data_bundle.py
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402

from data_sources import school_districts as sd  # noqa: E402
from data_sources import school_zones as sz  # noqa: E402

OUT = os.path.join(REPO, "data", "school_geo")
SIMPLIFY = 0.0001   # degrees, about 10 m
STATES = ("06", "09", "17", "18", "34", "36", "42", "48", "53")


def _write(name: str, frame: "gpd.GeoDataFrame") -> int:
    frame = frame.copy()
    frame["geometry"] = frame.geometry.simplify(SIMPLIFY, preserve_topology=True)
    frame["geometry"] = shapely.set_precision(frame.geometry.values, 1e-5)
    frame = frame[~frame.geometry.is_empty]
    path = os.path.join(OUT, f"{name}.geojson.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(frame.to_json(drop_id=True))
    return os.path.getsize(path)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for fips in STATES:
        for kind in sd._KINDS:
            paths = glob.glob(os.path.join(sd._root(), f"tl_2024_{fips}_{kind}", "*.shp"))
            if paths:
                g = gpd.read_file(paths[0], columns=["GEOID", "NAME"]).to_crs(4326)
                total += _write(f"district_{fips}_{kind}", g)
        paths = glob.glob(os.path.join(sd._place_root(), f"tl_2024_{fips}_place", "*.shp"))
        if paths:
            g = gpd.read_file(paths[0], columns=["GEOID", "NAME"]).to_crs(4326)
            area_sq_mi = g.to_crs(5070).area / 2_589_988.11
            total += _write(f"place_{fips}", g[area_sq_mi <= sd.MAX_PLACE_SQ_MI])
    for layer in sz.ZONE_LAYERS:
        folder = os.path.join(sz._root(), layer.folder)
        files = glob.glob(os.path.join(folder, "*.geojson")) or glob.glob(os.path.join(folder, "*.shp"))
        if not files:
            print("missing raw zone layer", layer.folder)
            continue
        g = gpd.read_file(files[0])
        g = (g.set_crs(4326) if g.crs is None else g).to_crs(4326)
        keep = list(dict.fromkeys([*layer.name_fields, layer.id_field, *( [layer.only_where[0]] if layer.only_where else [])]))
        total += _write(f"zone_{layer.folder}", g[[c for c in keep if c in g.columns] + ["geometry"]])
    # NYC school code -> name (NCES), 1,500 rows
    df = pd.read_csv(sz._nces_csv(), dtype=str, low_memory=False, usecols=["ST", "SCH_NAME", "ST_SCHID", "LEA_NAME"])
    ny = df[(df.ST == "NY") & df.LEA_NAME.str.contains("GEOGRAPHIC DISTRICT", na=False)]
    names = {}
    import re
    for lea, sid, name in zip(ny.LEA_NAME, ny.ST_SCHID, ny.SCH_NAME):
        d = re.search(r"#\s*(\d+)", str(lea))
        if d and str(sid)[-4:].isdigit():
            names[f"{int(d.group(1))}:{int(str(sid)[-4:])}"] = str(name)
    with open(os.path.join(OUT, "nyc_dbn_names.json"), "w") as f:
        json.dump(names, f, separators=(",", ":"))
    total += os.path.getsize(os.path.join(OUT, "nyc_dbn_names.json"))
    print(f"bundle written to {OUT}: {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
