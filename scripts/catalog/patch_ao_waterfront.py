"""
Targeted AO waterfront patches:

1. Brighton Beach — Overpass missed the ocean beach entirely (wf=0).
   NB confirms ocean at 0.66km. Inject base=25.0, no decay, ocean_beach.

2. Prospect Heights — park beach (Prospect Park) misclassified as ocean_beach.
   Prior inland-beach fix missed it because NB water_type='ocean' (Upper NY Bay).
   Downgrade 25→22 (swimming_area level), reclassify ocean_beach→lake_river.

3. Windsor Terrace — same issue as Prospect Heights.
"""

import json
import math
import shutil
from pathlib import Path

NYC = Path("data/nyc_metro_place_catalog_scores_merged.jsonl")

PATCHES = {
    "Brighton Beach": {
        "action": "inject_ocean_beach",
        "wf_raw": 25.0,
        "ob_norm": 100.0,
    },
    "Prospect Heights": {
        "action": "downgrade_to_lake_river",
    },
    "Windsor Terrace": {
        "action": "downgrade_to_lake_river",
    },
}


def _update_score(p: dict, ao: dict, old_ao_score: float, new_wf: float) -> None:
    daily = ao["breakdown"].get("daily_urban_outdoors", 0) or 0
    wild = ao["breakdown"].get("wild_adventure", 0) or 0
    new_ao_score = round(min(100.0, daily + wild + new_wf), 1)
    delta = round(new_ao_score - old_ao_score, 4)
    ao["score"] = new_ao_score

    weight = ao.get("weight")
    old_contrib = ao.get("contribution")
    if weight is not None and old_contrib is not None:
        new_contrib = round(old_contrib + delta * weight / 100.0, 4)
        ao["contribution"] = new_contrib
        ts_ao = p["score"]["total_score_breakdown"].get("active_outdoors", {})
        if isinstance(ts_ao, dict):
            ts_ao["score"] = new_ao_score
            if ts_ao.get("contribution") is not None:
                ts_ao["contribution"] = new_contrib
        p["score"]["total_score"] = round((p["score"].get("total_score") or 0) + delta * weight / 100.0, 4)
    else:
        ts_ao = p["score"]["total_score_breakdown"].get("active_outdoors", {})
        if isinstance(ts_ao, dict):
            ts_ao["score"] = new_ao_score


def process(rows: list) -> list[str]:
    log = []
    for p in rows:
        name = p.get("catalog", {}).get("name", "?")
        if name not in PATCHES:
            continue
        patch = PATCHES[name]
        ao = p["score"]["livability_pillars"]["active_outdoors"]
        bk = ao.get("breakdown") or {}
        old_ao = ao.get("score") or 0
        old_wf = bk.get("waterfront_lifestyle", 0) or 0

        if patch["action"] == "inject_ocean_beach":
            new_wf = patch["wf_raw"]
            bk["waterfront_lifestyle"] = new_wf
            bk["waterfront_breakdown"] = {
                "ocean_beach": patch["ob_norm"],
                "lake_river": 0.0,
                "bay_harbor": 0.0,
            }
            ao["breakdown"] = bk
            _update_score(p, ao, old_ao, new_wf)
            log.append(f"{name}: injected ocean_beach wf=0→{new_wf}, AO {old_ao}→{ao['score']}")

        elif patch["action"] == "downgrade_to_lake_river":
            new_wf = round(old_wf * 22.0 / 25.0, 1)
            norm = round(new_wf / 25.0 * 100.0, 1)
            bk["waterfront_lifestyle"] = new_wf
            bk["waterfront_breakdown"] = {
                "ocean_beach": 0.0,
                "lake_river": norm,
                "bay_harbor": 0.0,
            }
            ao["breakdown"] = bk
            _update_score(p, ao, old_ao, new_wf)
            log.append(f"{name}: ocean_beach→lake_river wf={old_wf}→{new_wf}, AO {old_ao}→{ao['score']}")

    return log


def main():
    rows = []
    with open(NYC) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    log = process(rows)
    if not log:
        print("No changes.")
        return

    backup = NYC.with_suffix(".jsonl.wf_patch.bak")
    shutil.copy2(NYC, backup)
    with open(NYC, "w") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    print(f"Backup → {backup.name}")
    for line in log:
        print(f"  {line}")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent.parent)
    main()
