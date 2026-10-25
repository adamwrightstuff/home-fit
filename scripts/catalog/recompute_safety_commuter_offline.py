#!/usr/bin/env python3
"""
Offline: fix the commuter (people-present) adjustment in community_safety rows for neighborhood-circle places.

Two cases among rows stored with workplace_jobs_in_radius == 0 and resident_workers_in_radius == 0:
  * The LODES commuter grid now has cells there (Austin: Texas was added after these rows were scored): the rates are
    rescaled to the new ambient population = residents + 45/168 x (workplace jobs - resident workers). Rates per 1,000
    are linear in 1 / population, so new_rate = stored_rate x old_ambient / new_ambient (exact), and the score is
    rebuilt with the live _score_rates and trend delta. A row is skipped (and listed) unless the stored rates reproduce the
    stored raw_score under the current scale.
  * The grid has no cell near the place (Illinois, most of Pennsylvania): the adjustment is unavailable, not zero. The
    zeros are removed, commuter_adjustment is set to "unavailable", the pillar is marked degraded; the score is unchanged.
No API calls. Run recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 scripts/catalog/recompute_safety_commuter_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_safety_commuter_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data_sources.lodes_h8_commuter_context import jobs_in_disk  # noqa: E402
from data_sources.people_present import people_present  # noqa: E402
from pillars.community_safety import _score_rates, _trend_delta  # noqa: E402

REASON = "community_safety_commuter_adjustment_unavailable: no LODES grid cells near the place"


def area_type_of(score: dict):
    for k in ("active_outdoors", "climate_risk", "diversity", "social_fabric", "housing_value", "healthcare_access"):
        at = ((score.get("livability_pillars") or {}).get(k) or {}).get("area_classification", {}).get("area_type")
        if at:
            return at
    return None


def process(score: dict, state=None):
    """(status, detail) where status is skipped:<why>, unavailable, or recomputed."""
    P = score.get("livability_pillars") or {}
    cs = P.get("community_safety")
    if not cs or not isinstance(cs.get("score"), (int, float)):
        return None
    b = cs.get("breakdown") or {}
    pd = b.get("population_denominator") or {}
    if pd.get("population_denominator_method") != "ambient_residents_plus_workers":
        return None
    if not (pd.get("workplace_jobs_in_radius") == 0 and pd.get("resident_workers_in_radius") == 0):
        return None
    co = score.get("coordinates") or {}
    radius = pd.get("population_denominator_radius_m")
    jobs = jobs_in_disk(co["lat"], co["lon"], radius, state=state) if radius and co.get("lat") is not None else None
    dq = cs.get("data_quality") or {}
    if jobs is None:
        pd.pop("workplace_jobs_in_radius", None)
        pd.pop("resident_workers_in_radius", None)
        pd["commuter_adjustment"] = "unavailable"
        dq["degraded"] = True
        dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + [REASON]))
        cs["data_quality"], b["population_denominator"], cs["breakdown"] = dq, pd, b
        return "unavailable", None
    residents, old_amb = pd.get("residents_in_radius"), pd.get("ambient_population")
    area = area_type_of(score)
    if not residents or not old_amb or not area:
        return "skipped:missing_inputs", None
    v_old, p_old = b.get("violent_per_1k"), b.get("property_per_1k")
    chk = _score_rates(v_old, p_old, area)
    if abs(round(chk[2], 1) - b.get("raw_score", -999)) > 0.11:
        return "skipped:stored_rates_do_not_reproduce_the_score", None
    new_amb = max(1, int(round(people_present(residents, jobs[0], jobs[1]))))
    f = old_amb / new_amb
    v_new, p_new = v_old * f, p_old * f
    v_slot, p_slot, raw, _ = _score_rates(v_new, p_new, area)
    final = round(max(0.0, min(100.0, raw + _trend_delta(b.get("trend_pct")))), 1)
    old = cs["score"]
    b.update({"violent_per_1k": round(v_new, 3), "property_per_1k": round(p_new, 3), "violent_slot": round(v_slot, 1),
              "property_slot": round(p_slot, 1), "raw_score": round(raw, 1)})
    pd.update({"workplace_jobs_in_radius": int(round(jobs[0])), "resident_workers_in_radius": int(round(jobs[1])),
               "ambient_population": new_amb, "commuter_adjustment": "applied"})
    b["population_denominator"] = pd
    cs["breakdown"], cs["score"] = b, final
    if isinstance(cs.get("weight"), (int, float)):
        cs["contribution"] = round(cs["weight"] * final / 100.0, 4)
    return "recomputed", (old, final, new_amb / old_amb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    counts, skipped, deltas, ratios, tdeltas = {}, [], [], [], []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            cs = P.get("community_safety")
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(cs)) if cs else None
            res = process(s, (rec.get("catalog") or {}).get("state_abbr")) if cs else None
            if not res:
                out.append(line)
                continue
            status, detail = res
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            counts[(metro, status)] = counts.get((metro, status), 0) + 1
            if status.startswith("skipped"):
                skipped.append(f"{metro}|{cat.get('name')}|{status}")
                out.append(line)
                continue
            if status == "recomputed":
                deltas.append(detail[1] - detail[0])
                ratios.append(detail[2])
                tb = (s.get("total_score_breakdown") or {}).get("community_safety")
                if isinstance(tb, dict):
                    tb["score"], tb["contribution"] = cs["score"], cs["contribution"]
                new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
                if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                    s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                    tdeltas.append(s["total_score"] - old_total)
            old_vals[f"{metro}|{cat.get('name')}"] = {"community_safety": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_safety_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print("by metro and status:", {f"{m}:{s}": n for (m, s), n in sorted(counts.items())})
    print("skipped:", skipped[:6], len(skipped))
    if deltas:
        print("recomputed: score delta mean %.2f min %.1f max %.1f | ambient/old ratio median %.2f max %.2f | total_score delta mean %.3f min %.2f max %.2f" % (
            st.mean(deltas), min(deltas), max(deltas), st.median(ratios), max(ratios), st.mean(tdeltas) if tdeltas else 0, min(tdeltas, default=0), max(tdeltas, default=0)))


if __name__ == "__main__":
    main()
