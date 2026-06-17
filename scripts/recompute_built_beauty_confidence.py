#!/usr/bin/env python3
"""
Recompute built_beauty `confidence` for every catalog place from already-stored data.

Catalog confidence was frozen at build time (mostly 90, or hardcoded 85 by the recent
stale-coverage backfill). `data_sources/data_quality.py:assess_pillar_data_quality` now
discounts confidence based on `architectural_analysis.data_warning` (3% for informational
warnings like suspiciously_low_height_diversity/low_building_coverage, 12% for real failures
like api_error/timeout/no_buildings) — but that logic was added after most of the catalog was
built, so it was never back-applied. This recomputes it from the architectural_analysis +
enhancer data already in each catalog row (no OSM re-fetch).

confidence is metadata only (not part of score/contribution math), so this does NOT cascade
into total_score or happiness_index.

Usage: python3 scripts/recompute_built_beauty_confidence.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]


def main():
    dry_run = "--dry-run" in sys.argv
    from data_sources.data_quality import assess_pillar_data_quality

    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        if not dry_run:
            shutil.copyfile(fn, fn + ".bakBBConf")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as outf:
            for line in src:
                row = json.loads(line)
                cat = row.get("catalog", {})
                sc = row.get("score", {})
                bb = sc.get("livability_pillars", {}).get("built_beauty")
                if bb:
                    aa = bb.get("details", {}).get("architectural_analysis", {}) or {}
                    combined = {
                        "architectural_analysis": aa,
                        "enhancers": bb.get("details", {}).get("enhancer_bonus", {}) or {},
                    }
                    at = (sc.get("data_quality_summary", {})
                          .get("area_classification", {}).get("effective_area_type")
                          or "suburban")
                    try:
                        lat, lon = float(cat["lat"]), float(cat["lon"])
                    except (TypeError, ValueError, KeyError):
                        outf.write(json.dumps(row) + "\n")
                        continue
                    qm = assess_pillar_data_quality("built_beauty", combined, lat, lon, at)
                    old_conf = bb.get("confidence")
                    new_conf = qm["confidence"]
                    if old_conf != new_conf:
                        shifts.append((cat.get("name", ""), old_conf, new_conf, aa.get("data_warning")))
                        if not dry_run:
                            bb["confidence"] = new_conf
                        n += 1
                outf.write(json.dumps(row) + "\n")
        if dry_run:
            os.remove(tmp)
        else:
            os.replace(tmp, fn)
        print(f"{fn}: {'would change' if dry_run else 'changed'} {n} places"
              f"{'' if dry_run else f' (backup: {fn}.bakBBConf)'}", flush=True)

    print(f"\ntotal confidence changes: {len(shifts)}")
    warn_breakdown = Counter(w for _, _, _, w in shifts)
    print("by data_warning:")
    for k, v in warn_breakdown.most_common():
        print(f"  {str(k):35s} {v}")
    print("\nbiggest drops:")
    for nm, old, new, w in sorted(shifts, key=lambda x: (x[1] or 0) - (x[2] or 0), reverse=True)[:10]:
        print(f"   {nm:22s} {old} -> {new}  ({w})")


if __name__ == "__main__":
    main()
