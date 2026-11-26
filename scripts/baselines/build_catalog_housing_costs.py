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
import math
import os
import urllib.request
import zipfile
from collections import defaultdict

from scripts.baselines.build_zillow_zhvi_city_bedrooms import norm_county

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SOI_URL = 'https://www.irs.gov/pub/irs-soi/23zpallagi.csv'
TAX_YEAR = 2023
MIN_ITEMIZERS = 100
ZCTA_URL = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip'


def load_zcta() -> dict[str, tuple[float, float, float]]:
    """ZCTA -> (lat, lon, land sq mi) from the Census gazetteer."""
    path = os.path.join(ROOT, 'data_cache', 'gazetteer_zcta_2023.zip')
    if not os.path.exists(path):
        urllib.request.urlretrieve(ZCTA_URL, path)
    zf = zipfile.ZipFile(path)
    out = {}
    for line in zf.read(zf.namelist()[0]).decode().splitlines()[1:]:
        p = line.split('\t')
        out[p[0].strip()] = (float(p[5]), float(p[6]), float(p[3]))
    return out


def miles(a: float, b: float, c: float, d: float) -> float:
    return 3959 * math.acos(min(1.0, math.sin(math.radians(a)) * math.sin(math.radians(c))
                                + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.cos(math.radians(b - d))))


def usable_zip(z: str, lat: float, lon: float, zcta: dict) -> str:
    """The stored ZIP when it is a real ZCTA near the pin; otherwise the ZCTA whose centroid is nearest the pin.
    Stored ZIPs can be PO-box or unique-organization ZIPs (no ZCTA, no price or tax data), or plainly wrong
    (Hayward CA stored as 25426, a West Virginia ZIP)."""
    if z in zcta and miles(lat, lon, zcta[z][0], zcta[z][1]) <= max(8.0, 2 * math.sqrt(zcta[z][2] / math.pi)):
        return z
    return min(zcta, key=lambda k: miles(lat, lon, zcta[k][0], zcta[k][1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--soi', default=None)
    ap.add_argument('--city-values', nargs='*', default=[], metavar='all | NAME|ST|county',
                    help='places that take the Zillow CITY bedroom values (data/zillow_zhvi_city_bedrooms.json) instead of the ZIP values')
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
    city = json.load(open(os.path.join(ROOT, 'data', 'zillow_zhvi_city_bedrooms.json')))['cities'] if a.city_values else {}
    zcta = load_zcta()
    places = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '*_metro_place_catalog_scores_merged.composites_recomputed.jsonl'))):
        metro = os.path.basename(f).split('_metro_')[0]
        for line in open(f):
            r = json.loads(line)
            c, s = r.get('catalog') or {}, r.get('score') or {}
            z = str((s.get('location_info') or {}).get('zip') or '').zfill(5)
            c_lat, c_lon = c.get('lat'), c.get('lon')
            if c_lat is None or c_lon is None:
                if z == '00000':
                    continue
            else:
                z = usable_zip(z, float(c_lat), float(c_lon), zcta)
            vals = [zh['bedrooms'][str(b)].get(z) for b in range(1, 6)]
            ckey = f"{c.get('name')}|{c.get('state_abbr')}|{norm_county(c.get('county_borough'))}"
            if ('all' in a.city_values or ckey in a.city_values) and ckey in city:
                vals = [cv if cv is not None else zv for cv, zv in zip(city[ckey], vals)]  # city value where Zillow has one, else the ZIP value
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
