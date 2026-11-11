#!/usr/bin/env python3
"""
Offline: retire the old name-guessing Local Scene everywhere in the catalog and put the new one in its place. No API calls.

From each place's stored score.local_scene_v2.independent_venues_1200m it writes:
  score.local_scene_score   0-100 (pillars.local_scene_v2.scene_score), read by twin matching, vibe matching and hotness
  score.local_scene_bucket  the same tier the Explorer shows (High / Some / Low)
and removes local_scene_breakdown and local_scene_bucket_v1. Places with no venue read get score and bucket None (the old values are cleared, not kept).
it_score (hotness) is recomputed from the new score where it was stored.

  python3 scripts/catalog/apply_local_scene_score.py            # dry run
  python3 scripts/catalog/apply_local_scene_score.py --write
"""
import argparse, glob, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402
from pillars.composite_indices import compute_hotness_score  # noqa: E402


def process(path, write=True):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    changed = 0
    for r in rows:
        s = r.get("score") if r.get("success") else None
        if not isinstance(s, dict):
            continue
        # no venue read yet: the old score is retired too, so the place simply has no local scene until it is read
        count = (s.get("local_scene_v2") or {}).get("independent_venues_1200m")
        s["local_scene_score"] = ls.scene_score(count)
        s["local_scene_bucket"] = ls.activity_bucket(count)
        s.pop("local_scene_breakdown", None)
        s.pop("local_scene_bucket_v1", None)
        if isinstance(s.get("it_score"), (int, float)):
            hc = (s.get("status_signal_breakdown") or {}).get("home_cost")
            s["it_score"] = compute_hotness_score(
                s.get("status_signal"), s["local_scene_score"], hc if isinstance(hc, (int, float)) else None,
                s.get("happiness_index"), s.get("total_score"))
        changed += 1
    if write:
        Path(path).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"{Path(path).name}: {changed} places updated")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        process(path, write=a.write)
    if not a.write:
        print("dry run: pass --write to save")


if __name__ == "__main__":
    main()
