"""
Build data/zillow_zhvi_zip_bedrooms.json from Zillow Research public CSVs.

Zillow publishes ZHVI by bedroom count (1, 2, 3, 4, 5+) at ZIP level, middle tier
(0.33-0.67), single-family plus condo/co-op combined. Zillow does not publish a
single-family-only series split by bedroom count, so home type cannot be separated
here; use the catalog housing_stock share for that.

Output JSON structure:
{
  "as_of": "2026-04-30",
  "source": "...",
  "bedrooms": {
    "1": { "11201": 650000, ... },
    "2": {...}, "3": {...}, "4": {...}, "5": {...}   # "5" means 5 or more
  }
}

Run from repo root:
  PYTHONPATH=. python3 scripts/baselines/build_zillow_zhvi_bedrooms.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.request

URL = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
       "Zip_zhvi_bdrmcnt_{n}_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'zillow_zhvi_zip_bedrooms.json')


def _fetch(n: int) -> tuple[dict[str, int], str]:
    url = URL.format(n=n)
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        text = resp.read().decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(text)))
    date_cols = sorted(k for k in rows[0] if len(k) == 10 and k[4] == '-' and k[7] == '-')
    latest = date_cols[-1]
    out: dict[str, int] = {}
    for row in rows:
        z = str(row.get('RegionName', '')).zfill(5)
        raw = (row.get(latest) or '').strip()
        if z == '00000' or not raw:
            continue
        try:
            out[z] = int(float(raw))
        except ValueError:
            continue
    return out, latest


def main() -> None:
    bedrooms: dict[str, dict[str, int]] = {}
    as_of = None
    for n in range(1, 6):
        vals, latest = _fetch(n)
        bedrooms[str(n)] = vals
        as_of = max(as_of or latest, latest)
        print(f"  {n}-bed: {len(vals)} ZIPs, latest column {latest}")
    payload = {
        "as_of": as_of,
        "source": "Zillow Research ZHVI by bedroom count, ZIP, middle tier 0.33-0.67, SFR+condo, smoothed seasonally adjusted",
        "bedrooms": bedrooms,
    }
    with open(OUT_PATH, 'w') as f:
        json.dump(payload, f, separators=(',', ':'))
    print(f"Wrote {os.path.abspath(OUT_PATH)}")


if __name__ == "__main__":
    main()
