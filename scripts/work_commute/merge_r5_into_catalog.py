"""
Replace the transit times in work_commute with r5 (our own router) results.

For every catalog place and hub:
  transit_centroid  = r5 best-timed trip from the place centroid
  transit_station   = r5 best-timed trip from its rail station (rail towns only)
  transit           = min of the two (as before)
Drive times (Google) are left untouched; so is everything outside `work_commute`.
Pairs r5 cannot route are stored as null (UI shows "no transit route"), EXCEPT where
--keep-google-when-unreachable is set and Google had a value (used only while feeds are
still being added).

A backup is written next to the catalog before overwriting. Adds a top-level
`work_commute_meta` with the source and schedule date so the provenance is in the data.

--update-cbd (NYC): also rewrites the older single-number card line that shows when no work hub
is chosen: cbd_transit_minutes_gct (to the Grand Central pin = nyc_midtown_east), 
cbd_transit_minutes_penn (to the Penn Station pin, r5 destination `cbd_penn`),
cbd_transit_minutes (the smaller of the two) and cbd_transit_dest, so the card and the hub
picker agree. Each is the best of the town-center and station origins.

Usage:
    .venv-r5/bin/python scripts/work_commute/merge_r5_into_catalog.py --metro nyc [--update-cbd] [--dry-run]
"""

import argparse
import datetime as dt
import json
import shutil

import pandas as pd

CATALOGS = {m: f'data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl' for m in ('nyc', 'sf', 'la', 'seattle')}
SCHEDULE_DATE = '2026-10-13'
CBD_HUB = {'sf': 'sf_fidi', 'la': 'la_downtown'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', required=True)
    parser.add_argument('--percentile', default='p1')
    parser.add_argument('--keep-google-when-unreachable', action='store_true')
    parser.add_argument('--update-cbd', action='store_true', help='NYC: also refresh cbd_transit_* card fields')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    r5 = pd.read_csv(f'data/cache/transit/{args.metro}/r5_transit.csv')
    col = f'travel_time_{args.percentile}'
    # Floor at 1 minute: a place sitting on its hub routes in 0 minutes, which reads oddly on a card.
    lookup = {(r.from_id, r.to_id): (None if pd.isna(getattr(r, col)) else max(1.0, round(float(getattr(r, col)), 1)))
              for r in r5.itertuples()}
    # Only user-facing hubs belong in work_commute; helper destinations (cbd_*) are not hubs.
    hubs = sorted(h for h in r5.to_id.unique() if not str(h).startswith('cbd_'))

    path = CATALOGS[args.metro]
    rows = [json.loads(l) for l in open(path)]
    kept_google = nulled = added = changed = 0
    for i, row in enumerate(rows):
        wc = row.setdefault('work_commute', {})
        for hub in hubs:
            entry = wc.setdefault(hub, {})
            if hub not in (row.get('work_commute') or {}) or 'transit' not in entry and not entry:
                added += 1
            # transit_station = best of the place's access-point origins (rail station "s", ferry terminal "f").
            for key, prefixes in (('transit_centroid', ('c',)), ('transit_station', ('s', 'f'))):
                pairs = [(f'{p}:{i}', hub) for p in prefixes if (f'{p}:{i}', hub) in lookup]
                if not pairs:
                    if key == 'transit_station':
                        entry.pop('transit_station', None)  # no rail station or ferry terminal for this place
                    continue
                vals = [lookup[pr] for pr in pairs if lookup[pr] is not None]
                new = min(vals) if vals else None
                if new is None and args.keep_google_when_unreachable and isinstance(entry.get(key), (int, float)):
                    kept_google += 1
                    continue
                if new is None:
                    nulled += 1
                if entry.get(key) != new:
                    changed += 1
                entry[key] = new
            opts = [entry[k] for k in ('transit_centroid', 'transit_station') if isinstance(entry.get(k), (int, float))]
            entry['transit'] = min(opts) if opts else None
        row['work_commute_meta'] = {
            'transit_source': 'r5py',
            'transit_measure': f'best-timed trip, departures 7:30 to 8:45, each agency on its typical weekday',
            'schedule_label_date': SCHEDULE_DATE,
            'built': dt.date.today().isoformat(),
        }

    cbd_changed = 0
    if args.update_cbd:
        def best(i, dest):
            vals = [lookup.get((f'{p}:{i}', dest)) for p in ('c', 's', 'f')]
            vals = [v for v in vals if v is not None]
            return min(vals) if vals else None
        if args.metro in CBD_HUB:
            # The older single-number card line measured to the metro's downtown pin, which is the same
            # point as one hub (SF: Montgomery St BART = sf_fidi; LA: 7th St/Metro Center = la_downtown).
            for i, row in enumerate(rows):
                t = best(i, CBD_HUB[args.metro])
                if t is not None:
                    if row.get('cbd_transit_minutes') != t:
                        cbd_changed += 1
                    row['cbd_transit_minutes'] = t
        for i, row in enumerate(rows if args.metro == 'nyc' else []):
            gct, penn = best(i, 'nyc_midtown_east'), best(i, 'cbd_penn')
            if gct is None and penn is None:
                continue  # no transit route: leave whatever was there
            new = {
                'cbd_transit_minutes_gct': gct,
                'cbd_transit_minutes_penn': penn,
                'cbd_transit_minutes': min(v for v in (gct, penn) if v is not None),
                'cbd_transit_dest': 'penn' if (penn is not None and (gct is None or penn < gct)) else 'gct',
            }
            for k, v in new.items():
                if row.get(k) != v:
                    cbd_changed += 1
                row[k] = v
    print(f'{len(rows)} places x {len(hubs)} hubs: {cbd_changed} cbd card values changed; {changed} values changed, {nulled} set to null (no route), '
          f'{kept_google} kept from Google, hubs: {hubs}')
    if args.dry_run:
        return
    backup = path.replace('.jsonl', f'.bak.{dt.datetime.now():%Y%m%d-%H%M%S}')
    shutil.copy(path, backup)
    with open(path, 'w') as fh:
        for row in rows:
            fh.write(json.dumps(row) + '\n')
    print(f'wrote {path} (backup {backup})')


if __name__ == '__main__':
    main()
