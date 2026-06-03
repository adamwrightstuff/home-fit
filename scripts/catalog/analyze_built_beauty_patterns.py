#!/usr/bin/env python3
"""
Cross-catalog built beauty pattern analysis.
Beauty classifications are type-neutral: historic urban, prewar residential,
planned suburban, midcentury modern, hillside, coastal, and estate communities
are all treated as valid forms of architectural beauty.
"""
import json
import statistics
from collections import defaultdict

# ── Beauty classification ──────────────────────────────────────────────────
# BEAUTIFUL: genuinely architecturally beautiful regardless of density/type
# NOT_BEAUTIFUL: genuinely undistinguished — generic tract, auto-oriented sprawl
# (unlabeled = contested/unclassified, excluded from discriminator analysis)

BEAUTIFUL = {
    # ── NYC: historic urban landmark ──
    'SoHo', 'Nolita', 'Carnegie Hill', 'NoHo', 'East Village', 'West Village',
    'Greenwich Village', 'Chinatown', 'Little Italy', 'Tribeca', 'Flatiron',
    'Murray Hill', 'Gramercy Park',
    # ── NYC: prewar residential density ──
    'Upper West Side', 'Upper East Side', 'Harlem', 'Morningside Heights',
    'Washington Heights', 'Yorkville', 'Kips Bay', 'Chelsea',
    # ── NYC: brownstone Brooklyn ──
    'Carroll Gardens', 'Park Slope', 'Boerum Hill', 'Cobble Hill', 'Brooklyn Heights',
    'Clinton Hill', 'Crown Heights', 'Bed-Stuy', 'Prospect Heights',
    'Greenpoint', 'Williamsburg', 'Fort Greene',
    # ── NYC: industrial conversion / waterfront ──
    'DUMBO', 'Long Island City', 'Mott Haven', 'Red Hook',
    # ── NYC: planned + intentional suburb ──
    'Forest Hills',      # Forest Hills Gardens — Olmsted-designed, landmark district
    'Fieldston',         # Bronx: purpose-built Tudor mansion enclave
    'Jackson Heights',   # garden apartment historic district, one of NYC's finest
    'Ditmas Park',       # Victorian detached homes, distinctive character
    'Garden City',       # planned community, Olmsted-inspired
    # ── NYC: historic suburban towns ──
    'Tarrytown', 'Bronxville', 'Larchmont', 'Rye', 'Scarsdale',
    'Hastings-on-Hudson', 'Sleepy Hollow', 'Irvington', 'Pelham', 'Pelham Manor',
    # ── NYC: NJ historic suburbs ──
    'Glen Ridge', 'Montclair', 'Maplewood', 'South Orange', 'Westfield',
    'Hoboken',
    # ── NYC: other recognizable character ──
    'Astoria', 'Ridgewood', 'Sunset Park', 'Kensington',
    'Windsor Terrace', 'Mamaroneck', 'Ossining',
    # ── LA: urban landmark / historic ──
    'Arts District', 'Little Tokyo', 'Downtown LA', 'Chinatown LA',
    # ── LA: walkable neighborhood character ──
    'Venice', 'Silver Lake', 'Los Feliz', 'Highland Park', 'Echo Park',
    'Larchmont Village', 'Miracle Mile', 'Atwater Village', 'Frogtown',
    'Mount Washington', 'Elysian Valley',
    # ── LA: prewar residential estate ──
    'Hancock Park',      # 1920s Spanish Colonial, city landmark district
    'Windsor Square',    # 1910s-20s grand homes, landmark district
    'Leimert Park',      # 1920s planned Spanish Colonial community
    'Boyle Heights',     # historic working-class, significant cultural architecture
    'Pasadena',          # Greene & Greene Craftsman, Old Pasadena, world-class
    'San Marino',        # beautiful 1910s-30s residential, Huntington Library
    'Whittier',          # Quaker-founded historic town, genuine character
    # ── LA: planned coastal / hillside estate ──
    'Palos Verdes Estates',  # 1920s Olmsted-designed Spanish Colonial planned community
    'Beverly Hills',         # Spanish Colonial Revival, Italian Renaissance residential
    'Bel Air',               # custom modernist estates, Neutra / Lautner / Eames era
    'Pacific Palisades',     # midcentury modern on canyon lots, Eames House nearby
    'Brentwood',             # hillside residential, architectural quality
    'Hollywood Hills',       # Case Study Houses, Neutra, Schindler, midcentury modern
    # ── LA: other character neighborhoods ──
    'San Pedro', 'Culver City', 'Hermosa Beach', 'El Segundo',
    'West Hollywood',    # walkable character, historic architecture
}

NOT_BEAUTIFUL = {
    # ── NYC: generic postwar tract ──
    'Howard Beach',   # 1960s grid tract, no design distinction
    'Oceanside',      # generic Long Island suburb
    'Hewlett',        # generic
    'Bellmore',       # generic
    'Edgewater',      # modern high-rise waterfront, no street character
    'New Dorp',       # generic Staten Island
    'Great Kills',    # generic Staten Island
    'Tottenville',    # generic Staten Island
    'Rockaway Beach', # generic
    'Chatham',        # undistinguished NJ suburb
    'Morristown',     # mixed but core is unremarkable
    'Old Greenwich',  # generic CT suburb
    # ── LA: generic tract / auto-oriented sprawl ──
    'Reseda',         # generic San Fernando Valley
    'Chatsworth',     # generic San Fernando Valley
    'Tarzana',        # generic, named for Tarzan author but no architectural merit
    'Thousand Oaks',  # master-planned sprawl, no character
    'Lakewood',       # literally one of the first postwar Levittown-style tracts in the West
    'La Mirada',      # planned sprawl, undistinguished
    'Cerritos',       # planned suburb, no character
    'El Monte',       # generic San Gabriel Valley
    'East Los Angeles', # largely generic postwar tract
    'Encino',         # generic San Fernando Valley
    'Porter Ranch',   # master-planned tract, entirely generic
    'La Crescenta',   # generic
    'Van Nuys',       # generic SFV strip commercial (not Highland Park)
}

BEAUTY_TYPE = {
    # Useful for understanding what kind of beauty each place represents
    'SoHo': 'urban_landmark', 'Nolita': 'urban_landmark', 'Carnegie Hill': 'urban_landmark',
    'NoHo': 'urban_landmark', 'East Village': 'urban_mixed', 'West Village': 'urban_charming',
    'Greenwich Village': 'urban_charming', 'Chinatown': 'urban_heritage',
    'Carroll Gardens': 'brownstone', 'Park Slope': 'brownstone', 'Boerum Hill': 'brownstone',
    'Brooklyn Heights': 'brownstone', 'Crown Heights': 'brownstone', 'Bed-Stuy': 'brownstone',
    'Forest Hills': 'planned_suburb', 'Fieldston': 'planned_suburb',
    'Jackson Heights': 'planned_suburb', 'Garden City': 'planned_suburb',
    'Palos Verdes Estates': 'planned_suburb', 'Leimert Park': 'planned_suburb',
    'Tarrytown': 'historic_town', 'Larchmont': 'historic_town', 'Rye': 'historic_town',
    'Bronxville': 'historic_town', 'Scarsdale': 'historic_town', 'Montclair': 'historic_town',
    'Maplewood': 'historic_town', 'Glen Ridge': 'historic_town', 'Westfield': 'historic_town',
    'Pasadena': 'historic_town', 'Whittier': 'historic_town',
    'Hancock Park': 'prewar_estate', 'Windsor Square': 'prewar_estate',
    'San Marino': 'prewar_estate', 'Beverly Hills': 'prewar_estate',
    'Bel Air': 'modernist_estate', 'Pacific Palisades': 'modernist_estate',
    'Hollywood Hills': 'modernist_estate', 'Brentwood': 'modernist_estate',
    'Venice': 'coastal_character', 'Hermosa Beach': 'coastal_character',
    'Silver Lake': 'hillside_eclectic', 'Los Feliz': 'hillside_eclectic',
    'Echo Park': 'hillside_eclectic', 'Highland Park': 'craftsman',
    'Arts District': 'industrial_creative', 'DUMBO': 'industrial_creative',
    'Mott Haven': 'industrial_creative',
}


def load_catalog(path, metro):
    rows = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            cat = d.get('catalog', {})
            sc = d.get('score', d)
            bb = sc.get('livability_pillars', {}).get('built_beauty', {})
            if not isinstance(bb, dict):
                continue
            score = bb.get('score')
            if score is None:
                continue
            s = bb.get('summary', {})
            dq = bb.get('data_quality', {})
            rows.append({
                'name': cat.get('name', ''),
                'metro': metro,
                'cat_type': cat.get('type', ''),
                'score': round(score, 1),
                'ht': round(s.get('height_diversity', 0) or 0, 1),
                'tp': round(s.get('type_diversity', 0) or 0, 1),
                'ft': round(s.get('footprint_variation', 0) or 0, 1),
                'cov': round(s.get('built_coverage_ratio', 0) or 0, 3),
                'heritage': int(s.get('heritage_count', 0) or 0),
                'enhancer': round(s.get('enhancer_bonus', 0) or 0, 2),
                'component': round(s.get('component_score', 0) or 0, 1),
                'tags': s.get('built_context_tags', '') or '',
                'yr': str(s.get('median_year_built', '') or ''),
                'has_data': (s.get('height_diversity', 0) or 0) > 0 or (s.get('footprint_variation', 0) or 0) > 0,
                'api_error': 'api_error' in (dq.get('data_warnings') or []),
                'beauty_type': BEAUTY_TYPE.get(cat.get('name', ''), ''),
            })
    return rows


def pct(vals, label):
    if not vals:
        return
    print(f"    {label:<14}: mean={statistics.mean(vals):5.1f}  median={statistics.median(vals):5.1f}"
          f"  min={min(vals):5.1f}  max={max(vals):5.1f}")


def main():
    nyc = load_catalog('data/nyc_metro_place_catalog_scores_merged.jsonl', 'NYC')
    la  = load_catalog('data/la_metro_place_catalog_scores_merged.jsonl', 'LA')
    all_rows = nyc + la

    clean = [r for r in all_rows if not r['api_error']]
    b = [r for r in clean if r['name'] in BEAUTIFUL]
    nb = [r for r in clean if r['name'] in NOT_BEAUTIFUL]

    print(f"Total: {len(all_rows)} | Clean: {len(clean)} | Beautiful: {len(b)} | Not-beautiful: {len(nb)}")
    print()

    # ── Overall discriminator stats ───────────────────────────────────────
    print("=" * 70)
    print("METRIC SEPARATORS: beautiful vs not-beautiful")
    print("=" * 70)
    b_med = statistics.median([r['score'] for r in b])
    nb_med = statistics.median([r['score'] for r in nb])
    print(f"\nBeautiful n={len(b)}  median score={b_med}")
    pct([r['score'] for r in b], 'score')
    pct([r['ht'] for r in b], 'height_div')
    pct([r['tp'] for r in b], 'type_div')
    pct([r['ft'] for r in b], 'foot_var')
    pct([r['cov'] for r in b], 'coverage')
    pct([r['heritage'] for r in b], 'heritage')
    pct([r['enhancer'] for r in b], 'enhancer')

    print(f"\nNot-beautiful n={len(nb)}  median score={nb_med}")
    pct([r['score'] for r in nb], 'score')
    pct([r['ht'] for r in nb], 'height_div')
    pct([r['tp'] for r in nb], 'type_div')
    pct([r['ft'] for r in nb], 'foot_var')
    pct([r['cov'] for r in nb], 'coverage')
    pct([r['heritage'] for r in nb], 'heritage')
    pct([r['enhancer'] for r in nb], 'enhancer')

    print("\nGaps (beautiful − not-beautiful median):")
    for metric, label in [('score','score'), ('heritage','heritage'), ('ht','height_div'),
                           ('tp','type_div'), ('ft','foot_var'), ('cov','coverage'), ('enhancer','enhancer')]:
        bv = statistics.median([r[metric] for r in b])
        nv = statistics.median([r[metric] for r in nb])
        print(f"  {label:<14}: {bv:6.1f} − {nv:6.1f} = {bv-nv:+6.1f}{'  ← STRONG' if abs(bv-nv) > 5 else ''}")

    # ── By beauty type ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SCORES BY BEAUTY TYPE")
    print("=" * 70)
    by_type = defaultdict(list)
    for r in b:
        bt = r['beauty_type'] or 'other'
        by_type[bt].append(r)
    for bt, members in sorted(by_type.items()):
        scores = [r['score'] for r in members]
        print(f"\n  {bt} (n={len(members)})")
        print(f"    score: mean={statistics.mean(scores):.1f}  median={statistics.median(scores):.1f}  range={min(scores):.1f}–{max(scores):.1f}")
        for r in sorted(members, key=lambda x: x['score']):
            print(f"    {r['score']:5.1f}  [{r['metro']}] {r['name']}")

    # ── Score inversions ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SCORE INVERSIONS")
    print("=" * 70)
    print(f"\nBeautiful scoring BELOW not-beautiful median ({nb_med:.1f}):")
    for r in sorted([r for r in b if r['score'] < nb_med], key=lambda x: x['score']):
        bt = r['beauty_type'] or '?'
        print(f"  [{r['metro']}] {r['name']:<28} {r['score']:5.1f}  type={bt}  ht={r['ht']:4.1f} tp={r['tp']:4.1f} ft={r['ft']:4.1f} cov={r['cov']:.3f} her={r['heritage']:3}")

    print(f"\nNot-beautiful scoring ABOVE beautiful median ({b_med:.1f}):")
    for r in sorted([r for r in nb if r['score'] > b_med], key=lambda x: -x['score']):
        print(f"  [{r['metro']}] {r['name']:<28} {r['score']:5.1f}  ht={r['ht']:4.1f} tp={r['tp']:4.1f} ft={r['ft']:4.1f} cov={r['cov']:.3f} her={r['heritage']:3}  [{r['tags']}]")

    # ── Full ranked table ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("FULL RANKED TABLE")
    print("=" * 70)
    print(f"{'Score':>5}  {'B?':>2}  {'Metro':>3}  {'Name':<28}  {'ht':>4} {'tp':>4} {'ft':>4} {'cov':>5} {'her':>3}  Tags")
    for r in sorted(all_rows, key=lambda x: -x['score']):
        label = ' * ' if r['name'] in BEAUTIFUL else (' - ' if r['name'] in NOT_BEAUTIFUL else '   ')
        err = '!' if r['api_error'] else ' '
        print(f"{r['score']:5.1f}{err} {label} [{r['metro']}] {r['name']:<28} {r['ht']:4.1f} {r['tp']:4.1f} {r['ft']:4.1f} {r['cov']:5.3f} {r['heritage']:3}  {r['tags'][:28]}")


if __name__ == '__main__':
    main()
