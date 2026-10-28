"""
Build data/tract_pop_area_centers.parquet: one row per 2020 Census tract with its center point,
land area and ACS 2022 5-year total population. The surrounding-area density (people per square
mile over the tracts whose center lies within a radius of a pin) reads this table locally instead
of calling the Census API per request.

Inputs (downloaded by hand, see docs/PLACE_CONTEXT.md):
  --gazetteer  2023_Gaz_tracts_national.zip   (census.gov 2023 Gazetteer, tracts, 2020 vintage)
  --acs-dir    folder of <state_fips>.json     (api.census.gov/data/2022/acs/acs5?get=B01003_001E&for=tract:*&in=state:XX)

Usage:
  PYTHONPATH=. python3 scripts/baselines/build_tract_table.py --gazetteer PATH --acs-dir DIR
"""
import argparse
import glob
import json
import os
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "data", "tract_pop_area_centers.parquet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gazetteer", required=True)
    ap.add_argument("--acs-dir", required=True)
    args = ap.parse_args()

    pop = {}
    for f in sorted(glob.glob(os.path.join(args.acs_dir, "*.json"))):
        for r in json.load(open(f))[1:]:
            try:
                pop[r[1] + r[2] + r[3]] = int(r[0])
            except (TypeError, ValueError):
                continue  # suppressed or missing: the tract is left out, never filled with zero

    z = zipfile.ZipFile(args.gazetteer)
    name = [n for n in z.namelist() if n.endswith(".txt")][0]
    rows = {"geoid": [], "lat": [], "lon": [], "pop": [], "land_sqmi": []}
    skipped = 0
    for line in z.read(name).decode("latin-1").splitlines()[1:]:
        p = line.split("\t")
        geoid, sqmi = p[1], float(p[4])
        if geoid not in pop or sqmi <= 0:
            skipped += 1
            continue
        rows["geoid"].append(geoid)
        rows["lat"].append(float(p[6]))
        rows["lon"].append(float(p[7].strip()))
        rows["pop"].append(pop[geoid])
        rows["land_sqmi"].append(sqmi)
    pq.write_table(pa.table(rows), OUT, compression="zstd")
    print(f"wrote {OUT}: {len(rows['geoid'])} tracts ({skipped} skipped: no population or no land area)")


if __name__ == "__main__":
    main()
