#!/usr/bin/env python3
"""
Scatter analysis: vibe score vs status signal across NYC + LA catalogs.
Computes vibe score from stored business_list data (no live API calls).
"""
import json, math, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Vibe algorithm (composite v3) ─────────────────────────────────────────────

KNOWN_CHAINS = {
    'starbucks','dunkin','mcdonald','subway','chipotle','pizza hut','kfc','taco bell',
    'burger king','wendys','chick-fil-a','panera','pret','sweetgreen','shake shack',
    'five guys','jamba','great clips','supercuts','sport clips','fantastic sams',
    'planet fitness','la fitness','anytime fitness','crunch fitness','equinox',
    'barnes noble','whole foods','trader joe','sprouts','cvs','walgreens','rite aid',
    'h&m','zara','uniqlo','gap','banana republic','old navy','forever 21',
    'orangetheory','f45','solidcore','soulcycle','barry',
}
INDIE_WORDS = re.compile(
    r'\b(artisan|craft|roast|roastery|brew|brewer|grind|press|provision|provisions|'
    r'collective|workshop|studio|atelier|goods|supply|mercantile|boulangerie|patisserie|'
    r'trattoria|osteria|enoteca|bistro|brasserie|tavern|speakeasy|apothecary|creamery|'
    r'sourdough|farm.to|root|vine|grove|harvest|larder|co\b|co\.|& co|company|brothers|sisters)\b', re.I)
GENERIC_WORDS = re.compile(
    r'\b(palace|garden|dragon|golden|lucky|express|buffet|wok|dynasty|empire|'
    r'super\s|best\s|#1|number\s*one|no\.?\s*1)\b', re.I)
POSSESSIVE = re.compile(r"^[A-Z][a-z]+'s\b|^[A-Z][a-z]+ [A-Z][a-z]+'s\b")
AMPERSAND  = re.compile(r'\s&\s')


def score_biz_name(name):
    nl = name.lower()
    if any(c in nl for c in KNOWN_CHAINS):
        return -1
    if GENERIC_WORDS.search(name):
        return -1
    pts = 0
    if INDIE_WORDS.search(name): pts += 1
    if AMPERSAND.search(name):   pts += 1
    if POSSESSIVE.match(name):   pts += 1
    if re.match(r'^The [A-Z]', name): pts += 1
    return min(pts, 1)


def featurize(biz):
    by_type = {}
    for b in biz:
        t = b.get('type', '?')
        by_type[t] = by_type.get(t, 0) + 1
    total = sum(by_type.values())
    if not total:
        return None
    cafe     = by_type.get('cafe', 0)
    salon    = by_type.get('salon', 0)
    bar      = by_type.get('bar', 0)
    rest     = by_type.get('restaurant', 0)
    cultural = (by_type.get('gallery', 0) + by_type.get('bookstore', 0)
                + by_type.get('records', 0))
    name_scores = [score_biz_name(b.get('name', '')) for b in biz]
    indie_ratio = (
        sum(1 for s in name_scores if s == 1) -
        sum(1 for s in name_scores if s == -1)
    ) / total
    return {
        'total':          total,
        'cultural_log':   math.log(1 + cultural),
        'bar_restaurant': bar / (rest + 1),
        'total_log':      math.log(1 + total),
        'linger_utility': (cafe + bar) / (salon + 1),
        'salon_share':    salon / total,
        'indie_ratio':    indie_ratio,
    }


def composite(f):
    score = (
        0.25 * min(f['cultural_log'],   3.5) / 3.5 +
        0.25 * min(f['bar_restaurant'], 0.7) / 0.7 +
        0.20 * min(f['linger_utility'], 10)  / 10  +
        0.20 * max(0, f['indie_ratio'] + 0.2) / 0.7 +
        0.10 * min(f['total_log'],      6)   / 6
    ) * 100
    salon_penalty = min(f['salon_share'] * 30, 12)
    return max(0, score - salon_penalty)


def vibe_bucket(score):
    if score >= 34: return 'HIGH'
    if score >= 22: return 'SOME'
    return 'LOW'


# ── Load catalog ──────────────────────────────────────────────────────────────

def load_catalog(path, metro):
    records = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if not d.get('success'):
                continue
            score_obj = d.get('score', {})
            biz = (score_obj
                   .get('livability_pillars', {})
                   .get('neighborhood_amenities', {})
                   .get('breakdown', {})
                   .get('business_list', []))
            status = score_obj.get('status_signal')
            name = d.get('catalog', {}).get('name', 'Unknown')
            area_type = (score_obj
                         .get('livability_pillars', {})
                         .get('neighborhood_amenities', {})
                         .get('breakdown', {})
                         .get('area_type', ''))
            if not biz or status is None:
                continue
            f_val = featurize(biz)
            if f_val is None:
                continue
            vs = composite(f_val)
            records.append({
                'name':        name,
                'metro':       metro,
                'area_type':   area_type,
                'vibe_score':  round(vs, 1),
                'vibe_bucket': vibe_bucket(vs),
                'status':      round(status, 1),
                'n_biz':       f_val['total'],
            })
    return records


def main():
    nyc_path = ROOT / 'data/nyc_metro_place_catalog_scores_merged.jsonl'
    la_path  = ROOT / 'data/la_metro_place_catalog_scores_merged.jsonl'

    records = load_catalog(nyc_path, 'NYC') + load_catalog(la_path, 'LA')

    # ── Correlation ────────────────────────────────────────────────────────────
    vibes   = [r['vibe_score'] for r in records]
    statuses = [r['status']    for r in records]
    n = len(records)
    mv = sum(vibes) / n
    ms = sum(statuses) / n
    cov = sum((v - mv) * (s - ms) for v, s in zip(vibes, statuses)) / n
    sv  = math.sqrt(sum((v - mv)**2 for v in vibes) / n)
    ss  = math.sqrt(sum((s - ms)**2 for s in statuses) / n)
    corr = cov / (sv * ss)

    print(f"\n{'='*60}")
    print(f"  Vibe Score vs Status Signal — {n} places (NYC + LA)")
    print(f"  Pearson r = {corr:.3f}  {'(low — good orthogonality)' if abs(corr) < 0.4 else '(HIGH — vibe may be picking up wealth signal)'}")
    print(f"{'='*60}\n")

    # ── Quadrant breakdown ────────────────────────────────────────────────────
    med_status = sorted(statuses)[n // 2]
    print(f"Median status signal: {med_status:.1f}\n")

    quads = {'HV_HS': [], 'HV_LS': [], 'LV_HS': [], 'LV_LS': []}
    for r in records:
        hv = r['vibe_score'] >= 34
        hs = r['status'] >= med_status
        key = ('HV' if hv else 'LV') + '_' + ('HS' if hs else 'LS')
        quads[key].append(r)

    labels = {
        'HV_HS': 'HIGH vibe + HIGH status  (Cobble Hill, West Village)',
        'HV_LS': 'HIGH vibe + LOW status   (Bushwick, Highland Park)',
        'LV_HS': 'LOW vibe  + HIGH status  (Greenwich, Palos Verdes)',
        'LV_LS': 'LOW vibe  + LOW status   (strip-mall suburbs)',
    }
    for key, lbl in labels.items():
        places = sorted(quads[key], key=lambda r: r['vibe_score'], reverse=True)
        print(f"── {lbl}  (n={len(places)})")
        for r in places[:8]:
            print(f"   {r['name']:<28} vibe={r['vibe_score']:>5.1f}  status={r['status']:>5.1f}  [{r['metro']}]")
        if len(places) > 8:
            print(f"   … +{len(places)-8} more")
        print()

    # ── Vibe bucket × status distribution ────────────────────────────────────
    print("── Vibe bucket × avg status signal")
    for bucket in ('HIGH', 'SOME', 'LOW'):
        bucket_records = [r for r in records if r['vibe_bucket'] == bucket]
        avg_s = sum(r['status'] for r in bucket_records) / len(bucket_records)
        print(f"   {bucket:<4}  n={len(bucket_records):>3}  avg_status={avg_s:.1f}")

    # ── Notable outliers ──────────────────────────────────────────────────────
    print("\n── Biggest gaps (high vibe, low status)")
    gap_records = sorted(records, key=lambda r: r['vibe_score'] - r['status'], reverse=True)
    for r in gap_records[:10]:
        print(f"   {r['name']:<28} vibe={r['vibe_score']:>5.1f}  status={r['status']:>5.1f}  gap={r['vibe_score']-r['status']:>+.1f}  [{r['metro']}]")

    print("\n── Biggest gaps (low vibe, high status)")
    for r in reversed(gap_records[-10:]):
        print(f"   {r['name']:<28} vibe={r['vibe_score']:>5.1f}  status={r['status']:>5.1f}  gap={r['vibe_score']-r['status']:>+.1f}  [{r['metro']}]")


if __name__ == '__main__':
    main()
