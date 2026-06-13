#!/usr/bin/env python3
"""
Offline re-score of Public Transit Access to the v3 subway/commuter-split model.

The v2 model collapsed GTFS route_type 1 (subway, frequent/all-day/walk-to) and
route_type 2 (commuter rail, peak-oriented/often drive-to) into a single "heavy rail"
weight, which underrated subway-rich neighborhoods (Park Slope, Astoria, Jackson Heights
all stuck in the high-70s/low-80s while a single suburban commuter station scored
similarly). v3 weights subway 3 / commuter 1 / light 2 / bus 0.7 on an absolute
log-supply curve (anchor 120), decoupling the urban top from the suburban floor.

No network: route counts are already in each place's stored transit summary. The
subway/commuter split is taken from transit_modes_available ('Subway/Metro' present =>
the heavy-rail routes are subway, else commuter rail). This is exact for pure-subway and
pure-commuter places (~all of the catalog); mixed-mode places (PATH + NJ Transit, etc.)
are approximated toward subway. A live re-fetch would refine only those few.

Transit feeds only total_score (happiness's 'commute' is a separate commute-minutes
channel; longevity/status don't reference transit), so the cascade is pillar
contribution -> total_score_breakdown -> total_score. Writes a .bak alongside each file.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys

import numpy as np

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
ANCHOR = 120.0
RESCORE_VERSION = "transit_v3_subway_commuter_split"


def _supply(weighted: float) -> float:
    if weighted <= 0:
        return 0.0
    return 100.0 * min(1.0, math.log(1.0 + weighted) / math.log(1.0 + ANCHOR))


def split_counts(summary: dict):
    """Return (subway, commuter, light, bus) from a stored transit summary."""
    heavy = summary.get("heavy_rail_routes") or 0
    modes = summary.get("transit_modes_available") or []
    has_subway = "Subway/Metro" in modes
    subway = heavy if has_subway else 0
    commuter = 0 if has_subway else heavy
    light = summary.get("light_rail_routes") or 0
    bus = summary.get("bus_routes") or 0
    return subway, commuter, light, bus


def new_score(summary: dict) -> float:
    sub, com, light, bus = split_counts(summary)
    return _supply(3.0 * sub + 1.0 * com + 2.0 * light + 0.7 * bus)


def apply_cascade(sc: dict) -> tuple[float, float] | None:
    """Mutate one place's score dict in place. Returns (old_pillar, new_pillar) or None."""
    lp = sc.get("livability_pillars", {}).get("public_transit_access")
    if not lp:
        return None
    summary = lp.get("summary", {})
    old = lp["score"]
    new = round(new_score(summary), 1)

    sub, com, light, bus = split_counts(summary)
    summary["subway_routes"] = sub
    summary["commuter_rail_routes"] = com

    # --- pillar ---
    weight = lp["weight"]
    lp["score"] = new
    lp["contribution"] = round(new * weight / 100.0, 4)
    lp["_rescore_version"] = RESCORE_VERSION

    # --- total_score ---
    tsb = sc.get("total_score_breakdown", {}).get("public_transit_access")
    if tsb:
        old_contrib = tsb["contribution"]
        new_contrib = round(new * tsb["weight"] / 100.0, 4)
        tsb["score"] = new
        tsb["contribution"] = new_contrib
        sc["total_score"] = round(sc["total_score"] - old_contrib + new_contrib, 4)

    return old, new


def main():
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            print(f"skip (missing): {fn}", flush=True)
            continue
        shutil.copyfile(fn, fn + ".bak")
        tmp = fn + ".new"
        n_upd = n_skip = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                res = apply_cascade(row.get("score", {}))
                if res:
                    n_upd += 1
                    shifts.append(res[1] - res[0])
                else:
                    n_skip += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: updated={n_upd} skipped={n_skip} (backup: {fn}.bak)", flush=True)
    if shifts:
        sh = np.array(shifts)
        print(f"\nΔ mean={sh.mean():+.1f} median={np.median(sh):+.1f} "
              f"min={sh.min():+.0f} max={sh.max():+.0f} | raised={(sh>0).sum()} lowered={(sh<0).sum()}",
              flush=True)


if __name__ == "__main__":
    main()
