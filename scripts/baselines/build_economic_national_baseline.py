#!/usr/bin/env python3
"""
Build the national economic baseline used by pillars/economic_opportunity.py.

Pulls every US metropolitan and micropolitan area (CBSA) in a few wildcard Census API calls:
  ACS 2022 profile DP03 (employment, industry shares) and B01001 (population),
  Census BDS 2022 (establishments, entry, exit),
  Census County Business Patterns 2022 and 2023 (paid employment level and growth),
plus the BLS OEWS wage file (data/oews_metro_wage_distribution.json, metro areas only; see
build_oews_metro_wages.py). Metrics are computed exactly as the pillar computes them, then a
population-weighted mean and standard deviation (weights: ACS 2022 population) is stored under
baselines["all"]["all"] in data/economic_baselines.json. The older division x area-type cells are left
untouched (the job-category overlays still use them). Per-area metrics go to
data/economic_area_metrics_national.json for the offline catalog recompute.

  cd /path/to/home-fit
  PYTHONPATH=. python3 scripts/baselines/build_economic_national_baseline.py            # dry run, prints only
  PYTHONPATH=. python3 scripts/baselines/build_economic_national_baseline.py --write

Supersedes scripts/baselines/build_economic_baselines.py, which imports a module that does not exist.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_sources.economic_security_data import compute_anchored_vs_cyclical_balance, compute_industry_hhi  # noqa: E402

GEO = "metropolitan statistical area/micropolitan statistical area"
WILDCARD = f"{GEO}:*"
ACS_YEAR, BDS_YEAR, CBP_BASE_YEAR, CBP_LATEST_YEAR = 2022, 2022, 2022, 2023
INDUSTRY_VARS = {
    "ag_mining": "DP03_0033PE", "construction": "DP03_0034PE", "manufacturing": "DP03_0035PE",
    "wholesale": "DP03_0036PE", "retail": "DP03_0037PE", "transport_util": "DP03_0038PE",
    "information": "DP03_0039PE", "finance_realestate": "DP03_0040PE", "prof_services": "DP03_0041PE",
    "educ_health": "DP03_0042PE", "leisure_hospitality": "DP03_0043PE", "other_services": "DP03_0044PE",
    "public_admin": "DP03_0045PE",
}
METRICS = [
    "unemployment_rate", "emp_pop_ratio", "estabs_per_1k", "net_estab_entry_per_1k", "industry_hhi",
    "anchored_balance", "wage_p25_annual", "wage_p75_annual", "qcew_employment_per_1k",
    "qcew_employment_growth_pct", "log10_employment", "log10_establishments",
]


def _get(url: str, params: dict, key: str) -> list:
    r = requests.get(url, params={**params, "key": key}, timeout=120)
    r.raise_for_status()
    rows = r.json()
    head = rows[0]
    return [dict(zip(head, row)) for row in rows[1:]]


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > -1e6 else None  # Census uses large negative sentinels for missing


def build(key: str, oews: dict) -> dict:
    dp_vars = ["DP03_0001E", "DP03_0004E", "DP03_0009PE", *INDUSTRY_VARS.values()]
    dp = _get(f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5/profile", {"get": "NAME," + ",".join(dp_vars), "for": WILDCARD}, key)
    pop = {r[GEO]: _f(r["B01001_001E"]) for r in _get(f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5", {"get": "NAME,B01001_001E", "for": WILDCARD}, key)}
    bds = {r[GEO]: r for r in _get("https://api.census.gov/data/timeseries/bds", {"get": "NAME,ESTAB,ESTABS_ENTRY,ESTABS_EXIT", "YEAR": str(BDS_YEAR), "NAICS": "00", "for": WILDCARD}, key)}
    cbp = {y: {r[GEO]: _f(r["EMP"]) for r in _get(f"https://api.census.gov/data/{y}/cbp", {"get": "NAME,EMP", "NAICS2017": "00", "for": WILDCARD}, key)} for y in (CBP_BASE_YEAR, CBP_LATEST_YEAR)}
    areas = {}
    for r in dp:
        code = r[GEO]
        p, b = pop.get(code), bds.get(code)
        p16, emp = _f(r["DP03_0001E"]), _f(r["DP03_0004E"])
        if not p or p <= 0 or not b or not p16 or emp is None:
            continue
        shares = {k: _f(r[v]) for k, v in INDUSTRY_VARS.items()}
        estab, entry, exit_ = _f(b["ESTAB"]), _f(b["ESTABS_ENTRY"]), _f(b["ESTABS_EXIT"])
        m = {
            "unemployment_rate": _f(r["DP03_0009PE"]),
            "emp_pop_ratio": 100.0 * emp / p16,
            "industry_hhi": compute_industry_hhi(shares),
            "anchored_balance": compute_anchored_vs_cyclical_balance(shares),
        }
        if estab is not None and estab >= 0:
            m["estabs_per_1k"] = estab / p * 1000.0
            m["log10_establishments"] = math.log10(estab + 1)
        if entry is not None and exit_ is not None:
            m["net_estab_entry_per_1k"] = (entry - exit_) / p * 1000.0
        e0, e1 = cbp[CBP_BASE_YEAR].get(code), cbp[CBP_LATEST_YEAR].get(code)
        if e0 is not None and e0 >= 0:
            m["qcew_employment_per_1k"] = e0 / p * 1000.0
            m["log10_employment"] = math.log10(e0 + 1)
            if e0 > 0 and e1 is not None and e1 > 0:
                m["qcew_employment_growth_pct"] = 100.0 * (e1 / e0 - 1.0)
        o = oews.get(code)
        if o:
            if o.get("wage_p25_annual") is not None:
                m["wage_p25_annual"] = float(o["wage_p25_annual"])
            if o.get("wage_p75_annual") is not None:
                m["wage_p75_annual"] = float(o["wage_p75_annual"])
        areas[code] = {"name": r["NAME"], "population": p, **{k: v for k, v in m.items() if v is not None}}
    return areas


def baseline(areas: dict) -> dict:
    out = {}
    for m in METRICS:
        pts = [(a[m], a["population"]) for a in areas.values() if m in a]
        w = sum(p for _, p in pts)
        mean = sum(v * p for v, p in pts) / w
        std = math.sqrt(sum(p * (v - mean) ** 2 for v, p in pts) / w)
        out[m] = {"mean": mean, "std": std, "n": len(pts)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--oews", default=str(ROOT / "data" / "oews_metro_wage_distribution.json"))
    a = ap.parse_args()
    key = os.getenv("CENSUS_API_KEY")
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            key = os.getenv("CENSUS_API_KEY")
        except ImportError:
            pass
    if not key:
        sys.exit("CENSUS_API_KEY is not set")
    oews = json.loads(Path(a.oews).read_text()) if Path(a.oews).is_file() else {}
    if not oews:
        print("WARNING: no OEWS wage file; wage baselines will be empty", file=sys.stderr)
    areas = build(key, oews)
    base = baseline(areas)
    print(f"{len(areas)} areas")
    for m, s in base.items():
        print(f"  {m:28s} n={s['n']:4d} mean={s['mean']:12.4f} std={s['std']:12.4f}")
    if not a.write:
        print("dry run: nothing written")
        return
    path = ROOT / "data" / "economic_baselines.json"
    cur = json.loads(path.read_text())
    cur["all"] = {
        "all": base,
        "_meta": {
            "description": "National baseline: population-weighted mean and std over all US metro and micro areas. "
                           "Sourced and reproducible, not validated against an outcome (see analysis/economic_national_baseline_estimate_2026-10-24.md).",
            "built_by": "scripts/baselines/build_economic_national_baseline.py",
            "sources": {"acs": f"ACS 5-year {ACS_YEAR} DP03 and B01001", "bds": f"Census BDS {BDS_YEAR}",
                        "cbp": f"Census County Business Patterns {CBP_BASE_YEAR} (level) and {CBP_LATEST_YEAR} (growth)",
                        "oews": "BLS OEWS May 2024 metro areas only (data/oews_metro_wage_distribution.json)"},
            "weighting": "ACS population",
        },
    }
    path.write_text(json.dumps(cur, indent=2, sort_keys=False))
    (ROOT / "data" / "economic_area_metrics_national.json").write_text(json.dumps(areas, indent=1))
    print("wrote data/economic_baselines.json (all/all) and data/economic_area_metrics_national.json")


if __name__ == "__main__":
    main()
