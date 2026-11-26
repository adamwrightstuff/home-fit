#!/usr/bin/env python3
"""Build data/tract_age_counts.parquet (geoid, youth, prime, seniors, age_25_34) from the cached ACS 2022 state pull (B01001). Offline.
  PYTHONPATH=. python3 scripts/catalog/build_tract_age_counts_offline.py"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "catalog"))
import diversity_identify_geography_offline as D
import pyarrow as pa, pyarrow.parquet as pq
ids, Y, P, S, YP = [], [], [], [], []
for (kind, g), v in D.load().items():
    if kind != "tract": continue
    ids.append(g)
    # 25 to 34 (young professionals): male 25-29, 30-34 = B01001_011, 012; female = 035, 036. A subset of the 18-64 "prime" count.
    YP.append(int(sum(v.get(f"B01001_{j:03d}E", 0) for j in (11, 12, 35, 36))))
    Y.append(int(sum(v.get(f"B01001_{j:03d}E", 0) for j in list(range(3, 7)) + list(range(27, 31)))))
    P.append(int(sum(v.get(f"B01001_{j:03d}E", 0) for j in list(range(7, 20)) + list(range(31, 44)))))
    S.append(int(sum(v.get(f"B01001_{j:03d}E", 0) for j in list(range(20, 26)) + list(range(44, 50)))))
pq.write_table(pa.table({"geoid": ids, "youth": Y, "prime": P, "seniors": S, "age_25_34": YP}), REPO / "data" / "tract_age_counts.parquet")
print("tracts", len(ids))
