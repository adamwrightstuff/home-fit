#!/usr/bin/env python3
"""
Fix the commuter-access floor: re-floor using FRESH Census commute + transit share.

BUG: apply_commuter_access_floor.py used each place's STORED Happiness `commute` value for
offline determinism. For ~36% of floored places that stored value was stale (resolved a
different/shorter-commute tract than the live scorer's get_commute_time), inflating their
transit score — Harrison 83.4 (fresh 62), Riverside/Chatham/Pelham Manor +30. The v3 supply
model is unaffected; only the commute INPUT to the floor was stale.

This re-floors every currently-floored place from its v3-supply base (data/*.bakCommute2)
using fresh get_commute_time + get_transit_mode_share — i.e. the SAME inputs the live pillar
uses, so catalog now matches live. floor = _score_commute_time(fresh) * ridership_ramp(share);
transit = max(v3_supply, floor). Cascades total_score. Backup .bakFreshFloor.

Usage: python3 scripts/fix_commuter_floor_fresh.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time  # noqa: E402

from data_sources.census_api import get_commute_time_stable, get_transit_mode_share  # noqa: E402
from pillars.public_transit_access import _score_commute_time  # noqa: E402


def _retry(fn, *a, tries=4):
    """Census times out intermittently; retry so a hiccup never changes a score."""
    for i in range(tries):
        try:
            v = fn(*a)
        except Exception:
            v = None
        if v is not None:
            return v
        time.sleep(1.5 * (i + 1))
    return None

CATALOGS = ["data/nyc_metro_place_catalog_scores_merged.jsonl",
            "data/la_metro_place_catalog_scores_merged.jsonl"]
PILLAR = "public_transit_access"
TAG_OLD = "commuter_access_floor_ridership"
TAG_NEW = "commuter_access_floor_fresh"


def ramp(share):
    return max(0.0, min(1.0, (share - 0.05) / 0.25))


def v3_base(fn):
    base = {}
    bak = fn + ".bakCommute2"
    if os.path.isfile(bak):
        for line in open(bak):
            r = json.loads(line)
            base[r["catalog"]["name"]] = r["score"]["livability_pillars"][PILLAR]["score"]
    return base


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        base = v3_base(fn)
        shutil.copyfile(fn, fn + ".bakFreshFloor")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                cat = row.get("catalog", {})
                nm = cat.get("name", "")
                sc = row.get("score", {})
                ta = sc.get("livability_pillars", {}).get(PILLAR)
                if ta and ta.get("_rescore_version") in (TAG_OLD, TAG_NEW) and nm in base:
                    at = (sc.get("data_quality_summary", {}).get("area_classification", {})
                          .get("effective_area_type"))
                    cm = _retry(get_commute_time_stable, float(cat["lat"]), float(cat["lon"]))
                    sh = _retry(get_transit_mode_share, float(cat["lat"]), float(cat["lon"]))
                    v3 = base[nm]
                    if cm and sh is not None:
                        floor = _score_commute_time(cm, at) * ramp(sh)
                        new = round(max(v3, floor), 1)
                    else:
                        # persistent fetch failure: SKIP — leave current value, never guess
                        print(f"   ⚠️  SKIP {nm} (commute={cm} share={sh}) — left unchanged", flush=True)
                        out.write(json.dumps(row) + "\n")
                        continue
                    old = ta["score"]
                    if abs(new - old) > 0.05:
                        w = ta.get("weight") or 0.0
                        ta["score"] = new
                        ta["contribution"] = round(new * w / 100.0, 4)
                        ta["_rescore_version"] = TAG_NEW
                        s = ta.setdefault("summary", {})
                        s["commute_minutes_fresh"] = round(cm, 1) if cm else None
                        s["transit_mode_share"] = round(sh, 3) if sh is not None else None
                        tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                        if tsb:
                            oc = tsb["contribution"]
                            nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                            tsb["score"] = new
                            tsb["contribution"] = nc
                            sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                        shifts.append((nm, old, new))
                        n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: corrected {n} (backup: {fn}.bakFreshFloor)", flush=True)

    print("\ncorrections (stale -> fresh):")
    for nm, o, nw in sorted(shifts, key=lambda x: x[1] - x[2], reverse=True):
        print(f"   {nm:16s} {o:5.1f} -> {nw:5.1f}  ({nw-o:+.1f})", flush=True)


if __name__ == "__main__":
    main()
