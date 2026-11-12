#!/usr/bin/env python3
"""
Add diversity.age_percentiles.young_professionals (25 to 34 share percentile among US tracts) to every catalog record. Offline.

Same geography rule as the other cohorts: places stored on their own geography use raw_shares.age.age_25_34; tract-level places
use the 1400 m pooled tract counts (pillars.diversity.pooled_age_counts). Needs the rebuilt data/tract_age_counts.parquet and
data/age_share_percentiles.json (scripts/baselines/build_age_share_percentiles.py --write). Dry run unless --write.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/backfill_young_professionals_percentile_offline.py
  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/backfill_young_professionals_percentile_offline.py --write --backup-dir data/backups_yp_percentile_2026-11-12
"""
import argparse, json, shutil, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pillars import diversity


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
            if not rs or not dv.get("age_percentiles"): continue
            share = None
            if rs.get("geo_level") == "tract":
                pooled = diversity.pooled_age_counts(r["catalog"]["lat"], r["catalog"]["lon"], rs.get("geoid"))
                if pooled and pooled[4] is not None:
                    share = pooled[4] / (pooled[0] + pooled[1] + pooled[2]) * 100.0
            else:
                share = (rs.get("age") or {}).get("age_25_34")
            pct = diversity._age_percentile("young_professionals", share) if share is not None else None
            if pct is None: skipped.append((path.name.split("_metro")[0], nm, "no share or baseline")); continue
            dv["age_percentiles"]["young_professionals"] = round(pct, 1)
            lines[i] = json.dumps(r, ensure_ascii=False); ch = True; done += 1
        if ch and a.write:
            b = Path(a.backup_dir); b.mkdir(parents=True, exist_ok=True); shutil.copy2(path, b / path.name)
            path.write_text("\n".join(lines))
    print(("WROTE" if a.write else "DRY RUN"), done, "places;", len(skipped), "skipped")
    for x in skipped[:30]: print("  ", *x)


if __name__ == "__main__":
    main()
