#!/usr/bin/env python3
"""
Does canopy measured only along streets track human ratings better than canopy over the whole circle?  (BACKLOG.md: a
tree-lined rowhouse block scores near zero on whole-circle canopy.)  LIVE (GEE only, no Overpass).  Uses the MIT Place
Pulse US points already measured in analysis/place_pulse/gvi_radius_measured.jsonl.  For each point it reads NLCD Tree
Canopy Cover (the pillar's primary canopy source) as the mean over (a) the whole circle and (b) the street corridor:
TIGER local and secondary roads (MTFCC S1200, S1400) inside the circle, buffered by a corridor half-width.  The half-width
has no source, so 10, 20 and 30 m are all read and reported.  Compares Spearman with the human beauty score, pooled and
within city.  Changes no score.  Resumable.

  measure: cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_street_canopy.py measure 3 2>&1 | grep -E "^(M|DONE)"
  report:  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/qa/place_pulse_street_canopy.py report
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
CSV = ROOT / "analysis" / "place_pulse" / "us_images_all.csv"
BASE = ROOT / "analysis" / "place_pulse" / "gvi_radius_measured.jsonl"
OUT = ROOT / "analysis" / "place_pulse" / "street_canopy.jsonl"
RADII = (400, 1000)
WIDTHS = (10, 20, 30)


def read_point(lat, lon):
    import ee
    pt = ee.Geometry.Point([lon, lat])
    # same selection as the pillar (gee_api._get_nlcd_tcc_canopy): filter by year and bounds, take the regional tile
    tcc = (ee.ImageCollection("USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5").filter(ee.Filter.eq("year", 2023))
           .filterBounds(pt.buffer(max(RADII))).first().select("NLCD_Percent_Tree_Canopy_Cover"))
    roads = ee.FeatureCollection("TIGER/2016/Roads").filter(ee.Filter.inList("mtfcc", ["S1200", "S1400"]))
    o = {}
    for rad in RADII:
        circle = pt.buffer(rad)
        o[f"whole_{rad}"] = tcc.reduceRegion(ee.Reducer.mean(), circle, 30, maxPixels=1e8).values().get(0).getInfo()
        near = roads.filterBounds(circle)
        for w in WIDTHS:
            corridor = near.geometry().buffer(w).intersection(circle, 1)
            v = tcc.reduceRegion(ee.Reducer.mean(), corridor, 30, maxPixels=1e8).values().get(0).getInfo()
            o[f"street{w}_{rad}"] = v
    return o


def measure(threads):
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    from data_sources import gee_api  # initializes Earth Engine
    imgs = pd.read_csv(CSV).drop_duplicates("img").set_index("img")
    base = [json.loads(l) for l in open(BASE)]
    done = {json.loads(l)["img"] for l in open(OUT)} if OUT.exists() else set()
    todo = [b for b in base if b["img"] not in done]
    print(f"M {len(done)} read, {len(todo)} to do", flush=True)

    def work(b):
        r = imgs.loc[b["img"]]; o = {"img": b["img"]}
        try:
            o.update(read_point(float(r.lat), float(r.lon)))
        except Exception as e:
            o["error"] = str(e)[:120]
        return o

    t0 = time.time()
    with ThreadPoolExecutor(threads) as ex, open(OUT, "a") as f:
        for k, fu in enumerate(as_completed([ex.submit(work, b) for b in todo]), 1):
            f.write(json.dumps(fu.result()) + "\n"); f.flush()
            if k % 10 == 0 or k == len(todo):
                print(f"M {k}/{len(todo)} done, {(time.time() - t0) / k:.1f}s per point", flush=True)
    print("DONE")


def sp(a, b):
    return a.rank().corr(b.rank())


def report():
    import numpy as np
    d = pd.DataFrame([json.loads(l) for l in open(BASE)]).merge(pd.DataFrame([json.loads(l) for l in open(OUT)]), on="img")
    cols = [f"whole_{r}" for r in RADII] + [f"street{w}_{r}" for r in RADII for w in WIDTHS] + ["gvi_800"]
    d = d.dropna(subset=cols + ["score"])
    print(f"n = {len(d)} points with every read")
    dense = ["New York", "Philadelphia", "Boston", "Chicago", "Washington DC"]
    rng = np.random.default_rng(3)
    for c in cols:
        pooled = sp(d[c], d["score"])
        within = d.groupby("city").apply(lambda g: sp(g[c], g["score"]) if len(g) >= 15 else float("nan"), include_groups=False)
        x = d[d.city.isin(dense)]
        print(f"  {c:14s} pooled {pooled:.3f} | mean within-city {within.mean():.3f} ({within.notna().sum()} cities) | older dense cities (n={len(x)}) {sp(x[c], x['score']):.3f}")
    for rad in RADII:
        for w in WIDTHS:
            c, b = f"street{w}_{rad}", f"whole_{rad}"
            diffs = []
            for _ in range(500):
                s = d.sample(len(d), replace=True, random_state=int(rng.integers(1e9)))
                diffs.append(sp(s[c], s["score"]) - sp(s[b], s["score"]))
            print(f"  {c} minus {b}: {np.mean(diffs):+.3f} (95% interval {np.percentile(diffs, 2.5):+.3f} to {np.percentile(diffs, 97.5):+.3f})")
    print(f"  correlation of street20_400 with gvi_800 (is it new information?): {sp(d['street20_400'], d['gvi_800']):.3f}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "measure":
        measure(int(sys.argv[2]))
    elif sys.argv[1:2] == ["report"]:
        report()
    else:
        sys.exit(__doc__)
