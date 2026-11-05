#!/usr/bin/env python3
"""
Offline: which Census geography produced each stored diversity value, and the new-formula race entropy for it.

For every catalog place, look up the cached state pull (scripts/catalog/pull_census_state_tables.py) for the tract,
place or county subdivision whose 25+ population equals the stored population_25_plus and whose income and age
entropy reproduce the stored ones. A unique reproduction identifies the geography the stored value came from.
Places still on the old race formula get the new-formula race entropy and headline from that geography.
Read-only; writes analysis/diversity_geography_identified.jsonl.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/diversity_identify_geography_offline.py
"""
from __future__ import annotations

import collections, glob, json, math, os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PULL = REPO / "data" / "census_pull_2026-10-28"
SUB = ("B02001_009E", "B02001_010E")


def ent(counts, n):
    t = sum(c for c in counts if c)
    if n <= 1 or t <= 0:
        return 0.0
    h = -sum(c / t * math.log(c / t) for c in counts if c and c > 0)
    return max(0.0, min(100.0, h / math.log(n) * 100))


def num(x):
    try:
        v = float(x)
        return 0 if v < -1e8 else v
    except (TypeError, ValueError):
        return 0


def load():
    geo = {}
    for f in glob.glob(str(PULL / "div_*_*.json")):
        kind = os.path.basename(f).split("_")[1]
        d = json.load(open(f)); h = d[0]
        for r in d[1:]:
            if kind == "tract":
                gid = ("tract", r[h.index("state")] + r[h.index("county")] + r[h.index("tract")])
            elif kind == "place":
                gid = ("place", r[h.index("state")] + r[h.index("place")])
            else:
                gid = ("cousub", r[h.index("state")] + r[h.index("county")] + r[h.index("county subdivision")])
            g = geo.setdefault(gid, {})
            for i, c in enumerate(h):
                if c[0] == "B":
                    g[c] = num(r[i])
    return geo


def derive(g):
    race = [g.get(f"B02001_{i:03d}E", 0) for i in range(2, 9)]
    race_all = [g.get(f"B02001_{i:03d}E", 0) for i in range(2, 11)]
    inc = [g.get(f"B19001_{i:03d}E", 0) for i in range(2, 18)]
    y = sum(g.get(f"B01001_{i:03d}E", 0) for i in list(range(3, 7)) + list(range(27, 31)))
    p = sum(g.get(f"B01001_{i:03d}E", 0) for i in list(range(7, 20)) + list(range(31, 44)))
    s = sum(g.get(f"B01001_{i:03d}E", 0) for i in list(range(20, 26)) + list(range(44, 50)))
    nz = lambda v: sum(1 for x in v if x > 0)
    return {
        "pop25": g.get("B15003_001E"),
        "race_new": ent(race, 7) if nz(race) >= 2 else None,
        "race_old": ent(race_all, nz(race_all)) if nz(race_all) >= 2 else None,
        "inc": ent(inc, nz(inc)) if nz(inc) >= 2 else None,
        "age": ent([y, p, s], 3) if y + p + s > 0 else None,
        "total": g.get("B02001_001E"),
    }


def close(a, b):
    return a is not None and b is not None and abs(round(a, 1) - b) <= 0.11


def main():
    geo = load()
    by_pop = collections.defaultdict(list)
    for gid, g in geo.items():
        d = derive(g)
        if d["pop25"]:
            by_pop[int(d["pop25"])].append((gid, d))
    out = []
    for f in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(f).split("_metro")[0]
        for l in open(f):
            if not l.strip():
                continue
            r = json.loads(l); dv = (r["score"].get("livability_pillars") or {}).get("diversity") or {}
            bd = dv.get("breakdown") or {}; edu = dv.get("education_attainment") or {}
            rec = {"metro": metro, "name": r["catalog"].get("name"), "stored_race": bd.get("race_entropy"),
                   "stored_headline": dv.get("score"), "geo": None}
            pop = edu.get("population_25_plus")
            if pop and bd.get("income_entropy") is not None and bd.get("age_entropy") is not None:
                hits = [(gid, d) for gid, d in by_pop.get(int(pop), [])
                        if close(d["inc"], bd["income_entropy"]) and close(d["age"], bd["age_entropy"])
                        and (bd.get("race_entropy") is None or close(d["race_new"], bd["race_entropy"]) or close(d["race_old"], bd["race_entropy"]))]
                rec["n_matches"] = len(hits)
                if len(hits) >= 1:
                    gid, d = hits[0]
                    rec.update(geo=gid[0], geoid=gid[1], race_new=d["race_new"], race_old=d["race_old"], total_pop=d["total"],
                               on_new_formula=close(d["race_new"], bd.get("race_entropy")),
                               on_old_formula=close(d["race_old"], bd.get("race_entropy")) and not close(d["race_new"], bd.get("race_entropy")))
                    comps = [x for x in (d["race_new"], bd["income_entropy"], bd["age_entropy"]) if x is not None]
                    rec["new_headline"] = round(sum(comps) / len(comps), 1)
            out.append(rec)
    p = REPO / "analysis" / "diversity_geography_identified.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in out))
    c = collections.Counter((x["geo"] or "unidentified") for x in out)
    print("places", len(out), dict(c))
    old = [x for x in out if x.get("on_old_formula")]
    print("identified AND still on old race formula:", len(old))
    d = [x["new_headline"] - x["stored_headline"] for x in old]
    if d:
        print("  headline change if rewritten: mean", round(sum(d) / len(d), 1), "min", round(min(d), 1), "max", round(max(d), 1))
    for x in out:
        if x["geo"] is None:
            print("  unidentified:", x["metro"], x["name"], x.get("n_matches"), x["stored_race"], x["stored_headline"])


if __name__ == "__main__":
    main()
