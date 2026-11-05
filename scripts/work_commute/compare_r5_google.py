"""
Validate r5 transit times against the Google times already stored in the catalog.

Pairs: work_commute[hub].transit_centroid vs r5 "c:<row>", transit_station vs "s:<row>".
Prints overall agreement, the biggest disagreements, and per-hub bias. Read-only.

Usage:
    .venv-r5/bin/python scripts/work_commute/compare_r5_google.py --metro nyc
"""

import argparse
import json

import pandas as pd

CATALOGS = {m: f'data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl' for m in ('nyc', 'sf', 'la', 'seattle')}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', required=True)
    parser.add_argument('--percentile', default='p1', choices=['p1', 'p5', 'p50'])
    args = parser.parse_args()

    r5 = pd.read_csv(f'data/cache/transit/{args.metro}/r5_transit.csv')
    r5 = r5.rename(columns={f'travel_time_{args.percentile}': 'r5'})[['from_id', 'to_id', 'name', 'r5']]
    rows = [json.loads(l) for l in open(CATALOGS[args.metro])]
    recs = []
    for i, r in enumerate(rows):
        for hub, v in (r.get('work_commute') or {}).items():
            for key, prefix in (('transit_centroid', 'c'), ('transit_station', 's')):
                if isinstance(v.get(key), (int, float)):
                    recs.append({'from_id': f'{prefix}:{i}', 'to_id': hub, 'google': v[key]})
    g = pd.DataFrame(recs)
    m = g.merge(r5, on=['from_id', 'to_id'], how='inner')
    m['diff'] = m.r5 - m.google
    both = m.dropna(subset=['r5'])
    print(f'{len(m)} pairs with Google times; r5 unreachable for {m.r5.isna().sum()}')
    a = both['diff'].abs()
    print(f'median |r5 - google| = {a.median():.1f} min; within 5 min: {(a <= 5).mean():.0%}; '
          f'within 10: {(a <= 10).mean():.0%}; median signed diff {both["diff"].median():+.1f}')
    print('\nPer hub (median signed diff, share within 10 min):')
    for hub, gr in both.groupby('to_id'):
        print(f'  {hub:<24} {gr["diff"].median():+6.1f}   {(gr["diff"].abs() <= 10).mean():.0%}   n={len(gr)}')
    print('\nOrigin type:')
    for p, gr in both.groupby(both.from_id.str[0]):
        print(f'  {"town center" if p == "c" else "station":<12} median |diff| {gr["diff"].abs().median():.1f}, within 10 min {(gr["diff"].abs() <= 10).mean():.0%}')
    print('\nLargest disagreements:')
    worst = both.reindex(both['diff'].abs().sort_values(ascending=False).index).head(20)
    for r in worst.itertuples():
        print(f'  {r.name:<22} {r.from_id[0]} -> {r.to_id:<24} google {r.google:6.1f}  r5 {r.r5:6.1f}  ({r.diff:+.1f})')


if __name__ == '__main__':
    main()
