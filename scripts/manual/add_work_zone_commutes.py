"""
Batch script: precompute weekday-morning commute times from each catalog place to a
fixed set of metro job hubs ("work zones") using the Google Distance Matrix API.

The frontend snaps a user's work address to the nearest zone, so no live API calls
are needed at request time.

To approximate the FASTEST weekday-morning commute, each pair is sampled at several
morning times (next Tuesday, metro-local time) and the minimum is kept per mode:
  - transit: arrival_time at 8:30, 9:00, 9:30
  - drive:   departure_time at 7:30, 8:15 (duration_in_traffic, best_guess model)

Transit fallback (mirrors fix_cbd_station_coords.py): if the best arrival_time result is
missing or >150 min (arrival_time failure mode for sparse schedules), also try
departure_time at 8:00 and keep the smaller.

--station-origins: for NYC commuter-rail towns, the transit origin is the town's train
station (same station address strings as fix_cbd_station_coords.py, which produced
cbd_transit_minutes), not the catalog centroid. Drive origins stay the centroid.

Stores `work_commute: {zone_id: {"transit": min, "transit_centroid", "transit_station", "drive": min}}` top-level on each
catalog entry. Skips pairs/modes already set (safe to re-run / resume).

Usage:
    PYTHONPATH=. python3 scripts/manual/add_work_zone_commutes.py --dry-run
    PYTHONPATH=. python3 scripts/manual/add_work_zone_commutes.py --metro nyc
    PYTHONPATH=. python3 scripts/manual/add_work_zone_commutes.py --modes transit
    PYTHONPATH=. python3 scripts/manual/add_work_zone_commutes.py --force
    # Redo transit for NYC rail towns from their stations; pilot first with --places
    PYTHONPATH=. python3 scripts/manual/add_work_zone_commutes.py --metro nyc --modes transit \
        --station-origins --only-station-towns --force --places "Scarsdale,Montclair" --dry-run
"""

import argparse
import datetime
import json
import os
import time
from zoneinfo import ZoneInfo

import requests

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
DISTANCE_MATRIX_URL = 'https://maps.googleapis.com/maps/api/distancematrix/json'
ZONES_PATH = 'frontend/lib/workZones.json'
BATCH_SIZE = 25  # Distance Matrix max origins per request

FILES = {
    'nyc': 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'sf': 'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'la': 'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'seattle': 'data/seattle_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
}

TIMEZONES = {
    'nyc': 'America/New_York',
    'sf': 'America/Los_Angeles',
    'la': 'America/Los_Angeles',
    'seattle': 'America/Los_Angeles',
}

# (mode, time param, local HH:MM samples). Minimum across samples is kept.
MODE_SAMPLES = {
    'transit': ('arrival_time', ['08:30', '09:00', '09:30']),
    'drive': ('departure_time', ['07:30', '08:15']),
}

TRANSIT_FALLBACK_OVER_MIN = 150
TRANSIT_FALLBACK_DEPARTURE = '08:00'

# Distance Matrix list prices per 1,000 elements (Essentials vs Pro/traffic).
PRICE_PER_1000 = {'transit': 5.0, 'drive': 10.0}


def next_tuesday_ts(metro: str, hhmm: str) -> int:
    """Unix timestamp for next Tuesday (at least a day out) at hh:mm metro-local time."""
    tz = ZoneInfo(TIMEZONES[metro])
    now = datetime.datetime.now(tz)
    days_ahead = (1 - now.weekday()) % 7 or 7  # Tuesday is 1; always a future Tuesday
    hh, mm = (int(x) for x in hhmm.split(':'))
    target = (now + datetime.timedelta(days=days_ahead)).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return int(target.timestamp())


def load_station_origins(metro: str, places: list) -> dict:
    """Map place index -> station address string, for commuter-rail towns."""
    if metro != 'nyc':
        return {}
    from scripts.manual.fix_cbd_station_coords import NYC_STATIONS
    out = {}
    for i, p in enumerate(places):
        name = p['catalog'].get('name')
        if name not in NYC_STATIONS:
            continue
        # Ridgewood NJ (NJT station) vs Ridgewood Queens: same rule as fix_cbd_station_coords.py
        if name == 'Ridgewood' and float(p['catalog'].get('lon') or 0) >= -74.05:
            continue
        out[i] = NYC_STATIONS[name]
    return out


def origin_for(p: dict, idx: int, mode: str, station_origins: dict) -> str:
    if mode == 'transit' and idx in station_origins:
        return station_origins[idx]
    return f"{p['catalog']['lat']},{p['catalog']['lon']}"


def stored_key(idx: int, mode: str, station_origins: dict) -> str:
    """Transit keeps both origins (transit_centroid / transit_station); `transit` is their minimum."""
    if mode != 'transit':
        return mode
    return 'transit_station' if idx in station_origins else 'transit_centroid'


def fetch_batch(origins: list, zone: dict, mode: str, time_param: str, ts: int) -> list:
    """Return minutes per origin (None on failure) for one request. Origins are 'lat,lon' or address strings."""
    params = {
        'origins': '|'.join(origins),
        'destinations': f'{zone["lat"]},{zone["lon"]}',
        'mode': 'transit' if mode == 'transit' else 'driving',
        time_param: ts,
        'key': GOOGLE_MAPS_API_KEY,
    }
    if mode == 'drive':
        params['traffic_model'] = 'best_guess'
    try:
        data = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=20).json()
    except Exception as e:
        print(f'    Request failed: {e}')
        return [None] * len(origins)
    if data.get('status') != 'OK':
        print(f'    API error: {data.get("status")} {data.get("error_message", "")}')
        return [None] * len(origins)
    out = []
    for row in data['rows']:
        el = row['elements'][0]
        if el.get('status') != 'OK':
            out.append(None)
            continue
        dur = el.get('duration_in_traffic') or el['duration']
        out.append(round(dur['value'] / 60, 1))
    return out


def process_metro(metro: str, zones: list, modes: list, force: bool, dry_run: bool,
                  station_origins_on: bool, only_station_towns: bool, only_places: set | None) -> float:
    path = FILES[metro]
    with open(path) as fh:
        places = [json.loads(line) for line in fh]

    station_origins = load_station_origins(metro, places) if station_origins_on else {}
    candidates = []
    for i, p in enumerate(places):
        cat = p.get('catalog', {})
        if cat.get('lat') is None or cat.get('lon') is None:
            continue
        if only_station_towns and i not in station_origins:
            continue
        if only_places is not None and cat.get('name') not in only_places:
            continue
        candidates.append(i)

    print(f'\n=== {metro.upper()}: {len(candidates)} places x {len(zones)} zones ===')
    for mode in modes:
        time_param, samples = MODE_SAMPLES[mode]
        stamps = ', '.join(
            datetime.datetime.fromtimestamp(next_tuesday_ts(metro, h), ZoneInfo(TIMEZONES[metro])).strftime('%a %Y-%m-%d %H:%M %Z')
            for h in samples)
        print(f'  {mode}: {time_param} samples = {stamps}; keep the minimum')
        if mode == 'transit':
            fb = datetime.datetime.fromtimestamp(next_tuesday_ts(metro, TRANSIT_FALLBACK_DEPARTURE), ZoneInfo(TIMEZONES[metro]))
            print(f'    fallback if best is missing or >{TRANSIT_FALLBACK_OVER_MIN} min: departure_time {fb.strftime("%a %Y-%m-%d %H:%M %Z")}')
    if dry_run:
        print('\n  Origins:')
        for i in candidates:
            p = places[i]
            origins = {m: origin_for(p, i, m, station_origins) for m in modes}
            desc = '; '.join(f'{m}: {o}' for m, o in origins.items())
            print(f"    {p['catalog']['name']} ({p['catalog'].get('county_borough')}, {p['catalog'].get('state_abbr')}) -> {desc}")
        print('\n  Destinations: ' + '; '.join(f"{z['label']} ({z['lat']},{z['lon']})" for z in zones))

    est_cost = 0.0
    for zone in zones:
        for mode in modes:
            time_param, samples = MODE_SAMPLES[mode]
            todo = [i for i in candidates
                    if force or (places[i].get('work_commute') or {}).get(zone['id'], {}).get(
                        stored_key(i, mode, station_origins)) is None]
            elements = len(todo) * len(samples)
            est_cost += elements * PRICE_PER_1000[mode] / 1000
            if not todo:
                continue
            print(f'  {zone["label"]} [{mode}]: {len(todo)} places, {elements} elements (+ fallback calls if needed)')
            if dry_run:
                continue

            origins_all = [origin_for(places[i], i, mode, station_origins) for i in todo]
            best = [None] * len(todo)

            def run_sample(param: str, hhmm: str, idxs: list) -> None:
                ts = next_tuesday_ts(metro, hhmm)
                for start in range(0, len(idxs), BATCH_SIZE):
                    chunk = idxs[start:start + BATCH_SIZE]
                    results = fetch_batch([origins_all[k] for k in chunk], zone, mode, param, ts)
                    for k, minutes in zip(chunk, results):
                        if minutes is not None and (best[k] is None or minutes < best[k]):
                            best[k] = minutes
                    time.sleep(0.2)

            for hhmm in samples:
                run_sample(time_param, hhmm, list(range(len(todo))))
            if mode == 'transit':
                retry = [k for k, m in enumerate(best) if m is None or m > TRANSIT_FALLBACK_OVER_MIN]
                if retry:
                    print(f'    fallback departure_time for {len(retry)} places')
                    run_sample('departure_time', TRANSIT_FALLBACK_DEPARTURE, retry)

            failed = 0
            for i, minutes in zip(todo, best):
                if minutes is None:
                    failed += 1
                    continue
                entry = places[i].setdefault('work_commute', {}).setdefault(zone['id'], {})
                entry[stored_key(i, mode, station_origins)] = minutes
                if mode == 'transit':
                    # Fastest of town-center and station origins (bus from town center can beat the train).
                    opts = [v for v in (entry.get('transit_centroid'), entry.get('transit_station')) if v is not None]
                    entry['transit'] = min(opts)
                else:
                    entry[mode] = minutes
            if failed:
                print(f'    {failed} places had no {mode} route')

            # Write after every zone/mode so a crash never loses paid-for results.
            with open(path, 'w') as fh:
                for p in places:
                    fh.write(json.dumps(p) + '\n')

    if only_places is not None and not dry_run:
        print('\n  Pilot check (Midtown East = Grand Central pin, Midtown West ~ Penn):')
        for i in candidates:
            p = places[i]
            wc = p.get('work_commute') or {}
            print(f"    {p['catalog']['name']}: GCT stored {p.get('cbd_transit_minutes_gct')} vs new {wc.get('nyc_midtown_east', {}).get('transit')}; "
                  f"Penn stored {p.get('cbd_transit_minutes_penn')} vs new {wc.get('nyc_midtown_west', {}).get('transit')}")

    return est_cost


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', choices=list(FILES), help='Run one metro only')
    parser.add_argument('--modes', default='transit,drive', help='Comma list: transit,drive')
    parser.add_argument('--force', action='store_true', help='Re-fetch all, even if already set')
    parser.add_argument('--dry-run', action='store_true', help='Print the full plan and list-price cost; no API calls')
    parser.add_argument('--station-origins', action='store_true', help='Transit from commuter-rail stations (NYC)')
    parser.add_argument('--only-station-towns', action='store_true', help='Only places with a station origin')
    parser.add_argument('--places', help='Comma list of place names (pilot)')
    args = parser.parse_args()

    modes = [m.strip() for m in args.modes.split(',') if m.strip()]
    for m in modes:
        if m not in MODE_SAMPLES:
            raise SystemExit(f'Unknown mode: {m}')
    if not args.dry_run and not GOOGLE_MAPS_API_KEY:
        raise SystemExit('GOOGLE_PLACES_API_KEY not set in environment')

    with open(ZONES_PATH) as fh:
        all_zones = json.load(fh)

    only_places = {n.strip() for n in args.places.split(',')} if args.places else None
    metros = [args.metro] if args.metro else list(FILES)
    total = 0.0
    for metro in metros:
        total += process_metro(metro, all_zones[metro], modes, args.force, args.dry_run,
                               args.station_origins, args.only_station_towns, only_places)

    print(f'\nEstimated list-price cost: ${total:.2f} (before Google free monthly usage)')
    if not args.dry_run:
        print('Copy the updated JSONL files to frontend/data/ before deploying.')


if __name__ == '__main__':
    main()
