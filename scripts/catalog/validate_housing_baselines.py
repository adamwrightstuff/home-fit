#!/usr/bin/env python3
"""
Benchmark for the cost-burden validation: does the full housing score beat simple baselines?

Same test as validate_housing_costburden.py (Spearman against the share of households not paying 30 percent or more
of income on housing, 495 pin tracts), run for the score and for single-input baselines built from the same tract
medians: lower price-to-income, lower rent-to-income, higher income alone, and higher median rooms alone.

  python3 scripts/catalog/validate_housing_baselines.py [repo_root]
"""
import glob
import json
import statistics as st
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]


def num(x):
    try:
        v = float(x)
        return None if v < -1e8 else v
    except (TypeError, ValueError):
        return None


burden = {}
for f in glob.glob(str(ROOT / "data" / "census_pull_costburden_2026-10-30" / "costburden_tract_*.json")):
    d = json.load(open(f)); h = d[0]
    for r in d[1:]:
        v = {c: num(x) for c, x in zip(h, r) if c.startswith("B")}
        a = [v[f"B25070_{i:03d}E"] for i in range(7, 11)]
        b = [v[f"B25091_{i:03d}E"] for i in range(8, 12)]
        den = (v["B25070_001E"] or 0) - (v["B25070_011E"] or 0) + (v["B25091_002E"] or 0) - (v["B25091_012E"] or 0)
        if None in a or None in b or den < 50:
            continue
        burden[r[h.index("state")] + r[h.index("county")] + r[h.index("tract")]] = 1 - (sum(a) + sum(b)) / den
tr = {}
for f in glob.glob(str(ROOT / "data" / "census_pull_2026-10-28" / "housing_tract_*_0.json")):
    d = json.load(open(f)); h = d[0]
    for r in d[1:]:
        tr[r[h.index("state")] + r[h.index("county")] + r[h.index("tract")]] = {c: num(x) for c, x in zip(h, r) if c.startswith("B")}
rows = []
for l in open(ROOT / "analysis" / "audit_housing_d14_exact_places.jsonl"):
    p = json.loads(l)
    t = tr.get(p["pin_tract"]) or {}
    inc, val, rent, rooms = t.get("B19013_001E"), t.get("B25077_001E"), t.get("B25064_001E"), t.get("B25018_001E")
    rows.append(dict(metro=p["metro"], afford=burden.get(p["pin_tract"]), score=p["rebuilt"],
                     low_price_to_income=(-val / inc) if val and inc else None,
                     low_rent_to_income=(-rent * 12 / inc) if rent and inc else None,
                     high_income=inc, high_rooms=rooms))
df = pd.DataFrame(rows).dropna(subset=["afford", "score"])
print(f"places: {len(df)}")
print(f"{'measure':24s} {'n':>4s} {'all places':>10s} {'within-metro median':>20s}")
for col in ("score", "low_price_to_income", "low_rent_to_income", "high_income", "high_rooms"):
    s = df.dropna(subset=[col])
    per = [g[col].rank().corr(g["afford"].rank()) for _, g in s.groupby("metro") if len(g) >= 15]
    print(f"{col:24s} {len(s):4d} {s[col].rank().corr(s['afford'].rank()):10.3f} {st.median(per):20.3f}")
