#!/usr/bin/env python3
"""
Offline: pooled income / home value for the single-tract catalog places, for the status class (DPv2 Level 2).
No Census calls. Reads the cached state pull (data/census_pull_2026-10-28/housing_tract_*_0.json, kept in the
archive folder) and the tract centers table. Same pooling rule as the housing pillar (D14): the tracts containing
the pin or any of 8 ring points at 700 m, occupied-unit weighted, tract shape approximated as a disk of the tract's
land area (membership is approximate; checked against the live-geocoder run in audit_housing_d14_exact_places.jsonl).

  python3 scripts/catalog/pool_status_class_inputs_offline.py --pull <census_pull_dir> --exact <exact_places.jsonl> --out <pooled.json> [--shift-out <shift.json>]
"""
import argparse, glob, json, math, os, random, sys
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BAD = -1e8


def num(x):
    try:
        v = float(x)
        return None if v < BAD else v
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", required=True)
    ap.add_argument("--exact", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shift-out")
    ap.add_argument("--centers", default=os.path.join(REPO, "data", "tract_pop_area_centers.parquet"))
    a = ap.parse_args()

    T = {}
    for f in glob.glob(os.path.join(a.pull, "housing_tract_*_0.json")) + glob.glob(os.path.join(a.pull, "housing2_tract_*_0.json")):
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

    def ring_pts(lat, lon, R=700.0):
        pts = [(lat, lon)]
        for ang in range(0, 360, 45):
            pts.append((lat + R / 111000.0 * math.cos(math.radians(ang)),
                        lon + R / (111000.0 * math.cos(math.radians(lat))) * math.sin(math.radians(ang))))
        return pts

    def members(lat, lon, near, pin_g):
        hit = {pin_g}
        for la, lo in ring_pts(lat, lon):
            d = dist_m(la, lo, near)
            hit.update(CG[near][d <= CR[near]])
        return hit

    def members_shifted(lat, lon, near, shift_dlat, shift_dlon):
        # pool around the shifted pin; the shifted pin's own tract is the one whose disk contains it (nearest edge otherwise)
        la, lo = lat + shift_dlat, lon + shift_dlon
        d = dist_m(la, lo, near)
        own = CG[near][int(np.argmin(d - CR[near]))]
        return members(la, lo, near, own)

    def pooled(geoids):
        items = [T[g] for g in geoids if g in T and T[g].get("B25003_001E") and T[g].get("B19013_001E")]
        if not items:
            return None
        w = [t["B25003_001E"] for t in items]
        def wm(k):
            L = [(t.get(k), wi) for t, wi in zip(items, w) if t.get(k) is not None]
            return sum(v * wi for v, wi in L) / sum(wi for _, wi in L) if L else None
        return {"income": wm("B19013_001E"), "home_value": wm("B25077_001E"), "rent": wm("B25064_001E"), "tracts": len(items)}

    exact = {}
    for l in open(a.exact):
        r = json.loads(l); exact[(r["metro"], r["name"])] = r

    places = []
    for f in sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(f).split("_metro_")[0]
        for l in open(f):
            d = json.loads(l); s = d.get("score") or {}
            sm = ((s.get("livability_pillars") or {}).get("housing_value") or {}).get("summary") or {}
            if sm.get("geo_level") == "tract":
                c = d["catalog"]
                places.append((metro, c["name"], float(c["lat"]), float(c["lon"]), sm))

    out, nomatch, agree = {}, 0, []
    shifts = {}
    for metro, name, lat, lon, sm in places:
        pin_g = (exact.get((metro, name)) or {}).get("pin_tract")
        if not pin_g or pin_g not in T:
            nomatch += 1
            continue
        d_all = np.arange(len(CG))
        near = np.where(dist_m(lat, lon, d_all) <= 20000)[0]
        p = pooled(members(lat, lon, near, pin_g))
        if not p:
            nomatch += 1
            continue
        p["single_income"], p["single_home_value"] = sm.get("median_household_income"), sm.get("median_home_value")
        p["pin_tract"] = pin_g
        ex = (exact.get((metro, name)) or {}).get("parts_700", {}).get("median_home_value")
        if ex and p["home_value"]:
            p["home_value_vs_exact_pct"] = round(100 * (p["home_value"] - ex) / ex, 2)
            agree.append(abs(p["home_value_vs_exact_pct"]))
        out[f"{metro}|{name}"] = p
        if a.shift_out:
            res = []
            for ang in (0, 90, 180, 270):  # N, E, S, W at 500 m
                dlat = 500 / 111000.0 * math.cos(math.radians(ang))
                dlon = 500 / (111000.0 * math.cos(math.radians(lat))) * math.sin(math.radians(ang))
                near2 = np.where(dist_m(lat + dlat, lon + dlon, d_all) <= 20000)[0]
                g_own = None
                m_sh = members_shifted(lat, lon, near2, dlat, dlon)
                single_sh = None
                dd = dist_m(lat + dlat, lon + dlon, near2)
                g_own = CG[near2][int(np.argmin(dd - CR[near2]))]
                ps = pooled(m_sh)
                t = T.get(g_own, {})
                res.append({"pooled": ps, "single": {"income": t.get("B19013_001E"), "home_value": t.get("B25077_001E")}})
            shifts[f"{metro}|{name}"] = res
    json.dump(out, open(a.out, "w"))
    if a.shift_out:
        json.dump(shifts, open(a.shift_out, "w"))
    print(f"tract-level places {len(places)}; pooled {len(out)}; unmatched {nomatch}")
    if agree:
        agree.sort()
        print(f"pooled home value vs live-geocoder pool: median |diff| {agree[len(agree)//2]:.1f}%, p90 {agree[int(len(agree)*.9)]:.1f}%, within 2%: {sum(x<=2 for x in agree)} of {len(agree)}")


if __name__ == "__main__":
    main()
