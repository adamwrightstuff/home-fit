"""
Weight sensitivity for the housing value composite (DPv2 P4/P6). Offline, stored inputs only.

Rescored from each place's stored single-tract inputs (home value, income, rooms, rent, renter share) with the pillar's
own component functions, metro multiplier 1.0 (under 1 point effect). Components are scaled to 0..1 by their maximum
(50, 30, 20) and recombined under alternative weights; a missing component is left out and the rest rescaled, as the pillar does.

  python3 analysis/audit_housing_d14_scripts/weights_sensitivity.py <repo_root> <main_checkout_for_burden_and_pin_tracts>
"""
import glob, json, statistics as st, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import pandas as pd
import hvfuncs as H          # uses sys.argv[1]
from load import load

MAIN = sys.argv[2]
ALT = {'A 50/30/20 (current)': (50, 30, 20), 'B 70/20/10': (70, 20, 10), 'C 60/30/10': (60, 30, 10), 'D 40/30/30': (40, 30, 30),
       'E equal thirds': (100 / 3, 100 / 3, 100 / 3), 'F affordability only': (100, 0, 0), 'G 50/50/0 (no efficiency)': (50, 50, 0)}
MAX = (50.0, 30.0, 20.0)

rows = []
for r in load():
    if r['h'].get('score') is None:
        continue
    sm = r['h']['summary']
    t, aff, sp, ef = H.score(sm.get('median_home_value'), sm.get('median_household_income'), sm.get('median_rooms'),
                             sm.get('median_gross_rent'), sm.get('renter_pct'), 1.0)
    if t is None:
        continue
    comp = [aff, sp, ef]
    d = dict(metro=r['metro'], name=r['name'], geo=sm.get('geo_level'))
    for k, w in ALT.items():
        use = [(c / m, wi) for c, m, wi in zip(comp, MAX, w) if c is not None and wi > 0]
        d[k] = 100 * sum(c * wi for c, wi in use) / sum(wi for _, wi in use) if use else None
    rows.append(d)
df = pd.DataFrame(rows)
base = 'A 50/30/20 (current)'
print(f'places rescored: {len(df)}')
print(f"{'weights':28s} {'median |chg|':>12s} {'p90':>6s} {'>5':>5s} {'>10':>5s} {'rank corr vs A':>15s} {'within-metro med':>17s}")
for k in ALT:
    ch = (df[k] - df[base]).abs()
    per = [g[k].rank().corr(g[base].rank()) for _, g in df.groupby('metro') if len(g) >= 15]
    print(f"{k:28s} {ch.median():12.1f} {ch.quantile(.9):6.1f} {(ch > 5).sum():5d} {(ch > 10).sum():5d} {df[k].rank().corr(df[base].rank()):15.3f} {st.median(per):17.3f}")

# against measured cost burden (495 tract-level places)
def num(x):
    try:
        v = float(x); return None if v < -1e8 else v
    except (TypeError, ValueError):
        return None
burden = {}
for f in glob.glob(MAIN + '/data/census_pull_costburden_2026-10-30/costburden_tract_*.json'):
    d = json.load(open(f)); h = d[0]
    for r in d[1:]:
        v = {c: num(x) for c, x in zip(h, r) if c.startswith('B')}
        a = [v[f'B25070_{i:03d}E'] for i in range(7, 11)]; b = [v[f'B25091_{i:03d}E'] for i in range(8, 12)]
        den = (v['B25070_001E'] or 0) - (v['B25070_011E'] or 0) + (v['B25091_002E'] or 0) - (v['B25091_012E'] or 0)
        if None in a or None in b or den < 50:
            continue
        burden[r[h.index('state')] + r[h.index('county')] + r[h.index('tract')]] = 1 - (sum(a) + sum(b)) / den
pin = {}
for l in open(MAIN + '/analysis/audit_housing_d14_exact_places.jsonl'):
    p = json.loads(l); pin[(p['metro'], p['name'])] = p['pin_tract']
df['afford'] = [burden.get(pin.get((m, n))) for m, n in zip(df.metro, df.name)]
v = df[df.geo == 'tract'].dropna(subset=['afford'])
print(f'\nagainst share not cost-burdened, {len(v)} tract-level places (Spearman all / within-metro median):')
for k in ALT:
    per = [g[k].rank().corr(g['afford'].rank()) for _, g in v.groupby('metro') if len(g) >= 15]
    print(f"  {k:28s} {v[k].rank().corr(v['afford'].rank()):.3f} / {st.median(per):.3f}")
