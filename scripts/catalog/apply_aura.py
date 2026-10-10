#!/usr/bin/env python3
"""
Recompute local scene, the Aura score (it_score) and the per-metro Aura flag, offline.

For each metro's composites_recomputed catalog: rescore local scene from the stored business_list,
recompute it_score = 0.50 local scene + 0.35 livability (non-overlapping pillars) + 0.15 SES, then
set score["aura"] = True for places in the top AURA_TOP_PCT of scored places in that metro whose
local scene score is at least AURA_MIN_SCENE and that are not job centers (more than
AURA_MAX_JOBS_PER_RESIDENT jobs per resident in the stored LODES radius). Failing places are dropped, not backfilled.
Metros with fewer than AURA_MIN_METRO_PLACES scored places get no Aura flags (a percentile over a
handful of places is meaningless).

Usage: PYTHONPATH=. python3 scripts/catalog/apply_aura.py nyc la seattle
"""
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "catalog"))

from compute_local_scene import _compute  # noqa: E402
from pillars.composite_indices import compute_aura_score  # noqa: E402

AURA_TOP_PCT = 0.05
AURA_MIN_METRO_PLACES = 20
AURA_MIN_SCENE = 45  # judgment call, not researched: a standout-scene badge needs a real scene
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


def process(metro: str) -> None:
    path = ROOT / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    for d in rows:
        s = d.get("score")
        if not d.get("success") or not isinstance(s, dict):
            continue
        pillars = s.get("livability_pillars") or {}
        biz = (pillars.get("neighborhood_amenities") or {}).get("breakdown", {}).get("business_list") or []
        if biz:
            sc, bucket, sub = _compute(biz)
            s["local_scene_score"], s["local_scene_bucket"], s["local_scene_breakdown"] = sc, bucket, sub
        s["it_score"] = compute_aura_score(s.get("status_signal"), s.get("local_scene_score"), pillars)
        s["aura"] = False
        s.pop("aura_excluded", None)
    scored = [d for d in rows if d.get("success") and isinstance(d.get("score"), dict)
              and isinstance(d["score"].get("it_score"), (int, float))]
    n = math.ceil(len(scored) * AURA_TOP_PCT) if len(scored) >= AURA_MIN_METRO_PLACES else 0
    scored.sort(key=lambda d: -d["score"]["it_score"])
    winners = []
    for d in scored[:n]:
        sc = d["score"]
        if (sc.get("local_scene_score") or 0) < AURA_MIN_SCENE:
            continue
        jpr = jobs_per_resident(sc)
        if jpr is not None and jpr > AURA_MAX_JOBS_PER_RESIDENT:
            sc["aura_excluded"] = "job_center"
            continue
        winners.append(d)
    for d in winners:
        d["score"]["aura"] = True
    path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in rows) + "\n")
    print(f"{metro}: {len(scored)} scored, {len(winners)} Aura (top {n}, scene floor {AURA_MIN_SCENE}, jobs/resident <= {AURA_MAX_JOBS_PER_RESIDENT:g}): {[d['catalog']['name'] for d in winners]}")


if __name__ == "__main__":
    for m in sys.argv[1:] or ["nyc", "la", "seattle"]:
        process(m)
