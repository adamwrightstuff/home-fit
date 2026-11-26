#!/usr/bin/env python3
"""
Build data/catalog_surroundings.json: median household income, median home value and community safety
around each catalog place, next to the place's own figures. Display only: no pillar,
no weight, not counted in any score (docs/SURROUNDINGS.md).

Offline. Reads only numbers already stored in the catalog (housing_value.summary,
Census ACS 2022; community_safety score and breakdown), never calls an API.

Safety uses only places whose rate is their own (see _safety_key): a place on a city-wide,
county, sheriff-station or state rate gets no safety figure and is not counted as anyone's
neighbor for safety, because that rate describes a much larger area than the place.

"Around" is a weighted average over the OTHER catalog places within MAX_MILES,
each weighted exp(-(d / SCALE_MILES)^2), so the closest neighbors count most. Only
catalog places count, not every town or tract in the metro. A place with too little
nearby weight (fewer close catalog neighbors than about one place at zero distance)
gets no figure instead of one resting on a single far neighbor.

Values at the Census cap ($250,001 income, $2,000,001 home value) are kept at the cap,
so an average that includes capped neighbors is a floor, and a place that is itself
at the cap gets no comparison for that figure.

  PYTHONPATH=. python3 scripts/catalog/build_catalog_surroundings.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import catalog_api  # noqa: E402

OUT = ROOT / "data" / "catalog_surroundings.json"

# Judgment calls, not fitted to any research (docs/SURROUNDINGS.md): about a short drive.
MAX_MILES = 8.0
SCALE_MILES = 3.0
MIN_WEIGHT = 1.0
INCOME_CAP = 250_001
HOME_CAP = 2_000_001
FIELDS = (("income", "median_household_income", INCOME_CAP), ("home_value", "median_home_value", HOME_CAP))


def _miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    r = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def _place_list_pins(metro: str) -> Dict[str, Tuple[float, float]]:
    import csv

    path = ROOT / "data" / f"{metro}_metro_place_catalog.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {catalog_api.row_key(r): (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)}


_AGENCY_SOURCES = {"fbi_nibrs_agency", "fbi_ucr_agency", "ny_state_ucr", "ca_doj_ucr"}


def _safety_key(cat: Dict[str, Any], b: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(source, agency) when the safety score might be the place's own rate, else None.

    Own rate: measured in a circle around the place from a city incident feed (*_open_data), or the
    yearly total of a police department that is not a sheriff or county force and does not cover a
    city neighborhood. Never own: county agencies, LASD station totals, state aggregates. Whether an
    agency rate is shared by several catalog places is checked afterwards in _rows."""
    src = str(b.get("source") or "")
    if src.endswith("_open_data"):
        return (src, "")
    agency = str(b.get("agency_name") or "")
    if src not in _AGENCY_SOURCES or not agency or cat.get("type") == "neighborhood":
        return None
    if "sheriff" in agency.lower() or "county" in agency.lower():
        return None
    return (src, agency)


def _rows(metro: str) -> List[Dict[str, Any]]:
    """Catalog rows with a usable pin. A row scored at a pin the place list has since moved is left out
    entirely (no figure, and not anyone's neighbor), since its stored numbers describe the wrong spot."""
    pins = _place_list_pins(metro)
    out = []
    for line in catalog_api._metro_file(metro).open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        cat, score = row.get("catalog") or {}, row.get("score") or {}
        if not row.get("success") or not cat or not score:
            continue
        try:
            ll = (float(cat["lat"]), float(cat["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        want = pins.get(catalog_api.row_key(cat))
        if want and (abs(want[0] - ll[0]) > 0.0005 or abs(want[1] - ll[1]) > 0.0005):
            print(f"  {metro}: skipping {cat.get('name')} (scored at an old pin)")
            continue
        pillars = score.get("livability_pillars") or {}
        hv = (pillars.get("housing_value") or {}).get("summary") or {}
        cs = pillars.get("community_safety") or {}
        sv = cs.get("score")
        sv = float(sv) if isinstance(sv, (int, float)) and not isinstance(sv, bool) else None
        skey = _safety_key(cat, cs.get("breakdown") or {}) if sv is not None else None
        out.append({"key": catalog_api.row_key(cat), "name": cat.get("name"), "ll": ll,
                    **{f: _num(hv.get(src)) for f, src, _ in FIELDS},
                    "safety": sv if skey else None, "_safety_key": skey})
    # An agency total that several catalog places share is a city-wide or area-wide rate, not any one place's.
    shared: Dict[Tuple[str, str], int] = {}
    for r in out:
        k = r["_safety_key"]
        if k and k[1]:
            shared[k] = shared.get(k, 0) + 1
    for r in out:
        k = r.pop("_safety_key")
        if k and k[1] and shared[k] > 1:
            r["safety"] = None
    return out


def surroundings_for(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        near = []
        for o in rows:
            if o is r:
                continue
            d = _miles(r["ll"], o["ll"])
            if d <= MAX_MILES:
                near.append((math.exp(-((d / SCALE_MILES) ** 2)), o))
        entry: Dict[str, Any] = {}
        for f, cap in [(f, cap) for f, _, cap in FIELDS] + [("safety", math.inf)]:
            here = r[f]
            vals = [(w, o[f]) for w, o in near if o[f] is not None]
            total_w = sum(w for w, _ in vals)
            if here is None or here >= cap or total_w < MIN_WEIGHT:
                continue
            entry[f] = {"here": round(here), "around": round(sum(w * v for w, v in vals) / total_w)}
        if entry:
            near.sort(key=lambda t: -t[0])
            entry["neighbors"] = [o["name"] for _, o in near[:3]]
            result[r["key"]] = entry
    return result


def main() -> None:
    places: Dict[str, Any] = {}
    counts = []
    for metro in catalog_api.live_metros():
        if not catalog_api._metro_file(metro).is_file():
            continue
        rows = _rows(metro)
        s = surroundings_for(rows)
        counts.append(f"{metro} {len(s)}/{len(rows)}")
        places.update({f"{metro}::{k}": v for k, v in s.items()})
    doc = {
        "method": f"catalog places within {MAX_MILES:g} mi, weight exp(-(d/{SCALE_MILES:g} mi)^2), min weight {MIN_WEIGHT:g}; "
                  "Census ACS 2022 from housing_value.summary; display only (docs/SURROUNDINGS.md)",
        "places": places,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(places)} places ({', '.join(counts)})")


if __name__ == "__main__":
    main()
