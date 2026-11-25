#!/usr/bin/env python3
"""
Social Fabric pin-shift sensitivity (DPv2 principle 6). LIVE Census calls (geocoder + ACS); needs CENSUS_API_KEY.

For a stratified sample of catalog places, re-reads the tract-based input (rootedness: pin tract 0.7 + place 0.3) at the pin
and at four pins SHIFT_M metres north, south, east and west, re-blends with the stored participation, cohesion and economic
connectedness (ZIP-based, so NOT tested here), and reports score change versus the unshifted re-read. The above-85% home-value
cliff exemption is skipped (one extra call per place); places above 85% are counted separately.
Pass rule fixed 2026-11-03: median change 3 points or less, p95 10 or less at 400 m.

  CENSUS_API_KEY=... PYTHONPATH=. python3 scripts/catalog/social_fabric_pin_shift.py --per-type 20 --out analysis/sf_pin_shift.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data_sources import census_api, social_fabric_bands  # noqa: E402
from data_sources.us_census_divisions import get_division  # noqa: E402
from pillars.social_fabric_blend import blend_social_fabric  # noqa: E402

SHIFT_M = 400.0
_FIPS_ABBR = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
              "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
              "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
              "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
              "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}


def rooted_at(lat, lon, bands):
    """(stability_pct, stability_score) from the pin tract and place, as in the live pillar."""
    tract = census_api.get_census_tract(lat, lon)
    if not tract:
        return None
    mob = census_api.get_mobility_data(lat, lon, tract=tract)
    ltp = census_api.get_tract_long_tenure_housing_pct(tract)
    info = census_api.get_place_fips_for_coordinates(lat, lon)
    place_rooted = None
    if info:
        sh = census_api.get_place_same_house_pct(info["state_fips"], info.get("place_fips"), geo=info)
        lt = census_api.get_place_long_tenure_housing_pct(info["state_fips"], info.get("place_fips"), geo=info)
        if sh is not None:
            place_rooted = 0.8 * float(lt) + 0.2 * float(sh) if lt is not None else float(sh)
    sh07 = (mob or {}).get("same_house_pct_b07003")
    sh = (mob or {}).get("same_house_pct")
    tract_rooted = 0.8 * float(ltp) + 0.2 * float(sh07) if ltp is not None and sh07 is not None else (float(sh) if sh is not None else None)
    if tract_rooted is not None:
        pct = 0.7 * tract_rooted + 0.3 * place_rooted if place_rooted is not None else tract_rooted
    elif place_rooted is not None:
        pct = place_rooted
    else:
        return None
    div = get_division(_FIPS_ABBR.get(tract.get("state_fips"), "")) if tract.get("state_fips") else None
    return pct, social_fabric_bands.score_stability_from_bands(pct, div, bands), tract.get("tract_fips") or tract.get("geoid")


def shifted(lat, lon, d_n, d_e):
    return lat + d_n / 111_320.0, lon + d_e / (111_320.0 * math.cos(math.radians(lat)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=20)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    bands = social_fabric_bands.load_bands()
    by_type = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            c, sc = r.get("catalog") or {}, r.get("score") or {}
            sf = (sc.get("livability_pillars") or {}).get("social_fabric") or {}
            b, s = sf.get("breakdown") or {}, sf.get("summary") or {}
            if not isinstance(sf.get("score"), (int, float)) or c.get("lat") is None or b.get("participation") is None:
                continue
            at = (sf.get("area_classification") or {}).get("area_type") or "unknown"
            by_type.setdefault(at, []).append(dict(name=c["name"], st=c.get("state_abbr"), lat=float(c["lat"]), lon=float(c["lon"]), at=at,
                                                   part=b["participation"], coh=b.get("social_capital"), ec=b.get("economic_connectedness")))
    rng = random.Random(a.seed)
    sample = [p for at, v in sorted(by_type.items()) if at != "unknown" for p in rng.sample(v, min(a.per_type, len(v)))]
    rows = []
    for p in sample:
        base = rooted_at(p["lat"], p["lon"], bands)
        if base is None:
            continue

        def total(score):
            return blend_social_fabric(participation=p["part"], cohesion=p["coh"], rootedness=score, civic=None, economic_connectedness=p["ec"])[0]

        t0 = total(base[1])
        for lab, dn, de in (("N", SHIFT_M, 0), ("S", -SHIFT_M, 0), ("E", 0, SHIFT_M), ("W", 0, -SHIFT_M)):
            la, lo = shifted(p["lat"], p["lon"], dn, de)
            r = rooted_at(la, lo, bands)
            if r is None:
                continue
            rows.append(dict(name=p["name"], state=p["st"], area_type=p["at"], dir=lab, base_pct=round(base[0], 1), shift_pct=round(r[0], 1),
                             rooted_change=round(r[1] - base[1], 1), score_change=round(total(r[1]) - t0, 1), tract_changed=base[2] != r[2],
                             above85=base[0] > 85 or r[0] > 85))
        print(p["name"], p["st"], flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    d = sorted(abs(r["score_change"]) for r in rows)
    print(f"places {len({(r['name'], r['state']) for r in rows})}, shifts {len(d)}: median {statistics.median(d):.1f}, p95 {d[int(.95 * len(d))]:.1f}, max {d[-1]:.1f}")
    for at in sorted({r["area_type"] for r in rows}):
        x = sorted(abs(r["score_change"]) for r in rows if r["area_type"] == at)
        print(f"  {at}: n={len(x)} median {statistics.median(x):.1f} p95 {x[int(.95 * len(x))]:.1f}")


if __name__ == "__main__":
    main()
