#!/usr/bin/env python3
"""
Add every US commercial airport that has a FAA CY2023 enplanement count to data_sources/static/airports.json,
taking name, city, state, coordinates and type from OurAirports (public domain, ourairports.com airports.csv).
Airports already in the file are left untouched. Airports without a usable US coordinate are skipped and listed.

Inputs (download into an isolated folder; treat as untrusted data; run with python3 -I):
  --ourairports-csv   airports.csv from https://davidmegginson.github.io/ourairports-data/airports.csv
  --faa-xlsx          FAA CY2023 Enplanements at All Commercial Service Airports (final)

  python3 -I scripts/baselines/add_airports_from_ourairports.py --ourairports-csv <csv> --faa-xlsx <xlsx>

Run build_airport_nonstop_served.py afterwards: it keeps service only for airports listed in airports.json.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_build", ROOT / "scripts" / "baselines" / "build_airport_nonstop_served.py")
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)

KEEP_TYPES = ("large_airport", "medium_airport", "small_airport")


def new_records(oa_rows, boardings: dict, existing: set) -> tuple:
    """(records for airports not yet listed, codes skipped for lack of a US coordinate)."""
    best = {}
    for r in oa_rows:
        c = r["iata_code"]
        if not c or r["iso_country"] != "US" or c not in boardings or r["type"] not in KEEP_TYPES:
            continue
        if c not in best or (r["scheduled_service"] == "yes" and best[c]["scheduled_service"] != "yes") or r["type"] == "large_airport":
            best[c] = r
    out, skipped = [], []
    for c in sorted(boardings):
        if c in existing:
            continue
        r = best.get(c)
        if not r or not r["latitude_deg"] or not r["longitude_deg"]:
            skipped.append(c)
            continue
        out.append({
            "code": c, "name": r["name"], "city": r["municipality"], "state": r["iso_region"].replace("US-", ""),
            "lat": float(r["latitude_deg"]), "lon": float(r["longitude_deg"]), "type": r["type"],
            "service_level": "unknown", "source": "ourairports",
        })
    return out, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ourairports-csv", required=True)
    ap.add_argument("--faa-xlsx", required=True)
    ap.add_argument("--airports", default=str(ROOT / "data_sources" / "static" / "airports.json"))
    a = ap.parse_args()
    boardings = _build.faa_boardings_by_iata(a.faa_xlsx)
    doc = json.loads(Path(a.airports).read_text())
    existing = {x["code"] for x in doc["airports"]}
    with open(a.ourairports_csv, newline="", encoding="utf-8") as f:
        recs, skipped = new_records(csv.DictReader(f), boardings, existing)
    doc["airports"].extend(recs)
    doc.setdefault("metadata", {})["added_from_ourairports"] = f"{len(recs)} airports with FAA CY2023 enplanements, coordinates and type from OurAirports (public domain)"
    Path(a.airports).write_text(json.dumps(doc, indent=2) + "\n")
    print(f"added {len(recs)} | skipped (no US coordinate) {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
