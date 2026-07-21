#!/usr/bin/env python3
"""
Compute local_scene_score + local_scene_bucket from stored business_list data.
Writes fields in-place to both NYC and LA catalog JSONL files.

Label: Local Scene
Tooltip: Reflects the presence of independent places to spend time,
         like cafés, bookstores, bars, and galleries.
Buckets: High >= 34, Some 22-34, Low < 22
"""
import json, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CATALOGS = [
    ROOT / 'data/nyc_metro_place_catalog_scores_merged.jsonl',
    ROOT / 'data/la_metro_place_catalog_scores_merged.jsonl',
]

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
    r'sourdough|farm.to|root|vine|grove|harvest|larder|co\b|co\.|& co|company|brothers|sisters)\b',
    re.I,
)
GENERIC_WORDS = re.compile(
    r'\b(palace|garden|dragon|golden|lucky|express|buffet|wok|dynasty|empire|'
    r'super\s|best\s|#1|number\s*one|no\.?\s*1)\b', re.I)
POSSESSIVE = re.compile(r"^[A-Z][a-z]+'s\b|^[A-Z][a-z]+ [A-Z][a-z]+'s\b")
AMPERSAND  = re.compile(r'\s&\s')


def _score_name(name: str) -> int:
    nl = name.lower()
    if any(c in nl for c in KNOWN_CHAINS):
        return -1
    if GENERIC_WORDS.search(name):
        return -1
    pts = 0
    if INDIE_WORDS.search(name):  pts += 1
    if AMPERSAND.search(name):    pts += 1
    if POSSESSIVE.match(name):    pts += 1
    if re.match(r'^The [A-Z]', name): pts += 1
    return min(pts, 1)


def _compute(biz: list) -> tuple[float, str] | tuple[None, None]:
    by_type: dict[str, int] = {}
    for b in biz:
        t = b.get('type', '?')
        by_type[t] = by_type.get(t, 0) + 1

    total = sum(by_type.values())
    if not total:
        return None, None

    cafe     = by_type.get('cafe', 0)
    salon    = by_type.get('salon', 0)
    bar      = by_type.get('bar', 0)
    rest     = by_type.get('restaurant', 0)
    cultural = (by_type.get('gallery', 0) + by_type.get('bookstore', 0)
                + by_type.get('records', 0))

    name_scores = [_score_name(b.get('name', '')) for b in biz]
    indie_ratio = (
        sum(1 for s in name_scores if s == 1) -
        sum(1 for s in name_scores if s == -1)
    ) / total

    raw = (
        0.25 * min(math.log(1 + cultural),        3.5) / 3.5 +
        0.25 * min(bar / (rest + 1),              0.7) / 0.7 +
        0.20 * min((cafe + bar) / (salon + 1),   10.0) / 10.0 +
        0.20 * max(0, indie_ratio + 0.2)               / 0.7 +
        0.10 * min(math.log(1 + total),            6.0) / 6.0
    ) * 100

    salon_penalty = min((salon / total) * 30, 12)
    score = round(max(0.0, raw - salon_penalty), 1)

    if score >= 34:
        bucket = 'High'
    elif score >= 22:
        bucket = 'Some'
    else:
        bucket = 'Low'

    return score, bucket


def process(path: Path) -> None:
    lines = path.read_text().splitlines()
    out = []
    scored = skipped = no_biz = 0

    for line in lines:
        if not line.strip():
            continue
        d = json.loads(line)
        if not d.get('success'):
            out.append(line)
            skipped += 1
            continue

        biz = (d.get('score', {})
               .get('livability_pillars', {})
               .get('neighborhood_amenities', {})
               .get('breakdown', {})
               .get('business_list', []))

        if not biz:
            out.append(line)
            no_biz += 1
            continue

        score, bucket = _compute(biz)
        if score is None:
            out.append(line)
            no_biz += 1
            continue

        d['score']['local_scene_score']  = score
        d['score']['local_scene_bucket'] = bucket
        out.append(json.dumps(d, ensure_ascii=False))
        scored += 1

    path.write_text('\n'.join(out) + '\n')
    print(f'{path.name}: {scored} scored, {no_biz} no-biz-data, {skipped} skipped')


def main():
    for path in CATALOGS:
        process(path)
    print('Done.')


if __name__ == '__main__':
    main()
