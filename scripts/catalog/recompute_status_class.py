#!/usr/bin/env python3
"""
Apply the income-and-housing status_signal class (pillars.status_signal._classify_class) to a metro catalog.

1. Fetches ACS B25105 (median monthly housing cost) for places that lack it, at the same geography level the
   stored housing_value used, and stores it in housing_value.summary.median_monthly_housing_cost.
2. Classifies each place from the stored housing summary and the metro class cutoffs, then updates the class
   fields (archetype, archetype_rule, status_label, status_insight, top_drivers) and re-blends the composite
   status_signal and it_score from the STORED wealth / home_cost / education / occupation, using the new class's
   weights. Also re-derives the direction-only trajectory (Up-and-Coming | Stable | Declining) from the stored
   price-momentum inputs. Nothing else on the row changes; no recompute of the inputs, so no drift from live lookups.

  PYTHONPATH=. python3 scripts/catalog/recompute_status_class.py --metro dallas            # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_status_class.py --metro dallas --write
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CBSA = {"nyc": "35620", "sf": "41860", "la": "31080", "seattle": "42660", "austin": "12420",
        "chicago": "16980", "philadelphia": "37980", "dallas": "19100", "houston": "26420"}
ORDER = ["Struggling", "Working Class", "Middle Class", "Affluent", "Elite"]
ACS = "https://api.census.gov/data/2022/acs/acs5"


def _acs_cost(for_clause, in_clause, key):
    r = None
    for attempt in range(4):
        try:
            r = requests.get(ACS, params={"get": "B25105_001E", "for": for_clause, "in": in_clause, "key": key}, timeout=20)
            break
        except requests.RequestException:
            time.sleep(1.5 * (attempt + 1))
    if r is None or r.status_code != 200:
        return None
    d = r.json()
    try:
        v = float(d[1][0])
    except (IndexError, TypeError, ValueError):
        return None
    return v if v > 0 else None


def fetch_housing_cost(lat, lon, level):
    from data_sources.census_api import CENSUS_API_KEY, get_census_tract, get_place_fips_for_coordinates
    v = None
    if level and level != "tract":
        g = get_place_fips_for_coordinates(lat, lon)
        if g:
            if g.get("geo_type") == "county_subdivision":
                v = _acs_cost(f"county subdivision:{g['cousub_fips']}", f"state:{g['state_fips']} county:{g['county_fips']}", CENSUS_API_KEY)
            else:
                v = _acs_cost(f"place:{g['place_fips']}", f"state:{g['state_fips']}", CENSUS_API_KEY)
    if v is None:
        t = get_census_tract(lat, lon)
        if t:
            v = _acs_cost(f"tract:{t['tract_fips']}", f"state:{t['state_fips']} county:{t['county_fips']}", CENSUS_API_KEY)
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", required=True, choices=list(CBSA))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from pillars.composite_indices import _area_type_from_payload, compute_hotness_score
    from pillars.status_signal import (
        _build_top_drivers, _classify_class, _classify_trajectory, _composite_score_from_weights, _get_archetype_weights,
        _get_status_insight, _get_status_label, _signal_strength_band,
    )

    baselines = json.load(open(REPO / "data" / "status_signal_baselines.json"))
    key = f"{args.metro}_metro"

    path = REPO / "data" / f"{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

    # 1. housing cost for places that lack it
    todo = []
    for i, r in enumerate(rows):
        s = r.get("score") if r.get("success") else None
        if not isinstance(s, dict):
            continue
        hv = (s.get("livability_pillars") or {}).get("housing_value") or {}
        sm = hv.get("summary") if isinstance(hv.get("summary"), dict) else hv
        co = s.get("coordinates") or {}
        if sm.get("median_monthly_housing_cost") is None and co.get("lat") is not None:
            todo.append((i, co["lat"], co["lon"], sm.get("geo_level")))
    with ThreadPoolExecutor(8) as ex:
        costs = list(ex.map(lambda t: fetch_housing_cost(t[1], t[2], t[3]), todo))
    got = 0
    for (i, *_), c in zip(todo, costs):
        if c:
            hv = rows[i]["score"]["livability_pillars"]["housing_value"]
            sm = hv.get("summary") if isinstance(hv.get("summary"), dict) else hv
            sm["median_monthly_housing_cost"] = c
            got += 1
    print(f"{args.metro}: housing cost fetched for {got}/{len(todo)} places that lacked it")

    # 2. classify from stored inputs and re-blend the composite
    old_c, new_c, moved = collections.Counter(), collections.Counter(), []
    traj_c = collections.Counter()
    for r in rows:
        s = r.get("score") if r.get("success") else None
        if not isinstance(s, dict):
            continue
        bd = s.get("status_signal_breakdown") or {}
        hv = (s.get("livability_pillars") or {}).get("housing_value") or {}
        sm = hv.get("summary") if isinstance(hv.get("summary"), dict) else hv
        cls = _classify_class(sm, [key], baselines)
        if cls is None or not bd:
            continue
        arch, rule = cls
        old_label = bd.get("status_label")
        old_c[old_label] += 1
        new_c[_get_status_label(arch)] += 1
        if old_label != _get_status_label(arch):
            moved.append((r["catalog"]["name"], old_label, _get_status_label(arch)))
        w, h, e, o = bd.get("wealth"), bd.get("home_cost"), bd.get("education"), bd.get("occupation")
        bd["archetype"], bd["archetype_rule"] = arch, rule
        bd["status_label"] = _get_status_label(arch)
        bd["status_insight"] = _get_status_insight(arch)
        bd["top_drivers"] = _build_top_drivers(w, h, e, o, arch)
        ci = bd.get("classifier_inputs") or {}
        bd["trajectory"], bd["trajectory_rule"] = _classify_trajectory(
            archetype=arch, wealth=w, home_cost=h, stability=ci.get("stability"),
            appreciation_3yr=ci.get("appreciation_3yr"), velocity_6mo=ci.get("velocity_6mo"),
            renter_pct=sm.get("renter_pct"), area_type=_area_type_from_payload(s))
        traj_c[bd["trajectory"]] += 1
        raw = _composite_score_from_weights(*_get_archetype_weights(arch), w, h, e, o)
        if raw is not None:
            final = round(max(0.0, min(100.0, raw)), 1)
            ss_key, ss_label = _signal_strength_band(final)
            bd["composite_score"], bd["signal_strength"], bd["signal_strength_label"] = final, ss_key, ss_label
            s["status_signal"] = final
            s["it_score"] = compute_hotness_score(
                final, s.get("local_scene_score"), h if isinstance(h, (int, float)) else None,
                s.get("happiness_index"), s.get("total_score"))
        s["status_signal_breakdown"] = bd

    print("  trajectory", dict(traj_c))
    print("  before", [old_c[k] for k in ORDER], " after", [new_c[k] for k in ORDER], f" ({len(moved)} labels changed)")
    if args.write:
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
