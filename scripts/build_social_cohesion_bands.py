#!/usr/bin/env python3
"""
Build area-type cohesion bands for Social Fabric from the Social Capital Atlas.

The Atlas (Chetty et al. 2022, 21B Facebook friendships) measures network cohesion
directly at ZIP level. Urban networks are structurally ~25% less clustered than
suburban/rural ones, so a single national curve mis-ranks dense neighborhoods.
We grade each place against its area-type peers instead.

Steps:
  1. ZCTA land area (sq mi) from the Census ZCTA->tract crosswalk.
  2. ZIP density = pop2018 / land_area -> area_type via classify_area_by_density.
  3. Per-area-type quantile bands for clustering_zip, support_ratio_zip,
     civic_organizations_zip.

Outputs data/social_cohesion_bands.json.
"""
from __future__ import annotations

import csv
import json
import os

import numpy as np

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCA = os.path.join(_BASE, "data", "social_capital_zip.csv")
_XWALK = os.path.join(_BASE, "data", "crosswalks", "tab20_zcta520_tract20_natl.txt")
_OUT = os.path.join(_BASE, "data", "social_cohesion_bands.json")

_SQM_PER_SQMI = 2_589_988.11


def classify_area_type(density: float) -> str:
    if density >= 10_000:
        return "urban_core"
    if density >= 5_000:
        return "urban_residential"
    if density >= 2_500:
        return "suburban"
    if density >= 1_000:
        return "exurban"
    return "rural"


def load_zcta_land_sqmi() -> dict:
    """GEOID_ZCTA5_20 -> land area (sq mi). One row per ZCTA suffices for the area."""
    land: dict = {}
    with open(_XWALK, encoding="utf-8-sig") as f:
        r = csv.DictReader(f, delimiter="|")
        for row in r:
            z = (row.get("GEOID_ZCTA5_20") or "").strip()
            a = row.get("AREALAND_ZCTA5_20") or ""
            if not z or not a:
                continue
            try:
                land[z.zfill(5)] = float(a) / _SQM_PER_SQMI
            except ValueError:
                continue
    return land


def fval(row: dict, key: str):
    v = row.get(key, "")
    if v in (None, "", "NA"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def main() -> None:
    land = load_zcta_land_sqmi()
    print(f"Loaded land area for {len(land)} ZCTAs")

    buckets: dict = {}  # area_type -> {metric -> [values]}
    metrics = ("clustering_zip", "support_ratio_zip", "civic_organizations_zip")
    matched = 0
    with open(_SCA, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            z = (row.get("zip") or "").strip().zfill(5)
            pop = fval(row, "pop2018")
            area = land.get(z)
            if not z or pop is None or not area or area <= 0:
                continue
            density = pop / area
            at = classify_area_type(density)
            matched += 1
            b = buckets.setdefault(at, {m: [] for m in metrics})
            for m in metrics:
                v = fval(row, m)
                if v is not None:
                    b[m].append(v)

    print(f"Matched {matched} ZIPs to density/area_type")

    out = {
        "schema_version": 1,
        "description": (
            "Area-type quantile bands for Social Capital Atlas cohesion metrics "
            "(clustering, support ratio, civic organizations). Grades each place "
            "against its morphological peers so urban networks aren't penalized "
            "for structurally lower clustering."
        ),
        "score_anchors": {"at_knot": [12, 30, 50, 70, 85]},
        "by_area_type": {},
    }
    pcts = [10, 25, 50, 75, 90]
    for at, mdict in sorted(buckets.items()):
        out["by_area_type"][at] = {}
        for m, vals in mdict.items():
            if len(vals) < 30:
                continue
            arr = np.array(vals)
            out["by_area_type"][at][m] = {
                f"p{p}": round(float(np.percentile(arr, p)), 6) for p in pcts
            }
            out["by_area_type"][at][m]["n"] = len(vals)

    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {_OUT}")

    # Quick readout
    for at in ("urban_core", "urban_residential", "suburban", "exurban", "rural"):
        c = out["by_area_type"].get(at, {}).get("clustering_zip")
        if c:
            print(f"  {at:18s} clustering p25={c['p25']} p50={c['p50']} p75={c['p75']} (n={c['n']})")


if __name__ == "__main__":
    main()
