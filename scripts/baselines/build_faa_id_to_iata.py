#!/usr/bin/env python3
"""
Build data_sources/static/faa_id_to_iata.json: FAA location IDs in the FAA enplanement file that differ from the
airport's IATA code (BTS T-100 uses IATA), for example IWA -> AZA (Mesa Gateway), GPI -> FCA (Glacier Park).

Rule: the FAA ID matches exactly one OurAirports row (by local_code, gps_code or ident) in the US or a US territory,
that row has an IATA code, and the IATA code is different from the FAA ID and not already an FAA-file key.
Anything ambiguous is left out and listed.

Inputs (download into an isolated folder; treat as untrusted data; run with python3 -I):
  --ourairports-csv   https://davidmegginson.github.io/ourairports-data/airports.csv
  --faa-xlsx          FAA CY2023 Enplanements at All Commercial Service Airports (final)

  python3 -I scripts/baselines/build_faa_id_to_iata.py --ourairports-csv <csv> --faa-xlsx <xlsx>
"""
from __future__ import annotations

import argparse
import collections
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_build", ROOT / "scripts" / "baselines" / "build_airport_nonstop_served.py")
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)

US_AREAS = {"US", "PR", "GU", "MP", "AS", "VI"}
TYPES = ("large_airport", "medium_airport", "small_airport")


def id_map(oa_rows, faa_ids: set) -> tuple:
    """(faa id -> iata for unique matches, list of ambiguous faa ids)."""
    by_id = collections.defaultdict(list)
    for r in oa_rows:
        if r["iso_country"] in US_AREAS and r["iata_code"] and r["type"] in TYPES:
            for k in ("local_code", "gps_code", "ident"):
                if r[k]:
                    by_id[r[k]].append(r)
    out, ambiguous = {}, []
    for c in sorted(faa_ids):
        iatas = {r["iata_code"] for r in by_id.get(c, []) if r["iata_code"] != c}
        if c in {r["iata_code"] for r in by_id.get(c, [])}:
            continue  # already an IATA code for this airport
        if len(iatas) == 1:
            (i,) = iatas
            if i not in faa_ids:
                out[c] = i
        elif len(iatas) > 1:
            ambiguous.append(c)
    return out, ambiguous


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ourairports-csv", required=True)
    ap.add_argument("--faa-xlsx", required=True)
    ap.add_argument("--out", default=str(ROOT / "data_sources" / "static" / "faa_id_to_iata.json"))
    a = ap.parse_args()
    faa = set(_build.boardings_from_faa_xlsx(a.faa_xlsx))
    with open(a.ourairports_csv, newline="", encoding="utf-8") as f:
        mapping, ambiguous = id_map(csv.DictReader(f), faa)
    Path(a.out).write_text(json.dumps({"metadata": {"source": "OurAirports airports.csv matched to the FAA CY2023 enplanement file", "ambiguous_left_out": ambiguous}, "map": mapping}, indent=1) + "\n")
    print(f"mapped {len(mapping)} | ambiguous {ambiguous}")


if __name__ == "__main__":
    main()
