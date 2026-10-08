"""
Resolve commuter-rail station coordinates for work-zone commute origins.

Why: Distance Matrix resolves station-name text loosely and silently (e.g. "Ridgewood Train
Station, Ridgewood, NJ" became the ZIP centroid; Morristown and Mount Kisco became town
centers). Origins must be coordinates. See docs/WORK_COMMUTE_PLAYBOOK.md, Step 2.

Source: OpenStreetMap via one Overpass bbox query per metro (free, no Google). Each station
address string from scripts/manual/fix_cbd_station_coords.py is matched by name to the
nearest OSM railway=station|halt to its catalog town (rail yards, subway-only and
service stations excluded). Unmatched stations are printed and left out, never guessed.

Writes data/rail_station_coords.json:
    {metro: {station_address_string: {"lat", "lon", "osm_name", "towns": [...]}}}

Usage:
    PYTHONPATH=. python3 scripts/work_commute/fetch_station_coords.py
    PYTHONPATH=. python3 scripts/work_commute/fetch_station_coords.py --metro sf
"""

import argparse
import json
import math
import re
import time

import requests

from scripts.manual.fix_cbd_station_coords import STATIONS_BY_METRO

OUT_PATH = 'data/rail_station_coords.json'
OVERPASS_URLS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter']
CATALOGS = {
    'nyc': 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'sf': 'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'la': 'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
}
MAX_MATCH_MILES = 6.0

# Agency named in the address string -> words expected in OSM network/operator tags.
AGENCY_HINTS = {
    'BART': ('bart', 'bay area rapid transit'),
    'Caltrain': ('caltrain',),
    'Metrolink': ('metrolink',),
    'Metro-North': ('metro-north', 'metro north'),
    'Long Island Rail Road': ('long island rail road', 'lirr'),
}

# Station strings in fix_cbd_station_coords.py that name stations that don't exist or are closed.
# These towns get town-center origins only (never a guessed station).
NONEXISTENT_STATIONS = {
    'Atherton Caltrain Station, Atherton, CA 94027': 'closed Dec 2020',
    'Newark BART Station, Newark, CA 94560': 'Newark CA has no BART station',
    'Livermore BART Station, Livermore, CA 94550': 'no BART station in Livermore (ACE stop serves San Jose)',
}

# Agency/type words stripped from address strings to get the station's own name.
SUFFIXES = [
    'Metro-North Railroad Station', 'Long Island Rail Road Station', 'Borough Hall Train Station',
    'Transportation Center', 'Train Station', 'Caltrain Station', 'BART Station', 'Metrolink Station',
]


def miles(a_lat, a_lon, b_lat, b_lon):
    r = math.radians
    h = math.sin(r(b_lat - a_lat) / 2) ** 2 + math.cos(r(a_lat)) * math.cos(r(b_lat)) * math.sin(r(b_lon - a_lon) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def station_name(address: str) -> str:
    name = address.split(',')[0].strip()
    for suf in SUFFIXES:
        if name.endswith(suf):
            name = name[: -len(suf)].strip()
            break
    if name.startswith('Glen Rock'):
        return 'Glen Rock'
    return name


def words(text: str) -> set:
    return set(re.sub(r'[^a-z0-9 ]', ' ', text.lower()).split())


def name_tokens(name: str) -> list:
    """Alternatives for names like 'Whittier/Norwalk' or 'Dublin/Pleasanton'."""
    return [t.strip().lower() for t in re.split(r'[/]', name) if t.strip()]


def name_matches(token: str, osm_name: str) -> bool:
    """All words of the token appear in the OSM name, in any order ('Burbank Downtown' ~ 'Downtown Burbank')."""
    return words(token) <= words(osm_name)


def fetch_osm_stations(bbox):
    s, w, n, e = bbox
    query = (
        f'[out:json][timeout:170];'
        f'(node["railway"~"station|halt"]({s},{w},{n},{e});'
        f'way["railway"~"station|halt"]({s},{w},{n},{e}););out tags center;'
    )
    for attempt in range(4):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
        try:
            r = requests.post(url, data={'data': query}, timeout=200,
                              headers={'User-Agent': 'homefit-station-coords'})
            r.raise_for_status()
            return r.json()['elements']
        except Exception as exc:
            print(f'  Overpass attempt {attempt + 1} ({url}) failed: {exc}')
            time.sleep(30)
    raise SystemExit('Overpass unavailable; try again later')


def usable(el) -> bool:
    tags = el.get('tags', {})
    if 'name' not in tags:
        return False
    if tags.get('railway') not in ('station', 'halt'):
        return False
    is_subway = tags.get('station') == 'subway' or tags.get('subway') == 'yes'
    is_bart = 'bart' in (tags.get('network', '') + tags.get('operator', '')).lower() or \
        'bay area rapid transit' in (tags.get('network', '') + tags.get('operator', '')).lower()
    # BART is tagged like a subway in OSM but is the commuter rail we want; NYC subway is not.
    if is_subway and not is_bart:
        return False
    if 'yard' in tags['name'].lower():
        return False
    return True


def point(el):
    if 'lat' in el:
        return el['lat'], el['lon']
    return el['center']['lat'], el['center']['lon']


def process(metro: str) -> dict:
    stations = STATIONS_BY_METRO[metro]
    catalog = [json.loads(l)['catalog'] for l in open(CATALOGS[metro])]
    towns = {}
    for c in catalog:
        if c['name'] not in stations:
            continue
        # Ridgewood NJ (NJT) vs Ridgewood Queens: same rule as fix_cbd_station_coords.py
        if c['name'] == 'Ridgewood' and float(c['lon']) >= -74.05:
            continue
        towns[c['name']] = (float(c['lat']), float(c['lon']))

    lats = [t[0] for t in towns.values()]
    lons = [t[1] for t in towns.values()]
    bbox = (min(lats) - 0.1, min(lons) - 0.1, max(lats) + 0.1, max(lons) + 0.1)
    print(f'\n=== {metro.upper()}: {len(towns)} towns, {len(set(stations.values()))} stations ===')
    elements = [e for e in fetch_osm_stations(bbox) if usable(e)]
    print(f'  {len(elements)} OSM rail stations in bbox')

    by_address = {}
    for town, coords in sorted(towns.items()):
        by_address.setdefault(stations[town], []).append((town, coords))

    out = {}
    for address, town_list in sorted(by_address.items()):
        names = [t for t, _ in town_list]
        if address in NONEXISTENT_STATIONS:
            print(f'  SKIP: {", ".join(names)} -> "{address}" ({NONEXISTENT_STATIONS[address]})')
            continue
        full = station_name(address)
        tokens = name_tokens(full)
        cands = []
        for el in elements:
            if any(name_matches(tok, el['tags']['name']) for tok in tokens):
                lat, lon = point(el)
                # Shared stations (e.g. Portola Valley -> Redwood City): distance to the nearest town using it.
                d = min(miles(lat, lon, t_lat, t_lon) for _, (t_lat, t_lon) in town_list)
                if d <= MAX_MATCH_MILES:
                    cands.append((d, el))
        if not cands:
            print(f'  NO MATCH: {", ".join(names)} -> "{address}" (looked for {tokens})')
            continue
        # Narrow by the agency named in the address (BART vs ACE, Metrolink vs Metro light rail).
        for agency, hints in AGENCY_HINTS.items():
            if agency in address:
                tagged = [c for c in cands if any(h in (c[1]['tags'].get('network', '') + ' ' + c[1]['tags'].get('operator', '')).lower() for h in hints)]
                cands = tagged or cands
        # Prefer the full station name ('Dublin/Pleasanton'), then an exact token name, then nearest.
        full_match = [c for c in cands if words(c[1]['tags']['name']) == words(full)]
        exact = [c for c in cands if words(c[1]['tags']['name']) in [words(t) for t in tokens]]
        d, el = min(full_match or exact or cands, key=lambda c: c[0])
        lat, lon = point(el)
        out[address] = {'lat': round(lat, 6), 'lon': round(lon, 6), 'osm_name': el['tags']['name'], 'towns': names}
        print(f'  {", ".join(names)}: {el["tags"]["name"]} ({d:.1f} mi from town center)')
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', choices=list(CATALOGS))
    args = parser.parse_args()
    try:
        existing = json.load(open(OUT_PATH))
    except FileNotFoundError:
        existing = {}
    for metro in ([args.metro] if args.metro else list(CATALOGS)):
        existing[metro] = process(metro)
        # Save after each metro so a later Overpass failure doesn't lose earlier results.
        with open(OUT_PATH, 'w') as fh:
            json.dump(existing, fh, indent=1, sort_keys=True)
        print(f'  saved {metro} to {OUT_PATH}')
        time.sleep(5)


if __name__ == '__main__':
    main()
