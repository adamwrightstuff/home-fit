#!/usr/bin/env python3
"""
Aura flag, offline (owner decision 2026-11-06, replaces the weighted score and the top-5% quota).

Rebuilt on the local scene ladder 2026-11-11 (owner decision: Aura is built on whatever the ladder is).
score["aura"] is True only when ALL of these hold for the stored place:
  1. the local scene ladder level is buzzing (score.local_scene_level; see docs/LOCAL_SCENE_LADDER_DPV2.md);
  2. status class (status_signal_breakdown.archetype) is Affluent or Elite;
  and it is not a job center (more than AURA_MAX_JOBS_PER_RESIDENT workers per resident in the stored LODES radius).
No weights, no quota. Only score["aura"] and score["aura_excluded"] are written.

Usage: PYTHONPATH=. python3 scripts/catalog/apply_aura.py            (every metro)
       PYTHONPATH=. python3 scripts/catalog/apply_aura.py nyc la
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "catalog"))

AURA_CLASSES = ("Affluent", "Elite")
# Judgment call: above ~5 workers per resident a place is a job center, not a neighborhood scene.
# Residential places tested at 0.1 to 1.3; office cores at 7 to 22. Only applied when LODES jobs data
# exists for the place (the table covers only the NYC area, SF Bay and LA).
AURA_MAX_JOBS_PER_RESIDENT = 5.0


def jobs_per_resident(s: dict):
    den = (((s.get("livability_pillars") or {}).get("community_safety") or {}).get("breakdown") or {}).get("population_denominator") or {}
    jobs, res = den.get("workplace_jobs_in_radius"), den.get("residents_in_radius")
    if not isinstance(jobs, (int, float)) or not isinstance(res, (int, float)) or res <= 0:
        return None  # no jobs data: do not exclude
    return jobs / res


def qualifies(s: dict) -> tuple:
    """(is_aura, excluded_reason) from the stored score."""
    cls = (s.get("status_signal_breakdown") or {}).get("archetype")
    if s.get("local_scene_level") != "buzzing":
        return False, None
    if cls not in AURA_CLASSES:
        return False, None
    jpr = jobs_per_resident(s)
    if jpr is not None and jpr > AURA_MAX_JOBS_PER_RESIDENT:
        return False, "job_center"
    return True, None


def process(metro: str) -> None:
    path = ROOT / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    winners = []
    for d in rows:
        s = d.get("score")
        if not d.get("success") or not isinstance(s, dict):
            continue
        ok, why = qualifies(s)
        s["aura"] = ok
        s.pop("aura_excluded", None)
        if why:
            s["aura_excluded"] = why
        if ok:
            winners.append(d)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in rows) + "\n")
    os.replace(tmp, path)  # atomic: a crash mid-write leaves the original file intact
    print(f"{metro}: {len(winners)} Aura of {len(rows)}: {[d['catalog']['name'] for d in winners]}")


if __name__ == "__main__":
    import glob
    metros = sys.argv[1:] or sorted(Path(f).name.split("_metro_")[0] for f in glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")))
    for m in metros:
        process(m)
