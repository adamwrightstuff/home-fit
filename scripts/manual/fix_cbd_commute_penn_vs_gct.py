"""
Re-fetch Distance Matrix to Penn Station for all NYC metro places and compare
to existing GCT-based cbd_transit_minutes. Stores the minimum (fairest) value
and records both raw times so it's auditable.

Fields written:
  cbd_transit_minutes          — min(gct, penn), rounded to 1 decimal
  cbd_transit_minutes_gct      — original GCT measurement (preserved)
  cbd_transit_minutes_penn     — new Penn Station measurement
  cbd_transit_dest             — 'gct' or 'penn' (which destination won)

Usage:
    PYTHONPATH=. python3 scripts/manual/fix_cbd_commute_penn_vs_gct.py
    PYTHONPATH=. python3 scripts/manual/fix_cbd_commute_penn_vs_gct.py --dry-run
    PYTHONPATH=. python3 scripts/manual/fix_cbd_commute_penn_vs_gct.py --force  # re-fetch even already done
"""

import argparse
import datetime
import json
import os
import time

import requests

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
DISTANCE_MATRIX_URL = 'https://maps.googleapis.com/maps/api/distancematrix/json'

FILE = 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl'

GCT  = {'lat': 40.7527, 'lon': -73.9772, 'label': 'Grand Central'}
PENN = {'lat': 40.7506, 'lon': -73.9971, 'label': 'Penn Station'}


def next_monday_9am_ts() -> int:
    now = datetime.datetime.now()
    days_ahead = 7 - now.weekday()
    if days_ahead == 7:
        days_ahead = 0
    target = (now + datetime.timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    return int(target.timestamp())


def fetch_minutes(origin_lat: float, origin_lon: float, dest: dict, departure_ts: int) -> float | None:
    params = {
        'origins': f'{origin_lat},{origin_lon}',
        'destinations': f'{dest["lat"]},{dest["lon"]}',
        'mode': 'transit',
        'arrival_time': departure_ts,
        'key': GOOGLE_MAPS_API_KEY,
    }
    try:
        r = requests.get(DISTANCE_MATRIX_URL, params=params, timeout=10)
        data = r.json()
        if data.get('status') != 'OK':
            return None
        el = data['rows'][0]['elements'][0]
        if el.get('status') != 'OK':
            return None
        return round(el['duration']['value'] / 60, 1)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true', help='Re-fetch even places already processed')
    args = parser.parse_args()

    if not GOOGLE_MAPS_API_KEY:
        raise SystemExit('GOOGLE_PLACES_API_KEY not set')

    with open(FILE) as f:
        places = [json.loads(l) for l in f]

    departure_ts = next_monday_9am_ts()
    updated = skipped = failed = 0

    for i, p in enumerate(places):
        name = p.get('catalog', {}).get('name', '?')

        if not args.force and p.get('cbd_transit_minutes_penn') is not None:
            skipped += 1
            continue

        lat = p.get('catalog', {}).get('lat')
        lon = p.get('catalog', {}).get('lon')
        if lat is None or lon is None:
            print(f'  [{i+1}] {name}: no coords — skip')
            failed += 1
            continue

        gct_existing = p.get('cbd_transit_minutes')

        penn_min = fetch_minutes(lat, lon, PENN, departure_ts)
        time.sleep(0.15)

        if penn_min is None:
            print(f'  [{i+1}] {name}: Penn fetch failed')
            failed += 1
            continue

        # If we don't have a fresh GCT time, use the stored one
        gct_min = gct_existing

        if gct_min is not None:
            winner = 'penn' if penn_min < gct_min else 'gct'
            best = min(penn_min, gct_min)
        else:
            winner = 'penn'
            best = penn_min

        changed = (gct_existing is None or abs(best - gct_existing) >= 0.5)

        p['cbd_transit_minutes_gct'] = gct_existing
        p['cbd_transit_minutes_penn'] = penn_min
        p['cbd_transit_minutes'] = best
        p['cbd_transit_dest'] = winner

        tag = f' ← {winner} wins ({gct_min} gct vs {penn_min} penn)' if changed and gct_min else ''
        print(f'  [{i+1}] {name}: {best} min{tag}')
        updated += 1

    print(f'\nDone — updated: {updated}, skipped: {skipped}, failed: {failed}')

    if args.dry_run:
        print('(dry-run — not writing)')
        return

    with open(FILE, 'w') as f:
        for p in places:
            f.write(json.dumps(p) + '\n')
    print(f'Wrote {FILE}')


if __name__ == '__main__':
    main()
