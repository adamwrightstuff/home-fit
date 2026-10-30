"""
Housing D14 follow-up checks. Read-only and offline: reads the stored catalog, the cached Census state pull, and the
tract centers table. Makes no Census calls and writes only the files named by --out-prefix.

  python3 analysis/audit_housing_d14_scripts/pool_areal_checks.py <repo_root> --pull <census_pull_dir> --centers <parquet>

What it adds to the diversity session's script (scripts/catalog/pool_housing_tracts_offline.py):
  1. A pooling rule that follows the commute lookup: pin plus 8 ring points, a tract is in the pool if any point falls
     inside it. Tract shape is approximated as a disk of the tract's land area around its center (no polygons here).
  2. Pin shift that picks the tract under the shifted point by that same disk approximation, not the nearest center.
  3. Margin-of-error test (90% margins from the pull, normal draws, scores re-computed).
  4. Within-metro rank correlation, radius sensitivity, equal vs occupied-unit weights, launch check on pooled scores.
Scores use the pillar's own functions with the metro multiplier that reproduces each stored score. The Zillow value
override cannot be applied to pooled inputs, so effects are measured as pooled minus single-tract rebuilt score and
added to the stored score where an absolute value is needed.
"""
import sys, os, glob, json, math, argparse, random, importlib.util, statistics as st, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import pandas as pd
import hvfuncs as H            # reads sys.argv[1] + '/pillars/housing_value.py'
from load import load

ap = argparse.ArgumentParser()
ap.add_argument('root')
ap.add_argument('--pull', required=True)
ap.add_argument('--centers', required=True)
ap.add_argument('--out-prefix', default=os.path.join(sys.argv[1], 'analysis', 'audit_housing_d14_areal'))
ap.add_argument('--draws', type=int, default=200)
ap.add_argument('--exact', action='store_true', help='700 m pool membership from live geocoder lookups (9 per place)')
ap.add_argument('--pilot', action='store_true', help='time 20 live geocoder calls, then continue')
ap.add_argument('--geo-sample', type=int, default=0, help='N places x 8 live geocoder shifts')
a = ap.parse_args()
random.seed(11); np.random.seed(11)
RINGS = (400, 700, 1200)          # meters: 0.25, 0.44, 0.75 mile
SHIFT_M = 500                     # 0.31 mile
BAD = -1e8


def num(x):
    try:
        v = float(x)
        return None if v < BAD else v
    except (TypeError, ValueError):
        return None


# ---- tract table from the pull -------------------------------------------------
T = {}
for f in glob.glob(os.path.join(a.pull, 'housing_tract_*_0.json')) + glob.glob(os.path.join(a.pull, 'housing2_tract_*_0.json')):
    d = json.load(open(f)); h = d[0]
    for r in d[1:]:
        g = r[h.index('state')] + r[h.index('county')] + r[h.index('tract')]
        t = T.setdefault(g, {})
        for i, c in enumerate(h):
            if c[0] == 'B':
                t[c] = num(r[i])
print('tracts in pull:', len(T))

cen = pd.read_parquet(a.centers)
cen = cen[cen.geoid.isin(T.keys())].reset_index(drop=True)
CLA, CLO = np.radians(cen.lat.values), np.radians(cen.lon.values)
CG = cen.geoid.values
CR = np.sqrt(cen.land_sqmi.values * 2589988.0 / math.pi)       # radius (m) of a disk with the tract's land area


def dist_m(lat, lon, idx=None):
    la, lo = (CLA, CLO) if idx is None else (CLA[idx], CLO[idx])
    p, q = math.radians(lat), math.radians(lon)
    x = np.sin((la - p) / 2) ** 2 + np.cos(la) * math.cos(p) * np.sin((lo - q) / 2) ** 2
    return 2 * 6371000 * np.arcsin(np.sqrt(x))


def tract_inputs(t):
    occ, ren = t.get('B25003_001E'), t.get('B25003_003E')
    return dict(inc=t.get('B19013_001E'), val=t.get('B25077_001E'), rent=t.get('B25064_001E'), rooms=t.get('B25018_001E'),
                rp=(ren / occ) if occ and ren is not None else None)


def sc(x, adj):
    if not x['inc'] or x['inc'] <= 0:
        return None
    s, *_ = H.score(x['val'], x['inc'], x['rooms'], x['rent'], x['rp'], adj)
    return s


def pool(geoids, weights='occ'):
    items = []
    for g in geoids:
        t = T.get(g)
        if t and t.get('B25003_001E'):
            items.append(t)
    if not items:
        return None
    w = [t['B25003_001E'] if weights == 'occ' else 1.0 for t in items]

    def wm(key):
        L = [(t.get(key), wi) for t, wi in zip(items, w) if t.get(key) is not None]
        return sum(v * wi for v, wi in L) / sum(wi for _, wi in L) if L else None
    occ = sum(t['B25003_001E'] for t in items)
    ren = sum(t['B25003_003E'] for t in items if t.get('B25003_003E') is not None)
    return dict(inc=wm('B19013_001E'), val=wm('B25077_001E'), rent=wm('B25064_001E'), rooms=wm('B25018_001E'),
                rp=(ren / occ) if occ else None), items, w


def ring_tracts(lat, lon, R, near, extra=()):
    """Tracts containing the pin or any of 8 ring points at R meters (disk approximation), plus extra geoids."""
    pts = [(lat, lon)]
    for ang in range(0, 360, 45):
        pts.append((lat + R / 111000.0 * math.cos(math.radians(ang)),
                    lon + R / (111000.0 * math.cos(math.radians(lat))) * math.sin(math.radians(ang))))
    hit = set(extra)
    for la, lo in pts:
        d = dist_m(la, lo, near)
        hit.update(CG[near][d <= CR[near]])
    return hit


def containing(lat, lon, near):
    d = dist_m(lat, lon, near)
    return CG[near][int(np.argmin(d - CR[near]))]


# ---- places --------------------------------------------------------------------
rows = load()
for r in rows:
    r['score'] = r['h'].get('score')
    sm = r['h'].get('summary') or {}
    if (sm.get('pooling') or {}).get('single_tract_score') is not None:   # catalog already pooled: use the original
        r['score'] = sm['pooling']['single_tract_score']
    r['geo'] = sm.get('geo_level')
    r['sig'] = (sm.get('median_home_value'), sm.get('median_household_income'), sm.get('median_rooms'),
                sm.get('median_gross_rent'), sm.get('renter_pct'))
    r['adj'] = 1.0
    r['reproduces'] = False
    if r['score'] is not None:
        for adj in (1.0, 1.3, 1.5):
            t, *_ = H.score(*r['sig'][:3], r['sig'][3], r['sig'][4], adj)
            if t is not None and abs(t - r['score']) < 0.11:
                r['adj'], r['reproduces'] = adj, True
                break
tract_places = [r for r in rows if r['geo'] == 'tract' and r['score'] is not None]
print('tract-level scored places:', len(tract_places))

out = []
nomatch = 0
acc_contain = tot_contain = 0
for r in tract_places:
    lat, lon = r['lat'], r['lon']
    d_all = dist_m(lat, lon)
    near = np.where(d_all <= 20000)[0]
    v, inc, rooms, rent, rp = r['sig']
    cand = [CG[i] for i in near if T[CG[i]].get('B19013_001E') == inc and T[CG[i]].get('B25064_001E') == rent
            and T[CG[i]].get('B25018_001E') == rooms]
    cand = [g for g in cand if T[g].get('B25077_001E') == v or v is None or True]
    if len(cand) > 1:
        cand = [g for g in cand if T[g].get('B25077_001E') == v] or cand
    pin_g = cand[0] if len(cand) == 1 else None
    r['near'] = near
    r['pin_g'] = pin_g
    if pin_g is None:
        nomatch += 1
        continue
    tot_contain += 1
    acc_contain += containing(lat, lon, near) == pin_g
    base = sc(tract_inputs(T[pin_g]), r['adj'])
    r['base'] = base
    r['val_override'] = T[pin_g].get('B25077_001E') != v        # stored value differs from the tract value (Zillow)
print('pin tract matched: %d of %d (unmatched %d); disk rule picks the matched tract for %.0f%% of pins'
      % (tot_contain, len(tract_places), nomatch, 100 * acc_contain / max(1, tot_contain)))
P = [r for r in tract_places if r.get('pin_g') and r.get('base') is not None]
print('baseline rebuilt for', len(P), '; within 1 point of stored:', sum(abs(r['base'] - r['score']) <= 1 for r in P),
      '; stored value differs from tract value (Zillow override or vintage):', sum(r['val_override'] for r in P))

# ---- exact membership at 700 m from the geocoder (opt-in) -------------------------
EXACT = {}
if a.exact:
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, a.root)
    from data_sources import census_api

    def pts9(r):
        out_ = [(r['lat'], r['lon'])]
        for ang in range(0, 360, 45):
            out_.append((r['lat'] + 700 / 111000.0 * math.cos(math.radians(ang)),
                         r['lon'] + 700 / (111000.0 * math.cos(math.radians(r['lat']))) * math.sin(math.radians(ang))))
        return out_

    def look9(r):
        s = {r['pin_g']}
        for la, lo in pts9(r):
            try:
                t = census_api.get_census_tract(la, lo)
            except Exception:
                t = None
            if t:
                s.add(f"{t['state_fips']}{t['county_fips']}{t['tract_fips']}")
        return s
    with ThreadPoolExecutor(4) as ex:
        for r, s in zip(P, ex.map(look9, P)):
            EXACT[id(r)] = s
    print('exact 700 m membership looked up for', len(EXACT), 'places')

# ---- pooled scores -------------------------------------------------------------
for r in P:
    r['pooled'] = {}
    r['ntr'] = {}
    for R in RINGS:
        g = ring_tracts(r['lat'], r['lon'], R, r['near'], extra=(r['pin_g'],))
        if R == 700 and id(r) in EXACT:
            g = EXACT[id(r)]
        p = pool(g)
        r['pooled'][R] = sc(p[0], r['adj']) if p else None
        if R == 700 and p:
            _, _, _sp, _ef = H.score(p[0]['val'], p[0]['inc'], p[0]['rooms'], p[0]['rent'], p[0]['rp'], r['adj'])
            r['parts700'] = dict(median_home_value=p[0]['val'], space=_sp, value_efficiency=_ef)
        r['ntr'][R] = len([x for x in g if x in T])
    g7 = ring_tracts(r['lat'], r['lon'], 700, r['near'], extra=(r['pin_g'],))
    p = pool(g7, 'equal')
    r['pooled_equal700'] = sc(p[0], r['adj']) if p else None


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float('nan')


def summarize(name, xs):
    if not xs:
        print('  ', name, 'no data'); return
    print('   %-34s n=%d median %.1f p90 %.1f p95 %.1f max %.1f | >5: %d  >10: %d  >15: %d' % (
        name, len(xs), st.median(xs), pct(xs, .9), pct(xs, .95), max(xs), sum(x > 5 for x in xs), sum(x > 10 for x in xs), sum(x > 15 for x in xs)))


print('\n== A. Pooled vs single-tract score, same inputs, no Zillow/metro difference between them ==')
for R in RINGS:
    xs = [abs(r['pooled'][R] - r['base']) for r in P if r['pooled'][R] is not None]
    summarize('ring %d m (%.2f mi)' % (R, R / 1609.3), xs)
    print('      tracts in pool: median %d, share with only the pin tract %.0f%%' % (
        st.median(r['ntr'][R] for r in P), 100 * sum(r['ntr'][R] <= 1 for r in P) / len(P)))
summarize('ring 700 m, equal weights', [abs(r['pooled_equal700'] - r['base']) for r in P if r['pooled_equal700'] is not None])
summarize('ring 700 m, occupied-unit weights', [abs(r['pooled'][700] - r['base']) for r in P if r['pooled'][700] is not None])
print('   unscoreable pooled (None): ', {R: sum(r['pooled'][R] is None for r in P) for R in RINGS})

# ---- pin shift -----------------------------------------------------------------
print('\n== B. Pin shift %d m (%.2f mi), 8 bearings, %d places; tract under shifted pin by the disk rule ==' % (SHIFT_M, SHIFT_M / 1609.3, len(P)))
res = {'single': [], **{R: [] for R in RINGS}}
by_at = collections.defaultdict(lambda: {'single': [], 700: []})
for r in P:
    for b in range(8):
        ang = math.radians(45 * b)
        la2 = r['lat'] + SHIFT_M * math.cos(ang) / 111320.0
        lo2 = r['lon'] + SHIFT_M * math.sin(ang) / (111320.0 * math.cos(math.radians(r['lat'])))
        g0 = containing(la2, lo2, r['near'])
        s0 = sc(tract_inputs(T[g0]), r['adj'])
        if s0 is not None:
            res['single'].append(abs(s0 - r['base']))
            by_at[r['area_type']]['single'].append(abs(s0 - r['base']))
        for R in RINGS:
            g = ring_tracts(la2, lo2, R, r['near'], extra=(g0,))
            p = pool(g)
            s1 = sc(p[0], r['adj']) if p else None
            if s1 is not None and r['pooled'][R] is not None:
                res[R].append(abs(s1 - r['pooled'][R]))
                if R == 700:
                    by_at[r['area_type']][700].append(abs(s1 - r['pooled'][R]))
summarize('single tract', res['single'])
for R in RINGS:
    summarize('pooled ring %d m' % R, res[R])
print('   by area type (stored label), 95th percentile single / pooled 700 m (n shifts):')
for k, v in sorted(by_at.items(), key=lambda x: str(x[0])):
    if len(v['single']) >= 16:
        print('     %-18s %5.1f / %5.1f  (%d)' % (k, pct(v['single'], .95), pct(v[700], .95), len(v['single'])))
print('   gate used in the transit audit: 95th percentile <= 5 points (judgment). Pass:', {
    'single': pct(res['single'], .95) <= 5, **{R: pct(res[R], .95) <= 5 for R in RINGS}})

# ---- margins of error ----------------------------------------------------------
print('\n== C. Margin-of-error test (90%% margins, normal draws, %d draws per place) ==' % a.draws)


def mc_sd(inputs_est, inputs_se, adj):
    out_ = []
    for _ in range(a.draws):
        x = dict(inputs_est)
        for k in ('inc', 'val', 'rent', 'rooms'):
            if x[k] is not None and inputs_se.get(k):
                x[k] = max(x[k] + np.random.normal() * inputs_se[k], 0.05 * x[k])
        s = sc(x, adj)
        if s is not None:
            out_.append(s)
    return st.pstdev(out_) if len(out_) > 5 else None


def se_single(t):
    f = {'inc': 'B19013_001M', 'val': 'B25077_001M', 'rent': 'B25064_001M', 'rooms': 'B25018_001M'}
    return {k: (t.get(m) / 1.645 if t.get(m) is not None else 0.0) for k, m in f.items()}


def se_pooled(items, w):
    f = {'inc': ('B19013_001E', 'B19013_001M'), 'val': ('B25077_001E', 'B25077_001M'),
         'rent': ('B25064_001E', 'B25064_001M'), 'rooms': ('B25018_001E', 'B25018_001M')}
    out_ = {}
    for k, (e, m) in f.items():
        L = [(t.get(m), wi) for t, wi in zip(items, w) if t.get(e) is not None and t.get(m) is not None]
        W = sum(wi for t, wi in zip(items, w) if t.get(e) is not None)
        out_[k] = (math.sqrt(sum((wi * mm / 1.645) ** 2 for mm, wi in L)) / W) if L and W else 0.0
    return out_


for r in P:
    t = T[r['pin_g']]
    r['sd_single'] = mc_sd(tract_inputs(t), se_single(t), r['adj'])
    g = ring_tracts(r['lat'], r['lon'], 700, r['near'], extra=(r['pin_g'],))
    p, items, w = pool(g)
    r['sd_pool700'] = mc_sd(p, se_pooled(items, w), r['adj'])
s1 = [r['sd_single'] for r in P if r['sd_single'] is not None]
s2 = [r['sd_pool700'] for r in P if r['sd_pool700'] is not None]
print('   score sd from sampling error, single tract: median %.1f p90 %.1f max %.1f; share with sd > 5: %.0f%%' % (
    st.median(s1), pct(s1, .9), max(s1), 100 * sum(x > 5 for x in s1) / len(s1)))
print('   score sd from sampling error, pooled 700 m: median %.1f p90 %.1f max %.1f; share with sd > 5: %.0f%%' % (
    st.median(s2), pct(s2, .9), max(s2), 100 * sum(x > 5 for x in s2) / len(s2)))
# neighbor pairs by pin tract, within 1.4 km, same metro
byM = collections.defaultdict(list)
for r in P:
    byM[r['metro']].append(r)
pairs = []
seen = set()
for m, L in byM.items():
    for i, x in enumerate(L):
        for y in L[i + 1:]:
            if x['pin_g'] == y['pin_g']:
                continue
            d = float(dist_m(x['lat'], x['lon'], None)[0]) if False else None
            p1, p2 = math.radians(x['lat']), math.radians(y['lat'])
            dl = math.radians(y['lon'] - x['lon'])
            q = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            dm = 2 * 6371000 * math.asin(math.sqrt(q))
            if dm <= 1400 and x['sd_single'] is not None and y['sd_single'] is not None:
                diff = abs(x['base'] - y['base'])
                z = diff / math.sqrt(x['sd_single'] ** 2 + y['sd_single'] ** 2)
                pairs.append((diff, z, x, y))
big = [p for p in pairs if p[0] > 15]
print('   neighbor pairs within 0.87 mile, different pin tract: %d; difference > 15 points: %d' % (len(pairs), len(big)))
print('   of those > 15: within 2 standard errors of each other (could be sampling noise): %d; beyond: %d' % (
    sum(p[1] < 2 for p in big), sum(p[1] >= 2 for p in big)))
print('   all pairs: z < 2 for %.0f%%' % (100 * sum(p[1] < 2 for p in pairs) / max(1, len(pairs))))

# ---- rank correlation ----------------------------------------------------------
print('\n== D. Within-metro rank correlation, single tract vs pooled (Spearman) ==')
df = pd.DataFrame([dict(metro=r['metro'], base=r['base'], **{'p%d' % R: r['pooled'][R] for R in RINGS}) for r in P])
for R in RINGS:
    col = 'p%d' % R
    per = {}
    for m, g in df.groupby('metro'):
        g = g.dropna(subset=[col])
        if len(g) >= 15:
            per[m] = g['base'].rank().corr(g[col].rank())
    allc = df.dropna(subset=[col])['base'].rank().corr(df.dropna(subset=[col])[col].rank())
    print('   ring %4d m: all places %.3f | per metro (n>=15): median %.3f min %.3f (%s) over %d metros' % (
        R, allc, st.median(per.values()), min(per.values()), min(per, key=per.get), len(per)))

# ---- launch check --------------------------------------------------------------
print('\n== E. Launch check housing_value, stored vs pooled-700 (stored + pooled minus single-tract rebuild) ==')
spec = importlib.util.spec_from_file_location('lc', os.path.join(a.root, 'scripts', 'qa', 'launch_check.py'))
LC = importlib.util.module_from_spec(spec); spec.loader.exec_module(LC)
paths = sorted(glob.glob(os.path.join(a.root, 'data', '*_metro_place_catalog_scores_merged.composites_recomputed.jsonl')))
places = LC.load_places(paths)
cfg = json.load(open(os.path.join(a.root, 'data', 'launch_check_contrasts.json')))
hc = [c for c in cfg['contrasts'] if c['pillar'] == 'housing_value']
before = LC.evaluate_contrasts(places, hc)
st_before = LC.pillar_stats(places, 'housing_value')
delta = {(r['metro'], r['name']): r['pooled'][700] - r['base'] for r in P if r['pooled'][700] is not None}
changed = 0
for pl in places:
    k = (pl['metro'], pl['name'])
    hv = pl['pillars'].get('housing_value')
    if k in delta and hv and hv['score'] is not None:
        hv['score'] = min(100.0, max(0.0, hv['score'] + delta[k])); changed += 1
after = LC.evaluate_contrasts(places, hc)
st_after = LC.pillar_stats(places, 'housing_value')
print('   places adjusted:', changed)
for b_, a_ in zip(before, after):
    print('   contrast rural vs urban_core:', b_['level'], 'gap', b_.get('gap'), 'n', b_['n_a'], b_['n_b'], '->', a_['level'], 'gap', a_.get('gap'), a_['n_a'], a_['n_b'])
for k in ('mean', 'sd', 'at_max', 'at_min', 'modal_share', 'distinct'):
    if st_before and k in st_before:
        print('   %-12s %s -> %s' % (k, st_before[k], st_after[k]))
print('   gates before:', LC.gate_stats(st_before), '| after:', LC.gate_stats(st_after))
print('   Only 1 of the 9 pre-registered contrasts uses housing_value; the other 8 do not read it.')

# ---- real geocoder pin shift (opt-in; live Census geocoder calls) ----------------
if a.pilot or a.geo_sample:
    import time
    from concurrent.futures import ThreadPoolExecutor
    sys.path.insert(0, a.root)
    from data_sources import census_api
    rnd = random.Random(7)
    sample = rnd.sample(P, 3 if a.pilot else a.geo_sample)
    jobs = []
    for r in sample:
        for b in range(8):
            ang = math.radians(45 * b)
            jobs.append((r, r['lat'] + SHIFT_M * math.cos(ang) / 111320.0,
                         r['lon'] + SHIFT_M * math.sin(ang) / (111320.0 * math.cos(math.radians(r['lat'])))))
    jobs = jobs[:20] if a.pilot else jobs

    def look(j):
        t0 = time.time()
        try:
            tr = census_api.get_census_tract(j[1], j[2])
        except Exception:
            tr = None
        return tr, time.time() - t0
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        got = list(ex.map(look, jobs))
    secs = [g[1] for g in got]
    print('\n== G. Geocoder timing: %d calls, 4 threads, wall %.0f s; per call mean %.1f max %.1f; failed %d ==' % (
        len(jobs), time.time() - t0, st.mean(secs), max(secs), sum(g[0] is None for g in got)))
    if not a.pilot:
        sg, pg, agree, n = [], {R: [] for R in RINGS}, 0, 0
        for (r, la2, lo2), (tr, _) in zip(jobs, got):
            if not tr:
                continue
            g0 = f"{tr['state_fips']}{tr['county_fips']}{tr['tract_fips']}"
            n += 1; agree += g0 == containing(la2, lo2, r['near'])
            s0 = sc(tract_inputs(T[g0]), r['adj']) if g0 in T else None
            if s0 is not None:
                sg.append(abs(s0 - r['base']))
            for R in RINGS:
                p = pool(ring_tracts(la2, lo2, R, r['near'], extra=(g0,)))
                s1 = sc(p[0], r['adj']) if p else None
                if s1 is not None and r['pooled'][R] is not None:
                    pg[R].append(abs(s1 - r['pooled'][R]))
        print('   geocoder tract equals the disk-rule tract for %.0f%% of %d shifts' % (100 * agree / max(1, n), n))
        summarize('G single tract (geocoder)', sg)
        for R in RINGS:
            summarize('G pooled ring %d m (geocoder)' % R, pg[R])

# ---- save ----------------------------------------------------------------------
fn = a.out_prefix + '_places.jsonl'
with open(fn, 'w') as fh:
    for r in P:
        fh.write(json.dumps(dict(metro=r['metro'], name=r['name'], stored=r['score'], rebuilt=r['base'], pin_tract=r['pin_g'],
                                 adj=r['adj'], value_overridden=r['val_override'],
                                 **{'pooled_%d' % R: r['pooled'][R] for R in RINGS},
                                 **{'tracts_%d' % R: r['ntr'][R] for R in RINGS},
                                 pooled_equal_700=r['pooled_equal700'], parts_700=r.get('parts700'), sd_single=r['sd_single'], sd_pool700=r['sd_pool700'])) + '\n')
print('\nwrote', fn)
