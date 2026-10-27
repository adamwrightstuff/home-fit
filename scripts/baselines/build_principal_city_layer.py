"""
Build data/principal_city_places.parquet: the outlines of the places that OMB lists as principal cities of
metropolitan and micropolitan areas, so the area type can ask "is this pin inside a principal city?" from a
local file at request time.

Inputs (downloaded by hand, see docs/PLACE_CONTEXT.md):
  --omb-xlsx   list2_2023.xlsx  (census.gov, OMB July 2023 delineation, List 2: principal cities)
  --place-dir  folder holding tl_2024_<state fips>_place/ Census TIGER/Line place shapefiles

Only the states present in --place-dir are covered. The covered state FIPS codes are stored in the file's
metadata (key "covered_states"); a pin in any other state gets "unknown", never "not a principal city".
Outlines are simplified to about 50 m. The column named_in_title marks principal cities whose name is part of
their metro's OMB title (Chicago in "Chicago-Naperville-Elgin", not Aurora), the metro's major cities; the area
type counts only those, because HUD's labels agree better with them (accuracy 0.851 against 0.840 for all
principal cities, precision 0.89 against 0.84).

Usage:
  PYTHONPATH=. python3 scripts/baselines/build_principal_city_layer.py --omb-xlsx PATH --place-dir DIR
"""
import argparse
import glob
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile

import geopandas as gpd
import pyarrow as pa
import pyarrow.parquet as pq

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "data", "principal_city_places.parquet")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_omb(path):
    z = zipfile.ZipFile(path)
    ss = ["".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))
          for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    out = {}
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter("{%s}row" % NS["m"]):
        cells = {}
        for c in r.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is not None:
                cells[re.match(r"[A-Z]+", c.get("r")).group(0)] = ss[int(v.text)] if c.get("t") == "s" else v.text
        if re.fullmatch(r"\d{2}", cells.get("E", "")) and re.fullmatch(r"\d{5}", cells.get("F", "")):
            out[(cells["E"], cells["F"])] = (cells["B"], cells["C"].split()[0])  # (CBSA title, Metropolitan|Micropolitan)
    return out


def named_in_title(name, title):
    segs = [s.strip().lower() for s in re.split(r"[-–,]", title.split(",")[0])]
    n = re.sub(r"\s*\(.*\)", "", name.lower()).strip()
    n = re.sub(r"\s+(city|town|village|borough)$", "", n)
    return any(n == s or n.startswith(s) or s.startswith(n) for s in segs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--omb-xlsx", required=True)
    ap.add_argument("--place-dir", required=True)
    args = ap.parse_args()
    pcs = read_omb(args.omb_xlsx)
    rows = {"statefp": [], "placefp": [], "name": [], "cbsa_title": [], "kind": [], "named_in_title": [], "wkb": []}
    covered = []
    for shp in sorted(glob.glob(os.path.join(args.place_dir, "tl_2024_*_place", "*.shp"))):
        g = gpd.read_file(shp)[["STATEFP", "PLACEFP", "NAME", "geometry"]].to_crs(4326)
        covered.append(g["STATEFP"].iloc[0])
        for _, r in g.iterrows():
            key = (r["STATEFP"], r["PLACEFP"])
            if key not in pcs:
                continue
            rows["statefp"].append(key[0]); rows["placefp"].append(key[1]); rows["name"].append(r["NAME"])
            rows["cbsa_title"].append(pcs[key][0]); rows["kind"].append(pcs[key][1])
            rows["named_in_title"].append(named_in_title(r["NAME"], pcs[key][0]))
            rows["wkb"].append(r["geometry"].simplify(0.0005, preserve_topology=True).wkb)
    table = pa.table(rows).replace_schema_metadata({"covered_states": json.dumps(sorted(set(covered)))})
    pq.write_table(table, OUT, compression="zstd")
    print(f"wrote {OUT}: {len(rows['name'])} principal-city outlines in {len(set(covered))} states "
          f"({os.path.getsize(OUT) / 1e6:.1f} MB); OMB list has {len(pcs)} principal cities")


if __name__ == "__main__":
    main()
