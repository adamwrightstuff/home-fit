#!/usr/bin/env python3
"""
Offline: apply the fail-loud social fabric blend (pillars/social_fabric_blend.py) to stored catalog rows.

Before 2026-10-24 a missing component was handled by handing its weight to participation (cohesion
missing: participation 0.80; civic nodes zero: 0.70) and a missing stability reading was scored as 0 at
weight 0.10. Now the remaining base weights (participation 0.60, cohesion 0.20, rootedness 0.10, civic
0.10) are scaled proportionally and the pillar is marked degraded with the reason.

No API calls. The stability score is not stored, so it is recovered from the stored score and the old
weights: stability = (score - old_weights . other components) / 0.10 (accurate to +-0.5 because the stored
score is rounded to 0.1; the effect on the new score is under 0.07). Only places with a missing component
change score; every place gets summary.weights_used / components_missing and, where data is missing or
the civic read is implausibly thin, a degraded flag. Run recompute_catalog_composites.py --in-place
--no-census afterwards for the composites that read social fabric (longevity, local scene, aura).

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_failloud_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_failloud_offline.py --write --backup-dir <dir>
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
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402


def recompute(score: dict):
    sf = (score.get("livability_pillars") or {}).get("social_fabric")
    if not sf or not isinstance(sf.get("score"), (int, float)):
        return None
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    part, coh = b.get("participation"), b.get("social_capital")
    civ = b.get("peer_civic") or 0.0
    stab_none = s.get("stability_tract_input") == "none"
    # old weights, exactly as the retired code applied them
    w_sc = 0.20 if coh is not None else 0.0
    w_civ = 0.10 if civ > 0 else 0.0
    w_part = 1.0 - w_sc - w_civ - 0.10
    old = sf["score"]
    stab = None if stab_none else (old - (w_sc * (coh or 0.0) + w_civ * civ + w_part * (part or 0.0))) / 0.10
    if stab is not None and not -2.0 <= stab <= 102.0:
        return "reconstruction_failed"
    new, weights, _ = blend_social_fabric(participation=part, cohesion=coh, rootedness=stab, civic=civ if civ > 0 else None)
    missing = {}
    if coh is None:
        missing["cohesion"] = "atlas_zip_not_found"
    if stab_none:
        missing["rootedness"] = "no_tract_or_place_mobility_data"
    if civ <= 0:
        missing["civic"] = "osm_error" if (sf.get("source_status") or {}).get("civic_osm") == "error" else "no_civic_nodes_found"
    reasons = [f"social_fabric_{k}_missing: {v}" for k, v in missing.items() if not (k == "civic" and v == "no_civic_nodes_found")]
    if s.get("civic_reliability") == "suspect_thin" and "civic" not in missing:
        reasons.append("social_fabric_civic_suspect_thin: OSM civic count implausibly low for the density")
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    s["components_missing"] = missing
    sf["summary"] = s
    if reasons:
        dq = sf.get("data_quality") or {}
        dq["degraded"] = True
        dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + reasons))
        sf["data_quality"] = dq
    sf["score"] = new
    if isinstance(sf.get("weight"), (int, float)):
        sf["contribution"] = round(sf["weight"] * new / 100.0, 4)
    return old, new, bool(reasons)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    rows = changed_score = flagged = failed = 0
    deltas, tdeltas = [], []
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
            sf = (s.get("livability_pillars") or {}).get("social_fabric")
            if not sf or not isinstance(sf.get("score"), (int, float)):
                out.append(line)
                continue
            P = s["livability_pillars"]
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(sf))
            res = recompute(s)
            if res == "reconstruction_failed" or res is None:
                failed += 1
                out.append(line)
                continue
            old, new, flag = res
            rows += 1
            flagged += flag
            tb = (s.get("total_score_breakdown") or {}).get("social_fabric")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = sf["score"], sf["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                tdeltas.append(s["total_score"] - old_total)
            if abs(new - old) > 1e-9:
                changed_score += 1
                deltas.append(new - old)
            cat = rec.get("catalog")
            old_vals[f"{metro}|{(cat or {}).get('name') if isinstance(cat, dict) else s.get('input')}"] = {
                "social_fabric": snap, "total_score": old_total}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_social_fabric_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print(f"rows processed {rows} | score changed {changed_score} | newly flagged degraded {flagged} | reconstruction failed {failed}")
    if deltas:
        print("social fabric score delta (changed rows): mean %.2f min %.1f max %.1f | total_score delta mean %.3f min %.2f max %.2f" % (
            st.mean(deltas), min(deltas), max(deltas), st.mean(tdeltas), min(tdeltas), max(tdeltas)))


if __name__ == "__main__":
    main()
