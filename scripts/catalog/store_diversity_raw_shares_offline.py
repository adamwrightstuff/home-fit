#!/usr/bin/env python3
"""
Store the raw continuous shares behind the diversity pillar in each catalog record (no score change).

Adds diversity.raw_shares: race_ethnicity (8 groups, percent), income_brackets (16 ACS B19001 brackets, percent), age
(under 18, 18 to 64, 65 and over, plus 25 to 34 as a subset of 18 to 64, percent), geo_level, geoid, total_population. The geography is found per record by matching
its stored 25+ population, 16-bracket income entropy and age entropy to the Census cache (so same-name places cannot collide);
places whose stored population is from another geography use --override. Unmatched places are listed and skipped.

  PYTHONPATH=. python3 scripts/catalog/store_diversity_raw_shares_offline.py --override <geo8_override.json>
  PYTHONPATH=. python3 scripts/catalog/store_diversity_raw_shares_offline.py --override <geo8_override.json> --write --backup-dir data/backups_diversity_shares_2026-10-28
"""
import argparse, collections, glob, json, os, shutil, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "catalog"))
import diversity_identify_geography_offline as D

RACE_KEYS = ["white_nh", "black_nh", "aian_nh", "asian_nh", "nhpi_nh", "other_nh", "two_plus_nh", "hispanic"]


def load_hisp():
    H = {}
    for f in glob.glob(str(REPO / "data/census_pull_2026-10-28/hisp_*_0.json")):
        kind = os.path.basename(f).split("_")[1]; d = json.load(open(f)); h = d[0]
        for r in d[1:]:
            gid = (r[h.index("state")] + r[h.index("county")] + r[h.index("tract")] if kind == "tract" else
                   r[h.index("state")] + r[h.index("place")] if kind == "place" else
                   r[h.index("state")] + r[h.index("county")] + r[h.index("county subdivision")])
            H[(kind, gid)] = [D.num(r[h.index(f"B03002_{i:03d}E")]) for i in (3, 4, 5, 6, 7, 8, 9, 12)]
    return H


def shares(v):
    t = sum(v)
    return [round(x / t * 100, 1) for x in v] if t > 0 else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); ap.add_argument("--backup-dir"); ap.add_argument("--override")
    a = ap.parse_args()
    if a.write and not a.backup_dir: sys.exit("--write requires --backup-dir")
    geo, H = D.load(), load_hisp()
    ov = json.load(open(a.override)) if a.override else {}
    by_pop = collections.defaultdict(list)
    for k, g in geo.items():
        if g.get("B15003_001E") and k in H: by_pop[int(g["B15003_001E"])].append(k)
    done, skipped = 0, []
    for path in sorted(REPO.glob("data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
        metro = path.name.split("_metro")[0]; lines = path.read_text().split("\n"); ch = False
        for i, l in enumerate(lines):
            if not l.strip(): continue
            r = json.loads(l); nm = r["catalog"].get("name"); dv = (r["score"].get("livability_pillars") or {}).get("diversity") or {}
            bd = dv.get("breakdown") or {}
            if dv.get("status") == "no_data" or dv.get("score") is None: continue
            key = ov.get(f"{metro}|{nm}"); k = tuple(key) if key else None
            if k is None:
                pop = (dv.get("education_attainment") or {}).get("population_25_plus")
                hits = []
                for c in by_pop.get(int(pop or -1), []):
                    d = D.derive(geo[c]); inc = [geo[c].get(f"B19001_{j:03d}E", 0) for j in range(2, 18)]
                    if abs(round(d["age"] or -9, 1) - (bd.get("age_entropy") or -9)) <= 0.11 and abs(round(D.ent(inc, 16), 1) - (bd.get("income_entropy") or -9)) <= 0.11:
                        hits.append(c)
                if len(hits) > 1 and len({tuple(geo[c].get(f"B19001_{j:03d}E", 0) for j in range(2, 18)) + tuple(H[c]) for c in hits}) == 1:
                    hits = sorted(hits, key=lambda c: c[0] != "cousub")[:1]  # identical counts (New England town as place and as county subdivision)
                if len(hits) != 1: skipped.append((metro, nm, f"{len(hits)} geography matches")); continue
                k = hits[0]
            g = geo[k]
            y = sum(g.get(f"B01001_{j:03d}E", 0) for j in list(range(3, 7)) + list(range(27, 31)))
            p = sum(g.get(f"B01001_{j:03d}E", 0) for j in list(range(7, 20)) + list(range(31, 44)))
            s = sum(g.get(f"B01001_{j:03d}E", 0) for j in list(range(20, 26)) + list(range(44, 50)))
            rs, ins, ags = shares(H[k]), shares([g.get(f"B19001_{j:03d}E", 0) for j in range(2, 18)]), shares([y, p, s])
            if not (rs and ins and ags): skipped.append((metro, nm, "empty counts")); continue
            # 25 to 34 share of all residents (B01001_011, 012, 035, 036), a subset of the 18-64 band.
            yp = sum(g.get(f"B01001_{j:03d}E", 0) for j in (11, 12, 35, 36))
            yp_share = round(yp / (y + p + s) * 100, 1)
            dv["raw_shares"] = {"race_ethnicity": dict(zip(RACE_KEYS, rs)), "income_brackets": ins,
                                "age": {**dict(zip(["under_18", "age_18_64", "age_65_plus"], ags)), "age_25_34": yp_share},
                                "geo_level": {"tract": "tract", "place": "place", "cousub": "county_subdivision"}[k[0]], "geoid": k[1],
                                "total_population": int(sum(H[k])), "source": "ACS 2022 5-year: B03002, B19001, B01001"}
            lines[i] = json.dumps(r, ensure_ascii=False); ch = True; done += 1
        if ch and a.write:
            b = Path(a.backup_dir); b.mkdir(parents=True, exist_ok=True); shutil.copy2(path, b / path.name)
            path.write_text("\n".join(lines))
    print(("WROTE" if a.write else "DRY RUN"), done, "places;", len(skipped), "skipped")
    for x in skipped[:30]: print("  ", *x)


if __name__ == "__main__":
    main()
