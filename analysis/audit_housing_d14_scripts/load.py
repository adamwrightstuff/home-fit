import json, glob, collections, sys, math

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'


def load():
    rows = []
    for f in sorted(glob.glob(f'{ROOT}/data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl')):
        m = f.split('/')[-1].split('_metro_')[0]
        for l in open(f):
            d = json.loads(l)
            c = d['catalog']
            s = d.get('score') or {}
            lp = s.get('livability_pillars') or {}
            h = lp.get('housing_value') or {}
            dq = s.get('data_quality_summary')
            ac = dq.get('area_classification') if isinstance(dq, dict) else None
            at = ac.get('area_type') if isinstance(ac, dict) else None
            rows.append(dict(metro=m, name=c['name'], type=c.get('type'), state=c.get('state_abbr'),
                             lat=float(c['lat']), lon=float(c['lon']), h=h,
                             area_type=at, s=s))
    return rows


def hav(a, b, c, d):
    R = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp = p2 - p1
    dl = math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))
