#!/usr/bin/env python3
"""
Build data/relocation_rpp.json for comparison/relocation_equivalency.py.

National sources only, no catalog places:
- BEA Regional Price Parities (metro MARPP, state SARPP), every price line for the latest
  year: goods, housing (rent), utilities, other services.
- Census ACS 2023 5-year metro medians (B25064 gross rent, B25077 home value, B25003 tenure),
  joined to BEA by CBSA code.
- A least-squares fit of how BEA's all-items index weights its lines, so the non-housing
  price index can be weighted the way BEA weights it (BEA's own weights are not in the bulk
  files).

- Zillow Home Value Index (ZHVI, metro, all homes, mid tier, latest month), free with
  attribution to Zillow (https://www.zillow.com/research/data/), matched to metros by first
  principal city and state.  Metros without a match fall back to the ACS median home value.

Usage:  PYTHONPATH=. python3 scripts/baselines/build_relocation_inputs.py   (needs CENSUS_API_KEY)
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.request
import zipfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEA = "https://apps.bea.gov/regional/zip/{}.zip"
LINES = {"1": "all_items", "2": "goods", "3": "housing", "4": "utilities", "5": "other_services"}
ZHVI_URL = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
            "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
ACS_URL = ("https://api.census.gov/data/2023/acs/acs5?get=NAME,B25064_001E,B25077_001E,B25003_003E,B25003_001E"
           "&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*&key={}")


def _read(table: str, csv_name: str):
    raw = urllib.request.urlopen(BEA.format(table), timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        rows = list(csv.DictReader(io.StringIO(z.read(csv_name).decode("utf-8-sig"))))
    return rows, max(k for k in rows[0] if k.isdigit())


def _collect(rows, year, skip):
    out = {}
    for r in rows:
        lc = (r.get("LineCode") or "").strip()
        v = (r.get(year) or "").strip()
        code = r["GeoFIPS"].strip().strip('"')
        if lc in LINES and v not in ("", "(NA)") and code not in skip:
            out.setdefault(code, {"name": r["GeoName"].strip()})[LINES[lc]] = float(v)
    return {k: v for k, v in out.items() if len(v) == 6}


def _zillow_metro_values():
    """{(first city, first state): (name, latest ZHVI, month)} for Zillow metros."""
    text = urllib.request.urlopen(ZHVI_URL, timeout=120).read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    month = list(rows[0])[-1]
    out = {}
    for r in rows:
        if r["RegionType"] != "msa" or not r[month]:
            continue
        city, st = r["RegionName"].rsplit(", ", 1)
        out[(city.split("-")[0].strip().lower(), st.split("-")[0])] = (r["RegionName"], float(r[month]), month)
    return out


def main() -> None:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY not set")
    m_rows, year = _read("MARPP", "MARPP_MSA_2008_2024.csv")
    s_rows, s_year = _read("SARPP", "SARPP_STATE_2008_2024.csv")
    msa_all = _collect(m_rows, year, {"00000", "00999"})
    state = {v["name"]: {k: x for k, x in v.items() if k != "name"}
             for k, v in _collect(s_rows, s_year, {"00000"}).items()}

    names = ["goods", "housing", "utilities", "other_services"]
    A = np.array([[v[n] for n in names] for v in msa_all.values()])
    y = np.array([v["all_items"] for v in msa_all.values()])
    w, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ w
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    acs = json.load(urllib.request.urlopen(ACS_URL.format(key), timeout=120))[1:]
    msa = {}
    for name, rent, val, renters, occ, code in acs:
        if code in msa_all and rent and val and float(rent) > 0 and float(val) > 0:
            tail = name.split(",")[-1].strip()  # e.g. "NY-NJ Metro Area"
            msa[code] = {
                **msa_all[code],
                "acs_name": name,
                "states": tail.split(" ")[0].split("-"),
                "median_gross_rent": float(rent),
                "median_home_value": float(val),
                "renter_share": round(float(renters) / float(occ), 3) if occ and float(occ) > 0 else None,
            }

    zillow = _zillow_metro_values()
    matched = 0
    for m in msa.values():
        head, tail = m["acs_name"].split(",", 1)
        k = (head.split("-")[0].strip().lower(), tail.strip().split(" ")[0].split("-")[0])
        if k in zillow:
            m["zhvi"], m["zhvi_month"], m["zillow_name"] = zillow[k][1], zillow[k][2], zillow[k][0]
            matched += 1

    out = {
        "_meta": {
            "zillow": "Zillow Home Value Index (ZHVI), metro, all homes mid tier, latest month; data from Zillow Research, attribution required",
            "zillow_matched": matched,
            "source": "BEA Regional Price Parities (MARPP metro, SARPP state), US = 100; Census ACS 2023 5-year metro medians",
            "bea_year": int(year),
            "metros": len(msa),
            "metros_in_bea": len(msa_all),
            "all_items_weights_by_line": {n: round(float(x), 4) for n, x in zip(names, w)},
            "all_items_fit_r2": round(float(r2), 4),
            "all_items_fit_max_abs_error": round(float(abs(y - pred).max()), 2),
            "note": "weights are least-squares estimates of how BEA combines the lines, not BEA's published weights",
        },
        "msa": msa,
        "state": state,
    }
    with open(os.path.join(ROOT, "data", "relocation_rpp.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out["_meta"], indent=1))


if __name__ == "__main__":
    main()
