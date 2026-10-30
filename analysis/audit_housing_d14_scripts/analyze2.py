import os, sys, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyze.py')).read().split("# what drives instability")[0].replace("print(", "(lambda *a, **k: None)("))

nodata = [r for r in rows if r['score'] is None]
print('NO-DATA places:')
for r in nodata:
    sm = r['h'].get('summary') or {}
    print(' ', r['metro'], r['name'], sm.get('no_data_reason'), 'weight', round(r['h'].get('weight') or 0, 2), 'total', r['s'].get('total_score'))


def pooled_score(r, nbs):
    grp = [r] + nbs
    def m(i):
        xs = [g['sig'][i] for g in grp if g['sig'][i] is not None]
        return sum(xs) / len(xs) if xs else None
    v, inc, rooms, rent, rp = m(0), m(1), m(2), m(3), m(4)
    t, *_ = H.score(v, inc, rooms, rent, rp, r['adj'] or 1.0)
    return t


def recomputed_self(r):
    t, *_ = H.score(*r['sig'][:3], r['sig'][3], r['sig'][4], r['adj'] or 1.0)
    return t

for R, key in ((0.7, 'nbs07'), (1.4, 'nbs14')):
    print('\n=== Option (a) pool within %.1f km (%.2f mi), equal weight, catalog-pin tracts only ===' % (R, R / 1.609))
    moved = []
    for r in tr:
        if r['score'] is None:
            continue
        nbs = r[key]
        if not nbs:
            r['pool_' + key] = None
            continue
        p = pooled_score(r, nbs)
        r['pool_' + key] = p
        moved.append((r, p - recomputed_self(r), p))
    n_all = sum(r['score'] is not None for r in tr)
    print('places with a pool of >=2 tracts: %d of %d tract-level' % (len(moved), n_all))
    d = [abs(x[1]) for x in moved]
    print('abs change vs own recomputed score: median %.1f p90 %.1f max %.1f' % (st.median(d), st.quantiles(d, n=10)[8], max(d)))
    for th in (2, 5, 10, 15):
        print('   moves >%d: %d' % (th, sum(x > th for x in d)))
    # total score impact (weight/100)
    ts = [abs(x[1]) * (x[0]['h'].get('weight') or 0) / 100 for x in moved]
    print('effect on 0-100 total (weight share): median %.2f p90 %.2f max %.2f' % (st.median(ts), st.quantiles(ts, n=10)[8], max(ts)))
    # pairs after pooling
    pooled_by = {id(x[0]): x[2] for x in moved}
    before, after = [], []
    seen = set()
    for r in assessable:
        for o in r[key]:
            if id(r) in pooled_by and id(o) in pooled_by:
                k = tuple(sorted([id(r), id(o)]))
                if k in seen:
                    continue
                seen.add(k)
                before.append(abs(recomputed_self(r) - recomputed_self(o)))
                after.append(abs(pooled_by[id(r)] - pooled_by[id(o)]))
    if before:
        print('neighbor pairs (n=%d): median |diff| %.1f -> %.1f ; p90 %.1f -> %.1f ; pairs>15: %d -> %d' % (
            len(before), st.median(before), st.median(after), st.quantiles(before, n=10)[8], st.quantiles(after, n=10)[8],
            sum(x > 15 for x in before), sum(x > 15 for x in after)))
    biggest = sorted(moved, key=lambda x: -abs(x[1]))[:8]
    for r, dlt, p in biggest:
        print('   biggest mover:', r['metro'], r['name'], 'stored', r['score'], '-> pooled %.1f' % p, '(n tracts %d)' % (1 + len(r[key])))
    by_at = collections.defaultdict(list)
    for r, dlt, p in moved:
        by_at[r['area_type']].append(abs(dlt))
    print('   by area type (n, median abs move, moves >5):', {k: (len(v), round(st.median(v), 1), sum(x > 5 for x in v)) for k, v in by_at.items()})

# non-reproducing stored scores (stale scoring)
bad = [r for r in rows if r['score'] is not None and r['adj'] is None]
print('\nStored scores that do not reproduce from stored inputs:', len(bad), collections.Counter(r['metro'] for r in bad), collections.Counter(r['geo'] for r in bad))
print(' tract-level among them:', sum(r['geo'] == 'tract' for r in bad))
over = [r for r in rows if r['score'] is not None and (r['h']['breakdown'].get('value_efficiency') or 0) > 20.01]
print(' stored value_efficiency above its 20 point cap:', len(over), collections.Counter(r['metro'] for r in over))
over2 = [r for r in rows if r['score'] is not None and r['score'] > 100]
print(' stored score above 100:', len(over2))

# option (b): the 7 no data. nearest distinct-tract catalog neighbors
print('\nOption (b) for the no-data places: catalog tracts within 1.4 km (stored scores)')
for r in nodata:
    near = [(round(hav(r['lat'], r['lon'], o['lat'], o['lon']), 2), o['name'], o['score'], o['geo']) for o in rows
            if o['metro'] == r['metro'] and o['score'] is not None and o is not r and hav(r['lat'], r['lon'], o['lat'], o['lon']) <= 3.0]
    near.sort()
    print(' ', r['metro'], r['name'], near[:5])
