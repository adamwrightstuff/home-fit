#!/usr/bin/env python3
"""
Build the metro cutoffs used by the status_signal class (Struggling / Working / Middle / Affluent / Elite).

For each metro, from ACS 5-year tract data (county list per CBSA from build_metro_baselines_from_cbsa):
  income_p80 / income_p90  household-weighted percentiles of tract median household income (B19013 x B11001)
  home_value_p90           owner-weighted 90th percentile of tract median home value (B25077 x B25003_002)
Also stores the national anchors used by the class rule: median household income (B19013, US) and the
HHS poverty guideline for a household of three.

Usage (project root):
  PYTHONPATH=. python3 scripts/baselines/build_class_cuts.py                      # all registered metros
  PYTHONPATH=. python3 scripts/baselines/build_class_cuts.py --only dallas_metro
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from data_sources.census_api import CENSUS_API_KEY
from scripts.baselines.build_metro_baselines_from_cbsa import CBSA_COUNTIES, CBSA_TO_KEY

BASELINES = Path(__file__).resolve().parents[2] / "data" / "status_signal_baselines.json"
ACS = "https://api.census.gov/data/2022/acs/acs5"
POVERTY_GUIDELINE_3P_2022 = 23030  # HHS 2022 guideline, 48 states + DC, household of three


def _pull(var_a: str, var_b: str, state: str, county: str) -> List[Tuple[float, float]]:
    r = requests.get(ACS, params={"get": f"{var_a},{var_b}", "for": "tract:*",
                                  "in": f"state:{state} county:{county}", "key": CENSUS_API_KEY}, timeout=30)
    r.raise_for_status()
    out = []
    for row in r.json()[1:]:
        try:
            v, w = float(row[0]), float(row[1])
        except (TypeError, ValueError):
            continue
        if v > 0 and w > 0:
            out.append((v, w))
    return out


def _weighted_pct(pts: List[Tuple[float, float]], p: float) -> float:
    pts = sorted(pts)
    total = sum(w for _, w in pts)
    acc = 0.0
    for v, w in pts:
        acc += w
        if acc / total >= p / 100.0:
            return v
    return pts[-1][0]


def build_metro(key: str) -> Dict:
    inc: List[Tuple[float, float]] = []
    hv: List[Tuple[float, float]] = []
    for cbsa, k in CBSA_TO_KEY.items():
        if k != key or cbsa not in CBSA_COUNTIES:
            continue
        for state, counties in CBSA_COUNTIES[cbsa].items():
            for county in counties:
                inc += _pull("B19013_001E", "B11001_001E", state, county)
                hv += _pull("B25077_001E", "B25003_002E", state, county)
                time.sleep(0.1)
    return {
        "income_p80": _weighted_pct(inc, 80),
        "income_p90": _weighted_pct(inc, 90),
        "home_value_p90": _weighted_pct(hv, 90),
        "tracts_income": len(inc),
        "tracts_home_value": len(hv),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    b = json.loads(BASELINES.read_text())
    r = requests.get(ACS, params={"get": "B19013_001E", "for": "us:1", "key": CENSUS_API_KEY}, timeout=30).json()
    b["class_national"] = {"median_household_income": float(r[1][0]),
                           "poverty_guideline_3p": POVERTY_GUIDELINE_3P_2022, "acs_year": 2022}
    cuts = b.setdefault("class_cuts", {})
    for key in sorted(set(CBSA_TO_KEY.values())):
        if args.only and key != args.only:
            continue
        print(f"=== {key}")
        cuts[key] = build_metro(key)
        print("   ", cuts[key])
    BASELINES.write_text(json.dumps(b, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
