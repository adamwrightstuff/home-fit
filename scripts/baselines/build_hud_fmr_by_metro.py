#!/usr/bin/env python3
"""
Build data/hud_fmr_metro.json: HUD two-bedroom Fair Market Rent for each metro (CBSA).

HUD defines FMR areas inside metros (New York, NY; Newark, NJ; Nassau-Suffolk, NY ...), not
one rent per metro.  This weights each county's HUD area rent by the county's renter
households, then averages over the counties of each Census CBSA.

Sources (all public, no key except Census):
- HUD "Fair Market Rents" feature service (HUD Open Data, ArcGIS): metro FMR area polygons and
  FMR_2BDR.  The service labels its coverage FY2024 (see data/hud_fmr_metro.json _meta).
- Census OMB 2023 CBSA delineation (county -> CBSA), Census 2023 Gazetteer (county centroids).
- ACS 2023 B25003_003 renter-occupied units by county (CENSUS_API_KEY).

A county takes the rent of the HUD metro area polygon that contains its centroid (nearest
polygon of the same metro if the centroid falls outside, e.g. a non-convex county).  Needs
shapely (admin script; not used at request time).

Usage:  PYTHONPATH=. python3 scripts/baselines/build_hud_fmr_by_metro.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HUD_LAYER = "https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/Fair_Market_Rents/FeatureServer/0"
HUD_QUERY = (HUD_LAYER + "/query?where=FMR_CODE%20LIKE%20%27METRO%25%27&outFields=FMR_CODE,FMR_AREANAME,FMR_2BDR"
             "&maxAllowableOffset=0.01&geometryPrecision=3&resultRecordCount=1000&f=geojson")
DELINEATION = ("https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/"
               "delineation-files/list1_2023.xlsx")
GAZETTEER = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip"


def _get(url: str) -> bytes:
    return urllib.request.urlopen(url, timeout=180).read()


def _xlsx_rows(raw: bytes):
    """Rows of the first sheet of an .xlsx as lists of strings (stdlib only)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(x.text or "" for x in si.iter("{%s}t" % ns["m"])))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        for row in sheet.find("m:sheetData", ns).findall("m:row", ns):
            cells = {}
            for c in row.findall("m:c", ns):
                col = re.match(r"[A-Z]+", c.get("r")).group()
                v = c.find("m:v", ns)
                if v is None:
                    continue
                cells[col] = shared[int(v.text)] if c.get("t") == "s" else v.text
            yield [cells.get(ch, "") for ch in "ABCDEFGHIJKL"]


def county_to_cbsa() -> dict:
    out = {}
    for r in _xlsx_rows(_get(DELINEATION)):
        if r[4] == "Metropolitan Statistical Area" and r[9] and r[10]:
            out[r[9] + r[10]] = r[0]
    return out


def county_centroids() -> dict:
    with zipfile.ZipFile(io.BytesIO(_get(GAZETTEER))) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "ignore")
    rows = csv.reader(io.StringIO(text), delimiter="\t")
    header = [h.strip() for h in next(rows)]
    gi, la, lo = header.index("GEOID"), header.index("INTPTLAT"), header.index("INTPTLONG")
    return {r[gi]: (float(r[la]), float(r[lo])) for r in rows if len(r) > lo}


def county_renters(key: str) -> dict:
    url = ("https://api.census.gov/data/2023/acs/acs5?get=B25003_003E&for=county:*&in=state:*&key=" + key)
    return {s + c: float(v) for v, s, c in json.loads(_get(url))[1:] if v not in (None, "") and float(v) > 0}


def main() -> None:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY not set")
    fc = json.loads(_get(HUD_QUERY))
    areas = []  # (cbsa, polygon, fmr_2br, name)
    for f in fc["features"]:
        p = f["properties"]
        if p["FMR_2BDR"] and f["geometry"]:
            areas.append((p["FMR_CODE"][5:10], shape(f["geometry"]).buffer(0), float(p["FMR_2BDR"]), p["FMR_AREANAME"]))
    by_cbsa = {}
    for a in areas:
        by_cbsa.setdefault(a[0], []).append(a)

    c2c, cent, renters = county_to_cbsa(), county_centroids(), county_renters(key)
    acc = {}
    matched = outside = 0
    for fips, cbsa in c2c.items():
        cand = by_cbsa.get(cbsa)
        if not cand or fips not in cent or fips not in renters:
            continue
        lat, lon = cent[fips]
        pt = Point(lon, lat)
        hit = [a for a in cand if a[1].contains(pt)]
        if hit:
            area = hit[0]
            matched += 1
        else:
            area = min(cand, key=lambda a: a[1].distance(pt))
            outside += 1
        w = renters[fips]
        s = acc.setdefault(cbsa, {"w": 0.0, "wf": 0.0, "counties": 0})
        s["w"] += w
        s["wf"] += w * area[2]
        s["counties"] += 1

    out = {
        "_meta": {
            "description": "HUD two-bedroom Fair Market Rent by metro (CBSA): county HUD-area rent weighted by renter households",
            "hud_layer": HUD_LAYER,
            "hud_coverage_per_layer_metadata": "FY2024 (Oct 1 - Sep 30)",
            "weights": "ACS 2023 B25003_003 renter-occupied units by county",
            "counties_in_polygon": matched,
            "counties_nearest_polygon": outside,
            "metros": len(acc),
        },
        "metros": {c: {"fmr_2br": round(v["wf"] / v["w"], 1), "counties": v["counties"]} for c, v in sorted(acc.items())},
    }
    with open(os.path.join(ROOT, "data", "hud_fmr_metro.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out["_meta"], indent=1))
    for c in ("19100", "35620", "31080", "41860", "38060", "37980"):
        print(c, out["metros"].get(c))


if __name__ == "__main__":
    main()
