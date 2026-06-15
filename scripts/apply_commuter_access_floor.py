#!/usr/bin/env python3
"""
Apply the (ridership-weighted) commuter-access floor to the catalog's transit scores.

Commuter-rail towns (Pelham, Bronxville, Larchmont, Scarsdale, Rye, Darien, ...) are chosen
for ease of commute, but the v3 supply model scored them only on raw route supply (~35-55).
The pillar floors them at their commute-quality score WEIGHTED by actual transit ridership
(tract-level ACS B08301): a short *car* commute earns no transit credit, a town where people
genuinely take the train does. Ramp 0->1 between 5% and 30% transit share. No artificial cap —
share x commute-quality is self-limiting and stays below subway hubs.

Inputs:
  - commute-quality score: already stored as each place's Happiness `commute` component
    (same _score_commute_time function/inputs).
  - transit share: fetched per place via census_api.get_transit_mode_share (tract-level,
    reliable — NOT the noisy Transitland path; see [[transit-fetch-noisy]]).

Applies as a FLOOR over the stored v3 supply score; cascades total_score (transit feeds only
total_score). Run on the v3-supply base (restore *.bakCommute first if re-running).
Backup .bakCommute2. Usage: python3 scripts/apply_commuter_access_floor.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.census_api import get_transit_mode_share  # noqa: E402

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
PILLAR = "public_transit_access"
SHARE_RAMP_LO = 0.05   # below this transit share -> no transit credit (car town)
SHARE_RAMP_HI = 0.30   # at/above this -> full commute-quality credit
THROTTLE = 0.15


def ramp(share: float) -> float:
    return max(0.0, min(1.0, (share - SHARE_RAMP_LO) / (SHARE_RAMP_HI - SHARE_RAMP_LO)))


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakCommute2")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                sc = row.get("score", {})
                cat = row.get("catalog", {})
                ta = sc.get("livability_pillars", {}).get(PILLAR)
                if ta:
                    summ = ta.get("summary", {}) or {}
                    sub = summ.get("subway_routes")
                    com = summ.get("commuter_rail_routes")
                    commute = (sc.get("happiness_index_breakdown", {}) or {}).get("commute")
                    cur = ta.get("score")
                    if (com and com > 0 and (sub == 0 or sub is None)
                            and isinstance(commute, (int, float)) and cur is not None
                            and cur < 85.0):
                        try:
                            share = get_transit_mode_share(float(cat["lat"]), float(cat["lon"]))
                        except Exception:
                            share = None
                        time.sleep(THROTTLE)
                        if share is not None:
                            credit = round(commute * ramp(share), 1)
                            if credit > cur:
                                w = ta.get("weight") or 0.0
                                ta["score"] = credit
                                ta["contribution"] = round(credit * w / 100.0, 4)
                                ta["_rescore_version"] = "commuter_access_floor_ridership"
                                summ["transit_mode_share"] = round(share, 3)
                                tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                                if tsb:
                                    oc = tsb["contribution"]
                                    nc = round(credit * (tsb.get("weight") or 0.0) / 100.0, 4)
                                    tsb["score"] = credit
                                    tsb["contribution"] = nc
                                    sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                                shifts.append((cat.get("name", ""), cur, credit, share))
                                n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: floored {n} commuter places (backup: {fn}.bakCommute2)", flush=True)

    print("\nlifts (ridership-weighted):")
    for nm, o, nw, sh in sorted(shifts, key=lambda x: x[2] - x[1], reverse=True)[:20]:
        print(f"   {nm:22s} {o:5.1f} -> {nw:5.1f}  (share {sh*100:.0f}%)", flush=True)


if __name__ == "__main__":
    main()
