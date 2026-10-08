#!/usr/bin/env python3
"""
How sensitive are happiness index results to the weights?

Offline: reads stored component scores (happiness_index_breakdown) from the catalog JSONL files. Draws
random weight sets by multiplying each base weight by a random factor (default +/-30%), renormalizes
over each place's available components exactly as the index does, and reports how much scores and
ranks move. Also compares the old v4 weights and equal weights.

  PYTHONPATH=. python3 scripts/catalog/happiness_weight_sensitivity.py [--draws 2000] [--spread 0.3]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
FILES = ["nyc", "la", "sf"]
BASE = {"social": .26, "safety": .18, "home_space": .14, "green": .12, "economic": .08,
        "active_outdoors": .07, "climate": .06, "commute": .05, "neighborhood": .04}
OLD_V4 = {"social": .30, "safety": .20, "commute": .15, "neighborhood": .05, "home_space": .10, "green": .12, "education": .08}
KEYS = list(BASE)


def load():
    names, mats = [], []
    for f in FILES:
        for line in (REPO / "data" / f"{f}_metro_place_catalog_scores_merged.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("success"):
                continue
            bd = r["score"].get("happiness_index_breakdown") or {}
            row = [bd.get(k) for k in KEYS]
            if all(v is None for v in row):
                continue
            names.append(f"{r['catalog']['name']} ({f.upper()})")
            mats.append([np.nan if v is None else float(v) for v in row])
    return names, np.array(mats)


def score(X, w):
    mask = ~np.isnan(X)
    Xz = np.where(mask, X, 0.0)
    W = mask * w
    return (Xz * W).sum(1) / W.sum(1)


def ranks(s):
    return (-s).argsort().argsort() + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--spread", type=float, default=0.3)
    args = ap.parse_args()
    names, X = load()
    n = len(names)
    base_w = np.array([BASE[k] for k in KEYS])
    base = score(X, base_w)
    rng = np.random.default_rng(7)
    S = np.empty((args.draws, n))
    for i in range(args.draws):
        w = base_w * rng.uniform(1 - args.spread, 1 + args.spread, len(KEYS))
        S[i] = score(X, w)
    sd = S.std(0)
    lo, hi = np.percentile(S, [5, 95], axis=0)
    R = np.array([ranks(s) for s in S])
    rank_base = ranks(base)
    print(f"{n} places, {args.draws} draws, each weight varied by +/-{args.spread:.0%}")
    print(f"Score spread across draws: median SD {np.median(sd):.2f} points, 95th percentile SD {np.percentile(sd,95):.2f}; "
          f"median 90% band width {np.median(hi-lo):.1f} points, max {np.max(hi-lo):.1f}")
    print(f"Rank movement: median SD {np.median(R.std(0)):.1f} places, 95th percentile SD {np.percentile(R.std(0),95):.1f} (of {n})")
    idx = rng.choice(n, size=(20000, 2))
    idx = idx[idx[:, 0] != idx[:, 1]]
    a, b = idx[:, 0], idx[:, 1]
    gap = np.abs(base[a] - base[b])
    flip = np.array([(np.sign(S[:, i] - S[:, j]) != np.sign(base[i] - base[j])).mean() for i, j in zip(a[:4000], b[:4000])])
    g = gap[:4000]
    print("\nHow often does a pair of places swap order when weights change?")
    for lo_, hi_ in [(0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 100)]:
        m = (g >= lo_) & (g < hi_)
        if m.sum():
            print(f"  base gap {lo_:>2}-{hi_:<3} points: swaps in {flip[m].mean():5.1%} of draws (n={m.sum()} pairs)")
    # smallest gap where a swap is rare
    for thr in (0.05, 0.10):
        for gp in np.arange(0.5, 12, 0.5):
            m = (g >= gp) & (g < gp + 0.5)
            if m.sum() > 20 and flip[m].mean() < thr:
                print(f"  swaps drop below {thr:.0%} once the gap reaches about {gp:.1f} points"); break
    top_base = set(np.argsort(-base)[:20])
    topfreq = (R <= 20).mean(0)
    print(f"\nTop 20: {sum(topfreq[list(top_base)] >= 0.9)} of the baseline top 20 stay in the top 20 in at least 90% of draws")
    print("Least stable in top 20:", ", ".join(f"{names[i]} ({topfreq[i]:.0%})" for i in sorted(top_base, key=lambda i: topfreq[i])[:5]))
    def spearman(a_, b_):
        ra, rb = ranks(a_), ranks(b_)
        return float(np.corrcoef(ra, rb)[0, 1])
    eq = score(X, np.ones(len(KEYS)))
    v4 = np.array([OLD_V4.get(k, 0.0) for k in KEYS]); v4 = np.where(v4 == 0, 0, v4)
    print("\nRank correlation with the current weights:")
    print(f"  equal weights: {spearman(base, eq):.3f}")
    print(f"  old v4 weights (education missing here): {spearman(base, score(X, v4 + 1e-9)):.3f}")
    per = []
    for j, k in enumerate(KEYS):
        w = base_w.copy(); w[j] *= 1.3; up = score(X, w); w[j] = base_w[j] * 0.7; dn = score(X, w)
        per.append((spearman(up, dn), k, np.abs(up - dn).mean()))
    print("\nWhich single weight matters most (+/-30% on one weight at a time):")
    for rho, k, d in sorted(per):
        print(f"  {k:<16} mean score swing {d:.2f} points, rank correlation between low and high {rho:.3f}")


if __name__ == "__main__":
    main()
