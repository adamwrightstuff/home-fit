"""
Build a metro's place list from a small spec, with the checks learned the hard way.

  PYTHONPATH=. python -m scripts.metro_agent init --metro tucson --spec data/metro_specs/tucson.json

Spec (data/metro_specs/<slug>.json):
  {"slug": "tucson", "label": "TUS", "long_label": "Tucson metro", "cbsa": "46060", "states": ["AZ"],
   "neighborhoods": {"Tucson": ["Downtown Tucson", "Armory Park"]},     # parent city -> neighborhood names
                                                                          # (or {"name": "Midtown Phoenix", "query": "Midtown"})
   "suburbs": ["Oro Valley", "Marana", "Sahuarita"]}

How each pin is chosen (DESIGN_PRINCIPLES.md: objective, reproducible, the same rule for every place)
  suburb         the OpenStreetMap place node (city/town/village/suburb) of that name within 25 miles of the Census
                 gazetteer point; falls back to the gazetteer point, then to a Nominatim lookup. The Census internal
                 point of a large or oddly shaped city can sit 5 to 15 miles from the built-up town (Scottsdale 13.6 mi),
                 which scores the place on empty land.
  neighborhood   a Nominatim lookup of "<name>, <parent city>, <ST>"; rejected unless the result names the parent city.
Checks that fail loudly instead of silently
  * a neighborhood pin must fall inside its parent city's Census boundary (an enclave city listed as a neighborhood
    would be scored with the parent city's police department)
  * every place must be in a county of the metro's Census CBSA definition
  * names that cannot be located are reported, never guessed
"""
from __future__ import annotations

import csv
import json
import math
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from . import registry

REPO = registry.REPO
UA = {"User-Agent": "HomeFit/1.0 (place list builder)"}
RANK = {"city": 0, "town": 1, "village": 2, "suburb": 3, "hamlet": 4}
STATE_FULL = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
FIELDS = ["name", "type", "county_borough", "state_full", "state_abbr", "lat", "lon", "search_query"]


def miles(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    p = math.pi / 180
    h = 0.5 - math.cos((b_lat - a_lat) * p) / 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * (1 - math.cos((b_lon - a_lon) * p)) / 2
    return 7917.5 * math.asin(math.sqrt(h))


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\b(saint|st)\b", "st", s.lower().replace(".", "")))


# ----------------------------------------------------------------------------------------------
# data sources
# ----------------------------------------------------------------------------------------------
def load_gazetteer() -> Dict[Tuple[str, str], List[Dict[str, str]]]:
    z = REPO / "data_cache" / "gazetteer_places_2023.zip"
    if not z.is_file():
        raise FileNotFoundError("data_cache/gazetteer_places_2023.zip is missing (Census gazetteer of places)")
    with zipfile.ZipFile(z) as zf:
        lines = zf.read(next(n for n in zf.namelist() if n.endswith(".txt"))).decode("latin-1").splitlines()
    hdr = [h.strip() for h in lines[0].split("\t")]
    out: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) < len(hdr):
            continue
        r = {h: v.strip() for h, v in zip(hdr, p)}
        base = re.sub(r"\s+(city|town|village|CDP|borough|municipality|city and borough)$", "", r["NAME"])
        out.setdefault((r["USPS"], base), []).append(r)
    return out


def overpass_place_node(url: str, name: str, lat: float, lon: float, max_miles: float = 25.0) -> Optional[Dict[str, Any]]:
    n = name.replace('"', '\\"')
    q = f'[out:json][timeout:60];node[place~"city|town|village|suburb|hamlet"][name="{n}"]({lat - 0.5},{lon - 0.6},{lat + 0.5},{lon + 0.6});out;'
    try:
        els = requests.post(url, data={"data": q}, timeout=120).json()["elements"]
    except Exception:  # noqa: BLE001
        return None
    els = [e for e in els if miles(lat, lon, e["lat"], e["lon"]) <= max_miles]
    if not els:
        return None
    els.sort(key=lambda e: (RANK.get(e["tags"].get("place"), 9), miles(lat, lon, e["lat"], e["lon"])))
    return els[0]


def nominatim(q: str) -> List[Dict[str, Any]]:
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1, "countrycodes": "us"},
                         headers=UA, timeout=25).json()
    except Exception:  # noqa: BLE001
        return []
    time.sleep(1.2)
    return r


def county_of(lat: float, lon: float) -> str:
    for t in range(4):
        try:
            r = requests.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
                             params={"x": lon, "y": lat, "benchmark": "Public_AR_Current", "vintage": "Current_Current",
                                     "layers": "Counties", "format": "json"}, timeout=30).json()
            return r["result"]["geographies"]["Counties"][0]["BASENAME"]
        except Exception:  # noqa: BLE001
            time.sleep(2 * (t + 1))
    return ""


def cbsa_county_names(cbsa: str) -> Optional[set]:
    """County names of the CBSA from the Census delineation file cached in data_cache (see prereqs.fetch_delineation)."""
    p = REPO / "data_cache" / "cbsa_delineation_2023.json"
    if not p.is_file():
        return None
    d = json.loads(p.read_text()).get(cbsa)
    return {c.lower() for c in d["county_names"]} if d else None


def place_polygons(state: str):
    """Census place outlines for a state (data_cache/tiger_place_2024), or None when not downloaded."""
    import glob

    import geopandas as gpd

    from data_sources.school_districts import _STATE_FIPS

    fips = _STATE_FIPS.get(state)
    paths = glob.glob(str(REPO / "data_cache" / "tiger_place_2024" / f"tl_2024_{fips}_place" / "*.shp")) if fips else []
    return gpd.read_file(paths[0]).to_crs(4326) if paths else None


# ----------------------------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------------------------
def build(spec: Dict[str, Any], overpass_url: str, log: Callable[[str], None] = print) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Returns (rows, notes, problems). Problems must be fixed (or the spec edited) before scoring."""
    states = spec["states"]
    gaz = load_gazetteer()
    rows: List[Dict[str, Any]] = []
    notes: List[str] = []
    problems: List[str] = []
    seen = set()
    st0 = states[0]

    # neighborhoods
    polys = {s: place_polygons(s) for s in states}
    for city, names in (spec.get("neighborhoods") or {}).items():
        for item in names:
            # a name, or {"name": shown name, "query": the name to look up} when they differ ("Midtown Phoenix" -> "Midtown")
            n, qn = (item["name"], item.get("query", item["name"])) if isinstance(item, dict) else (item, item)
            q = f"{qn}, {city}, {st0}" if not qn.lower().startswith("downtown") else f"Downtown, {city}, {st0}"
            r = nominatim(q)
            if not r:
                notes.append(f"{n}: not found by Nominatim; dropped")
                continue
            disp = r[0]["display_name"]
            if city.replace("St. ", "Saint ") not in disp and city not in disp:
                notes.append(f"{n}: result is not in {city} ({disp[:60]}); dropped")
                continue
            lat, lon = round(float(r[0]["lat"]), 4), round(float(r[0]["lon"]), 4)
            g = polys.get(st0)
            if g is not None:
                from shapely.geometry import Point

                hit = g[g.contains(Point(lon, lat))]
                if len(hit) and hit.iloc[0]["LSAD"] in ("25", "43", "47", "21") and norm(hit.iloc[0]["NAME"]) != norm(city):
                    problems.append(f"{n}: pin is inside {hit.iloc[0]['NAME']}, not {city}. It is a separate city: move it to "
                                    f"`suburbs` (otherwise it is scored with {city}'s police department).")
                    continue
            rows.append({"name": n, "type": "neighborhood", "county_borough": "", "state_full": STATE_FULL[st0], "state_abbr": st0,
                         "lat": lat, "lon": lon, "search_query": q})
            seen.add(n)

    # suburbs
    for n in spec.get("suburbs") or []:
        if n in seen:
            continue
        st = next((s for s in states if (s, n) in gaz), None)
        if st:
            cands = gaz[(st, n)]
            g = sorted(cands, key=lambda r: (r["LSAD"] not in ("25", "43", "21", "47"), -float(r["ALAND_SQMI"] or 0)))[0]
            la, lo = float(g["INTPTLAT"]), float(g["INTPTLONG"])
            node = overpass_place_node(overpass_url, n, la, lo) if overpass_url else None
            if node:
                moved = miles(la, lo, node["lat"], node["lon"])
                la, lo = node["lat"], node["lon"]
                if moved >= 1.0:
                    notes.append(f"{n}: pin moved {moved:.1f} mi from the Census point to the OSM {node['tags'].get('place')} center")
        else:
            st = st0
            r = nominatim(f"{n}, {STATE_FULL[st0]}")
            ok = [x for x in r if n.split()[0] in x["display_name"] and STATE_FULL[st0] in x["display_name"] and x.get("class") in ("boundary", "place")]
            if not ok:
                notes.append(f"{n}: not in the Census gazetteer and no OSM match; dropped")
                continue
            la, lo = float(ok[0]["lat"]), float(ok[0]["lon"])
            notes.append(f"{n}: not a Census place (a town); pin from OpenStreetMap")
        rows.append({"name": n, "type": "suburb", "county_borough": "", "state_full": STATE_FULL[st], "state_abbr": st,
                     "lat": round(la, 4), "lon": round(lo, 4), "search_query": f"{n}, {st}"})
        seen.add(n)

    # counties, validated against the CBSA (the county is needed for the query check below)
    with ThreadPoolExecutor(4) as ex:
        counties = list(ex.map(lambda r: county_of(r["lat"], r["lon"]), rows))
    allowed = cbsa_county_names(spec["cbsa"])
    keep = []
    for r, c in zip(rows, counties):
        r["county_borough"] = c
        if not c:
            problems.append(f"{r['name']}: could not determine the county")
        elif allowed is not None and c.lower() not in allowed:
            notes.append(f"{r['name']}: {c} County is outside CBSA {spec['cbsa']}; dropped")
            continue
        keep.append(r)
    problems += check_queries(keep, log=log)
    if allowed is None:
        problems.append(f"CBSA {spec['cbsa']} county list unavailable (data_cache/cbsa_delineation_2023.json): counties not validated. "
                        "Run `metro_agent init --fetch` to download the Census delineation file.")
    return keep, notes, problems


def query_distance(query: str, lat: float, lon: float) -> Optional[Tuple[float, str]]:
    """Miles between the pin and where the SCORER's geocoder puts `query`, and the city it names; None when it finds nothing.
    The scorer geocodes `search_query` for the city, state and ZIP (crime and school lookups key on them), so a query that
    lands in another town ("Citrus Heights, CA" -> a neighborhood in Fontana) scores the place with the wrong town's data."""
    from data_sources.geocoding import geocode_with_full_result

    try:
        r = geocode_with_full_result(query)
    except Exception:  # noqa: BLE001
        return None
    time.sleep(1.0)    # stay inside Nominatim's usage policy
    if not r or r[0] is None:
        return None
    return miles(lat, lon, float(r[0]), float(r[1])), str(r[4] or "")


def check_queries(rows: List[Dict[str, Any]], max_miles: float = 15.0, log: Callable[[str], None] = print) -> List[str]:
    """For each suburb, make sure the search query geocodes near its pin. A failing query is retried with the county
    ("Citrus Heights, Sacramento County, CA"); the row is updated when that works, otherwise a problem is returned."""
    problems = []
    for r in rows:
        if r["type"] != "suburb":
            continue
        res = query_distance(r["search_query"], r["lat"], r["lon"])
        if res is not None and res[0] <= max_miles:
            continue
        alt = f"{r['name']}, {r['county_borough']} County, {r['state_abbr']}"
        res2 = query_distance(alt, r["lat"], r["lon"])
        if res2 is not None and res2[0] <= max_miles:
            log(f"  query for {r['name']}: '{r['search_query']}' geocodes {'nowhere' if res is None else f'{res[0]:.0f} miles away ({res[1]})'}; using '{alt}'")
            r["search_query"] = alt
        else:
            problems.append(f"{r['name']}: query '{r['search_query']}' does not geocode within {max_miles:.0f} miles of the pin and the county form did not help")
    return problems


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def record_pin_exceptions(rows: List[Dict[str, Any]], gaz: Dict[Tuple[str, str], List[Dict[str, str]]]) -> int:
    """Preflight compares suburb pins with the Census point of the same name (5 km). A pin moved to the OSM place center
    is intentional, so record why (data/pin_exceptions.json)."""
    p = REPO / "data" / "pin_exceptions.json"
    exc = json.loads(p.read_text())
    n = 0
    for r in rows:
        if r["type"] != "suburb":
            continue
        cands = gaz.get((r["state_abbr"], r["name"]))
        if not cands:
            continue
        d = min(miles(r["lat"], r["lon"], float(c["INTPTLAT"]), float(c["INTPTLONG"])) for c in cands)
        key = f"{r['name']}|{r['state_abbr']}"
        if d * 1.609 > 3.0 and key not in exc:
            exc[key] = (f"Pin is the OpenStreetMap place center of {r['name']}; the Census internal point of this place lies {d:.1f} miles "
                        f"away (large or oddly shaped area, so it can fall in empty land). Chosen by the place-list builder's rule.")
            n += 1
    p.write_text(json.dumps(exc, indent=2) + "\n")
    return n
