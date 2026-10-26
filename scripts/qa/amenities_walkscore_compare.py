#!/usr/bin/env python3
"""
Validation helper (DPv2 P7): compare our amenities score with hand-looked-up Walk Scores.

Fill the walk_score column of analysis/amenities_walkscore_sample_2026-10-26.csv (lat/lon are the pins; look each up at
walkscore.com), then run:
  PYTHONPATH=. python3 scripts/qa/amenities_walkscore_compare.py [csv]
Prints Spearman and Pearson correlation, the mean gap, and the places that disagree most. Walk Score is built from similar
amenity counts, so agreement supports the access construct but is not independent validation.
"""
from __future__ import annotations

import csv
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "analysis" / "amenities_walkscore_sample_2026-10-26.csv"


def rank(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    return sum((p - ma) * (q - mb) for p, q in zip(a, b)) / math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    rows = [r for r in csv.DictReader(open(path)) if (r.get("walk_score") or "").strip()]
    if len(rows) < 15:
        sys.exit(f"need at least 15 filled walk_score values, found {len(rows)}")
    ours = [float(r["our_score"]) for r in rows]
    ws = [float(r["walk_score"]) for r in rows]
    print(f"n={len(rows)}  Spearman {corr(rank(ours), rank(ws)):.2f}  Pearson {corr(ours, ws):.2f}  mean gap (ours minus Walk Score) {st.mean(o - w for o, w in zip(ours, ws)):+.1f}")
    for r, o, w in sorted(zip(rows, ours, ws), key=lambda t: -abs(t[1] - t[2]))[:8]:
        print(f"  {r['metro']:12s} {r['name']:26s} ours {o:5.1f}  Walk Score {w:5.1f}")


if __name__ == "__main__":
    main()
