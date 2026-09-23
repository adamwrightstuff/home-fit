"""
For every commuter-rail suburb, geocode the train station by name and:
  1. Re-fetch cbd_transit_minutes with arrival_time=9am, using the station as the
     transit origin (text-based, via Distance Matrix — does not touch catalog lat/lon,
     which is the place's actual location and is what pillar scoring is keyed to)
  2. Re-fetch with departure_time for results >150 min (arrival_time failure mode)
  3. NYC: update gct/penn/dest fields too (takes min of GCT and Penn)

Run:
    PYTHONPATH=. python3 scripts/manual/fix_cbd_station_coords.py
    PYTHONPATH=. python3 scripts/manual/fix_cbd_station_coords.py --dry-run
    PYTHONPATH=. python3 scripts/manual/fix_cbd_station_coords.py --metro nyc
"""

import argparse, datetime, json, os, time, requests

KEY = os.environ.get('GOOGLE_PLACES_API_KEY', '')
DM  = 'https://maps.googleapis.com/maps/api/distancematrix/json'
GEO = 'https://maps.googleapis.com/maps/api/geocode/json'

FILES = {
    'nyc': 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'sf':  'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'la':  'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
}

CBDS = {
    'nyc': {'lat': 40.7527, 'lon': -73.9772},
    'sf':  {'lat': 37.7894, 'lon': -122.4013},
    'la':  {'lat': 34.0487, 'lon': -118.2595},
}
GCT  = {'lat': 40.7527, 'lon': -73.9772}
PENN = {'lat': 40.7506, 'lon': -73.9971}

# Metro-North New Haven Line (all to GCT)
MNR_NEW_HAVEN = {
    'Larchmont':     'Larchmont Metro-North Railroad Station, 1 Railroad Way, Larchmont, NY 10538',
    'Mamaroneck':    'Mamaroneck Metro-North Railroad Station, Mamaroneck, NY 10543',
    'Harrison':      'Harrison Metro-North Railroad Station, Harrison, NY 10528',
    'Rye':           'Rye Metro-North Railroad Station, Rye, NY 10580',
    'Port Chester':  'Port Chester Metro-North Railroad Station, Port Chester, NY 10573',
    'Cos Cob':       'Cos Cob Metro-North Railroad Station, Cos Cob, Greenwich, CT 06807',
    'Old Greenwich': 'Old Greenwich Metro-North Railroad Station, Old Greenwich, CT 06870',
    'Greenwich':     'Greenwich Metro-North Railroad Station, Greenwich, CT 06830',
    'Riverside':     'Riverside Metro-North Railroad Station, Riverside, CT 06878',
    'Stamford':      'Stamford Transportation Center, Stamford, CT 06901',
    'Darien':        'Noroton Heights Metro-North Railroad Station, Darien, CT 06820',
    'Norwalk':       'South Norwalk Metro-North Railroad Station, Norwalk, CT 06854',
    'Westport':      'Westport Train Station, 46 Railroad Pl, Westport, CT 06880',
    'Southport':     'Southport Metro-North Railroad Station, 591 Pequot Ave, Southport, CT 06890',
    'Fairfield':     'Fairfield Metro-North Railroad Station, Fairfield, CT 06824',
}

# Metro-North Harlem Line (to GCT)
MNR_HARLEM = {
    'Bronxville':    'Bronxville Metro-North Railroad Station, Bronxville, NY 10708',
    'Tuckahoe':      'Tuckahoe Metro-North Railroad Station, Tuckahoe, NY 10707',
    'Eastchester':   'Tuckahoe Metro-North Railroad Station, Tuckahoe, NY 10707',
    'Scarsdale':     'Scarsdale Metro-North Railroad Station, Scarsdale, NY 10583',
    'White Plains':  'White Plains Metro-North Railroad Station, White Plains, NY 10601',
    'Pleasantville': 'Pleasantville Metro-North Railroad Station, Pleasantville, NY 10570',
    'Chappaqua':     'Chappaqua Metro-North Railroad Station, Chappaqua, NY 10514',
    'Katonah':       'Katonah Metro-North Railroad Station, Katonah, NY 10536',
    'Bedford':       'Bedford Hills Metro-North Railroad Station, Bedford Hills, NY 10507',
    'Mount Kisco':   'Mount Kisco Metro-North Railroad Station, Mount Kisco, NY 10549',
}

# Metro-North Hudson Line (to GCT)
MNR_HUDSON = {
    'Yonkers':          'Yonkers Metro-North Railroad Station, Yonkers, NY 10701',
    'Ardsley':          'Dobbs Ferry Metro-North Railroad Station, Dobbs Ferry, NY 10522',
    'Dobbs Ferry':      'Dobbs Ferry Metro-North Railroad Station, Dobbs Ferry, NY 10522',
    'Irvington':        'Irvington Metro-North Railroad Station, Irvington, NY 10533',
    'Tarrytown':        'Tarrytown Metro-North Railroad Station, Tarrytown, NY 10591',
    'Sleepy Hollow':    'Philipse Manor Metro-North Railroad Station, Sleepy Hollow, NY 10591',
    'Ossining':         'Ossining Metro-North Railroad Station, Ossining, NY 10562',
    'Croton-on-Hudson': 'Croton-Harmon Metro-North Railroad Station, Croton-on-Hudson, NY 10520',
    'Peekskill':        'Peekskill Metro-North Railroad Station, Peekskill, NY 10566',
}

# LIRR (to Penn Station primarily, but we take min of GCT/Penn)
LIRR = {
    'Huntington':       'Huntington Long Island Rail Road Station, Huntington, NY 11743',
    # Cold Spring Harbor LIRR: old pin is accurate; new geocode gets worse results — skip
    # 'Cold Spring Harbor': ...,
    'Babylon':          'Babylon Long Island Rail Road Station, Babylon, NY 11702',
    'Roslyn':           'Roslyn Long Island Rail Road Station, Roslyn Heights, NY 11577',
    'Manhasset':        'Plandome Long Island Rail Road Station, Manhasset, NY 11030',
    'Port Washington':  'Port Washington Long Island Rail Road Station, Port Washington, NY 11050',
    'Great Neck':       'Great Neck Long Island Rail Road Station, Great Neck, NY 11021',
    'Bayside':          'Bayside Long Island Rail Road Station, Bayside, NY 11361',
    'Forest Hills':     'Forest Hills Long Island Rail Road Station, Forest Hills, NY 11375',
    # Kew Gardens LIRR — already at good station pin; skip
    # 'Kew Gardens':   'Kew Gardens Long Island Rail Road Station, Kew Gardens, NY 11415',
    'Jamaica':          'Jamaica Long Island Rail Road Station, Jamaica, NY 11435',
    'Long Beach':       'Long Beach Long Island Rail Road Station, Long Beach, NY 11561',
    'Lynbrook':         'Lynbrook Long Island Rail Road Station, Lynbrook, NY 11563',
    'Merrick':          'Merrick Long Island Rail Road Station, Merrick, NY 11566',
    'Bellmore':         'Bellmore Long Island Rail Road Station, Bellmore, NY 11710',
    'Freeport':         'Freeport Long Island Rail Road Station, Freeport, NY 11520',
    'Valley Stream':    'Valley Stream Long Island Rail Road Station, Valley Stream, NY 11580',
    'Rockville Centre': 'Rockville Centre Long Island Rail Road Station, Rockville Centre, NY 11570',
    'Malverne':         'Malverne Long Island Rail Road Station, Malverne, NY 11565',
    'Floral Park':      'Floral Park Long Island Rail Road Station, Floral Park, NY 11001',
    'New Hyde Park':    'New Hyde Park Long Island Rail Road Station, New Hyde Park, NY 11040',
    'Garden City':      'Garden City Long Island Rail Road Station, Garden City, NY 11530',
    'Mineola':          'Mineola Long Island Rail Road Station, Mineola, NY 11501',
    'Hempstead':        'Hempstead Long Island Rail Road Station, Hempstead, NY 11550',
    'Woodmere':         'Woodmere Long Island Rail Road Station, Woodmere, NY 11598',
    'Lawrence':         'Lawrence Long Island Rail Road Station, Lawrence, NY 11559',
    'Cedarhurst':       'Cedarhurst Long Island Rail Road Station, Cedarhurst, NY 11516',
    'Hewlett':          'Hewlett Long Island Rail Road Station, Hewlett, NY 11557',
}

# Staten Island Railroad — already pinned to station coords from previous fix; skip.

# NJ Transit (to Penn Station — take min of GCT/Penn)
NJT = {
    'Westfield':   'Westfield Train Station, Westfield, NJ 07090',
    'Glen Ridge':  'Glen Ridge Train Station, Glen Ridge, NJ 07028',
    'Montclair':   'Bay Street Train Station, Montclair, NJ 07042',
    'Maplewood':   'Maplewood Train Station, Maplewood, NJ 07040',
    'South Orange':'South Orange Train Station, South Orange, NJ 07079',
    'Millburn':    'Millburn Train Station, Millburn, NJ 07041',
    'Short Hills': 'Short Hills Train Station, Short Hills, NJ 07078',
    'Summit':      'Summit Train Station, Summit, NJ 07901',
    'Madison':     'Madison Train Station, Madison, NJ 07940',
    'Chatham':     'Chatham Train Station, Chatham, NJ 07928',
    'Morristown':  'Morristown Train Station, Morristown, NJ 07960',
    'Cranford':    'Cranford Train Station, Cranford, NJ 07016',
    'Westwood':    'Westwood Train Station, Westwood, NJ 07675',
    # Glen Rock has two NJT stations — use the main line one
    'Glen Rock':   'Glen Rock Borough Hall Train Station, Glen Rock, NJ 07452',
}

# NJ — Bergen County suburbs with Pascack Valley / Main Line service
NJT_BERGEN = {
    'Ridgewood': 'Ridgewood Train Station, Ridgewood, NJ 07450',
}

# NYC: all stations by metro catalog name (excludes subway-only neighborhoods)
NYC_STATIONS = {}
NYC_STATIONS.update(MNR_NEW_HAVEN)
NYC_STATIONS.update(MNR_HARLEM)
NYC_STATIONS.update(MNR_HUDSON)
NYC_STATIONS.update(LIRR)
NYC_STATIONS.update(NJT)
NYC_STATIONS.update(NJT_BERGEN)

# SF — Caltrain
CALTRAIN = {
    'Palo Alto':          'Palo Alto Caltrain Station, Palo Alto, CA 94301',
    'Menlo Park':         'Menlo Park Caltrain Station, Menlo Park, CA 94025',
    'Redwood City':       'Redwood City Caltrain Station, Redwood City, CA 94063',
    'Belmont':            'Belmont Caltrain Station, Belmont, CA 94002',
    'San Carlos':         'San Carlos Caltrain Station, San Carlos, CA 94070',
    'Millbrae':           'Millbrae Caltrain Station, Millbrae, CA 94030',
    'San Mateo':          'San Mateo Caltrain Station, San Mateo, CA 94401',
    'Burlingame':         'Burlingame Caltrain Station, Burlingame, CA 94010',
    'San Bruno':          'San Bruno Caltrain Station, San Bruno, CA 94066',
    'South San Francisco':'South San Francisco Caltrain Station, South San Francisco, CA 94080',
    'Mountain View':      'Mountain View Caltrain Station, Mountain View, CA 94041',
    'Sunnyvale':          'Sunnyvale Caltrain Station, Sunnyvale, CA 94086',
    'Santa Clara':        'Santa Clara Caltrain Station, Santa Clara, CA 95050',
    'Campbell':           'Santa Clara Caltrain Station, Santa Clara, CA 95050',
    'Cupertino':          'Lawrence Caltrain Station, Sunnyvale, CA 94086',
    'Saratoga':           'Lawrence Caltrain Station, Sunnyvale, CA 94086',
    # Los Gatos Caltrain closed — no active rail service; skip
    # 'Los Gatos': ...,
    'Los Altos':          'San Antonio Caltrain Station, Mountain View, CA 94040',
    'Los Altos Hills':    'San Antonio Caltrain Station, Mountain View, CA 94040',
    'Woodside':           'Redwood City Caltrain Station, Redwood City, CA 94063',
    'Portola Valley':     'Redwood City Caltrain Station, Redwood City, CA 94063',
    'Atherton':           'Atherton Caltrain Station, Atherton, CA 94027',
    'Hillsborough':       'San Mateo Caltrain Station, San Mateo, CA 94401',
}

# SF — BART suburban
BART_SUBURBAN = {
    'Fremont':      'Fremont BART Station, Fremont, CA 94538',
    'Union City':   'Union City BART Station, Union City, CA 94587',
    'Hayward':      'Hayward BART Station, Hayward, CA 94541',
    'San Leandro':  'San Leandro BART Station, San Leandro, CA 94577',
    'Castro Valley':'Castro Valley BART Station, Castro Valley, CA 94546',
    'Dublin':       'Dublin/Pleasanton BART Station, Dublin, CA 94568',
    'Pleasanton':   'Dublin/Pleasanton BART Station, Pleasanton, CA 94566',
    'Livermore':    'Livermore BART Station, Livermore, CA 94550',
    'Walnut Creek': 'Walnut Creek BART Station, Walnut Creek, CA 94596',
    'Pleasant Hill':'Pleasant Hill BART Station, Pleasant Hill, CA 94523',
    'Concord':      'Concord BART Station, Concord, CA 94520',
    'Lafayette':    'Lafayette BART Station, Lafayette, CA 94549',
    'Orinda':       'Orinda BART Station, Orinda, CA 94563',
    'El Cerrito':   'El Cerrito del Norte BART Station, El Cerrito, CA 94530',
    'Richmond':     'Richmond BART Station, Richmond, CA 94801',
    'Milpitas':     'Milpitas BART Station, Milpitas, CA 95035',
    'Newark':       'Newark BART Station, Newark, CA 94560',
}

SF_STATIONS = {}
SF_STATIONS.update(CALTRAIN)
SF_STATIONS.update(BART_SUBURBAN)

# LA — Metrolink / Metro light rail suburban
LA_STATIONS = {
    'Burbank':      'Burbank Downtown Metrolink Station, 201 N Front St, Burbank, CA 91502',
    'San Fernando': 'San Fernando Metrolink Station, San Fernando, CA 91340',
    'Sylmar':       'Sylmar/San Fernando Metrolink Station, Sylmar, CA 91342',
    # Monrovia Metrolink gives worse result than town center; skip
    # 'Monrovia': ...,
    'Pasadena':     'Del Mar Metrolink Station, Pasadena, CA 91103',
    'Chatsworth':   'Chatsworth Metrolink Station, Chatsworth, CA 91311',
    'Porter Ranch': 'Chatsworth Metrolink Station, Chatsworth, CA 91311',
    'Whittier':     'Whittier/Norwalk Metrolink Station, Whittier, CA 90601',
    'El Monte':     'El Monte Metrolink Station, El Monte, CA 91731',
    'Arcadia':      'Arcadia Metrolink Station, Arcadia, CA 91006',
    'Cerritos':     'Norwalk/Santa Fe Springs Metrolink Station, Norwalk, CA 90650',
    'La Mirada':    'Norwalk/Santa Fe Springs Metrolink Station, Norwalk, CA 90650',
}

STATIONS_BY_METRO = {
    'nyc': NYC_STATIONS,
    'sf':  SF_STATIONS,
    'la':  LA_STATIONS,
}


def geocode(query: str):
    r = requests.get(GEO, params={'address': query, 'key': KEY}, timeout=10).json()
    if r.get('results'):
        loc = r['results'][0]['geometry']['location']
        return round(loc['lat'], 6), round(loc['lng'], 6), r['results'][0]['formatted_address']
    return None, None, None


def fetch_dm(origin, dest_lat, dest_lon, mode='arrival_time') -> float | None:
    """origin can be a 'lat,lon' string or a place name string."""
    t = next_monday_9am_ts()
    r = requests.get(DM, params={
        'origins': origin,
        'destinations': f'{dest_lat},{dest_lon}',
        'mode': 'transit', mode: t, 'key': KEY,
    }, timeout=10).json()
    el = r['rows'][0]['elements'][0]
    if el.get('status') == 'OK':
        return round(el['duration']['value'] / 60, 1)
    return None


def next_monday_9am_ts() -> int:
    now = datetime.datetime.now()
    days_ahead = 7 - now.weekday()
    if days_ahead == 7:
        days_ahead = 0
    return int((now + datetime.timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0).timestamp())


def best_minutes(origin: str, dest_lat, dest_lon, use_departure=False) -> float | None:
    """Fetch transit time. Uses arrival_time (best morning train) unless use_departure=True.
    Falls back to departure_time if arrival_time returns >150 or None."""
    if use_departure:
        mins = fetch_dm(origin, dest_lat, dest_lon, 'departure_time')
        time.sleep(0.12)
        return mins
    mins = fetch_dm(origin, dest_lat, dest_lon, 'arrival_time')
    time.sleep(0.12)
    if mins is None or mins > 150:
        dep = fetch_dm(origin, dest_lat, dest_lon, 'departure_time')
        time.sleep(0.12)
        if dep is not None and (mins is None or dep < mins):
            mins = dep
    return mins


def process(metro: str, dry_run: bool) -> None:
    path = FILES[metro]
    cbd = CBDS[metro]
    stations = STATIONS_BY_METRO[metro]
    # SF and LA: departure_time is more reliable (arrival_time can inflate for sparse schedules)
    use_dep = metro in ('sf', 'la')
    print(f'\n=== {metro.upper()} ({"departure" if use_dep else "arrival"}_time) ===')

    with open(path) as f:
        places = [json.loads(l) for l in f]

    # Build name→index; for duplicates, pick the one with lon in the right state
    name_to_idx: dict[str, int] = {}
    for i, p in enumerate(places):
        n = p.get('catalog', {}).get('name', '')
        lon = float(p['catalog'].get('lon') or 0)
        if n in name_to_idx:
            # Ridgewood NJ vs Queens: NJ has lon < -74.05
            existing_lon = float(places[name_to_idx[n]]['catalog'].get('lon') or 0)
            if n == 'Ridgewood' and lon < -74.05:
                name_to_idx[n] = i  # prefer the NJ one for NJT stations
            # Otherwise keep the existing (first found)
        else:
            name_to_idx[n] = i

    changed = []
    skipped_worse = []

    for place_name, query in sorted(stations.items()):
        idx = name_to_idx.get(place_name)
        if idx is None:
            continue

        p = places[idx]
        slat, slon, formatted = geocode(query)
        time.sleep(0.1)
        if slat is None:
            print(f'  {place_name}: geocode FAILED for "{query}"')
            continue

        old_lat = float(p['catalog'].get('lat') or 0)
        old_lon = float(p['catalog'].get('lon') or 0)
        dist_m = ((slat - old_lat) ** 2 + (slon - old_lon) ** 2) ** 0.5 * 111_000
        coord_tag = f' [{dist_m:.0f}m]' if dist_m > 100 else ''

        # Use station query TEXT as origin (Google snaps it to the platform correctly)
        gct_mins = best_minutes(query, cbd['lat'], cbd['lon'], use_departure=use_dep)
        if gct_mins is None:
            print(f'  {place_name}: transit fetch FAILED  ({formatted})')
            continue

        final_mins = gct_mins
        penn_mins = None

        if metro == 'nyc':
            penn_mins = best_minutes(query, PENN['lat'], PENN['lon'], use_departure=use_dep)
            if penn_mins is not None and penn_mins < gct_mins:
                final_mins = penn_mins

        old_mins = p.get('cbd_transit_minutes') or 999
        # Skip if new value is worse by >10 min and coord didn't change much
        if final_mins > old_mins + 10 and dist_m < 500:
            skipped_worse.append(f'{place_name}: {old_mins}→{final_mins} (skipped, worse){coord_tag}')
            continue

        delta = f'{old_mins}→{final_mins}'
        print(f'  {place_name}: {delta} min{coord_tag}  ({formatted})')

        if not dry_run:
            # Station coords (slat/slon) are used only for the skip-heuristic above and
            # for logging — they must never be written back into catalog lat/lon, which
            # is the place's actual location and what pillar scoring is keyed to.
            p['cbd_transit_minutes'] = final_mins
            if metro == 'nyc':
                p['cbd_transit_minutes_gct'] = gct_mins
                p['cbd_transit_minutes_penn'] = penn_mins
                p['cbd_transit_dest'] = 'penn' if (penn_mins and penn_mins < gct_mins) else 'gct'

        changed.append(place_name)

    if skipped_worse:
        print('\n  --- skipped (new > old + 10 min, small coord change) ---')
        for s in skipped_worse:
            print(f'  {s}')

    if not dry_run and changed:
        with open(path, 'w') as f:
            for p in places:
                f.write(json.dumps(p) + '\n')
        print(f'\nWrote {path} ({len(changed)} places updated)')
    else:
        print(f'\nDry-run: would update {len(changed)} places')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--metro', choices=['nyc', 'sf', 'la'])
    args = parser.parse_args()

    if not KEY:
        raise SystemExit('GOOGLE_PLACES_API_KEY not set')

    metros = [args.metro] if args.metro else ['nyc', 'sf', 'la']
    for m in metros:
        process(m, args.dry_run)

    print('\nAll done.')


if __name__ == '__main__':
    main()
