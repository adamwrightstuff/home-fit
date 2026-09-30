#!/usr/bin/env python3
"""
Build data/community_safety_national_scale.json — the population-weighted
national distribution of crime rates that community_safety scores against.

The scale answers "what share of Americans live somewhere with more crime than
this place?", the same idea as comparing against US neighborhoods.  It is built
from FBI Crime Data Explorer per-agency data for one calendar year (Part I
violent and property offenses divided by each agency's FBI service population),
sampled in three strata so every kind of place is represented:

  large_city  the ~100 largest US cities (Census ACS place population), every one
              included, each weighted by its population
  city        PER_STATE random city/town police departments per state, each
              weighted by population x (city agencies in state / sampled)
  county      COUNTY_PER_STATE random county sheriffs / county police per state
              (unincorporated suburbs and rural areas), weighted the same way

Agencies count only if they reported all 12 months, serve at least
MIN_POPULATION residents, and reported any crime.

Rates are divided by people present (residents plus workers for the share of the
week they're at work; data_sources/people_present.py), the same denominator
community_safety uses for every scored place, so places are compared like for like.

Usage (from project root):
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py
  # Rebuild from saved samples instead of calling the APIs:
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py \\
      --sample-jsonl analysis/us_agency_sample_2024.jsonl analysis/us_large_city_sample_2024.jsonl \\
                     analysis/us_county_sample_2024.jsonl
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import random
import re
import sys
import time
from collections import Counter
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, ROOT)

DEFAULT_OUTPUT = os.path.join(ROOT, "data", "community_safety_national_scale.json")
STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()
PER_STATE = 10
COUNTY_PER_STATE = 5
LARGE_CITY_COUNT = 110
MIN_POPULATION = 2_500
SEED = 42
COUNTY_SEED = 7

# Large cities whose FBI agency name doesn't follow "<City> Police Department".
_LARGE_CITY_AGENCY_OVERRIDES = {
    "Jacksonville city, Florida": ("FL", "jacksonville sheriff"),
    "Las Vegas city, Nevada": ("NV", "las vegas metropolitan"),
    "Washington city, District of Columbia": ("DC", "washington police department"),
    "Boise City city, Idaho": ("ID", "boise police"),
    "Urban Honolulu CDP, Hawaii": ("HI", "honolulu police"),
    "Arlington CDP, Virginia": ("VA", "arlington county police"),
}


def _fetch_agency_year(ori: str, name: str, offense: str, year: int, key: str) -> Optional[dict]:
    import requests
    from data_sources import crime_api

    for attempt in range(6):
        try:
            r = requests.get(
                f"{crime_api._FBI_CDE_BASE}/summarized/agency/{ori}/{offense}",
                params={"API_KEY": key, "from": f"01-{year}", "to": f"12-{year}"},
                timeout=40,
            )
            if r.status_code == 200:
                data = r.json()
                actuals = (data.get("offenses") or {}).get("actuals") or {}
                ag_key = next((k for k in actuals if "Offenses" in k and name.lower() in k.lower()), None)
                counts = [v for v in (actuals.get(ag_key) or {}).values() if v is not None]
                pops = ((data.get("populations") or {}).get("population") or {}).get(name) or {}
                pop_vals = [v for v in pops.values() if v]
                return {
                    "count": sum(counts) if counts else None,
                    "months": len(counts),
                    "population": int(sum(pop_vals) / len(pop_vals)) if pop_vals else None,
                }
        except Exception:
            pass
        time.sleep(5 * (attempt + 1))
    return None


def _agency_record(agency: dict, state: str, stratum: str, year: int, key: str, **extra) -> dict:
    rec = {"ori": agency["ori"], "state": state, "name": agency["agency_name"],
           "year": year, "stratum": stratum, **extra}
    for offense in ("violent-crime", "property-crime"):
        res = _fetch_agency_year(agency["ori"], agency["agency_name"], offense, year, key) or {}
        rec[offense] = res.get("count")
        rec[offense + "_months"] = res.get("months", 0)
        rec["population"] = res.get("population") or rec.get("population")
        time.sleep(1.0)
    print(stratum, state, agency["agency_name"], rec["violent-crime"], rec["property-crime"], rec["population"])
    return rec


def _largest_places() -> List[tuple]:
    import requests
    r = requests.get(
        "https://api.census.gov/data/2023/acs/acs5",
        params={"get": "NAME,B01003_001E", "for": "place:*", "key": os.getenv("CENSUS_API_KEY")},
        timeout=60,
    )
    rows = r.json()[1:]
    return sorted(((int(pop), name) for name, pop, *_ in rows), reverse=True)[:LARGE_CITY_COUNT]


def _large_city_agency(place: str, agencies_by_state: Dict[str, list]) -> Optional[tuple]:
    from data_sources import crime_api
    from data_sources.geocoding import STATE_ABBREVIATIONS

    if place in _LARGE_CITY_AGENCY_OVERRIDES:
        st, kw = _LARGE_CITY_AGENCY_OVERRIDES[place]
        ag = next((a for a in agencies_by_state[st] if kw in a["agency_name"].lower()), None)
        return (st, ag) if ag else None
    name, state = place.rsplit(", ", 1)
    if name.endswith(" CDP"):
        return None  # unincorporated; covered by the county stratum
    st = STATE_ABBREVIATIONS.get(state.lower())
    if not st:
        return None
    base = re.sub(
        r" (city|town|municipality|metropolitan government|urban county|unified government|"
        r"consolidated government)( \(balance\))?.*$", "", name,
    )
    base = re.split(r"[-/]", base)[0].strip().lower()
    cands = sorted(
        (a for a in agencies_by_state[st]
         if a.get("agency_type_name") == "City" and base in a["agency_name"].lower()
         and "police" in a["agency_name"].lower()
         and not crime_api._is_special_purpose_agency(a["agency_name"])),
        key=lambda a: len(a["agency_name"]),
    )
    return (st, cands[0]) if cands else None


def sample_agencies(year: int, out_dir: str) -> List[dict]:
    from dotenv import load_dotenv
    from data_sources import crime_api

    load_dotenv()
    key = crime_api._get_fbi_key()
    if not key:
        sys.exit("FBI API key not configured")
    agencies_by_state = {st: crime_api._fetch_fbi_agencies(st) or [] for st in STATES + ["DC"]}
    records: List[dict] = []

    for pop, place in _largest_places():
        hit = _large_city_agency(place, agencies_by_state)
        if hit:
            st, ag = hit
            records.append(_agency_record(ag, st, "large_city", year, key, census_pop=pop))
    large_oris = {r["ori"] for r in records}

    rng = random.Random(SEED)
    county_rng = random.Random(COUNTY_SEED)
    for st in STATES:
        city = [a for a in agencies_by_state[st]
                if a.get("agency_type_name") == "City"
                and not crime_api._is_special_purpose_agency(a.get("agency_name", ""))]
        rng.shuffle(city)
        for a in city[:PER_STATE]:
            if a["ori"] not in large_oris:
                records.append(_agency_record(a, st, "city", year, key))
        county = [a for a in agencies_by_state[st] if a.get("agency_type_name") == "County"]
        county_rng.shuffle(county)
        for a in county[:COUNTY_PER_STATE]:
            records.append(_agency_record(a, st, "county", year, key))

    with open(os.path.join(out_dir, f"us_agency_sample_all_{year}.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return records


def add_people_present_multipliers(records: List[dict]) -> None:
    """Attach each agency's people-present multiplier (town for city agencies,
    county for county agencies), located by the agency's FBI coordinates."""
    from data_sources import crime_api
    from data_sources.people_present import people_present_multiplier

    coords: Dict[str, tuple] = {}
    for st in {r["state"] for r in records}:
        for a in crime_api._fetch_fbi_agencies(st) or []:
            if a.get("latitude") is not None and a.get("longitude") is not None:
                coords[a["ori"]] = (float(a["latitude"]), float(a["longitude"]))
    for r in records:
        if "people_present_multiplier" in r:
            continue
        ll = coords.get(r["ori"])
        if not ll:
            r["people_present_multiplier"] = 1.0
            continue
        mult, _ = people_present_multiplier(ll[0], ll[1], "county" if r.get("stratum") == "county" else "municipal")
        r["people_present_multiplier"] = round(mult, 4)


def _weighted_percentiles(points: List[tuple]) -> List[float]:
    """0..100 percentiles of (value, weight) points, midpoint-cumulative interpolation."""
    s = sorted(points)
    total = sum(w for _, w in s)
    cum, mids = 0.0, []
    for _, w in s:
        cum += w
        mids.append((cum - w / 2) / total)
    out = []
    for q in range(101):
        t = q / 100
        if t <= mids[0]:
            out.append(round(s[0][0], 3))
        elif t >= mids[-1]:
            out.append(round(s[-1][0], 3))
        else:
            k = bisect.bisect_left(mids, t)
            f = (t - mids[k - 1]) / (mids[k] - mids[k - 1])
            out.append(round(s[k - 1][0] + f * (s[k][0] - s[k - 1][0]), 3))
    return out


def build_scale(records: List[dict], year: int) -> Dict:
    from data_sources import crime_api

    def usable(r: dict) -> bool:
        return ((r.get("population") or 0) >= MIN_POPULATION
                and r.get("violent-crime_months") == 12 and r.get("property-crime_months") == 12
                and (r.get("violent-crime") or 0) + (r.get("property-crime") or 0) > 0)

    for r in records:
        r.setdefault("stratum", "city")
    large_oris = {r["ori"] for r in records if r["stratum"] == "large_city"}
    records = [r for r in records if not (r["stratum"] != "large_city" and r["ori"] in large_oris)]

    # Expansion factor: agencies of that type in the state / agencies sampled there.
    frame: Dict[tuple, int] = {}
    for st in {r["state"] for r in records if r["stratum"] != "large_city"}:
        ags = crime_api._fetch_fbi_agencies(st) or []
        frame[(st, "city")] = sum(
            1 for a in ags if a.get("agency_type_name") == "City"
            and not crime_api._is_special_purpose_agency(a["agency_name"]) and a["ori"] not in large_oris
        )
        frame[(st, "county")] = sum(1 for a in ags if a.get("agency_type_name") == "County")
    sampled = Counter((r["state"], r["stratum"]) for r in records if r["stratum"] != "large_city")

    v_pts, p_pts, weights = [], [], Counter()
    for r in filter(usable, records):
        if r["stratum"] == "large_city":
            w = float(r["population"])
        else:
            w = r["population"] * frame[(r["state"], r["stratum"])] / sampled[(r["state"], r["stratum"])]
        present = r["population"] * float(r.get("people_present_multiplier") or 1.0)
        v_pts.append((r["violent-crime"] / present * 1000, w))
        p_pts.append((r["property-crime"] / present * 1000, w))
        weights[r["stratum"]] += w
    total_w = sum(weights.values())
    mean_v = sum(v * w for v, w in v_pts) / total_w
    mean_p = sum(p * w for p, w in p_pts) / total_w

    return {
        "_meta": {
            "description": (
                "Population-weighted percentiles (0..100) of annual crime rates per 1,000 residents "
                "across US places. community_safety slot = 100 - percentile, i.e. the share of "
                "Americans living somewhere with more crime."
            ),
            "source": "FBI Crime Data Explorer /summarized/agency (Part I violent and property offenses)",
            "data_year": year,
            "agencies_sampled": len(records),
            "agencies_used": len(v_pts),
            "agencies_used_by_stratum": dict(Counter(r["stratum"] for r in filter(usable, records))),
            "population_share_by_stratum": {k: round(v / total_w, 3) for k, v in weights.items()},
            "denominator": "people present (residents + workers x 45/168 hours), ACS 2022",
            "weighted_mean_violent_per_1k": round(mean_v, 2),
            "weighted_mean_property_per_1k": round(mean_p, 2),
            "filters": f"12 months reported, population >= {MIN_POPULATION}, any crime reported",
            "sampling": (
                f"large_city: {LARGE_CITY_COUNT} largest Census places; city: {PER_STATE}/state (seed {SEED}); "
                f"county: {COUNTY_PER_STATE}/state (seed {COUNTY_SEED})"
            ),
            "limitations": "Large cities enter at their citywide rate, so within-city variation is not represented.",
            "rebuild": "PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py",
        },
        "violent_per_1k_percentiles": _weighted_percentiles(v_pts),
        "property_per_1k_percentiles": _weighted_percentiles(p_pts),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--sample-jsonl", nargs="+", help="Reuse saved agency samples instead of calling the APIs")
    ap.add_argument("--sample-out-dir", default=os.path.join(ROOT, "analysis"))
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if args.sample_jsonl:
        records = []
        for path in args.sample_jsonl:
            with open(path, encoding="utf-8") as f:
                records.extend(json.loads(line) for line in f if line.strip())
    else:
        records = sample_agencies(args.year, args.sample_out_dir)

    add_people_present_multipliers(records)
    if args.sample_jsonl:
        # save multipliers back so rebuilds don't repeat the boundary lookups
        mult = {r["ori"]: r.get("people_present_multiplier") for r in records}
        for path in args.sample_jsonl:
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            for row in rows:
                row["people_present_multiplier"] = mult.get(row["ori"], row.get("people_present_multiplier"))
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(json.dumps(row) + "\n" for row in rows)
    scale = build_scale(records, args.year)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(scale, f, indent=2)
        f.write("\n")
    m = scale["_meta"]
    print(f"Wrote {args.output}: {m['agencies_used']} agencies {m['agencies_used_by_stratum']}")
    print(f"  population share {m['population_share_by_stratum']}")
    print(f"  weighted mean violent {m['weighted_mean_violent_per_1k']}  property {m['weighted_mean_property_per_1k']}")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q}: violent {scale['violent_per_1k_percentiles'][q]}  "
              f"property {scale['property_per_1k_percentiles'][q]}")


if __name__ == "__main__":
    main()
