#!/usr/bin/env python3
"""
Apply the commuter-access floor to the catalog's transit scores.

Commuter-rail towns (Pelham, Bronxville, Larchmont, Scarsdale, Rye, ...) are chosen for
ease of commute, but the v3 supply model scored them only on raw route supply (~35-55),
and the station-distance floor in the pillar fails to locate suburban rail stops. The
pillar now floors these places at the Census commute-time score (_score_commute_time) —
the reliable "ease of commute" signal.

That floor value is already stored per place as the Happiness index `commute` component
(identical function + inputs), so this applies the floor OFFLINE and deterministically —
no noisy Transitland re-fetch. For a commuter-only place (commuter_rail_routes > 0,
subway_routes == 0) scoring below its commute-time value, raise the transit score to it and
cascade total_score (transit feeds only total_score).

Backup .bakCommute. Usage: python3 scripts/apply_commuter_access_floor.py
"""
from __future__ import annotations

import json
import os
import shutil

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
PILLAR = "public_transit_access"


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakCommute")
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
                ta = sc.get("livability_pillars", {}).get(PILLAR)
                if ta:
                    summ = ta.get("summary", {}) or {}
                    sub = summ.get("subway_routes")
                    com = summ.get("commuter_rail_routes")
                    commute = (sc.get("happiness_index_breakdown", {}) or {}).get("commute")
                    cur = ta.get("score")
                    # commuter-only place with a stored commute-time signal, scoring below it
                    # Cap at 70 (good-commuter band, below subway hubs); mirrors the pillar.
                    floor = min(70.0, commute) if isinstance(commute, (int, float)) else None
                    if (com and com > 0 and (sub == 0 or sub is None)
                            and floor is not None and cur is not None
                            and cur < 75.0 and floor > cur):
                        new = round(floor, 1)
                        w = ta.get("weight") or 0.0
                        ta["score"] = new
                        ta["contribution"] = round(new * w / 100.0, 4)
                        ta["_rescore_version"] = "commuter_access_floor"
                        tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                        if tsb:
                            oc = tsb["contribution"]
                            nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                            tsb["score"] = new
                            tsb["contribution"] = nc
                            sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                        shifts.append((row.get("catalog", {}).get("name", ""), cur, new))
                        n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: floored {n} commuter places (backup: {fn}.bakCommute)", flush=True)

    print("\nlargest lifts:")
    for nm, o, nw in sorted(shifts, key=lambda x: x[2] - x[1], reverse=True)[:18]:
        print(f"   {nm:22s} {o:5.1f} -> {nw:5.1f}  (+{nw - o:.1f})", flush=True)


if __name__ == "__main__":
    main()
