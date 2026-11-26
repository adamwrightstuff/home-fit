"""
Build data/zillow_zhvi_city_bedrooms.json: Zillow ZHVI by bedroom count (1, 2, 3, 4, 5+) at CITY level,
middle tier, SFR+condo, same series as the ZIP file. Kept only for cities whose name, state AND county match a
catalog place, so the file stays small. Used where a catalog place is an incorporated place that shares
its ZIP with other towns (e.g. Bronxville village inside ZIP 10708).

Output: {"as_of": "...", "cities": {"Bronxville|NY|westchester": [v1, v2, v3, v4, v5], ...}}  (null = no value)

Run from repo root:
  PYTHONPATH=. python3 scripts/baselines/build_zillow_zhvi_city_bedrooms.py
"""
from __future__ import annotations

import csv
import glob
import io
import json
import os
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def norm_county(name: str) -> str:
    """'Westchester County' / 'Orleans Parish' / 'Westchester' -> 'westchester'"""
    n = (name or '').strip().lower()
    for suf in (' county', ' parish', ' borough', ' census area', ' city and borough', ' municipio'):
        if n.endswith(suf):
            n = n[: -len(suf)]
    return n.replace('.', '').replace("'", '')
URL = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
       "City_zhvi_bdrmcnt_{n}_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")


def main() -> None:
    wanted = set()
    for f in glob.glob(os.path.join(ROOT, 'data', '*_metro_place_catalog_scores_merged.composites_recomputed.jsonl')):
        for line in open(f):
            c = json.loads(line).get('catalog') or {}
            wanted.add(f"{c.get('name')}|{c.get('state_abbr')}|{norm_county(c.get('county_borough'))}")
    cities: dict[str, list] = {}
    as_of = None
    for n in range(1, 6):
        with urllib.request.urlopen(URL.format(n=n), timeout=180) as resp:
            rows = list(csv.DictReader(io.StringIO(resp.read().decode('utf-8'))))
        latest = sorted(k for k in rows[0] if len(k) == 10 and k[4] == '-' and k[7] == '-')[-1]
        as_of = max(as_of or latest, latest)
        for r in rows:
            key = f"{r['RegionName']}|{r['State']}|{norm_county(r['CountyName'])}"
            if key not in wanted:
                continue
            raw = (r.get(latest) or '').strip()
            cities.setdefault(key, [None] * 5)[n - 1] = int(float(raw)) if raw else None
        print(f'{n}-bed done ({latest})')
    with open(os.path.join(ROOT, 'data', 'zillow_zhvi_city_bedrooms.json'), 'w') as fh:
        json.dump({'as_of': as_of, 'source': 'Zillow Research ZHVI by bedroom count, city, middle tier, SFR+condo', 'cities': cities}, fh, separators=(',', ':'))
    print(f'{len(cities)} of {len(wanted)} catalog place names matched a Zillow city')


if __name__ == '__main__':
    main()
