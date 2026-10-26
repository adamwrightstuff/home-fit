"""
Fill breakdown.early_ed (kindergarten/childcare access from OpenStreetMap) for catalog places, using the private
Overpass server. Run `rescore_education_offline.py` afterwards to rebuild the stored education breakdowns.

The private server holds only the states in SERVED_STATES. A state outside them would answer HTTP 200 with an empty
element list (a false "none mapped"), so those places are skipped and marked early_ed_missing, never queried.

  OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/catalog/requery_early_ed.py [--metro la] [--limit 5] [--dry-run]
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from data_sources.schools_api import normalize_state
from pillars.schools import early_ed_access

SERVED_STATES = {"NY", "NJ", "CT", "CA", "WA", "TX", "IL", "IN", "PA", "DE", "MD"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--metro", action="append", help="metro file prefix, e.g. la (default: all)")
    ap.add_argument("--limit", type=int, default=0, help="query at most N places per metro (pilot)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not os.getenv("OVERPASS_URL"):
        print("OVERPASS_URL is not set; refusing to use the public servers")
        return 2
    import glob
    paths = sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")))
    for path in paths:
        metro = os.path.basename(path).split("_metro")[0]
        if args.metro and metro not in args.metro:
            continue
        out, done, failed, skipped = [], 0, 0, 0
        for line in open(path):
            row = json.loads(line)
            sc, cat = row.get("score") or {}, row.get("catalog") or {}
            p = (sc.get("livability_pillars") or {}).get("quality_education")
            st = normalize_state((sc.get("location_info") or {}).get("state"))
            if p is None or not p.get("breakdown") or p["breakdown"].get("model") != "zoned_v1":
                out.append(line.rstrip("\n"))
                continue
            bd = p["breakdown"]
            if st not in SERVED_STATES:
                bd["early_ed"], bd["early_ed_missing"] = None, True
                skipped += 1
            elif args.limit and done + failed >= args.limit:
                out.append(line.rstrip("\n"))
                continue
            else:
                e = early_ed_access(float(cat["lat"]), float(cat["lon"]))
                bd["early_ed"], bd["early_ed_missing"] = e, e is None
                done += e is not None
                failed += e is None
            out.append(json.dumps(row, ensure_ascii=False))
        print(f"{metro}: queried {done}, failed {failed}, outside server coverage {skipped}")
        if not args.dry_run:
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                f.write("\n".join(out) + "\n")
            os.replace(tmp, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
