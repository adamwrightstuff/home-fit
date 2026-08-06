"""
Patch political_lean breakdown for 6 places with empty breakdowns
due to missing precinct data in the state precinct files.

Data source: official 2024 general election results
  - CT: Secretary of State certified results
  - NJ: NJ Division of Elections official results

Short Hills shares Millburn Township results; Old Greenwich shares Greenwich;
Southport shares Fairfield. All town-level data → precinct_count=1, confidence=0.6.

Usage:
    PYTHONPATH=. python3 scripts/manual/patch_political_lean_nulls.py
"""

import json
import os
from pillars.political_lean import lean_label

# Patch data: (dem_2024, rep_2024, lean_2020_approx)
# lean_2020 set equal to lean_2024 — 2020 town-level data not available; trend=0.0
PATCHES = {
    "New Canaan": {
        "dem_2024": 6014, "rep_2024": 4600,
        "note": "CT Secretary of State 2024 certified results",
    },
    "Weston": {
        "dem_2024": 4294, "rep_2024": 1797,
        "note": "CT Secretary of State 2024 certified results",
    },
    "Old Greenwich": {
        # Old Greenwich is within Greenwich Township
        "dem_2024": 19603, "rep_2024": 14122,
        "note": "Greenwich Township CT 2024 certified results (town-level)",
    },
    "Southport": {
        # Southport is within Fairfield Township
        "dem_2024": 21154, "rep_2024": 12523,
        "note": "Fairfield Township CT 2024 certified results (town-level)",
    },
    "Millburn": {
        "dem_2024": 6801, "rep_2024": 3077,
        "note": "Essex County NJ 2024 official general results",
    },
    "Short Hills": {
        # Short Hills is a CDP within Millburn Township
        "dem_2024": 6801, "rep_2024": 3077,
        "note": "Millburn Township NJ 2024 official general results (CDP shares township data)",
    },
}

METRO_FILES = [
    ("data/nyc_metro_place_catalog_scores_merged.jsonl",
     "data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl"),
    ("data/sf_metro_place_catalog_scores_merged.jsonl",
     "data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl"),
    ("data/la_metro_place_catalog_scores_merged.jsonl",
     "data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl"),
]


def build_breakdown(dem: int, rep: int) -> dict:
    total = dem + rep
    lean = (dem - rep) / total
    dem_pct = round(dem / total * 100, 1)
    rep_pct = round(rep / total * 100, 1)
    return {
        "lean_2024": round(lean, 4),
        "lean_2020": round(lean, 4),   # 2020 town-level unavailable; use 2024 as proxy
        "trend": 0.0,
        "label": lean_label(lean),
        "dem_pct_2024": dem_pct,
        "rep_pct_2024": rep_pct,
        "precinct_count": 1,
        "preference": None,
    }


def patch_file(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return {}

    with open(path) as f:
        places = [json.loads(l) for l in f if l.strip()]

    changes = {}
    for p in places:
        name = p.get("catalog", {}).get("name", "")
        if name not in PATCHES:
            continue
        patch = PATCHES[name]
        breakdown = build_breakdown(patch["dem_2024"], patch["rep_2024"])

        pl = p.setdefault("score", {}).setdefault("livability_pillars", {}).setdefault("political_lean", {})
        current_bd = pl.get("breakdown", {})
        if current_bd:
            print(f"  SKIP {name}: already has breakdown data ({current_bd})")
            continue

        pl["breakdown"] = breakdown
        pl["confidence"] = 0.6
        # score is preference-dependent; leave as None (matches scorer behavior without pref)
        pl["score"] = None
        changes[name] = breakdown
        print(f"  Patched {name}: lean_2024={breakdown['lean_2024']:.3f} ({breakdown['label']})"
              f"  [{patch['note']}]")

    if changes:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            for p in places:
                f.write(json.dumps(p) + "\n")
        os.replace(tmp, path)
        print(f"  Wrote {path} ({len(changes)} change(s))")
    else:
        print(f"  No changes in {path}")

    return changes


def main():
    for merged, recomputed in METRO_FILES:
        for path in (merged, recomputed):
            if not os.path.exists(path):
                continue
            print(f"\n{path}:")
            patch_file(path)


if __name__ == "__main__":
    main()
