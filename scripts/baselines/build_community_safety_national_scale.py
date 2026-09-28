#!/usr/bin/env python3
"""
Build data/community_safety_national_scale.json — the national distribution of
municipal crime rates that community_safety scores against.

A random sample of city/town police departments (PER_STATE per state, all 50
states) is pulled from the FBI Crime Data Explorer for one calendar year.
Violent and property offense counts (FBI Part I definitions) are divided by
each agency's FBI service population.  Agencies are kept only if they reported
all 12 months, serve at least MIN_POPULATION residents, and reported any crime.

The output stores the 0th..100th percentile of each rate, so a place's safety
slot is simply "share of US towns with more crime than this place".

Usage (from project root):
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py
  # Reuse an existing sample instead of calling the API:
  PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py \
      --sample-jsonl analysis/us_agency_sample_2024.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
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
MIN_POPULATION = 2_500
SEED = 42


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


def sample_agencies(year: int, out_path: str) -> List[dict]:
    from dotenv import load_dotenv
    from data_sources import crime_api

    load_dotenv()
    key = crime_api._get_fbi_key()
    if not key:
        sys.exit("FBI API key not configured")
    rng = random.Random(SEED)
    records = []
    with open(out_path, "w", encoding="utf-8") as out:
        for st in STATES:
            agencies = crime_api._fetch_fbi_agencies(st) or []
            city = [
                a for a in agencies
                if a.get("agency_type_name") == "City"
                and not crime_api._is_special_purpose_agency(a.get("agency_name", ""))
            ]
            rng.shuffle(city)
            for a in city[:PER_STATE]:
                rec = {"ori": a["ori"], "state": st, "name": a["agency_name"], "year": year}
                for offense in ("violent-crime", "property-crime"):
                    res = _fetch_agency_year(a["ori"], a["agency_name"], offense, year, key) or {}
                    rec[offense] = res.get("count")
                    rec[offense + "_months"] = res.get("months", 0)
                    rec["population"] = res.get("population") or rec.get("population")
                    time.sleep(1.0)
                out.write(json.dumps(rec) + "\n")
                records.append(rec)
                print(st, a["agency_name"], rec["violent-crime"], rec["property-crime"], rec["population"])
    return records


def _percentiles(values: List[float]) -> List[float]:
    s = sorted(values)
    n = len(s)
    out = []
    for q in range(101):
        pos = q / 100 * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        out.append(round(s[lo] + (s[hi] - s[lo]) * (pos - lo), 3))
    return out


def build_scale(records: List[dict], year: int) -> Dict:
    usable = [
        r for r in records
        if (r.get("population") or 0) >= MIN_POPULATION
        and r.get("violent-crime_months") == 12
        and r.get("property-crime_months") == 12
        and (r.get("violent-crime") or 0) + (r.get("property-crime") or 0) > 0
    ]
    violent = [r["violent-crime"] / r["population"] * 1000 for r in usable]
    prop = [r["property-crime"] / r["population"] * 1000 for r in usable]
    return {
        "_meta": {
            "description": (
                "Percentiles (0..100) of annual crime rates per 1,000 residents across a random "
                "national sample of US city/town police departments. community_safety slot = "
                "100 - percentile of the place's rate."
            ),
            "source": "FBI Crime Data Explorer /summarized/agency (Part I violent and property offenses)",
            "data_year": year,
            "agencies_sampled": len(records),
            "agencies_used": len(usable),
            "states": len({r["state"] for r in usable}),
            "filters": f"agency_type=City, 12 months reported, population >= {MIN_POPULATION}, any crime reported",
            "sampling": f"{PER_STATE} random agencies per state, seed {SEED}",
            "rebuild": "PYTHONPATH=. python3 scripts/baselines/build_community_safety_national_scale.py",
        },
        "violent_per_1k_percentiles": _percentiles(violent),
        "property_per_1k_percentiles": _percentiles(prop),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--sample-jsonl", help="Reuse an existing agency sample instead of calling the API")
    ap.add_argument("--sample-out", default=os.path.join(ROOT, "analysis", "us_agency_sample.jsonl"))
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if args.sample_jsonl:
        with open(args.sample_jsonl, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    else:
        records = sample_agencies(args.year, args.sample_out)

    scale = build_scale(records, args.year)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(scale, f, indent=2)
        f.write("\n")
    m = scale["_meta"]
    print(f"Wrote {args.output}: {m['agencies_used']} agencies across {m['states']} states")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q}: violent {scale['violent_per_1k_percentiles'][q]}  "
              f"property {scale['property_per_1k_percentiles'][q]}")


if __name__ == "__main__":
    main()
