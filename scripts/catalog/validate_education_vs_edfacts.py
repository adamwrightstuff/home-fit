#!/usr/bin/env python3
"""
Check the school ratings behind the education score against an independent source: federal EDFacts state test
proficiency (reading and math), served by the Urban Institute Education Data API (free, no key, no SchoolDigger calls).

SchoolDigger's ratings are state-wide percentiles built from state test results, so they should rank schools the
way proficiency does. This compares them school by school (SchoolDigger school IDs are NCES IDs) per level and
lists the lowest-rated schools in the lowest-scoring catalog places with their proficiency.
Caveat: the original run used API year 2018 (labelled 2017-18 when written; the API's own year convention was not confirmed).
Checked 2026-10-26: API years 2019 and 2021 onward return errors, 2020 returns data, so 2020 is the newest year. COVID-era 2020 data may
have opt-outs and suppression. SchoolDigger ratings in the snapshot are the 2025 ratings, so this tests the ranking only.

  PYTHONPATH=. python3 scripts/catalog/validate_education_vs_edfacts.py [--lowest 12] [--year 2018]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List

import requests

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from data_sources import school_snapshot as ss  # noqa: E402
from data_sources.school_districts import districts_for_place  # noqa: E402
from data_sources.schools_api import _nyc_csd_ids_by_number, normalize_state  # noqa: E402
from pillars.schools import school_rating  # noqa: E402

API = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{year}/{grade}/"
GRADE = {"elementary": "grade-4", "middle": "grade-8", "high": "grade-9"}
METROS = ("nyc", "la", "sf", "seattle", "austin", "chicago", "philadelphia")
BIG = {"Chicago": ("IL", "1709930"), "Austin": ("TX", "4808940"), "SFUSD": ("CA", "0634410"), "LAUSD": ("CA", "0622710")}


def fetch(leaid: str, grade: str, year: int = 2018) -> Dict[str, float]:
    """{NCES school id: mean of reading and math proficiency midpoint (%)} for one district and grade."""
    r = requests.get(API.format(year=year, grade=grade), params={"leaid": leaid, "per_page": 1000}, timeout=90)
    if r.status_code != 200:
        return {}
    out = {}
    for x in r.json().get("results", []):
        vals = [v for v in (x.get("read_test_pct_prof_midpt"), x.get("math_test_pct_prof_midpt")) if v is not None and v >= 0]
        if vals:
            out[str(x["ncessch"])] = sum(vals) / len(vals)
    return out


def spearman(a: List[float], b: List[float]) -> float:
    import statistics

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r

    ra, rb = ranks(a), ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--lowest", type=int, default=12, help="how many lowest-scoring catalog places to list")
    ap.add_argument("--year", type=int, default=2018, help="EDFacts API year (2018 or 2020 return data)")
    args = ap.parse_args()

    # 1) rank agreement in the big districts (one request per district and grade)
    print(f"Rank agreement: SchoolDigger percentile vs EDFacts {args.year} proficiency (Spearman)")
    pools = dict(BIG)
    csd = _nyc_csd_ids_by_number("NY")
    for n, did in sorted(csd.items()):
        pools[f"NYC CSD {n}"] = ("NY", did)
    tot = {lv: ([], []) for lv in GRADE}
    by_group: Dict[str, Dict[str, tuple]] = {}
    for label, (st, leaid) in pools.items():
        group = "NYC" if label.startswith("NYC") else label
        schools = {s["schoolid"]: s for s in (ss.district_schools(st, leaid) or [])}
        for lv, grade in GRADE.items():
            prof = fetch(leaid, grade, args.year)
            for sid, p in prof.items():
                s = schools.get(sid)
                r = school_rating(s) if s and s.get("rankHistory") else None
                if r is not None:
                    tot[lv][0].append(r)
                    tot[lv][1].append(p)
                    g = by_group.setdefault(group, {}).setdefault(lv, ([], []))
                    g[0].append(r)
                    g[1].append(p)
            time.sleep(0.15)
    for lv, (a, b) in tot.items():
        print(f"  {lv:<11} schools {len(a):>4}  Spearman {spearman(a, b):.2f}" if len(a) > 5 else f"  {lv}: too few")

    print("  by district:")
    for group, lvls in by_group.items():
        parts = [f"{lv} {spearman(*v):.2f} (n={len(v[0])})" for lv, v in lvls.items() if len(v[0]) > 5]
        print(f"    {group:<9} " + ", ".join(parts))

    # 2) the lowest-scoring places: their schools next to proficiency
    rows = []
    for m in METROS:
        for line in open(os.path.join(REPO, "data", f"{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl")):
            o = json.loads(line)
            p = o["score"]["livability_pillars"]["quality_education"]
            if p.get("score") is not None:
                rows.append((p["score"], m, o))
    rows.sort(key=lambda r: r[0])
    print(f"\nLowest {args.lowest} places: scored school vs EDFacts {args.year} proficiency (reading/math midpoint, grade 4/8/9)")
    for score, m, o in rows[: args.lowest]:
        c = o["catalog"]
        st = normalize_state(o["score"]["location_info"]["state"])
        ds = districts_for_place(float(c["lat"]), float(c["lon"]), st, c["name"])
        print(f"- {c['name']} ({m}) score {score:.1f}; districts: {', '.join(d['name'][:30] for d in ds)}")
        b = o["score"]["livability_pillars"]["quality_education"]["breakdown"]
        for lv, v in (b.get("levels") or {}).items():
            for e in v.get("schools", [])[:2]:
                match = None
                for d in ds:
                    for s in ss.district_schools(st, d["id"]) or []:
                        if s["schoolName"] == e["name"]:
                            match = s
                            prof = fetch(d["id"] if "New York City" not in d["name"] else str(s["district"]["districtID"]), GRADE[lv], args.year)
                            p = prof.get(s["schoolid"])
                            print(f"    {lv:<10} {e['name'][:34]:<36} SchoolDigger pct {e['rating']:>5.1f}  proficiency {('%.1f%%' % p) if p is not None else 'n/a'}")
                            break
                    if match:
                        break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
