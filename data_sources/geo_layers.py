"""
Read a polygon layer from the slim bundle (data/school_geo/<name>.geojson.gz, committed, used in production)
or, when the bundle is absent, from the raw download (data_cache/...). Both give the same columns.
Build the bundle with scripts/catalog/build_school_data_bundle.py.
"""
from __future__ import annotations

import glob
import gzip
import json
import os
from typing import List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_dir() -> str:
    return os.getenv("HOMEFIT_SCHOOL_GEO_DIR", os.path.join(REPO, "data", "school_geo"))


def read_layer(name: str, raw_dir: str, columns: Optional[List[str]] = None):
    """GeoDataFrame in EPSG:4326 for bundle `name`, else the raw layer in `raw_dir`; None if neither exists."""
    import geopandas as gpd

    packed = os.path.join(bundle_dir(), f"{name}.geojson.gz")
    if os.path.isfile(packed):
        with gzip.open(packed, "rt", encoding="utf-8") as f:
            frame = gpd.GeoDataFrame.from_features(json.load(f)["features"], crs=4326)
    else:
        files = glob.glob(os.path.join(raw_dir, "*.geojson")) or glob.glob(os.path.join(raw_dir, "*.shp"))
        if not files:
            return None
        frame = gpd.read_file(files[0])
        if frame.crs is None:
            frame = frame.set_crs(4326)
        frame = frame.to_crs(4326)
    if columns:
        keep = [c for c in columns if c in frame.columns] + ["geometry"]
        frame = frame[keep]
    return frame
