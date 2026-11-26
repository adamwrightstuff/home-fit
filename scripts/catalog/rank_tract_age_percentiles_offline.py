#!/usr/bin/env python3
"""
Recompute diversity.age_percentiles for tract-level catalog places from the tract's own stored age shares (raw_shares.age), replacing
the 1,400 m pooled-ring percentiles. Own-geography places are untouched. Offline, no API calls. Dry run unless --write.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/rank_tract_age_percentiles_offline.py
  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/rank_tract_age_percentiles_offline.py --write --backup-dir data/backups_tract_age_percentiles_2026-11-12
"""
import argparse, json, shutil, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pillars import diversity

SHARE_KEY = {"children": "under_18", "working_age": "age_18_64", "older": "age_65_plus", "young_professionals": "age_25_34"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); ap.add_argument("--backup-dir")
    a = ap.parse_args()
    if a.write and not a.backup_dir: sys.exit("--write requires --backup-dir")
    done, skipped = 0, []
    for path in sorted(REPO.glob("data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
        lines = path.read_text().split("\n"); ch = False
        for i, l in enumerate(lines):
            if not l.strip(): continue
            r = json.loads(l); nm = r["catalog"].get("name")
            dv = (r["score"].get("livability_pillars") or {}).get("diversity") or {}
            rs = dv.get("raw_shares")
            if not rs or not dv.get("age_percentiles") or rs.get("geo_level") != "tract": continue
            age = rs.get("age") or {}
            new = {}
            for k, sk in SHARE_KEY.items():
                v = age.get(sk)
                p = diversity._age_percentile(k, v) if isinstance(v, (int, float)) else None
                if p is not None: new[k] = round(p, 1)
            if len(new) < 4: skipped.append((path.name.split("_metro")[0], nm, "missing share")); continue
            dv["age_percentiles"] = new; dv["age_percentile_basis"] = "own_tract"; dv.pop("age_pooled_tracts", None)
            lines[i] = json.dumps(r, ensure_ascii=False); ch = True; done += 1
        if ch and a.write:
            b = Path(a.backup_dir); b.mkdir(parents=True, exist_ok=True); shutil.copy2(path, b / path.name)
            path.write_text("\n".join(lines))
    print(("WROTE" if a.write else "DRY RUN"), done, "places;", len(skipped), "skipped")
    for x in skipped[:30]: print("  ", *x)


if __name__ == "__main__":
    main()
