#!/usr/bin/env python3
"""
Build data/age_share_percentiles.json: the national distribution of each age cohort's share of residents, as 101 percentile
points (0 to 100), over US tracts with 500 or more residents. pillars/diversity.py reads it to turn a place's cohort share into
a percentile, and the catalog Life stage filter keeps places at or above a percentile cutoff.

Cohorts: children (under 18), working_age (18 to 64), older (65 and over), young_professionals (25 to 34, a subset of 18 to 64).
Input is data/tract_age_counts.parquet (scripts/catalog/build_tract_age_counts_offline.py, ACS 2022 5-year B01001).

  PYTHONPATH=. python3 scripts/baselines/build_age_share_percentiles.py            # check only, writes nothing
  PYTHONPATH=. python3 scripts/baselines/build_age_share_percentiles.py --write
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "age_share_percentiles.json"
MIN_RESIDENTS = 500
COHORTS = {"children": "youth", "working_age": "prime", "older": "seniors", "young_professionals": "age_25_34"}


def build():
    t = pq.read_table(REPO / "data" / "tract_age_counts.parquet").to_pydict()
    total = np.array(t["youth"], float) + np.array(t["prime"], float) + np.array(t["seniors"], float)
    keep = total >= MIN_RESIDENTS
    points = {}
    for name, col in COHORTS.items():
        if col not in t:
            print(f"skip {name}: column {col} missing (rebuild tract_age_counts.parquet first)")
            continue
        share = np.array(t[col], float)[keep] / total[keep] * 100
        points[name] = [round(float(x), 4) for x in np.percentile(share, range(101))]
    return {
        "source": "ACS 2022 5-year B01001, US tracts with 500+ residents",
        "n_tracts": int(keep.sum()),
        "percentile_points": points,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    new = build()
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    print("n_tracts", old.get("n_tracts"), "->", new["n_tracts"])
    for name, pts in new["percentile_points"].items():
        ref = (old.get("percentile_points") or {}).get(name)
        diff = f"max diff vs stored {max(abs(a_ - b_) for a_, b_ in zip(pts, ref)):.4f}" if ref else "new"
        print(f"{name}: p50 {pts[50]:.1f} p67 {pts[67]:.1f} p75 {pts[75]:.1f} ({diff})")
    if a.write:
        OUT.write_text(json.dumps(new))
        print("WROTE", OUT)


if __name__ == "__main__":
    main()
