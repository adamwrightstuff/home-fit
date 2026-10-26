"""
Education pillar: a place with no usable school score is stored as no data (score None, status no_data, degraded),
never as 0.0. Same convention as the neighborhood_amenities no-data rows. Offline, idempotent.

  PYTHONPATH=. python3 scripts/catalog/mark_unrated_education_no_data.py [--dry-run]
Then: recompute_catalog_composites.py --in-place --no-census --input <metro file> for each metro that changed.
"""
import argparse
import glob
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for path in sorted(glob.glob(os.path.join(REPO, "data", "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        out, changed = [], []
        for line in open(path):
            row = json.loads(line)
            p = ((row.get("score") or {}).get("livability_pillars") or {}).get("quality_education")
            bd = (p or {}).get("breakdown") or {}
            if p and p.get("score") == 0.0 and not bd.get("rated_schools") \
                    and not any(v.get("score") is not None for v in (bd.get("levels") or {}).values()):
                reason = ("no rated school for any level" if bd.get("model") == "zoned_v1"
                          else "school scoring was not run and no district boundary matched")
                p["score"], p["contribution"], p["status"], p["confidence"] = None, 0.0, "no_data", 0
                dq = p.get("data_quality") or {}
                dq.update({"degraded": True, "quality_tier": "none", "reason": "No school data",
                           "degraded_reasons": [f"quality_education_no_data: {reason}"]})
                p["data_quality"] = dq
                changed.append(row["catalog"]["name"])
            out.append(json.dumps(row, ensure_ascii=False))
        if changed:
            print(f"{os.path.basename(path).split('_metro')[0]}: {changed}")
            if not args.dry_run:
                with open(path + ".tmp", "w") as f:
                    f.write("\n".join(out) + "\n")
                os.replace(path + ".tmp", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
