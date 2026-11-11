"""
Build data/catalog_housing_costs.json: per catalog place, the Zillow ZIP value for a 1-5+ bedroom
home (data/zillow_zhvi_zip_bedrooms.json) and the IRS average real estate tax per itemizing
return for the ZIP (SOI 2023 ZIP file, A18500 / N18500, summed over AGI brackets).

The IRS figure is what current owners pay, not what a new buyer would: it understates tax in
states that reassess on sale (California). It also covers itemizers only. ZIPs with under 100
itemizing returns get no tax value.

Run from repo root (downloads the ~200 MB SOI file unless --soi points at a local copy):
  PYTHONPATH=. python3 scripts/baselines/build_catalog_housing_costs.py [--soi path/to/23zpallagi.csv]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import urllib.request
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SOI_URL = 'https://www.irs.gov/pub/irs-soi/23zpallagi.csv'
TAX_YEAR = 2023
MIN_ITEMIZERS = 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--soi', default=None)
    a = ap.parse_args()
    soi = a.soi
    if not soi:
        soi = os.path.join(ROOT, 'data_cache', f'soi_{TAX_YEAR}_zip.csv')
        if not os.path.exists(soi):
            print(f'Downloading {SOI_URL} ...')
            urllib.request.urlretrieve(SOI_URL, soi)

    n_item, amt = defaultdict(float), defaultdict(float)
    for r in csv.DictReader(open(soi, encoding='latin-1')):
        z = r['zipcode'].zfill(5)
        n_item[z] += float(r['N18500'] or 0)
        amt[z] += float(r['A18500'] or 0)  # thousands of dollars

    zh = json.load(open(os.path.join(ROOT, 'data', 'zillow_zhvi_zip_bedrooms.json')))
    places = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '*_metro_place_catalog_scores_merged.composites_recomputed.jsonl'))):
        metro = os.path.basename(f).split('_metro_')[0]
        for line in open(f):
            r = json.loads(line)
            c, s = r.get('catalog') or {}, r.get('score') or {}
            z = str((s.get('location_info') or {}).get('zip') or '').zfill(5)
            if z == '00000':
                continue
            vals = [zh['bedrooms'][str(b)].get(z) for b in range(1, 6)]
            tax = round(amt[z] * 1000 / n_item[z]) if n_item[z] >= MIN_ITEMIZERS else None
            if all(v is None for v in vals) and tax is None:
                continue
            places[f"{metro}::{c.get('name')}|{c.get('county_borough')}|{c.get('state_abbr')}"] = {'zip': z, 'v': vals, 'tax': tax}

    out = {'bedrooms_as_of': zh['as_of'], 'tax_year': TAX_YEAR, 'places': places}
    p = os.path.join(ROOT, 'data', 'catalog_housing_costs.json')
    json.dump(out, open(p, 'w'), separators=(',', ':'))
    print(f'{len(places)} places, {sum(1 for v in places.values() if v["tax"] is not None)} with tax; wrote {p}')


if __name__ == '__main__':
    main()
