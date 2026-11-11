#!/usr/bin/env python3
"""
Offline: write the Local Scene ladder level from each place's stored score.local_scene_v2 facts. No API calls.

  score.local_scene_level   the ladder level the Explorer shows (quiet / low_key / lively / buzzing, None = no data)
and removes the retired fields: local_scene_score, local_scene_breakdown, local_scene_bucket, local_scene_bucket_v1 and the
v2 lively flag and bucket. Places with no venue data get level None (never Quiet).

  python3 scripts/catalog/apply_local_scene_level.py            # dry run
  python3 scripts/catalog/apply_local_scene_level.py --write
"""
import argparse, glob, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402


def process(path, write=True):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    changed = 0
    for r in rows:
        s = r.get("score") if r.get("success") else None
        if not isinstance(s, dict):
            continue
        v2 = s.get("local_scene_v2")
        s["local_scene_level"] = ls.scene_level(v2) if isinstance(v2, dict) else None
        s.pop("local_scene_bucket", None)
        s.pop("local_scene_score", None)
        if isinstance(v2, dict):
            v2.pop("lively", None)
            v2.pop("bucket", None)
        s.pop("local_scene_breakdown", None)
        s.pop("local_scene_bucket_v1", None)
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
