#!/usr/bin/env python3
"""
Offline: join the household type pull to catalog places by the Census geography the diversity read used
(analysis/diversity_geography_identified.jsonl, from diversity_identify_geography_offline.py). Output keys are
metro|name|state_fips because a metro can hold two places with one name (Ridgewood NJ and Ridgewood NY). No API calls.

  python3 scripts/catalog/join_household_type_offline.py --pull <pull_dir> --identified <diversity_geography_identified.jsonl> --out <pull_dir>/household_type_by_place.json
"""
import argparse, glob, json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", required=True)
    ap.add_argument("--identified", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    look = {}
    for f in glob.glob(f"{a.pull}/hh_*.json"):
        x = json.load(open(f)); h = x[0]
        for r in x[1:]:
            d = dict(zip(h, r))
            if "tract" in d:
                gid, kind = d["state"] + d["county"] + d["tract"], "tract"
            elif "place" in d:
                gid, kind = d["state"] + d["place"], "place"
            else:
                gid, kind = d["state"] + d["county"] + d["county subdivision"], "cousub"

            def n(k):
                try:
                    v = float(d[k])
                    return v if v >= 0 else None
                except (TypeError, ValueError):
                    return None
            t = n("B11001_001E")
            if t:
                look[(kind, gid)] = dict(households=t, family=n("B11001_002E"), married=n("B11001_003E"), alone=n("B11001_008E"),
                                         u18=n("B11005_002E"), o65=n("B11007_002E"))
    out, miss = {}, 0
    for l in open(a.identified):
        if not l.strip():
            continue
        r = json.loads(l)
        v = look.get((r.get("geo"), r.get("geoid"))) if r.get("geo") else None
        if not v or None in (v["family"], v["married"], v["alone"], v["u18"], v["o65"]):
            miss += 1
            continue
        H = v["households"]
        out[f"{r['metro']}|{r['name']}|{r['geoid'][:2]}"] = dict(
            geo=r["geo"], geoid=r["geoid"], households=H,
            pct_with_children=round(100 * v["u18"] / H, 1), pct_living_alone=round(100 * v["alone"] / H, 1),
            pct_married_couple=round(100 * v["married"] / H, 1), pct_family=round(100 * v["family"] / H, 1),
            pct_with_65plus=round(100 * v["o65"] / H, 1))
    json.dump(out, open(a.out, "w"))
    print(f"joined {len(out)}, unmatched {miss}")


if __name__ == "__main__":
    main()
