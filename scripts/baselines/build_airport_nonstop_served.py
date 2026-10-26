#!/usr/bin/env python3
"""
Build data_sources/static/airport_nonstop_served_2023.json for pillars/air_travel_access.py.

Inputs (download them yourself into an isolated folder; treat as untrusted data):
  --bts-csv   BTS T-100 Segment (All Carriers) for one calendar year, from
              https://www.transtats.bts.gov (table "T-100 Segment (All Carriers)", fields ORIGIN, DEST,
              DEPARTURES_PERFORMED, PASSENGERS, all months, "Download zip" checked)
  --faa-xlsx  FAA "CY 2023 Enplanements at All Commercial Service Airports" (final) spreadsheet from faa.gov

A destination counts as served from an origin when the pair had at least 52 departures performed in the year
(about weekly) and at least 5 passengers per departure on average (excludes cargo-only service). Only destinations
that appear in the FAA file (US commercial service airports) are kept, so coverage is domestic only.

  python3 -I scripts/baselines/build_airport_nonstop_served.py --bts-csv <csv> --faa-xlsx <xlsx> [--out <json>]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MIN_DEPARTURES = 52
MIN_PASSENGERS_PER_DEPARTURE = 5
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def boardings_from_faa_xlsx(path: str) -> dict:
    """Airport code -> CY enplanements, read from the first sheet (columns D = Locid, I = CY enplanements)."""
    z = zipfile.ZipFile(path)
    shared = [
        "".join(t.text or "" for t in si.iter(_NS + "t"))
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_NS + "si")
    ]
    out = {}
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(_NS + "row"):
        cells = {}
        for c in row.findall(_NS + "c"):
            v = c.find(_NS + "v")
            if v is not None:
                cells[re.match("[A-Z]+", c.get("r")).group()] = shared[int(v.text)] if c.get("t") == "s" else v.text
        if cells.get("D") and cells.get("I", "").isdigit():
            out[cells["D"]] = int(cells["I"])
    return out


def served_from_segments(rows, boardings: dict) -> dict:
    """origin -> sorted destinations served nonstop under the definition above."""
    departures = collections.Counter()
    passengers = collections.Counter()
    for r in rows:
        key = (r["ORIGIN"], r["DEST"])
        departures[key] += float(r["DEPARTURES_PERFORMED"] or 0)
        passengers[key] += float(r["PASSENGERS"] or 0)
    served = collections.defaultdict(set)
    for (origin, dest), deps in departures.items():
        if (deps >= MIN_DEPARTURES and passengers[(origin, dest)] / deps >= MIN_PASSENGERS_PER_DEPARTURE
                and dest in boardings and origin != dest):
            served[origin].add(dest)
    return {k: sorted(v) for k, v in served.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bts-csv", required=True)
    ap.add_argument("--faa-xlsx", required=True)
    ap.add_argument("--airports", default=str(Path(__file__).resolve().parents[2] / "data_sources" / "static" / "airports.json"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data_sources" / "static" / "airport_nonstop_served_2023.json"))
    a = ap.parse_args()
    boardings = boardings_from_faa_xlsx(a.faa_xlsx)
    with open(a.bts_csv, newline="") as f:
        served = served_from_segments(csv.DictReader(f), boardings)
    codes = {x["code"] for x in json.load(open(a.airports))["airports"]}
    served = {k: v for k, v in served.items() if k in codes}
    if not served or not boardings:
        sys.exit("empty result; check the input files")
    meta = {
        "served_source": "BTS T-100 Segment (All Carriers), transtats.bts.gov table FMG",
        "served_definition": (f"destination airports in the FAA file with at least {MIN_DEPARTURES} departures performed in the year "
                              f"and at least {MIN_PASSENGERS_PER_DEPARTURE} passengers per departure on average (excludes cargo-only service). Domestic only."),
        "boardings_source": "FAA CY2023 Enplanements at All Commercial Service Airports (final), faa.gov",
        "build_script": "scripts/baselines/build_airport_nonstop_served.py",
    }
    Path(a.out).write_text(json.dumps({"metadata": meta, "served": served, "boardings": boardings}, separators=(",", ":")))
    print(f"airports with service {len(served)} | boardings airports {len(boardings)}")


if __name__ == "__main__":
    main()
