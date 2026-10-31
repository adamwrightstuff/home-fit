#!/usr/bin/env python3
"""
Independent validation of the housing score (DPv2 P7): does it order tracts the way measured housing cost burden does?

For the 495 tract-level catalog places (pin tract from the pooled-housing run), compare the single-tract housing score
with the share of households NOT paying 30 percent or more of income on housing (ACS 2022, B25070 renters plus B25091
owners with a mortgage). Both come from the ACS, but the burden share is a measured outcome rather than the ratio of
two medians the score is built from. Reports Spearman overall and within metro, and the score by burden quintile.
No pass threshold is set here: any threshold is the owner's judgment and is recorded with the result.

  cd /Users/adamwright/Dev/home-fit && python3 scripts/catalog/validate_housing_costburden.py
"""
import glob
import json
import statistics as st
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
rows = {}
for f in glob.glob(str(ROOT / "data" / "census_pull_costburden_2026-10-30" / "costburden_tract_*.json")):
    d = json.load(open(f))
    h = d[0]
    for r in d[1:]:
        v = {c: (float(x) if x not in (None, "") and float(x) > -1e8 else None) for c, x in zip(h, r) if c.startswith("B")}
        a = [v[f"B25070_{i:03d}E"] for i in range(7, 11)]
        den_r = (v["B25070_001E"] or 0) - (v["B25070_011E"] or 0)
        b = [v[f"B25091_{i:03d}E"] for i in range(8, 12)]
        den_o = (v["B25091_002E"] or 0) - (v["B25091_012E"] or 0)
        if None in a or None in b or den_r + den_o < 50:
            continue
        rows[r[h.index("state")] + r[h.index("county")] + r[h.index("tract")]] = 1 - (sum(a) + sum(b)) / (den_r + den_o)
places = [json.loads(l) for l in open(ROOT / "analysis" / "audit_housing_d14_exact_places.jsonl") if l.strip()]
df = pd.DataFrame([dict(metro=p["metro"], name=p["name"], score=p["rebuilt"], pooled=p["pooled_700"], afford=rows.get(p["pin_tract"]))
                   for p in places]).dropna()
print(f"places with a burden figure: {len(df)} of {len(places)}")
rho = df["score"].rank().corr(df["afford"].rank())
print(f"Spearman, housing score vs share not cost-burdened, all places: {rho:.3f}")
per = {m: g["score"].rank().corr(g["afford"].rank()) for m, g in df.groupby("metro") if len(g) >= 15}
print("within metro (n>=15): median %.3f min %.3f (%s) max %.3f (%s)" % (
    st.median(per.values()), min(per.values()), min(per, key=per.get), max(per.values()), max(per, key=per.get)))
df["q"] = pd.qcut(df["afford"], 5, labels=False, duplicates="drop")
print("housing score by quintile of share not cost-burdened (0 = most burdened):")
print(df.groupby("q")["score"].agg(["count", "mean"]).round(1).to_string())
print("largest disagreements (high score, high burden / low score, low burden):")
df["gap"] = df["score"].rank(pct=True) - df["afford"].rank(pct=True)
for lab, sub in (("score too high", df.nlargest(5, "gap")), ("score too low", df.nsmallest(5, "gap"))):
    print(" ", lab, "; ".join(f"{r.metro} {r.name} score {r.score:.0f} not-burdened {r.afford:.0%}" for r in sub.itertuples()))
