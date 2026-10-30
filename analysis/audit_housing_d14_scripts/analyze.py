import os, sys, collections, statistics as st, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import load, hav
import hvfuncs as H

rows = load()
KM_07, KM_14 = 0.7, 1.4


def sig(r):
    sm = r['h'].get('summary') or {}
    return (sm.get('median_home_value'), sm.get('median_household_income'), sm.get('median_rooms'),
            sm.get('median_gross_rent'), sm.get('renter_pct'))


def geo(r):
    return (r['h'].get('summary') or {}).get('geo_level')


for r in rows:
    r['score'] = r['h'].get('score')
    r['geo'] = geo(r)
    r['sig'] = sig(r)
    r['adj'] = None
    if r['score'] is not None:
        sm = r['h']['summary']
        for adj in (1.0, 1.3, 1.5):
            t, *_ = H.score(*r['sig'][:3], r['sig'][3], r['sig'][4], adj)
            if t is not None and abs(t - r['score']) < 0.11:
                r['adj'] = adj
                break

tr = [r for r in rows if r['geo'] == 'tract']
print('tract-level places', len(tr), ' with score', sum(r['score'] is not None for r in tr),
      ' no-data', sum(r['score'] is None for r in tr))
print('distinct tract signatures among tract-level scored', len({r['sig'] for r in tr if r['score'] is not None}))
print('place-level (not exposed to single-tract issue):', sum(r['geo'] in ('incorporated_place', 'cdp', 'county_subdivision') for r in rows))
print('area_type of tract-level:', collections.Counter(r['area_type'] for r in tr))
print('area_type of place-level:', collections.Counter(r['area_type'] for r in rows if r['geo'] not in ('tract', None)))
print('type of tract-level:', collections.Counter(r['type'] for r in tr))
print('metro of tract-level:', sorted(collections.Counter(r['metro'] for r in tr).items(), key=lambda x: -x[1]))

# shared tract (identical signature in same metro within 1.4km)
by_metro = collections.defaultdict(list)
for r in tr:
    if r['score'] is not None:
        by_metro[r['metro']].append(r)

def neighbors(r, R):
    out = []
    for o in by_metro[r['metro']]:
        if o is r:
            continue
        d = hav(r['lat'], r['lon'], o['lat'], o['lon'])
        if d <= R:
            out.append((d, o))
    return out

res = []
for r in tr:
    if r['score'] is None:
        continue
    nb = neighbors(r, KM_14)
    distinct = {}
    for d, o in nb:
        if o['sig'] != r['sig']:
            distinct.setdefault(o['sig'], o)
    r['n_nb14'] = len(distinct)
    nb7 = {}
    for d, o in neighbors(r, KM_07):
        if o['sig'] != r['sig']:
            nb7.setdefault(o['sig'], o)
    r['n_nb07'] = len(nb7)
    r['nbs14'] = list(distinct.values())
    r['nbs07'] = list(nb7.values())
    if distinct:
        sc = [o['score'] for o in distinct.values()]
        r['nb_mean14'] = sum(sc) / len(sc)
        r['gap14'] = abs(r['score'] - r['nb_mean14'])
        r['range14'] = max(sc + [r['score']]) - min(sc + [r['score']])
    else:
        r['gap14'] = None; r['range14'] = None

assessable = [r for r in tr if r['score'] is not None and r['gap14'] is not None]
print('\nassessable (>=1 distinct-tract catalog neighbor within 1.4 km / 0.87 mi):', len(assessable), 'of', sum(r['score'] is not None for r in tr))
gaps = [r['gap14'] for r in assessable]
print('gap vs neighbor mean: median %.1f  p75 %.1f p90 %.1f max %.1f' % (st.median(gaps), st.quantiles(gaps, n=4)[2], st.quantiles(gaps, n=10)[8], max(gaps)))
for th in (5, 10, 15, 20, 30):
    print('  gap >%d:' % th, sum(g > th for g in gaps), '(%.0f%%)' % (100 * sum(g > th for g in gaps) / len(gaps)))
rg = [r['range14'] for r in assessable]
print('range among self + neighbors within 1.4 km: median %.1f p90 %.1f; >20:' % (st.median(rg), st.quantiles(rg, n=10)[8]), sum(x > 20 for x in rg), ' >40:', sum(x > 40 for x in rg))

# by area type and metro
print('\nBy area type (assessable): n, gap>15, share')
g = collections.defaultdict(list)
for r in assessable:
    g[r['area_type']].append(r)
for k, v in sorted(g.items(), key=lambda x: str(x[0])):
    print(' ', k, len(v), sum(x['gap14'] > 15 for x in v), '%.0f%%' % (100 * sum(x['gap14'] > 15 for x in v) / len(v)), 'median gap %.1f' % st.median(x['gap14'] for x in v))
print('\nBy metro (assessable): n, gap>15, share, median gap; tract-level n')
g = collections.defaultdict(list)
for r in assessable:
    g[r['metro']].append(r)
for k, v in sorted(g.items(), key=lambda x: -len(x[1])):
    print(' ', k, len(v), sum(x['gap14'] > 15 for x in v), '%.0f%%' % (100 * sum(x['gap14'] > 15 for x in v) / len(v)), 'median %.1f' % st.median(x['gap14'] for x in v), 'tract-level n', sum(1 for x in tr if x['metro'] == k))

# the named examples
print('\nNamed examples (D14):')
for nm in ('Bronzeville', 'Westwood', 'Midtown', 'Old Town', 'Hegewisch'):
    for r in tr:
        if r['name'] == nm:
            print(' ', r['metro'], nm, 'score', r['score'], 'n_nb14', r.get('n_nb14'), 'range14', None if r.get('range14') is None else round(r['range14'], 1),
                  'nb scores', [(o['name'], o['score'], round(hav(r['lat'], r['lon'], o['lat'], o['lon']), 2)) for o in r.get('nbs14', [])][:8])

# what drives instability: component contribution of pair differences
print('\nPair differences between distinct neighboring tracts within 1.4 km (all pairs):')
pairs = []
seen = set()
for r in assessable:
    for o in r['nbs14']:
        k = tuple(sorted([(r['metro'], r['name']), (o['metro'], o['name'])]))
        if k in seen:
            continue
        seen.add(k)
        br, bo = r['h']['breakdown'], o['h']['breakdown']
        def c(b, key):
            return b[key] if b.get(key) is not None else 0.0
        pairs.append(dict(a=r, b=o, d=abs(r['score'] - o['score']),
                          da=abs(c(br, 'local_affordability') - c(bo, 'local_affordability')),
                          ds=abs(c(br, 'space') - c(bo, 'space')),
                          de=abs(c(br, 'value_efficiency') - c(bo, 'value_efficiency')),
                          sa=(c(br, 'local_affordability') - c(bo, 'local_affordability')),
                          ss=(c(br, 'space') - c(bo, 'space')),
                          se=(c(br, 'value_efficiency') - c(bo, 'value_efficiency')),
                          tenure=abs((r['sig'][4] or 0) - (o['sig'][4] or 0)),
                          dist=hav(r['lat'], r['lon'], o['lat'], o['lon'])))
print('  pairs', len(pairs), ' median |diff| %.1f p90 %.1f' % (st.median(p['d'] for p in pairs), st.quantiles([p['d'] for p in pairs], n=10)[8]))
for th in (15, 20, 30):
    print('  pairs >%d:' % th, sum(p['d'] > th for p in pairs))
big = [p for p in pairs if p['d'] > 15]
print('  among pairs >15 (n=%d): mean |dAff| %.1f  mean |dSpace| %.1f  mean |dEff| %.1f' % (len(big), st.mean(p['da'] for p in big), st.mean(p['ds'] for p in big), st.mean(p['de'] for p in big)))
print('  all pairs: mean |dAff| %.1f  mean |dSpace| %.1f  mean |dEff| %.1f' % (st.mean(p['da'] for p in pairs), st.mean(p['ds'] for p in pairs), st.mean(p['de'] for p in pairs)))
# share of squared signed diff (variance) explained by each component
import math
sxx = sum(p['d'] ** 2 for p in pairs)
signed = [(p['sa'] + p['ss'] + p['se']) for p in pairs]
print('  mean |dTotal| %.1f; dominant component among pairs>15:' % st.mean(p['d'] for p in big),
      collections.Counter(max((('aff', p['da']), ('space', p['ds']), ('eff', p['de'])), key=lambda x: x[1])[0] for p in big))
# covariance share
def cov_share(key):
    tot = [p['sa'] + p['ss'] + p['se'] for p in pairs]
    num = sum(p[key] * t for p, t in zip(pairs, tot))
    den = sum(t * t for t in tot)
    return num / den
print('  share of squared total difference carried by: aff %.2f space %.2f eff %.2f' % (cov_share('sa'), cov_share('ss'), cov_share('se')))
print('  tenure (renter share) gap: pairs>15 mean %.2f vs pairs<=15 mean %.2f' % (st.mean(p['tenure'] for p in big), st.mean(p['tenure'] for p in pairs if p['d'] <= 15)))
# basis flip
def basis(r):
    return (r['h']['summary'] or {}).get('affordability_basis') or 'owner'
print('  affordability basis differs in pair: among >15:', sum(basis(p['a']) != basis(p['b']) for p in big), 'of', len(big), '; among <=15:', sum(basis(p['a']) != basis(p['b']) for p in pairs if p['d'] <= 15), 'of', sum(p['d'] <= 15 for p in pairs))

json.dump({'ok': True}, open('/dev/null', 'w'))
