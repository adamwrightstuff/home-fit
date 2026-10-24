#!/usr/bin/env python3
"""
Pin-sensitivity test for the community_safety neighborhood circle.

For each open-data neighborhood, scores the catalog pin plus the pin shifted 500 m north and
500 m east, with the circle radius floored at each --floors value (the circle still widens past
the floor until it holds MIN_NEIGHBORHOOD_RESIDENTS).  Reports how much the score moves when the pin
moves.  Raw residents / people-present per radius and the crime counts are saved to --out so
later comparisons need no new API calls.

Read-only: does not touch the catalog.  Needs CENSUS_API_KEY (reads .env if present).

Usage (from project root):
  PYTHONPATH=. python3 scripts/catalog/test_safety_radius_floor.py --metro boston
  PYTHONPATH=. python3 scripts/catalog/test_safety_radius_floor.py --floors 600,800,1000 --limit 10
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from data_sources import crime_api as ca  # noqa: E402
from data_sources.census_api import estimate_community_safety_disk_population as pop_fn  # noqa: E402
from data_sources.lodes_h8_commuter_context import jobs_in_disk  # noqa: E402
from data_sources.people_present import people_present  # noqa: E402
from pillars.community_safety import _score_rates  # noqa: E402

FETCHERS = {
    "nyc": ("nyc_open_data", "_fetch_nyc_part1"),
    "boston": ("boston_open_data", "_fetch_boston_part1"),
    "dallas": ("dallas_open_data", "_fetch_dallas_part1"),
    "chicago": ("chicago_open_data", "_fetch_chicago_part1"),
    "philadelphia": ("philadelphia_open_data", "_fetch_philadelphia_part1"),
    "sf": ("sf_open_data", "_fetch_sf_part1"),
}
RADII = (600, 800, 1000, 1200, 1500, 2000, 3000, 4000)
SHIFTS = (("c", 0.0, 0.0), ("n", 500.0, 0.0), ("e", 0.0, 500.0))


def _load_places(path: Path, names, source):
    out = {}
    for line in path.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        cs = ((d.get("score") or {}).get("livability_pillars") or {}).get("community_safety") or {}
        if (cs.get("breakdown") or {}).get("source") != source:
            continue
        cat = d["catalog"]
        if names and cat["name"] not in names:
            continue
        ao = ((d["score"]["livability_pillars"].get("active_outdoors") or {}).get("area_classification") or {})
        out[cat["name"]] = (float(cat["lat"]), float(cat["lon"]), ao.get("area_type"), cs.get("score"))
    return out


def _ambient_at(lat, lon, area_type, r):
    for attempt in range(6):
        residents, meta = pop_fn(lat, lon, r, area_type=area_type)
        if meta.get("population_denominator_method") == "areal_acs_tracts_in_disk":
            break
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"Census lookup failed at {lat},{lon} r={r}")
    jobs = jobs_in_disk(lat, lon, r)
    ambient = people_present(residents, jobs[0], jobs[1]) if jobs else float(residents)
    return {"residents": float(residents), "ambient": float(ambient)}


def _radius_for(lat, lon, area_type, floor, series):
    """Smallest radius >= floor holding the minimum residents; looks up each radius lazily."""
    for r in RADII:
        if r < floor:
            continue
        if r not in series:
            series[r] = _ambient_at(lat, lon, area_type, r)
        if series[r]["residents"] >= ca.MIN_NEIGHBORHOOD_RESIDENTS:
            return r
    return RADII[-1]


def _work(args):
    name, (lat, lon, area_type, current), floors, year, fetch = args
    res = {"current": current, "pins": {}}
    for tag, dn, de in SHIFTS:
        la = lat + dn / 111320.0
        lo = lon + de / (111320.0 * math.cos(math.radians(lat)))
        series = {}
        pin = {"series": series, "floors": {}}
        for f in floors:
            r = _radius_for(la, lo, area_type, f, series)
            c = fetch(la, lo, r, year)
            if not c:
                continue
            if r not in series:
                series[r] = _ambient_at(la, lo, area_type, r)
            p = series[r]["ambient"]
            score = _score_rates(c["violent"] / p * 1000, c["property"] / p * 1000)[2]
            pin["floors"][str(f)] = {"radius": r, "violent": c["violent"], "property": c["property"],
                                     "ambient": p, "score": round(score, 1)}
        res["pins"][tag] = pin
    print("done", name, flush=True)
    return name, res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metro", choices=sorted(FETCHERS), default="nyc")
    ap.add_argument("--input", type=Path, default=None, help="Scored JSONL (default: the metro's merged file)")
    ap.add_argument("--floors", default="600,800,1000", help="Comma-separated minimum radii in metres")
    ap.add_argument("--names", default=None, help="Comma-separated catalog names (default: all open-data places)")
    ap.add_argument("--limit", type=int, default=0, help="Only the first N places (testing)")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--out", type=Path, default=None, help="Default: analysis/safety_radius_floor_<metro>.json")
    a = ap.parse_args()

    floors = [int(x) for x in a.floors.split(",")]
    source, fetch_name = FETCHERS[a.metro]
    fetch = getattr(ca, fetch_name)
    if a.input is None:
        cands = sorted((REPO_ROOT / "data").glob(f"{a.metro}_metro_place_catalog_scores_merged*.jsonl"))
        a.input = cands[-1]
    places = _load_places(a.input, set(a.names.split(",")) if a.names else None, source)
    items = list(places.items())[: a.limit or None]
    print(f"{len(items)} places, floors {floors}", flush=True)

    with ThreadPoolExecutor(a.threads) as ex:
        results = dict(ex.map(_work, [(n, v, floors, a.year, fetch) for n, v in items]))
    a.out = a.out or REPO_ROOT / "analysis" / f"safety_radius_floor_{a.metro}.json"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(results))

    print(f"\n{'floor (m)':>10} {'mean |change when pin moves|':>30} {'swings >15':>11} {'mean score':>11} {'mean radius':>12}")
    for f in floors:
        ch, sc, rad = [], [], []
        for r in results.values():
            c = r["pins"]["c"]["floors"].get(str(f))
            if not c:
                continue
            sc.append(c["score"])
            rad.append(c["radius"])
            for tag in ("n", "e"):
                s = r["pins"][tag]["floors"].get(str(f))
                if s:
                    ch.append(abs(s["score"] - c["score"]))
        if ch:
            print(f"{f:>10} {st.mean(ch):>30.1f} {sum(x > 15 for x in ch):>5}/{len(ch):<5} {st.mean(sc):>11.1f} {st.mean(rad):>12.0f}")
    print(f"\nSaved raw numbers to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
