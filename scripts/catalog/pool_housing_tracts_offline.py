#!/usr/bin/env python3
"""
Side-by-side test of a pooled housing score (read-only; writes only analysis/housing_pooled_cache_run.jsonl).

For each place whose stored housing data came from one tract, pool the tracts whose centers fall within a radius
of the pin (plus the pin's own tract) and score the pooled inputs with the pillar's own functions. Tract inputs
come from the cached state pull (scripts/catalog/pull_census_state_tables.py); pooled values are occupied-unit
weighted means of tract medians, which is an approximation of a pooled median (no pooled median is available).
Zillow value override and the metro adjustment are NOT applied (same for the single-tract baseline), so only the
difference between the two is meaningful.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/pool_housing_tracts_offline.py
  add --shift-sample 30 to run the pin-shift test (240 free Census geocoder calls)
"""
from __future__ import annotations

import argparse, glob, json, math, os, random, statistics as S, sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.environ.pop("CENSUS_API_KEY", None)
from pillars.housing_value import _score_local_affordability, _score_rent_affordability, _score_space, _score_value_efficiency  # noqa: E402

PULL = REPO / "data" / "census_pull_2026-10-28"
BAD = -1e8


def num(x):
    try:
        v = float(x)
        return None if v < BAD else v
    except (TypeError, ValueError):
        return None


def load_tracts():
    rows = {}
    for f in glob.glob(str(PULL / "housing_tract_*_0.json")) + glob.glob(str(PULL / "housing2_tract_*_0.json")):
        d = json.load(open(f)); h = d[0]
        for r in d[1:]:
            g = r[h.index("state")] + r[h.index("county")] + r[h.index("tract")]
            t = rows.setdefault(g, {})
            for i, c in enumerate(h):
                if c[0] == "B":
                    t[c] = num(r[i])
    return rows


def score(inc, val, rent, rooms, renter_pct):
    """Mirror of get_housing_value_score's branches (no Zillow, no metro). None if not scoreable."""
    if not inc or inc <= 0:
        return None
    has_rent = rent is not None and rent > 0
    has_val = val is not None and val > 0
    if has_val and has_rent and renter_pct is not None:
        o = 1 - renter_pct
        oa, ra = _score_local_affordability(val, inc), _score_rent_affordability(rent, inc)
        aff = o * oa + renter_pct * ra if oa is not None and ra is not None else None
        sp = _score_space(rooms); ef = _score_value_efficiency(val, rooms, None)
        ef = ef * o if ef is not None else None
    elif not has_val and has_rent:
        aff = _score_rent_affordability(rent, inc); sp = _score_space(rooms); ef = 0.0 if sp is not None else None
    else:
        aff = _score_local_affordability(val, inc); sp = _score_space(rooms); ef = _score_value_efficiency(val, rooms, None)
    comp = {"a": (aff, 50.0), "s": (sp, 30.0), "e": (ef, 20.0)}
    pr = {k: v for k, v in comp.items() if v[0] is not None}
    if "a" not in pr or len(pr) < 2:
        return None
    return sum(v[0] for v in pr.values()) * 100.0 / sum(v[1] for v in pr.values())


def tract_inputs(t):
    occ = t.get("B25003_001E"); ren = t.get("B25003_003E")
    return (t.get("B19013_001E"), t.get("B25077_001E"), t.get("B25064_001E"), t.get("B25018_001E"),
            (ren / occ) if occ and ren is not None else None)


def pool(geoids, T):
    ws, acc = [], {k: [] for k in range(4)}
    ren = occ = 0.0
    for g in geoids:
        t = T.get(g)
        if not t or not t.get("B25003_001E"):
            continue
        w = t["B25003_001E"]; inp = tract_inputs(t)
        ws.append(w)
        for k in range(4):
            acc[k].append((inp[k], w))
        if t.get("B25003_003E") is not None:
            ren += t["B25003_003E"]; occ += w
    if not ws:
        return None
    def wm(L):
        L = [(v, w) for v, w in L if v is not None]
        return sum(v * w for v, w in L) / sum(w for _, w in L) if L else None
    return (wm(acc[0]), wm(acc[1]), wm(acc[2]), wm(acc[3]), (ren / occ) if occ else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shift-sample", type=int, default=0)
    ap.add_argument("--offline-shift", action="store_true", help="no geocoder: the tract under a shifted pin is approximated by the nearest tract center")
    ap.add_argument("--out", default=str(REPO / "analysis" / "housing_pooled_cache_run.jsonl"))
    a = ap.parse_args()
    T = load_tracts()
    tab = pd.read_parquet(REPO / "data" / "tract_pop_area_centers.parquet")
    la, lo, gid = np.radians(tab.lat.values), np.radians(tab.lon.values), tab.geoid.values

    def dist(lat, lon):
        p, q = math.radians(lat), math.radians(lon)
        d = np.sin((la - p) / 2) ** 2 + np.cos(la) * math.cos(p) * np.sin((lo - q) / 2) ** 2
        return 2 * 6371000 * np.arcsin(np.sqrt(d))

    places = []
    for f in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(f).split("_metro")[0]
        for l in open(f):
            if not l.strip():
                continue
            r = json.loads(l); s = r["score"]; h = (s.get("livability_pillars") or {}).get("housing_value")
            co = s.get("coordinates") or {}
            if h and co.get("lat") and (h.get("summary") or {}).get("geo_level") == "tract" and h.get("score") is not None:
                places.append((metro, r["catalog"].get("name"), co["lat"], co["lon"], h))
    out, stats = [], {"n": len(places), "pin_tract_matched": 0, "baseline_reproduces_stored": 0}
    for metro, name, lat, lon, h in places:
        sm = h["summary"]; stored = (sm.get("median_household_income"), sm.get("median_home_value"),
                                     sm.get("median_gross_rent"), sm.get("median_rooms"))
        d = dist(lat, lon); near = np.where(d <= 5000)[0]
        pin = [gid[i] for i in near if T.get(gid[i]) and (T[gid[i]].get("B19013_001E"), T[gid[i]].get("B25077_001E"),
               T[gid[i]].get("B25064_001E"), T[gid[i]].get("B25018_001E")) == tuple(stored)]
        pin_g = pin[0] if len(pin) == 1 else None
        stats["pin_tract_matched"] += pin_g is not None
        base = None
        if pin_g:
            base = score(*tract_inputs(T[pin_g]))
            stats["baseline_reproduces_stored"] += base is not None and abs(base - h["score"]) <= 1.0
        rec = {"metro": metro, "name": name, "lat": lat, "lon": lon, "stored": h["score"], "pin_tract": pin_g, "rebuilt": base}
        for R in (700, 1400):
            g = set(gid[np.where(d <= R)[0]]) | ({pin_g} if pin_g else set())
            p = pool(g, T)
            rec[f"pooled_{R}"] = score(*p) if p else None
            rec[f"n_tracts_{R}"] = len([x for x in g if x in T])
        out.append(rec)
    Path(a.out).write_text("\n".join(json.dumps(r) for r in out))
    print(json.dumps(stats))
    for R in (700, 1400):
        dl = [abs(r[f"pooled_{R}"] - r["rebuilt"]) for r in out if r["rebuilt"] is not None and r[f"pooled_{R}"] is not None]
        if dl:
            print(R, "m: n", len(dl), "median abs change vs single tract", round(S.median(dl), 1), "p90", round(sorted(dl)[int(.9 * len(dl))], 1),
                  "max", round(max(dl), 1), "over 5:", sum(x > 5 for x in dl), "over 10:", sum(x > 10 for x in dl))

    if a.shift_sample:
        census_api = None
        if not a.offline_shift:
            from data_sources import census_api
        rnd = random.Random(7)
        sample = rnd.sample([r for r in out if r["pin_tract"]], a.shift_sample)
        res = {"single": [], "pooled_700": [], "pooled_1400": []}
        for r in sample:
            for b in range(8):
                ang = math.radians(45 * b)
                lat2 = r["lat"] + 500 * math.cos(ang) / 111320
                lon2 = r["lon"] + 500 * math.sin(ang) / (111320 * math.cos(math.radians(r["lat"])))
                d2 = dist(lat2, lon2)
                if census_api is None:
                    g0 = gid[int(np.argmin(d2))]
                else:
                    tr = census_api.get_census_tract(lat2, lon2)
                    if not tr:
                        continue
                    g0 = f"{tr['state_fips']}{tr['county_fips']}{tr['tract_fips']}"
                if T.get(g0):
                    sc = score(*tract_inputs(T[g0]))
                    if sc is not None and r["rebuilt"] is not None:
                        res["single"].append(abs(sc - r["rebuilt"]))
                for R in (700, 1400):
                    p = pool(set(gid[np.where(d2 <= R)[0]]) | {g0}, T)
                    sc = score(*p) if p else None
                    if sc is not None and r[f"pooled_{R}"] is not None:
                        res[f"pooled_{R}"].append(abs(sc - r[f"pooled_{R}"]))
        for k, v in res.items():
            if v:
                v.sort(); print("pin shift 500 m,", k, "n", len(v), "median", round(S.median(v), 1), "p95", round(v[int(.95 * len(v))], 1), "max", round(v[-1], 1))


if __name__ == "__main__":
    main()
