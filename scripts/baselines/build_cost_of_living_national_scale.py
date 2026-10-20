#!/usr/bin/env python3
"""
Build the data behind pillars/cost_of_living.py.

1. Downloads BEA Regional Price Parities (metro MARPP, state SARPP) and writes
   data/cost_of_living_bea_goods_rpp.json (goods line, latest year).
2. Pulls the US median household income (the reference income) and, for every US place
   of 2,500+ people, its population and state; prices the reference household in each
   place with the pillar's own functions and writes population-weighted percentiles to
   data/cost_of_living_national_scale.json.

For the national distribution a place's goods price is its STATE goods RPP (places are
not mapped to metros here); the pillar uses the metro RPP when the metro is known.

Usage:  PYTHONPATH=. python3 scripts/baselines/build_cost_of_living_national_scale.py
Needs CENSUS_API_KEY.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from pillars import cost_of_living as col  # noqa: E402

DATA = os.path.join(ROOT, "data")
BEA = "https://apps.bea.gov/regional/zip/{}.zip"
ACS_YEAR = 2023
MIN_POP = 2500


def _read_bea(table: str, csv_name: str):
    raw = urllib.request.urlopen(BEA.format(table), timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(csv_name).decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    year = max(k for k in rows[0] if k.isdigit())
    return rows, year


def build_rpp() -> dict:
    out = {"msa": {}, "state": {}}
    msa_rows, year = _read_bea("MARPP", "MARPP_MSA_2008_2024.csv")
    for r in msa_rows:
        if (r.get("LineCode") or "").strip() == "2" and r[year].strip() not in ("", "(NA)"):
            code = r["GeoFIPS"].strip().strip('"')
            out["msa"][code] = {"name": r["GeoName"].strip(), "goods": float(r[year])}
    st_rows, st_year = _read_bea("SARPP", "SARPP_STATE_2008_2024.csv")
    for r in st_rows:
        if (r.get("LineCode") or "").strip() == "2" and r[st_year].strip() not in ("", "(NA)"):
            name = r["GeoName"].strip()
            if name != "United States":
                out["state"][name] = {"goods": float(r[st_year])}
    out["_meta"] = {
        "source": "BEA Regional Price Parities (MARPP metro, SARPP state), line 2: goods; US = 100",
        "year": int(year),
        "msas": len(out["msa"]),
        "states": len(out["state"]),
    }
    return out


def acs_places(key: str):
    states = json.load(urllib.request.urlopen(
        f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get=NAME&for=state:*&key={key}"))[1:]
    for name, fips in states:
        url = (f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get=NAME,B19013_001E,B01003_001E"
               f"&for=place:*&in=state:{fips}&key={key}")
        try:
            rows = json.load(urllib.request.urlopen(url, timeout=60))[1:]
        except Exception as e:
            print(f"skip {name}: {e}")
            continue
        for place_name, inc, pop, *_ in rows:
            try:
                inc, pop = float(inc), float(pop)
            except (TypeError, ValueError):
                continue
            if inc > 0 and pop >= MIN_POP:
                yield place_name.split(",")[0], name, inc, pop


def weighted_percentiles(values, weights, n=101):
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    out, cum, j = [], 0.0, 0
    for i in range(n):
        target = total * i / (n - 1)
        while j < len(pairs) - 1 and cum + pairs[j][1] < target:
            cum += pairs[j][1]
            j += 1
        out.append(pairs[j][0])
    return out


def main() -> None:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY not set")
    rpp = build_rpp()
    with open(os.path.join(DATA, "cost_of_living_bea_goods_rpp.json"), "w") as f:
        json.dump(rpp, f, indent=1)
    col._rpp.update(rpp)  # use the fresh table for the burdens below

    ref = float(json.load(urllib.request.urlopen(
        f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5?get=B19013_001E&for=us:1&key={key}"))[1][0])
    # Aggregate US places into (state, city-tax jurisdiction) groups weighted by population.
    # The pillar prices a household of ANY income in each group at runtime, so the national
    # reference distribution is income-aware.
    groups, skipped = {}, 0
    for place, state, _inc, pop in acs_places(key):
        g = rpp["state"].get(state, {}).get("goods")
        if g is None:
            skipped += 1
            continue
        city = re.sub(r" (city|town|village|CDP|borough|municipality|township)$", "", place)
        _, local_key = col.local_income_tax(city, state, 1.0, 0.0)
        k = (state, local_key)
        groups.setdefault(k, {"state": state, "local": local_key, "goods": g, "pop": 0.0})["pop"] += pop

    scale = {
        "_meta": {
            "description": "US places grouped by (state, city-tax jurisdiction) with population weights "
                           "and state goods RPP.  The pillar prices a household of any income in each "
                           "group and scores against the population-weighted 5th/95th percentile burden.",
            "places_used": sum(1 for _ in groups) and int(sum(g["pop"] for g in groups.values())),
            "groups": len(groups),
            "places_skipped_no_rpp": skipped,
            "min_population": MIN_POP,
            "reference_income": ref,
            "acs_year": ACS_YEAR,
            "grocery_spend_national": col.GROCERY_SPEND_NATIONAL,
            "goods_price_basis": "state goods RPP",
        },
        "groups": sorted(groups.values(), key=lambda g: (g["state"], g["local"] or "")),
    }
    with open(os.path.join(DATA, "cost_of_living_national_scale.json"), "w") as f:
        json.dump(scale, f, indent=1)
    print(json.dumps(scale["_meta"], indent=1))
    col._scale.clear(); col._scale.update(scale)
    for inc in (40000, ref, 150000, 300000):
        lo, hi = col.burden_anchors(inc)
        print(f"income {inc:>9,.0f}: burden p5 {lo:.3f}  p95 {hi:.3f}")


if __name__ == "__main__":
    main()
