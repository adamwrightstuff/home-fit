#!/usr/bin/env python3
"""
Offline: treat IRS nonprofit data as missing (not zero) for catalog places in states the IRS tract files do not cover.

The IRS tract-count files have no tracts for DE, DC, IL, IN, IA, KY, MD, MI, MN, NC, OH, PA, SC, VA, WV, WI (and
almost none for NE, ND, SD), so those places were scored as "zero nonprofits", which put a near-constant IRS slot
score (about 46) into participation. Now participation uses volunteering and the Atlas civic-organization rate only.

No API calls. The stored participation was built as
    s = 0.5 x irs_slot + 0.5 x volunteering,   e = 0.65 x s + 0.35 x atlas_civic_orgs
so volunteering is recovered as v = 2 s - irs_slot (irs_slot is the slot for a rate of 0 against the place's
area-type baseline) and the new participation is 0.65 v + 0.35 atlas. The stability score is recovered from the
stored pillar score and weights_used. A place is skipped (and listed) if its stored rate is not 0, if the atlas
score is missing, or if the recovered volunteering is outside 0-100. Run recompute_catalog_composites.py
--no-census on the changed rows afterwards (longevity, happiness, aura).

  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_irs_coverage_offline.py                 # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_irs_coverage_offline.py --write --backup-dir <dir>
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
from data_sources import irs_bmf  # noqa: E402
from data_sources.community_participation import _rate_to_z_score  # noqa: E402
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402

ABBREV_TO_FIPS = {v: k for k, v in irs_bmf.STATE_FIPS_TO_ABBREV_IRS.items()}


def recompute(score: dict, state_abbr: str):
    fips = ABBREV_TO_FIPS.get(state_abbr or "")
    if not fips or irs_bmf.state_has_coverage(fips, either=True):
        return "covered"
    sf = (score.get("livability_pillars") or {}).get("social_fabric")
    if not sf or not isinstance(sf.get("score"), (int, float)):
        return "no_pillar"
    b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
    if s.get("participation_mix") != "full":
        return "mix_not_full"
    if s.get("orgs_per_1k") != 0:
        return "rate_not_zero"
    atlas, e_old = s.get("atlas_civic_orgs_score"), b.get("participation")
    if e_old is None:
        return "no_participation"
    at = (sf.get("area_classification") or {}).get("area_type")
    stats = irs_bmf._pick_engagement_stats(None, at, use_legacy=False)
    if not stats or not stats.get("std"):
        return "no_baseline"
    irs_slot = _rate_to_z_score(0.0, float(stats["mean"]), float(stats["std"]))
    s_old = (e_old - 0.35 * atlas) / 0.65 if atlas is not None else e_old
    vol = 2.0 * s_old - irs_slot
    if not -1.0 <= vol <= 101.0:
        return "volunteering_out_of_range"
    vol = max(0.0, min(100.0, vol))
    e_new = 0.65 * vol + 0.35 * atlas if atlas is not None else vol

    w = s.get("weights_used") or {}
    others = {"cohesion": b.get("social_capital"), "civic": b.get("peer_civic") or None}
    stab = None
    if "rootedness" in w:
        rest = w.get("participation", 0.0) * e_old + sum(w[k] * v for k, v in others.items() if k in w and v is not None)
        stab = (sf["score"] - rest) / w["rootedness"]
        if not -2.0 <= stab <= 102.0:
            return "stability_reconstruction_failed"
    new, weights, _ = blend_social_fabric(participation=e_new, cohesion=others["cohesion"], rootedness=stab,
                                          civic=others["civic"])
    old = sf["score"]
    b["participation"] = round(e_new, 1)
    s["orgs_per_1k"] = None
    s["participation_mix"] = "vol_only"
    s["irs_bmf_status"] = "no_state_coverage"
    s["weights_used"] = {k: round(v, 4) for k, v in weights.items()}
    sf["breakdown"], sf["summary"] = b, s
    dq = sf.get("data_quality") or {}
    dq["degraded"] = True
    dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or [])
                                                + [f"social_fabric_irs_bmf_unavailable: no_state_coverage (state FIPS {fips})"]))
    sf["data_quality"] = dq
    sf["score"] = new
    if isinstance(sf.get("weight"), (int, float)):
        sf["contribution"] = round(sf["weight"] * new / 100.0, 4)
    return old, new, e_old, e_new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    changed, skipped = 0, {}
    dS, dE, dT, per_state = [], [], [], {}
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
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            P = s.get("livability_pillars") or {}
            sf = P.get("social_fabric")
            if not sf:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            snap = json.loads(json.dumps(sf))
            res = recompute(s, cat.get("state_abbr"))
            if isinstance(res, str):
                if res != "covered":
                    skipped.setdefault(res, []).append(f"{metro}|{cat.get('name')}")
                out.append(line)
                continue
            old, new, e_old, e_new = res
            tb = (s.get("total_score_breakdown") or {}).get("social_fabric")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = sf["score"], sf["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
                dT.append(s["total_score"] - old_total)
            changed += 1
            dS.append(new - old)
            dE.append(e_new - e_old)
            per_state[cat.get("state_abbr")] = per_state.get(cat.get("state_abbr"), 0) + 1
            old_vals[f"{metro}|{cat.get('name')}"] = {"social_fabric": snap, "total_score": old_total}
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
    print("places changed:", changed, per_state)
    print("skipped:", {k: len(v) for k, v in skipped.items()})
    for k, v in skipped.items():
        print("  ", k, v[:5])
    if dS:
        print("participation delta mean %.2f min %.1f max %.1f | social fabric score delta mean %.2f min %.1f max %.1f, |delta|>2: %d | total_score delta mean %.3f min %.2f max %.2f" % (
            st.mean(dE), min(dE), max(dE), st.mean(dS), min(dS), max(dS), sum(abs(x) > 2 for x in dS), st.mean(dT), min(dT), max(dT)))


if __name__ == "__main__":
    main()
