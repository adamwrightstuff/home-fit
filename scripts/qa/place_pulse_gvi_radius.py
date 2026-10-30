#!/usr/bin/env python3
"""
Which green view radius best tracks human ratings of street scenes?  LIVE (GEE only, no Overpass).  Uses the MIT
Place Pulse US images already in analysis/place_pulse/us_images_all.csv (votes >= 8): for a random sample it reads the
pillar's green view (semantic_gvi from get_urban_greenness_gee) at 400, 800, 1,200 and 2,000 m around each photo
point and correlates each radius with the human "beauty" score (Spearman), pooled and within city.  Resumable.

  measure:  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_gvi_radius.py measure 300 3 2>&1 | grep -E "^(M|DONE)"
  shift:    cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_gvi_radius.py shift 100 3 2>&1 | grep -E "^(M|DONE)"
  shiftreport: cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_gvi_radius.py shiftreport 2>&1 | grep "^  "
  report:   cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_gvi_radius.py report
"""
import json, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CSV = ROOT / "analysis" / "place_pulse" / "us_images_all.csv"
OUT = ROOT / "analysis" / "place_pulse" / "gvi_radius_measured.jsonl"
RADII = (400, 800, 1200, 2000)
SHIFT_OUT = ROOT / "analysis" / "place_pulse" / "gvi_radius_shift.jsonl"
SHIFT_RADII = (400, 800, 1200)
SHIFT_M = 250


def measure(n, threads):
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    from data_sources.gee_api import get_urban_greenness_gee
    imgs = pd.read_csv(CSV); imgs = imgs[imgs.votes >= 8].reset_index(drop=True)
    idx = list(range(len(imgs))); random.Random(7).shuffle(idx); idx = idx[:n]
    done = {json.loads(l)["img"] for l in open(OUT)} if OUT.exists() else set()
    todo = [imgs.iloc[i] for i in idx if imgs.iloc[i].img not in done]
    print(f"M {len(done)} measured, {len(todo)} to do", flush=True)

    def work(r):
        o = {"img": r.img, "city": r.city, "score": float(r.score)}
        for rad in RADII:
            try:
                g = get_urban_greenness_gee(float(r.lat), float(r.lon), radius_m=rad) or {}
                o[f"gvi_{rad}"] = g.get("semantic_gvi")
            except Exception:
                o[f"gvi_{rad}"] = None
        return o

    t0 = time.time()
    with ThreadPoolExecutor(threads) as ex, open(OUT, "a") as f:
        for k, fu in enumerate(as_completed([ex.submit(work, r) for r in todo]), 1):
            f.write(json.dumps(fu.result()) + "\n"); f.flush()
            if k % 10 == 0 or k == len(todo):
                print(f"M {k}/{len(todo)} done, {(time.time() - t0) / k:.1f}s per point", flush=True)
    print("DONE")


def sp(a, b):
    """Spearman rank correlation (Pearson on ranks; avoids needing scipy)."""
    return a.rank().corr(b.rank())


def report():
    d = pd.DataFrame([json.loads(l) for l in open(OUT)])
    cols = [f"gvi_{r}" for r in RADII]
    d = d.dropna(subset=cols + ["score"])
    print(f"n = {len(d)} photo points with all four radii read")
    for c in cols:
        pooled = sp(d[c], d["score"])
        within = d.groupby("city").apply(lambda g: sp(g[c], g["score"]) if len(g) >= 15 else float("nan"), include_groups=False)
        print(f"  {c.replace('gvi_', '')} m: pooled Spearman {pooled:.3f} | mean within-city {within.mean():.3f} ({within.notna().sum()} cities with 15+ points)")
    # bootstrap: is the best radius distinguishable from 1,200 m?
    import numpy as np
    rng = np.random.default_rng(3); best = max(cols, key=lambda c: sp(d[c], d["score"]))
    diffs = []
    for _ in range(500):
        s = d.sample(len(d), replace=True, random_state=int(rng.integers(1e9)))
        diffs.append(sp(s[best], s["score"]) - sp(s["gvi_1200"], s["score"]))
    print(f"best radius {best}; its gain over 1,200 m: {np.mean(diffs):+.3f} (95% interval {np.percentile(diffs, 2.5):+.3f} to {np.percentile(diffs, 97.5):+.3f})")


def shift(n, threads):
    """Pin-shift stability of green view by radius: re-read the first n measured photo points with the pin moved
    250 m north and compare with the base reads already in OUT.  LIVE (GEE only)."""
    import math
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    from data_sources.gee_api import get_urban_greenness_gee
    imgs = pd.read_csv(CSV).drop_duplicates("img").set_index("img")
    base = [json.loads(l) for l in open(OUT)]
    base = [b for b in base if all(b.get(f"gvi_{r}") is not None for r in SHIFT_RADII)][:n]
    done = {json.loads(l)["img"] for l in open(SHIFT_OUT)} if SHIFT_OUT.exists() else set()
    todo = [b for b in base if b["img"] not in done]
    print(f"M {len(done)} shifted, {len(todo)} to do", flush=True)

    def work(b):
        r = imgs.loc[b["img"]]
        la = float(r.lat) + SHIFT_M / 111320.0
        o = {"img": b["img"], "city": b["city"]}
        for rad in SHIFT_RADII:
            o[f"base_{rad}"] = b[f"gvi_{rad}"]
            try:
                g = get_urban_greenness_gee(la, float(r.lon), radius_m=rad) or {}
                o[f"shift_{rad}"] = g.get("semantic_gvi")
            except Exception:
                o[f"shift_{rad}"] = None
        return o

    t0 = time.time()
    with ThreadPoolExecutor(threads) as ex, open(SHIFT_OUT, "a") as f:
        for k, fu in enumerate(as_completed([ex.submit(work, b) for b in todo]), 1):
            f.write(json.dumps(fu.result()) + "\n"); f.flush()
            if k % 10 == 0 or k == len(todo):
                print(f"M {k}/{len(todo)} done, {(time.time() - t0) / k:.1f}s per point", flush=True)
    print("DONE")


def shift_report():
    """Per radius: how much green view moves when the pin moves 250 m.  Pillar points are approximate: the streets
    part is 0.7 x the stronger of green view and canopy and the blend gives streets half the weight, so a green
    view score change counts for at most about 0.35 of a pillar point."""
    import numpy as np
    from pillars.natural_beauty import _v9_score_gvi
    d = pd.DataFrame([json.loads(l) for l in open(SHIFT_OUT)])
    for r in SHIFT_RADII:
        x = d.dropna(subset=[f"base_{r}", f"shift_{r}"])
        dg = (x[f"shift_{r}"] - x[f"base_{r}"]).abs()
        ds = pd.Series([abs(_v9_score_gvi(a) - _v9_score_gvi(b)) for a, b in zip(x[f"shift_{r}"], x[f"base_{r}"])])
        print(f"  {r} m: n={len(x)} | green view change median {dg.median():.1f} p95 {np.percentile(dg, 95):.1f} pct points"
              f" | green view score change median {ds.median():.1f} p95 {np.percentile(ds, 95):.1f}"
              f" | approx pillar points p95 {0.35 * np.percentile(ds, 95):.1f} (gate 5)")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "measure":
        measure(int(sys.argv[2]), int(sys.argv[3]))
    elif len(sys.argv) >= 4 and sys.argv[1] == "shift":
        shift(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1:2] == ["shiftreport"]:
        shift_report()
    elif sys.argv[1:2] == ["report"]:
        report()
    else:
        sys.exit(__doc__)
