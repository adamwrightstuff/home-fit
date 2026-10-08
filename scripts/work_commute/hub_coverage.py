"""
Job-hub coverage analysis for the work-commute feature (docs/WORK_COMMUTE_PLAYBOOK.md, Step 1).

Uses Census LEHD LODES8 workplace job counts (WAC) to report:
  1. Share of metro jobs within RADIUS miles of the current hubs (frontend/lib/workZones.json)
  2. Jobs within RADIUS of each current hub
  3. Greedy best additions (largest still-uncovered job clusters)
  4. Coverage of candidate pins passed with --candidate "Label:lat,lon"

Single blocks above --max-block jobs are excluded and listed: LODES assigns some large
employers' whole payroll to one administrative address (e.g. 73k jobs on one Burbank block,
75k on LA's Civic Center HQ block), which would otherwise masquerade as office clusters.
Verify any listed block before treating it as real.

Free public data, no API keys. Files are cached in data/cache/lodes/ (gitignored).

Usage:
    PYTHONPATH=. python3 scripts/work_commute/hub_coverage.py --metro nyc
    PYTHONPATH=. python3 scripts/work_commute/hub_coverage.py --metro sf --add 6
    PYTHONPATH=. python3 scripts/work_commute/hub_coverage.py --metro nyc \\
        --candidate "Plaza District (5 Av/53 St):40.7602,-73.9753" --candidate "SoHo (Spring St):40.7262,-74.0037"
"""

import argparse
import json
import os
import urllib.request

import numpy as np
import pandas as pd

CACHE = 'data/cache/lodes'
YEAR = 2023
RADIUS_MILES = 0.6
CELL_MILES = 0.3

METROS = {
    # CBSA codes: NY-Newark-Jersey City + Bridgeport-Stamford (Fairfield County catalog towns)
    'nyc': {'states': ['ny', 'nj', 'ct'], 'cbsas': ['35620', '14860']},
    # SF-Oakland-Fremont + San Jose-Sunnyvale-Santa Clara
    'sf': {'states': ['ca'], 'cbsas': ['41860', '41940']},
    'la': {'states': ['ca'], 'cbsas': ['31080']},
    'seattle': {'states': ['wa'], 'cbsas': ['42660']},
}
CATALOGS = {
    m: f'data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl' for m in METROS
}


def cached(url: str, name: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        print(f'  downloading {url}')
        urllib.request.urlretrieve(url, path)
    return path


def load_jobs(metro: str) -> pd.DataFrame:
    frames = []
    for st in METROS[metro]['states']:
        base = f'https://lehd.ces.census.gov/data/lodes/LODES8/{st}'
        wac = pd.read_csv(cached(f'{base}/wac/{st}_wac_S000_JT00_{YEAR}.csv.gz', f'{st}_wac_{YEAR}.csv.gz'),
                          usecols=['w_geocode', 'C000'], dtype={'w_geocode': str})
        xw = pd.read_csv(cached(f'{base}/{st}_xwalk.csv.gz', f'{st}_xwalk_{YEAR}.csv.gz'),
                         usecols=['tabblk2020', 'cbsa', 'blklatdd', 'blklondd'], dtype={'tabblk2020': str, 'cbsa': str})
        frames.append(wac.merge(xw, left_on='w_geocode', right_on='tabblk2020'))
    d = pd.concat(frames)
    return d[d.cbsa.isin(METROS[metro]['cbsas'])]


class Plane:
    """Local equirectangular projection in miles (fine at metro scale)."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.kx = 69.17 * np.cos(np.radians(lat0))

    def xy(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.kx, (np.asarray(lat) - self.lat0) * 69.0

    def latlon(self, x, y):
        return y / 69.0 + self.lat0, x / self.kx + self.lon0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--metro', choices=list(METROS), required=True)
    parser.add_argument('--add', type=int, default=8, help='Greedy additions to list')
    parser.add_argument('--candidate', action='append', default=[], help='"Label:lat,lon" pin to evaluate')
    parser.add_argument('--max-block', type=int, default=15000, help='Exclude single blocks with more jobs (admin-address artifacts)')
    args = parser.parse_args()

    d = load_jobs(args.metro)
    big = d[d.C000 > args.max_block].sort_values('C000', ascending=False)
    if len(big):
        print(f'\nExcluded {len(big)} single blocks over {args.max_block:,} jobs (likely payroll/HQ address artifacts; verify):')
        for _, b in big.iterrows():
            print(f'  {int(b.C000):>7,} jobs at ({b.blklatdd:.4f},{b.blklondd:.4f})')
    d = d[d.C000 <= args.max_block]
    w = d.C000.values.astype(float)
    total = w.sum()
    plane = Plane(float(d.blklatdd.median()), float(d.blklondd.median()))
    x, y = plane.xy(d.blklatdd.values, d.blklondd.values)

    def within(px, py):
        return (x - px) ** 2 + (y - py) ** 2 <= RADIUS_MILES ** 2

    hubs = json.load(open('frontend/lib/workZones.json')).get(args.metro, [])
    catalog = [json.loads(l)['catalog'] for l in open(CATALOGS[args.metro])]
    cat_xy = [(plane.xy(float(c['lat']), float(c['lon'])), c['name']) for c in catalog]

    def nearest_place(px, py):
        return min(cat_xy, key=lambda t: (t[0][0] - px) ** 2 + (t[0][1] - py) ** 2)[1]

    print(f'\n{args.metro.upper()}: {total / 1e6:.2f}M jobs (LODES {YEAR}, CBSA {", ".join(METROS[args.metro]["cbsas"])})')
    covered = np.zeros(len(w), bool)
    print(f'\nCurrent hubs, jobs within {RADIUS_MILES} mi:')
    for h in hubs:
        m = within(*plane.xy(h['lat'], h['lon']))
        covered |= m
        print(f"  {h['label']:<34} {w[m].sum() / 1e3:>6.0f}k{'  (transitOnly)' if h.get('transitOnly') else ''}")
    print(f'  Union of current hubs: {w[covered].sum() / 1e6:.2f}M ({w[covered].sum() / total:.1%})')

    for cand in args.candidate:
        label, ll = cand.split(':', 1)
        lat, lon = (float(v) for v in ll.split(','))
        m = within(*plane.xy(lat, lon))
        print(f'  Candidate {label}: {w[m].sum() / 1e3:.0f}k within {RADIUS_MILES} mi, '
              f'{w[m & ~covered].sum() / 1e3:.0f}k not already covered')

    # Greedy additions over job-weighted cell centers.
    cells = pd.DataFrame({'gx': np.floor(x / CELL_MILES), 'gy': np.floor(y / CELL_MILES), 'w': w, 'wx': x * w, 'wy': y * w})
    cells = cells.groupby(['gx', 'gy']).sum()
    cells = cells[cells.w >= 1000]
    cand_xy = np.column_stack([cells.wx / cells.w, cells.wy / cells.w])
    print(f'\nGreedy additions (uncovered jobs within {RADIUS_MILES} mi):')
    for _ in range(args.add):
        best = None
        for px, py in cand_xy:
            gain = w[within(px, py) & ~covered].sum()
            if best is None or gain > best[0]:
                best = (gain, px, py)
        gain, px, py = best
        covered |= within(px, py)
        lat, lon = plane.latlon(px, py)
        print(f'  +{gain / 1e3:>5.0f}k  ({lat:.4f},{lon:.4f}) near {nearest_place(px, py):<22} cumulative {w[covered].sum() / total:.1%}')


if __name__ == '__main__':
    main()
