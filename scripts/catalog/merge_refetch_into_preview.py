#!/usr/bin/env python3
"""
Merge live-refetched built_beauty results into the offline-rescored preview catalogs.

Pure local JSON splicing -- NO live calls. Requires refetch JSONLs produced by the
current refetch_built_beauty.py, which persists the FULL calculate_built_beauty() result
(under "full_result") for every clean place, not just a summary. This does a complete
wholesale replacement of bb["score"] and bb["details"] from that full result -- no nested
field is ever left stale, because every nested field is overwritten.

If a refetch JSONL predates the full_result field (old runs), those places are skipped
with a warning -- re-run the refetch for them rather than partially merging stale data.

Never touches the real data/*_merged.jsonl catalogs -- only data/neighborhood_beauty_wip/*.

Usage:
  python3 scripts/catalog/merge_refetch_into_preview.py
"""
from __future__ import annotations
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WIP = REPO_ROOT / "data" / "neighborhood_beauty_wip"


def load_clean_refetches(*jsonl_paths):
    clean = {}
    stale_skipped = []
    for p in jsonl_paths:
        if not p.exists():
            continue
        for line in open(p):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("status") != "clean":
                continue
            if "full_result" not in r:
                stale_skipped.append(r["name"])
                continue
            clean[r["name"]] = r
    return clean, stale_skipped


def merge(tag, preview_path, refetch_jsonls):
    clean, stale_skipped = load_clean_refetches(*refetch_jsonls)
    print(f"\n=== {tag}: {len(clean)} clean refetched places to merge "
          f"(skipping {len(stale_skipped)} without full_result -- need re-run) ===")
    if stale_skipped:
        print(f"  NEEDS RE-REFETCH (old-format jsonl, no full_result): {', '.join(stale_skipped)}")

    rows = [json.loads(l) for l in open(preview_path) if l.strip()]
    merged = 0
    for rec in rows:
        name = rec["catalog"].get("name")
        r = clean.get(name)
        if not r:
            continue
        bb = rec["score"]["livability_pillars"].get("built_beauty")
        if not bb:
            continue
        old_score = bb.get("score")
        full = r["full_result"]
        # Wholesale replace -- calculate_built_beauty()'s return dict keys map 1:1 onto
        # the catalog's built_beauty subtree (score, score_before_normalization,
        # component_score_0_50, details, architectural_details, enhancers, ...).
        bb["score"] = full["score"]
        bb["details"] = full["details"]
        bb["data_quality"] = full.get("data_quality")
        merged += 1
        print(f"  {name:24s} old={old_score} new={round(full['score'],2)} "
              f"warn={full['details']['architectural_analysis'].get('data_warning')}")

    with open(preview_path, "w") as fh:
        for rec in rows:
            fh.write(json.dumps(rec) + "\n")
    print(f"{tag}: merged {merged}/{len(clean)} into {preview_path}")


merge("LA", WIP / "la_rescored_preview.jsonl",
      [WIP / "refetch_la.jsonl", WIP / "refetch_la_remaining.jsonl"])
merge("NYC", WIP / "nyc_rescored_preview.jsonl",
      [WIP / "refetch_nyc.jsonl"])
