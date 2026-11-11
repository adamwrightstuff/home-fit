"""
Monthly principal-and-interest cost per catalog place for an N-bedroom home, from the
Zillow ZIP bedroom-count values in data/zillow_zhvi_zip_bedrooms.json (offline, no API).

Basis: fixed cash down payment, fixed-rate 30-year mortgage on the rest. Property tax and
insurance are NOT in the repo, so they are excluded unless --tax-rate / --insurance-annual
are passed (annual tax as a share of home value, insurance in dollars per year).

Usage:
  PYTHONPATH=. python3 scripts/catalog/compute_bedroom_monthly_cost.py \
      --bedrooms 4 --down 600000 --rate 0.07 --out analysis/monthly_cost_4bed.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def monthly_pi(loan: float, annual_rate: float, years: int = 30) -> float:
    if loan <= 0:
        return 0.0
    r = annual_rate / 12
    n = years * 12
    return loan * r / (1 - (1 + r) ** -n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--bedrooms', type=int, default=4)
    ap.add_argument('--down', type=float, default=600000)
    ap.add_argument('--rate', type=float, default=0.07)
    ap.add_argument('--tax-rate', type=float, default=0.0)
    ap.add_argument('--insurance-annual', type=float, default=0.0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    z = json.load(open(os.path.join(ROOT, 'data', 'zillow_zhvi_zip_bedrooms.json')))
    values = z['bedrooms'][str(min(a.bedrooms, 5))]

    rows, missing = [], 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '*_metro_place_catalog_scores_merged.composites_recomputed.jsonl'))):
        metro = os.path.basename(f).split('_metro_')[0]
        for line in open(f):
            r = json.loads(line)
            cat, sc = r.get('catalog') or {}, r.get('score') or {}
            zip_code = str((sc.get('location_info') or {}).get('zip') or '').zfill(5)
            v = values.get(zip_code)
            hs = sc.get('housing_stock') or {}
            row = {
                'metro': metro, 'place': cat.get('name'), 'state': cat.get('state_abbr'), 'zip': zip_code,
                'home_value': v, 'pct_low_density': hs.get('pct_low_density'),
            }
            if v is None:
                missing += 1
                row.update(loan=None, monthly_pi=None, monthly_tax_ins=None, monthly_total=None)
            else:
                loan = max(v - a.down, 0)
                pi = monthly_pi(loan, a.rate)
                ti = v * a.tax_rate / 12 + a.insurance_annual / 12
                row.update(loan=round(loan), monthly_pi=round(pi), monthly_tax_ins=round(ti), monthly_total=round(pi + ti))
            rows.append(row)

    with open(a.out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} places, {len(rows) - missing} with a {a.bedrooms}-bed value, {missing} without. Wrote {a.out}")


if __name__ == '__main__':
    main()
