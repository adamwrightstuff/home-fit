"""
Compute weekday-morning transit commute times with our own router (r5py), no Google.

Inputs (built by the other scripts in this folder):
  data/cache/transit/<metro>/<metro>_region.osm.pbf   street network (OSM, clipped)
  data/cache/transit/<metro>/norm/gtfs_*.zip          schedules, each agency on its typical
                                                      weekday, all on normalize_gtfs.TARGET_DATE
  data/rail_station_coords.json                       station origins for rail towns
  frontend/lib/workZones.json                         hubs (destinations)

Origins: every catalog place centroid ("c:<row>") and, for commuter-rail towns, its station
("s:<row>"). Departures are swept minute by minute across the morning window and the travel time
includes any wait for the first vehicle. The 1st percentile (r5py's lowest) is the best-timed
trip, i.e. a commuter who catches the right train; this is the meaning of "commute time" shown
in the app. The 50th is a typical untimed trip. The percentile is chosen for what it means,
not tuned to match Google (which is only used as a sanity check).

Writes data/cache/transit/<metro>/r5_transit.csv (does NOT touch the catalog; merging is a
separate, reviewed step).

Usage (needs Java 21):
    JAVA_HOME=/opt/homebrew/opt/openjdk@21 .venv-r5/bin/python scripts/work_commute/compute_transit_r5.py --metro nyc
"""

import argparse
import datetime as dt
import glob
import io
import json
import sys
import zipfile

# r5py reads JVM options from argv; set before import.
sys.argv += ['--max-memory', '10G']

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import r5py  # noqa: E402
from shapely.geometry import Point  # noqa: E402

sys.path.insert(0, '.')
from scripts.work_commute.normalize_gtfs import TARGET_DATE  # noqa: E402
from scripts.manual.fix_cbd_station_coords import STATIONS_BY_METRO  # noqa: E402

CATALOGS = {m: f'data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl' for m in ('nyc', 'sf', 'la', 'seattle')}
# Departures swept every minute from 7:30 to 8:45. A 35-minute trip then arrives about 8:05 to 9:20 and
# an 80-minute trip about 8:50 to 10:05, i.e. mid-morning arrivals (nobody starts at 8:00 sharp).
DEPART_START = dt.time(7, 30)
DEPART_WINDOW = dt.timedelta(minutes=75)
MAX_TIME = dt.timedelta(hours=3)

# Rail feeds whose stop locations define where a station trip really starts (the platform stop,
# not the OSM station-building pin, which can be 150+ yards away and adds a fake walk).
# 'feed:rail' = a combined multi-agency feed; keep only stops served by route_type 1 (metro) or 2 (rail).
RAIL_FEEDS = {'nyc': ['mnr', 'lirr', 'njt_rail'], 'sf': ['511rg:rail'], 'la': ['metrolink']}
SNAP_MAX_METERS = 300

# Ferry towns: the router only walks about 20 minutes to a stop, so a town center a mile or two
# from the dock never boards the ferry. As for rail towns, also start from the terminal.
# Terminals come from the combined feed's route_type 4 routes; places within FERRY_ACCESS_METERS
# (a short drive or bike ride) of one get an extra "f:<row>" origin at the nearest terminal.
FERRY_METROS = {'sf': '511rg'}
FERRY_ACCESS_METERS = 3000

# Destinations that are not user-facing hubs but back the older "min to downtown" card line:
# the NYC card used Grand Central (= nyc_midtown_east, same pin) or Penn Station.
# Penn pin = the station complex itself (LIRR platforms 40.7506,-73.9936; NJ Transit 40.7500,-73.9924).
# The pin the old Google card used (40.7506,-73.9971) is 300 to 400 m west of the platforms.
EXTRA_DESTINATIONS = {'nyc': [('cbd_penn', 40.7503, -73.9930)]}


def rail_stops(metro: str) -> pd.DataFrame:
    frames = []
    for spec in RAIL_FEEDS.get(metro, []):
        feed, _, only = spec.partition(':')
        z = zipfile.ZipFile(f'data/cache/transit/{metro}/norm/gtfs_{feed}.zip')
        st = pd.read_csv(io.BytesIO(z.read('stops.txt')), dtype=str)
        if only == 'rail':
            routes = pd.read_csv(io.BytesIO(z.read('routes.txt')), dtype=str)
            rail_routes = set(routes[routes.route_type.isin(['1', '2'])].route_id)
            trips = pd.read_csv(io.BytesIO(z.read('trips.txt')), dtype=str, usecols=['trip_id', 'route_id'])
            rail_trips = set(trips[trips.route_id.isin(rail_routes)].trip_id)
            stt = pd.read_csv(io.BytesIO(z.read('stop_times.txt')), dtype=str, usecols=['trip_id', 'stop_id'])
            st = st[st.stop_id.isin(set(stt[stt.trip_id.isin(rail_trips)].stop_id))]
        frames.append(pd.DataFrame({'name': st.stop_name, 'lat': st.stop_lat.astype(float), 'lon': st.stop_lon.astype(float)}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=['name', 'lat', 'lon'])


def ferry_terminals(metro: str) -> pd.DataFrame:
    feed = FERRY_METROS.get(metro)
    if not feed:
        return pd.DataFrame(columns=['name', 'lat', 'lon'])
    z = zipfile.ZipFile(f'data/cache/transit/{metro}/norm/gtfs_{feed}.zip')
    routes = pd.read_csv(io.BytesIO(z.read('routes.txt')), dtype=str)
    ferry_routes = set(routes[routes.route_type == '4'].route_id)
    trips = pd.read_csv(io.BytesIO(z.read('trips.txt')), dtype=str, usecols=['trip_id', 'route_id'])
    ferry_trips = set(trips[trips.route_id.isin(ferry_routes)].trip_id)
    stt = pd.read_csv(io.BytesIO(z.read('stop_times.txt')), dtype=str, usecols=['trip_id', 'stop_id'])
    ids = set(stt[stt.trip_id.isin(ferry_trips)].stop_id)
    st = pd.read_csv(io.BytesIO(z.read('stops.txt')), dtype=str)
    st = st[st.stop_id.isin(ids)]
    return pd.DataFrame({'name': st.stop_name, 'lat': st.stop_lat.astype(float), 'lon': st.stop_lon.astype(float)})


def snap_to_stop(stops: pd.DataFrame, lat: float, lon: float):
    """Nearest rail stop within SNAP_MAX_METERS of (lat, lon), as (lat, lon, meters), else None."""
    if stops.empty:
        return None
    import numpy as np
    d = np.hypot((stops.lat.values - lat) * 111000, (stops.lon.values - lon) * 111000 * np.cos(np.radians(lat)))
    k = int(d.argmin())
    return (float(stops.lat.iloc[k]), float(stops.lon.iloc[k]), float(d[k])) if d[k] <= SNAP_MAX_METERS else None


def origins_for(metro: str) -> gpd.GeoDataFrame:
    rows = [json.loads(l)['catalog'] for l in open(CATALOGS[metro])]
    stations = STATIONS_BY_METRO.get(metro, {})
    coords = json.load(open('data/rail_station_coords.json')).get(metro, {})
    stops = rail_stops(metro)
    snapped = []
    recs = []
    for i, c in enumerate(rows):
        recs.append({'id': f'c:{i}', 'name': c['name'], 'geometry': Point(float(c['lon']), float(c['lat']))})
        name = c['name']
        if name in stations and not (name == 'Ridgewood' and float(c['lon']) >= -74.05):
            s = coords.get(stations[name])
            if s:
                lat, lon = s['lat'], s['lon']
                snap = snap_to_stop(stops, lat, lon)
                if snap:
                    snapped.append((name, round(snap[2])))
                    lat, lon = snap[0], snap[1]
                recs.append({'id': f's:{i}', 'name': name, 'geometry': Point(lon, lat)})
    ferries = ferry_terminals(metro)
    n_ferry = 0
    if not ferries.empty:
        import numpy as np
        for i, c in enumerate(rows):
            lat0, lon0 = float(c['lat']), float(c['lon'])
            d = np.hypot((ferries.lat.values - lat0) * 111000, (ferries.lon.values - lon0) * 111000 * np.cos(np.radians(lat0)))
            k = int(d.argmin())
            if d[k] <= FERRY_ACCESS_METERS:
                recs.append({'id': f'f:{i}', 'name': c['name'], 'geometry': Point(float(ferries.lon.iloc[k]), float(ferries.lat.iloc[k]))})
                n_ferry += 1
        print(f'added ferry-terminal origins for {n_ferry} places within {FERRY_ACCESS_METERS} m of a terminal')
    if snapped:
        moved = sorted((m for _, m in snapped), reverse=True)
        print(f'snapped {len(snapped)} station origins to the agency stop location; '
              f'median move {moved[len(moved) // 2]} m, max {moved[0]} m')
    return gpd.GeoDataFrame(recs, crs='EPSG:4326')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', required=True)
    args, _ = parser.parse_known_args()  # r5py's own JVM flags are also in argv
    base = f'data/cache/transit/{args.metro}'

    hubs = json.load(open('frontend/lib/workZones.json'))[args.metro]
    dest = gpd.GeoDataFrame(
        [{'id': h['id'], 'geometry': Point(h['lon'], h['lat'])} for h in hubs]
        + [{'id': i, 'geometry': Point(lo, la)} for i, la, lo in EXTRA_DESTINATIONS.get(args.metro, [])],
        crs='EPSG:4326')
    orig = origins_for(args.metro)
    print(f'{len(orig)} origins x {len(dest)} hubs')

    gtfs = sorted(glob.glob(f'{base}/norm/gtfs_*.zip'))
    print('building network from', glob.glob(f'{base}/*_region.osm.pbf')[0], 'and', len(gtfs), 'feeds')
    network = r5py.TransportNetwork(glob.glob(f'{base}/*_region.osm.pbf')[0], gtfs)

    ttm = r5py.TravelTimeMatrix(
        network,
        origins=orig,
        destinations=dest,
        departure=dt.datetime.combine(TARGET_DATE, DEPART_START),
        departure_time_window=DEPART_WINDOW,
        percentiles=[1, 50],
        transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
        max_time=MAX_TIME,
    )
    df = pd.DataFrame(ttm)
    df = df.merge(orig[['id', 'name']], left_on='from_id', right_on='id').drop(columns='id')
    out = f'{base}/r5_transit.csv'
    df.to_csv(out, index=False)
    print(f'wrote {out}: {len(df)} pairs, {df.travel_time_p1.isna().sum()} unreachable')


if __name__ == '__main__':
    main()
