#!/usr/bin/env python3
"""
Build data/oews_metro_wage_distribution.json for the economic pillar wage-distribution signal.

BLS OEWS metropolitan-area file (MSA_M<year>_dl.xlsx inside oesm<yy>ma.zip):
  https://www.bls.gov/oes/special-requests/oesm24ma.zip  (May 2024)
BLS blocks scripted downloads, so download the zip in a browser and extract it.

Keeps one row per area: all occupations (OCC_CODE 00-0000), cross-industry (NAICS 000000,
OWN_CODE 1235), and writes the annual 25th and 75th percentile wages keyed by the 5-digit area
(CBSA) code. An annual 75th percentile BLS prints as "#" means "at or above $239,200"; it is stored
as null, never as a made-up number. Parsing uses only the standard library (the XLSX is read as
zip + XML), so nothing needs installing.

Run from project root:
  PYTHONPATH=. python3 -I scripts/baselines/build_oews_metro_wages.py --input ~/Downloads/oesm24ma
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "oews_metro_wage_distribution.json"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WANTED = ("AREA", "AREA_TITLE", "NAICS", "OWN_CODE", "OCC_CODE", "TOT_EMP", "A_PCT25", "A_MEDIAN", "A_PCT75")


def _shared_strings(z: zipfile.ZipFile) -> list:
    out = []
    with z.open("xl/sharedStrings.xml") as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == NS + "si":
                out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
    return out


def _col(ref: str) -> str:
    return re.match(r"[A-Z]+", ref).group(0)


def _rows(z: zipfile.ZipFile, sheet: str, strings: list):
    """Yield {column letter: value} per row."""
    with z.open(sheet) as fh:
        for _, el in ET.iterparse(fh):
            if el.tag != NS + "row":
                continue
            row = {}
            for c in el.findall(NS + "c"):
                v = c.find(NS + "v")
                if v is None or v.text is None:
                    continue
                row[_col(c.get("r"))] = strings[int(v.text)] if c.get("t") == "s" else v.text
            yield row
            el.clear()


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None  # "#", "*", "**" and other BLS flags are not numbers


def build(xlsx: Path) -> dict:
    out = {}
    with zipfile.ZipFile(xlsx) as z:
        strings = _shared_strings(z)
        for sheet in sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
            header = None
            for row in _rows(z, sheet, strings):
                if header is None:
                    if "OCC_CODE" in row.values() and "AREA" in row.values():
                        header = {col: name for col, name in row.items() if name in WANTED}
                        header_cols = {name: col for col, name in header.items()}
                        if not all(k in header_cols for k in ("AREA", "OCC_CODE", "A_PCT25", "A_PCT75")):
                            break
                    continue
                g = lambda name: row.get(header_cols.get(name))
                if g("OCC_CODE") != "00-0000":
                    continue
                if "NAICS" in header_cols and g("NAICS") not in ("000000", "0"):
                    continue
                if "OWN_CODE" in header_cols and g("OWN_CODE") not in ("1235", None):
                    continue
                area = g("AREA")
                if not area or not str(area).strip().isdigit():
                    continue
                out[str(int(float(area)))] = {
                    "wage_p25_annual": _num(g("A_PCT25")),
                    "wage_median_annual": _num(g("A_MEDIAN")),
                    "wage_p75_annual": _num(g("A_PCT75")),
                    "total_employment": _num(g("TOT_EMP")),
                    "area_title": g("AREA_TITLE"),
                }
            if header is not None:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Extracted oesm directory or MSA_M*_dl.xlsx")
    ap.add_argument("--output", default=str(OUT_PATH))
    args = ap.parse_args()
    path = Path(args.input).expanduser()
    files = [path] if path.is_file() else sorted(path.rglob("MSA_M*_dl.xlsx"))
    if not files:
        sys.exit(f"No MSA_M*_dl.xlsx found under {path}")
    data = build(files[0])
    if not data:
        sys.exit("Parsed zero areas; refusing to write an empty file")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    n25 = sum(v["wage_p25_annual"] is not None for v in data.values())
    n75 = sum(v["wage_p75_annual"] is not None for v in data.values())
    print(f"Wrote {len(data)} areas to {args.output} (p25 present {n25}, p75 present {n75})")


if __name__ == "__main__":
    main()
