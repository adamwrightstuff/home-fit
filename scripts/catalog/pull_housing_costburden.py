#!/usr/bin/env python3
"""
Pull ACS 2022 5-year housing cost burden by tract for every state in the housing pull (state-level calls, ~51).

Independent check on the housing score (DPv2 P7): the share of households paying 30 percent or more of income on
housing is a measured outcome, not the median-based ratio the score uses.
  B25070  gross rent as % of income (renters): 001 total, 007-010 are 30% and above, 011 not computed
  B25091  owner costs as % of income, units with a mortgage: 002 total, 008-011 are 30% and above, 012 not computed
The script stops if the bracket counts do not add up to the totals (guards against a wrong variable id).

  cd /Users/adamwright/Dev/home-fit && set -a && source .env && set +a && python3 scripts/catalog/pull_housing_costburden.py
"""
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PULL = ROOT / "data" / "census_pull_2026-10-28"
OUT = ROOT / "data" / "census_pull_costburden_2026-10-30"
KEY = os.environ.get("CENSUS_API_KEY")
if not KEY:
    sys.exit("CENSUS_API_KEY not set (source .env first)")
VARS = ([f"B25070_{i:03d}E" for i in range(1, 12)] + [f"B25091_{i:03d}E" for i in range(2, 13)])
OUT.mkdir(exist_ok=True)
states = sorted({re.search(r"housing_tract_(\d\d)_", p).group(1) for p in glob.glob(str(PULL / "housing_tract_*_0.json"))})
bad = total = 0
for st in states:
    f = OUT / f"costburden_tract_{st}.json"
    if f.exists():
        continue
    r = requests.get("https://api.census.gov/data/2022/acs/acs5",
                     params={"get": ",".join(VARS), "for": "tract:*", "in": f"state:{st}", "key": KEY}, timeout=120)
    if r.status_code != 200:
        sys.exit(f"state {st}: HTTP {r.status_code} {r.text[:200]}")
    d = r.json()
    h = d[0]
    for row in d[1:]:
        v = {c: float(x) if x not in (None, "") and float(x) > -1e8 else None for c, x in zip(h, row) if c.startswith("B")}
        a = [v[f"B25070_{i:03d}E"] for i in range(2, 12)]
        b = [v[f"B25091_{i:03d}E"] for i in range(3, 13)]
        if None in a or None in b or v["B25070_001E"] is None or v["B25091_002E"] is None:
            continue
        total += 1
        if abs(sum(a) - v["B25070_001E"]) > 1 or abs(sum(b) - v["B25091_002E"]) > 1:
            bad += 1
    f.write_text(json.dumps(d))
    time.sleep(0.3)
print(f"states {len(states)}; tracts checked {total}; bracket sums that do not match totals: {bad}")
if total and bad / total > 0.02:
    sys.exit("variable ids look wrong (more than 2% of tracts fail the bracket check); do not use this pull")
print("ok")
