#!/usr/bin/env python3
"""
Download Natural Earth 10m physical data for water proximity scoring.

Puts files in data_sources/static/ (or HOMEFIT_NE_DATA_DIR).
Run once; then water_proximity_ne.py will load them at runtime.

If the Natural Earth server returns 406/500, download manually from:
  https://www.naturalearthdata.com/downloads/10m-physical-vectors/
Then unzip ne_10m_coastline.zip, ne_10m_lakes.zip, ne_10m_rivers_lake_centerlines.zip
into data_sources/static/ (or HOMEFIT_NE_DATA_DIR).

Usage:
  python scripts/download_natural_earth_water.py
  HOMEFIT_NE_DATA_DIR=/path/to/dir python scripts/download_natural_earth_water.py
"""

import os
import sys
import zipfile
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/physical"
FILES = [
    "ne_10m_coastline.zip",
    "ne_10m_lakes.zip",
    "ne_10m_rivers_lake_centerlines.zip",
]


def main():
    out_dir = os.environ.get(
        "HOMEFIT_NE_DATA_DIR",
        os.path.join(ROOT, "data_sources", "static"),
    )
    os.makedirs(out_dir, exist_ok=True)
    print(f"Downloading Natural Earth 10m data to {out_dir}")

    for name in FILES:
        path_zip = os.path.join(out_dir, name)
        if os.path.isfile(path_zip):
            print(f"  {name} already exists, skipping download")
        else:
            url = f"{BASE_URL}/{name}"
            print(f"  Fetching {url} ...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HomeFit/1.0 (https://github.com/adamwrightstuff/home-fit)"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    with open(path_zip, "wb") as f:
                        f.write(resp.read())
            except Exception as e:
                print(f"  ERROR: {e}")
                sys.exit(1)

        # Unzip
        base = name.replace(".zip", "")
        shp = os.path.join(out_dir, f"{base}.shp")
        if not os.path.isfile(shp):
            print(f"  Extracting {name} ...")
            with zipfile.ZipFile(path_zip, "r") as z:
                z.extractall(out_dir)
        else:
            print(f"  {base}.shp already present")

    print("Done. Natural Earth water data ready for water_proximity_ne.py.")


if __name__ == "__main__":
    main()
