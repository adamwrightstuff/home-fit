#!/usr/bin/env python3
"""
Offline: tract-pooled inputs for catalog NEIGHBORHOODS whose housing read was the whole city (housing_value.summary.geo_level
"incorporated_place"), e.g. Coconut Grove read as the City of Miami. No Census calls: reads the archived state pulls
(housing_tract and div_tract, the latter carries the B19001 income bins) and the tract centers table.

Pool = the tracts under the pin and an 8-point ring at --ring-m (default 350, the status label pool), occupied-unit
weighted, tract shape approximated as a disk of land area. The pin's own tract is the disk containing the pin (nearest
edge otherwise); there is no live-geocoder check for these places. Output per place: income, home_value, share_150k
(percent of households at $150,000 or more, from B19001 bins 016 and 017 over 001, pooled by households), tracts, pin_tract,
topcoded (a pooled tract at the ACS income cap of $250,001).

  python3 scripts/catalog/pool_neighborhood_city_level_offline.py --pull <archive>/data/census_pull_2026-10-28 --out pooled_nbhd.json [--ring-m 350]
"""
import argparse, glob, json, math, os
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAD = -1e8
TOPCODE = 250001.0


def num(x):
    try:
        v = float(x)
        return None if v < BAD else v
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ring-m", type=float, default=350.0)
    ap.add_argument("--centers", default=os.path.join(REPO, "data", "tract_pop_area_centers.parquet"))
    a = ap.parse_args()

    T = {}
    for pat in ("housing_tract_*_0.json", "housing2_tract_*_0.json", "div_tract_*_0.json"):
        for f in glob.glob(os.path.join(a.pull, pat)):
            d = json.load(open(f)); h = d[0]
            for r in d[1:]:
                g = r[h.index("state")] + r[h.index("county")] + r[h.index("tract")]
                t = T.setdefault(g, {})
                for i, c in enumerate(h):
                    if c[0] == "B":
                        t[c] = num(r[i])
    cen = pd.read_parquet(a.centers)
    cen = cen[cen.geoid.isin(T.keys())].reset_index(drop=True)
    CLA, CLO, CG = np.radians(cen.lat.values), np.radians(cen.lon.values), cen.geoid.values
    CR = np.sqrt(cen.land_sqmi.values * 2589988.0 / math.pi)

    def dist_m(lat, lon, idx):
        p, q = math.radians(lat), math.radians(lon)
        x = np.sin((CLA[idx] - p) / 2) ** 2 + np.cos(CLA[idx]) * math.cos(p) * np.sin((CLO[idx] - q) / 2) ** 2
        return 2 * 6371000 * np.arcsin(np.sqrt(x))

    out, nomatch = {}, 0
    allidx = np.arange(len(CG))
    for f in sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(f).split("_metro_")[0]
        for l in open(f):
            d = json.loads(l)
            if not d.get("success"):
                continue
            c = d["catalog"]
            sm = (((d.get("score") or {}).get("livability_pillars") or {}).get("housing_value") or {}).get("summary") or {}
            if not (c.get("type") == "neighborhood" and sm.get("geo_level") == "incorporated_place"):
                continue
            lat, lon = float(c["lat"]), float(c["lon"])
            near = np.where(dist_m(lat, lon, allidx) <= 20000)[0]
            own = CG[near][int(np.argmin(dist_m(lat, lon, near) - CR[near]))]
            hit = {own}
            for ang in range(0, 360, 45):
                la = lat + a.ring_m / 111000.0 * math.cos(math.radians(ang))
                lo = lon + a.ring_m / (111000.0 * math.cos(math.radians(lat))) * math.sin(math.radians(ang))
                hit.update(CG[near][dist_m(la, lo, near) <= CR[near]])
            items = [T[g] for g in hit if g in T and T[g].get("B25003_001E") and T[g].get("B19013_001E")]
            if not items:
                nomatch += 1
                continue

            def wm(k):
                L = [(t.get(k), t["B25003_001E"]) for t in items if t.get(k) is not None]
                return sum(v * w for v, w in L) / sum(w for _, w in L) if L else None

            hh = sum(t.get("B19001_001E") or 0 for t in items)
            top = sum((t.get("B19001_016E") or 0) + (t.get("B19001_017E") or 0) for t in items if t.get("B19001_001E"))
            out[f"{metro}|{c['name']}"] = {
                "income": wm("B19013_001E"), "home_value": wm("B25077_001E"),
                "share_150k": round(100.0 * top / hh, 2) if hh > 0 else None,
                "tracts": len(items), "pin_tract": own,
                "topcoded": any((t.get("B19013_001E") or 0) >= TOPCODE for t in items),
            }
    json.dump(out, open(a.out, "w"))
    print(f"city-level neighborhoods pooled {len(out)}, unmatched {nomatch}")


if __name__ == "__main__":
    main()
