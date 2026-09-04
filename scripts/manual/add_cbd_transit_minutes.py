"""
Batch script: compute transit travel time from each catalog place to its metro CBD
using the Google Distance Matrix API (transit mode, Monday 9am departure).

Stores result as `cbd_transit_minutes` top-level on each catalog entry.
Skips places that already have the field set (safe to re-run).

Usage:
    PYTHONPATH=. python3 scripts/manual/add_cbd_transit_minutes.py
    PYTHONPATH=. python3 scripts/manual/add_cbd_transit_minutes.py --metro nyc
    PYTHONPATH=. python3 scripts/manual/add_cbd_transit_minutes.py --force  # re-fetch all
"""

import argparse
import datetime
import json
import os
import time
import requests

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
DISTANCE_MATRIX_URL = 'https://maps.googleapis.com/maps/api/distancematrix/json'

# Primary CBD pin per metro — transit anchor point
CBDS = {
    'nyc': {'lat': 40.7527, 'lon': -73.9772, 'label': 'Grand Central / Midtown'},
    'sf':  {'lat': 37.7894, 'lon': -122.4013, 'label': 'Montgomery St BART / Financial District'},
    'la':  {'lat': 34.0487, 'lon': -118.2595, 'label': '7th/Metro Center / Downtown LA'},
}

FILES = {
    'nyc': 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'sf':  'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'la':  'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
}


def next_monday_9am_ts() -> int:
    """Return Unix timestamp for next Monday at 9:00 AM local time."""
    now = datetime.datetime.now()
    days_ahead = 7 - now.weekday()  # Monday is 0
    if days_ahead == 7:
        days_ahead = 0  # already Monday — use today
    target = (now + datetime.timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    return int(target.timestamp())


def fetch_transit_minutes(origin_lat: float, origin_lon: float, cbd: dict, departure_ts: int) -> float | None:
    params = {
        'origins': f'{origin_lat},{origin_lon}',
        'destinations': f'{cbd["lat"]},{cbd["lon"]}',
        'mode': 'transit',
        'departure_time': departure_ts,
        'key': GOOGLE_MAPS_API_KEY,
    }
    try:
        r = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=10)
        data = r.json()
        if data.get('status') != 'OK':
            print(f'  API error: {data.get("status")} {data.get("error_message", "")}')
            return None
        element = data['rows'][0]['elements'][0]
        if element.get('status') != 'OK':
            print(f'  Element error: {element.get("status")}')
            return None
        return round(element['duration']['value'] / 60, 1)  # seconds → minutes
    except Exception as e:
        print(f'  Request failed: {e}')
        return None


def process_metro(metro: str, force: bool) -> None:
    path = FILES[metro]
    cbd = CBDS[metro]
    departure_ts = next_monday_9am_ts()

    print(f'\n=== {metro.upper()} → {cbd["label"]} ===')
    print(f'File: {path}')

    with open(path) as fh:
        places = [json.loads(line) for line in fh]

    updated = 0
    skipped = 0
    failed = 0

    for i, p in enumerate(places):
        name = p.get('catalog', {}).get('name', '?')
        if not force and p.get('cbd_transit_minutes') is not None:
            skipped += 1
            continue

        lat = p.get('catalog', {}).get('lat')
        lon = p.get('catalog', {}).get('lon')
        if lat is None or lon is None:
            print(f'  [{i+1}] {name}: no lat/lon — skipping')
            failed += 1
            continue

        minutes = fetch_transit_minutes(lat, lon, cbd, departure_ts)
        if minutes is None:
            failed += 1
            print(f'  [{i+1}] {name}: FAILED')
        else:
            p['cbd_transit_minutes'] = minutes
            updated += 1
            print(f'  [{i+1}] {name}: {minutes} min')

        time.sleep(0.15)  # stay well under rate limits

    with open(path, 'w') as fh:
        for p in places:
            fh.write(json.dumps(p) + '\n')

    print(f'\n{metro.upper()} done — updated: {updated}, skipped: {skipped}, failed: {failed}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', choices=['nyc', 'sf', 'la'], help='Run one metro only')
    parser.add_argument('--force', action='store_true', help='Re-fetch all, even if already set')
    args = parser.parse_args()

    if not GOOGLE_MAPS_API_KEY:
        raise SystemExit('GOOGLE_PLACES_API_KEY not set in environment')

    metros = [args.metro] if args.metro else ['nyc', 'sf', 'la']
    for metro in metros:
        process_metro(metro, args.force)

    print('\nAll done. Run check_catalog_health.py to verify, then commit.')


if __name__ == '__main__':
    main()
