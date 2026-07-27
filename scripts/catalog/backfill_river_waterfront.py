"""
Offline backfill: inject river/waterway scores for places where AO waterfront_lifestyle=0
but NB data confirms nearby water.

Uses NB v9_breakdown.inputs.water_type and water_dist_km — no new OSM calls.

Placement rule:
  water_type = "river" or "ocean" (tidal river/estuary, OSM tags as coastline)
      → inject as lake_river, base = 18.0
  water_type = "bay"
      → inject as bay_harbor, base = 12.0

Area-type modifier (matches AO live scorer):
  urban_core: base *= 0.4  (lake_river)
  suburban / urban_residential: base unchanged for lake type (no 0.9 penalty)
  others: base unchanged

Distance decay (>3km): base *= exp(-0.00025 * (dist_m - 3000))

Excluded places (separate bug, genuine ocean features missing from Overpass query):
  Brighton Beach, Santa Monica

Writes updated JSONL files in-place (backup written alongside).
"""

import json
import math
import shutil
from pathlib import Path

SKIP_NAMES = {"Brighton Beach", "Santa Monica"}

# base scores matching _WATERFRONT_BASE in active_outdoors.py
BASE_LAKE_RIVER = 18.0
BASE_BAY_HARBOR = 12.0

CATALOGS = [
    Path("data/nyc_metro_place_catalog_scores_merged.jsonl"),
    Path("data/la_metro_place_catalog_scores_merged.jsonl"),
]


def area_type_modifier(water_type_category: str, area_type: str) -> float:
    """Apply the same area-type modifier the live scorer applies to non-beach features."""
    if water_type_category == "lake_river":
        # In live scorer: lake type skips the 0.9 penalty for suburban/urban_residential
        if area_type == "urban_core":
            return 0.4
        return 1.0
    else:  # bay_harbor
        if area_type == "urban_core":
            return 0.4
        if area_type in ("suburban", "urban_residential"):
            return 0.9
        return 1.0


def compute_raw_score(base: float, dist_km: float, area_type: str, category: str) -> float:
    dist_m = dist_km * 1000.0
    score = base * area_type_modifier(category, area_type)
    if dist_m > 3_000:
        score *= math.exp(-0.00025 * (dist_m - 3_000))
    return score


def process_place(p: dict) -> tuple[bool, str]:
    """
    Attempt to inject river waterfront score.
    Returns (changed, reason).
    """
    name = p.get("catalog", {}).get("name", "?")

    if name in SKIP_NAMES:
        return False, "skip-list"

    ao = p["score"]["livability_pillars"]["active_outdoors"]
    bd = ao.get("breakdown") or {}
    wf = bd.get("waterfront_lifestyle", None)
    if wf != 0.0:
        return False, f"wf={wf} (not 0)"

    # area_type from AO classification
    area_class = ao.get("area_classification") or {}
    area_type = area_class.get("area_type", "suburban")

    # NB water data
    nb = p["score"]["livability_pillars"].get("neighborhood_beauty", {})
    details = (nb.get("details") or {})
    natb = details.get("natural_beauty") or {}
    v9 = natb.get("v9_breakdown") or {}
    inp = v9.get("inputs") or {}
    water_type = inp.get("water_type")
    water_dist_km = inp.get("water_dist_km")

    if water_dist_km is None or water_dist_km > 6.0:
        return False, f"no nearby NB water (dist={water_dist_km})"

    # Determine category
    if water_type in ("river", "ocean"):
        category = "lake_river"
        base = BASE_LAKE_RIVER
    elif water_type == "bay":
        category = "bay_harbor"
        base = BASE_BAY_HARBOR
    else:
        return False, f"water_type={water_type!r} not actionable"

    raw = compute_raw_score(base, water_dist_km, area_type, category)
    new_wf = round(min(25.0, raw), 1)
    if new_wf <= 0:
        return False, "computed score = 0"

    # Normalized breakdown value (0-100 scale)
    norm_val = round(min(100.0, raw / 25.0 * 100.0), 1)

    # Update breakdown
    wfb = bd.get("waterfront_breakdown") or {"ocean_beach": 0.0, "lake_river": 0.0, "bay_harbor": 0.0}
    wfb[category] = norm_val
    bd["waterfront_lifestyle"] = new_wf
    bd["waterfront_breakdown"] = wfb

    # Recompute AO score
    daily = bd.get("daily_urban_outdoors", 0) or 0
    wild = bd.get("wild_adventure", 0) or 0
    old_ao_score = ao.get("score") or 0
    new_ao_score = round(min(100.0, daily + wild + new_wf), 1)
    delta = round(new_ao_score - old_ao_score, 4)

    ao["score"] = new_ao_score

    # Update contribution and total_score where data is clean
    weight = ao.get("weight")
    old_contrib = ao.get("contribution")
    if weight is not None and old_contrib is not None:
        new_contrib = round(old_contrib + delta * weight / 100.0, 4)
        ao["contribution"] = new_contrib

        ts_ao = p["score"]["total_score_breakdown"].get("active_outdoors", {})
        if isinstance(ts_ao, dict):
            ts_ao["score"] = new_ao_score
            old_ts_contrib = ts_ao.get("contribution")
            if old_ts_contrib is not None:
                ts_ao["contribution"] = new_contrib
        p["score"]["total_score"] = round(
            (p["score"]["total_score"] or 0) + delta * weight / 100.0, 4
        )
    else:
        # No contribution data — update score and TS score only
        ts_ao = p["score"]["total_score_breakdown"].get("active_outdoors", {})
        if isinstance(ts_ao, dict):
            ts_ao["score"] = new_ao_score

    return True, (
        f"wf 0→{new_wf} ({category}, dist={water_dist_km}km, area={area_type})"
        f"  AO {old_ao_score}→{new_ao_score}"
    )


def process_catalog(path: Path) -> int:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    changed = 0
    print(f"\n{'='*60}")
    print(f"  {path.name}  ({len(rows)} places)")
    print(f"{'='*60}")

    for p in rows:
        ok, reason = process_place(p)
        name = p.get("catalog", {}).get("name", "?")
        if ok:
            changed += 1
            print(f"  [UPDATED] {name}: {reason}")
        # else: silent skip

    if changed:
        backup = path.with_suffix(".jsonl.bak")
        shutil.copy2(path, backup)
        print(f"\n  Backup → {backup.name}")
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"  Wrote {path.name}  ({changed} places updated)")
    else:
        print(f"  No changes.")

    return changed


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent.parent)  # repo root

    total = 0
    for cat in CATALOGS:
        total += process_catalog(cat)
    print(f"\nTotal places updated: {total}")
