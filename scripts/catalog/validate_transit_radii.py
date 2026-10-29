#!/usr/bin/env python3
"""
Compare the stored transit score (area-type radii) with the score at the sourced radii (bus 800 m, rail 1,200 m, from
refetch_transit_radii.py) against two outside measures: tract transit commute share (ACS B08301) and households with
no vehicle (ACS B25044). Reports pooled and within-metro Spearman for both scores.

Fetches the two ACS values per place once into a side JSONL (resumable; failed lookups are retried on the next run).
Nothing in the catalog is read for writing or changed.

  cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/validate_transit_radii.py \
      --refetch analysis/transit_radii_refetch.jsonl --acs analysis/transit_radii_acs.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from data_sources import census_api  # noqa: E402

ANCHOR = 120.0
BONUS_KEYS = ("frequency_bonus", "weekend_service_bonus", "hub_connectivity_bonus", "destination_diversity_bonus")
BAD = {"-666666666", "-222222222", "-555555555", None}


def supply(w: float) -> float:
    return 0.0 if w <= 0 else 100.0 * min(1.0, math.log(1.0 + w) / math.log(1.0 + ANCHOR))


def acs_for(lat: float, lon: float):
    tract = census_api.get_census_tract(lat, lon)
    if not tract:
        return None
    share = census_api.get_transit_mode_share(lat, lon, tract=tract)
    r = requests.get(
        f"{census_api.CENSUS_BASE_URL}/{census_api.ACS_YEAR}/acs/acs5",
        params={"get": "B25044_001E,B25044_003E,B25044_010E", "for": f"tract:{tract['tract_fips']}",
                "in": f"state:{tract['state_fips']} county:{tract['county_fips']}", "key": census_api.CENSUS_API_KEY},
        timeout=15,
    )
    if r.status_code != 200 or len(r.json()) < 2:
        return None
    tot, o, rn = r.json()[1][:3]
    if tot in BAD or float(tot) <= 0:
        return None
    novehicle = (float(o) if o not in BAD else 0.0) + (float(rn) if rn not in BAD else 0.0)
    return {"transit_share": share, "no_vehicle": novehicle / float(tot)}


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a, b):
    if len(a) < 5:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", required=True)
    ap.add_argument("--acs", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    new = {json.loads(l)["key"]: json.loads(l) for l in open(a.refetch)}

    places = []
    for f in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            s, c = r.get("score") or {}, r.get("catalog") or {}
            co = s.get("coordinates") or {}
            t = (s.get("livability_pillars") or {}).get("public_transit_access") or {}
            if co.get("lat") is None or t.get("score") is None:
                continue
            key = f"{Path(f).name.split('_')[0]}|{c.get('name')}|{co['lat']:.4f},{co['lon']:.4f}"
            if key not in new:
                continue
            br = t.get("breakdown") or {}
            bonus = sum(br.get(k) or 0 for k in BONUS_KEYS)
            n = new[key]
            w = 3 * n["subway"] + 3 * n["commuter_rail"] + 2 * n["light_rail"] + 0.7 * n["bus"]
            places.append((key, co["lat"], co["lon"], t["score"], min(100.0, supply(w) + bonus)))

    acs_path = Path(a.acs)
    acs = {}
    if acs_path.exists():
        acs = {json.loads(l)["key"]: json.loads(l) for l in open(acs_path)}
    todo = [p for p in places if p[0] not in acs]
    print(f"{len(acs)} ACS rows cached, {len(todo)} to fetch")

    def job(p):
        try:
            return p[0], acs_for(p[1], p[2])
        except Exception:
            return p[0], None

    failed = 0
    with ThreadPoolExecutor(a.workers) as ex, open(acs_path, "a") as fh:
        for i, (key, res) in enumerate(ex.map(job, todo), 1):
            if res is None or res["transit_share"] is None:
                failed += 1
                continue
            acs[key] = {"key": key, **res}
            fh.write(json.dumps(acs[key]) + "\n")
            fh.flush()
            if i % 200 == 0:
                print(f"{i}/{len(todo)}")
    print(f"{failed} lookups failed (rerun to retry)")

    rows = [(p, acs[p[0]]) for p in places if p[0] in acs]
    print(f"\nvalidated on {len(rows)} places")
    for label, field in (("transit commute share", "transit_share"), ("no-vehicle households", "no_vehicle")):
        for name, idx in (("stored (area-type radii)", 3), ("sourced radii 800/1200 m", 4)):
            pooled = spearman([r[0][idx] for r in rows], [r[1][field] for r in rows])
            by = defaultdict(list)
            for r in rows:
                by[r[0][0].split("|")[0]].append(r)
            within = [x for x in (spearman([q[0][idx] for q in g], [q[1][field] for q in g]) for g in by.values()) if x is not None]
            print(f"{label:24s} {name:26s} pooled {pooled:.3f}  within-metro mean {st.mean(within):.3f}")


if __name__ == "__main__":
    main()
