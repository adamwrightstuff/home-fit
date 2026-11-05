"""
Normalize GTFS feeds to one representative weekday on a shared target date.

Why: a single real calendar date bakes in that day's disruptions. In Oct 2026 NJ Transit ran
no Morris & Essex trains into Penn Station (all diverted to Hoboken until Nov 17), and each
agency's feed covers a different window (NYC subway ended Oct 31), so no one date is "normal"
for every agency. See docs/WORK_COMMUTE_PLAYBOOK.md.

For each feed: describe every Tue/Wed/Thu it covers by what actually runs (count of trips per
route and final stop; service_ids alone don't work because Metro-North issues new ids almost
daily), pick the most common description (the regular weekday; diversions such as M&E to
Hoboken instead of Penn, and holidays, are the minority), and
write a copy whose calendar contains only that service on TARGET_DATE. The router then runs on
TARGET_DATE with every agency on its typical weekday.

Usage:
    .venv-r5/bin/python scripts/work_commute/normalize_gtfs.py --metro nyc
"""

import argparse
import datetime as dt
import glob
import io
import os
import zipfile
from collections import Counter

import pandas as pd

TARGET_DATE = dt.date(2026, 10, 13)  # a Tuesday; only used as the shared label date
LOOKAHEAD_DAYS = 120
MIDWEEK = {1, 2, 3}  # Tue, Wed, Thu


def read(z: zipfile.ZipFile, name: str):
    try:
        return pd.read_csv(io.BytesIO(z.read(name)), dtype=str)
    except KeyError:
        return None


def active_services(cal, cd, start: dt.date, end: dt.date) -> dict:
    """date -> set of active service_ids (calendar.txt + calendar_dates.txt exceptions)."""
    days = {}
    if cal is not None:
        for r in cal.itertuples():
            s = max(dt.datetime.strptime(r.start_date, '%Y%m%d').date(), start)
            e = min(dt.datetime.strptime(r.end_date, '%Y%m%d').date(), end)
            flags = [r.monday, r.tuesday, r.wednesday, r.thursday, r.friday, r.saturday, r.sunday]
            d = s
            while d <= e:
                if flags[d.weekday()] == '1':
                    days.setdefault(d, set()).add(r.service_id)
                d += dt.timedelta(days=1)
    if cd is not None:
        for r in cd.itertuples():
            d = dt.datetime.strptime(r.date, '%Y%m%d').date()
            if not (start <= d <= end):
                continue
            if r.exception_type == '1':
                days.setdefault(d, set()).add(r.service_id)
            else:
                days.get(d, set()).discard(r.service_id)
    return days


def normalize(src: str, dst: str, today: dt.date) -> dict:
    z = zipfile.ZipFile(src)
    cal, cd = read(z, 'calendar.txt'), read(z, 'calendar_dates.txt')
    trips = read(z, 'trips.txt')
    trip_counts = trips.service_id.value_counts()
    # Final stop of each trip, so a diversion to a different terminal changes the description.
    st = pd.read_csv(io.BytesIO(z.read('stop_times.txt')), dtype=str, usecols=['trip_id', 'stop_id', 'stop_sequence'])
    st['seq'] = st.stop_sequence.astype(int)
    last = st.loc[st.groupby('trip_id').seq.idxmax(), ['trip_id', 'stop_id']]
    t = trips[['trip_id', 'service_id', 'route_id']].merge(last, on='trip_id')
    # Combined feeds (e.g. the Bay Area's 511 feed, 41 agencies) get each agency's own typical
    # weekday: one combined signature would almost never repeat, since any agency's change alters it.
    routes = read(z, 'routes.txt')
    agency_of_route = dict(zip(routes.route_id, routes.agency_id)) if 'agency_id' in routes.columns else {}
    t['agency'] = t.route_id.map(agency_of_route).fillna('')
    per_service = {(ag, sid): Counter(zip(g.route_id, g.stop_id)) for (ag, sid), g in t.groupby(['agency', 'service_id'])}
    agencies = sorted(t.agency.unique())

    days = active_services(cal, cd, today, today + dt.timedelta(days=LOOKAHEAD_DAYS))
    midweek = {d: s for d, s in days.items() if d.weekday() in MIDWEEK and s}
    if not midweek:
        return None  # feed has no usable weekday service (expired or weekend-only); skipped

    keep_by_agency, rep_dates, shares, patterns_seen = {}, {}, [], 0
    for ag in agencies:
        def describe(services, ag=ag):
            c = Counter()
            for sid in services:
                c.update(per_service.get((ag, sid), {}))
            return frozenset(c.items())

        sigs = {d: describe(sv) for d, sv in midweek.items()}
        sigs = {d: sg for d, sg in sigs.items() if sg}  # days this agency runs weekday service
        if not sigs:
            continue
        sig_counts = Counter(sigs.values())
        best_sig, n_days = sig_counts.most_common(1)[0]
        rep_date = min(d for d, sg in sigs.items() if sg == best_sig)
        keep_by_agency[ag] = midweek[rep_date]
        rep_dates[ag] = rep_date
        shares.append(n_days / len(sigs))
        patterns_seen = max(patterns_seen, len(sig_counts))
    if not keep_by_agency:
        return None

    trips_all = read(z, 'trips.txt')
    trips_all['agency'] = trips_all.route_id.map(agency_of_route).fillna('')
    mask = pd.Series(False, index=trips_all.index)
    for ag, svc in keep_by_agency.items():
        mask |= (trips_all.agency == ag) & trips_all.service_id.isin(svc)
    keep_trips = trips_all[mask].drop(columns='agency')
    pattern = set(keep_trips.service_id)
    n_trips = len(keep_trips)
    rep_date = next(iter(rep_dates.values()))  # label only; with several agencies each uses its own day
    n_days = int(round(sorted(shares)[len(shares) // 2] * len(midweek))) if shares else 0
    sig_counts = range(patterns_seen)

    new_cd = pd.DataFrame({'service_id': sorted(pattern), 'date': TARGET_DATE.strftime('%Y%m%d'), 'exception_type': '1'})
    # Keep only the typical weekday's trips; routers reject trips whose service no longer exists.
    keep_ids = set(keep_trips.trip_id)
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as out:
        for name in z.namelist():
            if name in ('calendar.txt', 'calendar_dates.txt', 'feed_info.txt'):
                continue  # feed_info validity dates could exclude TARGET_DATE
            if name.startswith('fare_'):
                continue  # fares don't affect travel time, and several feeds' fare tables are inconsistent
            if name == 'trips.txt':
                out.writestr(name, keep_trips.to_csv(index=False))
            elif name in ('stop_times.txt', 'frequencies.txt'):
                df = read(z, name)
                df = df[df.trip_id.isin(keep_ids)]
                if len(df) or name == 'stop_times.txt':  # routers reject empty optional tables
                    out.writestr(name, df.to_csv(index=False))
            elif name == 'stops.txt':
                df = read(z, name)
                if 'stop_name' in df.columns and df.stop_name.isna().any():
                    # Some feeds leave boarding-area/entrance stops unnamed; routers require a name.
                    df['stop_name'] = df.stop_name.fillna(df.stop_id)
                out.writestr(name, df.to_csv(index=False))
            elif name == 'transfers.txt':
                df = read(z, name)
                for col in ('from_trip_id', 'to_trip_id'):
                    if col in df.columns:
                        df = df[df[col].isna() | df[col].isin(keep_ids)]
                if 'transfer_type' in df.columns:
                    df['transfer_type'] = df.transfer_type.fillna('0')  # spec default: recommended transfer point
                if len(df):
                    out.writestr(name, df.to_csv(index=False))
            else:
                data = z.read(name)
                # Routers reject optional tables that are header-only (e.g. empty fare_rules.txt).
                if name.endswith('.txt') and data.count(b'\n') <= 1 and name not in ('agency.txt', 'stops.txt', 'routes.txt'):
                    continue
                out.writestr(name, data)
        out.writestr('calendar_dates.txt', new_cd.to_csv(index=False))
    return {'feed': os.path.basename(src), 'representative_date': f'per agency ({len(keep_by_agency)} agencies)' if len(agencies) > 1 else rep_date.isoformat(),
            'pattern_days': n_days, 'midweek_days_covered': len(midweek), 'patterns_seen': len(sig_counts), 'trips': n_trips}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', required=True)
    args = parser.parse_args()
    base = f'data/cache/transit/{args.metro}'
    os.makedirs(f'{base}/norm', exist_ok=True)
    today = dt.date.today()
    for src in sorted(glob.glob(f'{base}/gtfs_*.zip')):
        dst = f'{base}/norm/{os.path.basename(src)}'
        if os.path.exists(dst):
            os.remove(dst)  # never leave a stale normalized copy of a skipped feed
        info = normalize(src, dst, today)
        if info is None:
            print(f'  {os.path.basename(src):<22} SKIPPED: no midweek service in the next {LOOKAHEAD_DAYS} days')
            continue
        print(f"  {info['feed']:<22} typical weekday = {info['representative_date']} "
              f"({info['pattern_days']}/{info['midweek_days_covered']} midweek days share it, "
              f"{info['patterns_seen']} patterns seen, {info['trips']:,} trips)")


if __name__ == '__main__':
    main()
