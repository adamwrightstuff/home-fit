#!/usr/bin/env python3
"""
Social post draft queue for Trovamo.

Picks interesting angles from the catalog and drafts Instagram posts + photo recs.
Run daily: python3 scripts/social/draft_queue.py

Output: scripts/social/output/drafts_YYYY-MM-DD.md
Log:    scripts/social/posted_log.json  (tracks what's been drafted to avoid repeats)
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

PILLAR_ORDER = [
    'quality_education', 'neighborhood_amenities', 'economic_opportunity',
    'climate_risk', 'active_outdoors', 'natural_beauty', 'diversity',
    'social_fabric', 'healthcare_access', 'public_transit_access',
    'air_travel_access', 'housing_value', 'community_safety',
]

TONE_RULES = """
Tone rules (strictly follow these):
- No em dashes. Use a period or start a new sentence.
- Never mention scores or numbers. Don't say "scores 78" or "ranks #1".
- No negative framings. Never compare a place unfavorably to another.
- Avoid the words: data, dimensions, livability, metrics.
- Lead with the place or a person, not an abstract concept.
- Short sentences. Conversational. Like telling a friend about a town you love.
- No bullet points or list-style conclusions.
- No "that's what X is for" signoffs.
- End every post with exactly: trovamo.co. Link in bio.
- Warm, direct, specific. Modeled on @suburbanjunglegroup's Instagram voice.
"""

CATALOG_FILES = {
    'nyc': 'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'la':  'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    'sf':  'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
}

SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / 'posted_log.json'
OUTPUT_DIR = SCRIPT_DIR / 'output'


def load_catalog(metro):
    places = []
    path = CATALOG_FILES.get(metro)
    if not path or not os.path.exists(path):
        return places
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            lp = d.get('score', {}).get('livability_pillars', {})
            scores = [lp.get(p, {}).get('score') or 0 for p in PILLAR_ORDER]
            eq = sum(scores) / len(scores) if scores else 0
            s = d.get('score', {})
            places.append({
                'name': d['catalog']['name'],
                'metro': metro,
                'county': d['catalog'].get('county_borough', ''),
                'state': d['catalog'].get('state_abbr', ''),
                'eq_score': round(eq, 1),
                'housing_value':       lp.get('housing_value', {}).get('score') or 0,
                'natural_beauty':      lp.get('natural_beauty', {}).get('score') or 0,
                'quality_education':   lp.get('quality_education', {}).get('score') or 0,
                'active_outdoors':     lp.get('active_outdoors', {}).get('score') or 0,
                'social_fabric':       lp.get('social_fabric', {}).get('score') or 0,
                'public_transit':      lp.get('public_transit_access', {}).get('score') or 0,
                'happiness_index':     s.get('happiness_index') or 0,
                'longevity_index':     s.get('longevity_index') or 0,
                'lp': lp,
            })
    return places


def load_log():
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []


def save_log(log):
    LOG_FILE.write_text(json.dumps(log, indent=2))


def pick_angles(all_places, posted_names, n=6):
    posted = set(posted_names)
    avail = [p for p in all_places if p['name'] not in posted and p['eq_score'] > 55]
    used = set()

    def best(pool, key):
        for p in sorted(pool, key=lambda x: -x[key]):
            if p['name'] not in used:
                used.add(p['name'])
                return p
        return None

    picks = []

    # 1. Top happiness index
    p = best(avail, 'happiness_index')
    if p: picks.append(('happiness', p))

    # 2. Value play: high overall score + good housing value (affordable for quality)
    value = [p for p in avail if p['housing_value'] > 70 and p['eq_score'] > 65 and p['name'] not in used]
    p = best(value, 'eq_score')
    if p: picks.append(('value', p))

    # 3. Natural beauty standout
    p = best(avail, 'natural_beauty')
    if p: picks.append(('nature', p))

    # 4. Schools + housing value: rare combo
    sv = [p for p in avail if p['quality_education'] > 85 and p['housing_value'] > 65 and p['name'] not in used]
    p = best(sv, 'eq_score')
    if p: picks.append(('schools_value', p))

    # 5. Top longevity index
    p = best(avail, 'longevity_index')
    if p: picks.append(('longevity', p))

    # 6. Top overall score not yet picked
    p = best(avail, 'eq_score')
    if p: picks.append(('top_overall', p))

    return picks[:n]


ANGLE_CONTEXT = {
    'happiness':     "This place ranks at the top of our happiness index. Write about what makes it feel genuinely good to live there day to day — the rhythm, the feel, what people notice when they actually live there.",
    'value':         "This place has strong schools and outdoor access but is more affordable than comparable towns nearby. Write about the value story without mentioning prices or scores.",
    'nature':        "This place has exceptional natural beauty scores. Write about what it looks and feels like to be there — landscapes, outdoors, the physical environment.",
    'schools_value': "This place has top-ranked schools AND is relatively affordable for what you get. That combination is rare. Write about that tension and why it matters for families.",
    'longevity':     "This place scores at the top of our longevity index. Write about the lifestyle factors — walkability, green space, community — that make it feel healthy and alive.",
    'top_overall':   "This place stands out across every category we measure. Write about what makes it worth knowing and why it keeps coming up when families go looking.",
}

PHOTO_SUGGESTIONS = {
    'happiness':     "Main street or town center — Saturday morning, coffee in hand, people out. Warm light.",
    'value':         "Residential street with mature trees. Charming, lived-in, not flashy.",
    'nature':        "Golden hour landscape — trails, water, tree canopy, or coastal view.",
    'schools_value': "Town center or neighborhood park. Community feel, families visible.",
    'longevity':     "Walkable street, waterfront, or green space. Active, calm, inviting.",
    'top_overall':   "Signature neighborhood view or main street scene.",
}


def main():
    # Load catalogs
    all_places = []
    for metro in CATALOG_FILES:
        batch = load_catalog(metro)
        print(f"  {metro}: {len(batch)} places")
        all_places.extend(batch)
    print(f"Total: {len(all_places)} places\n")

    # Load log, pick angles
    log = load_log()
    posted_names = [e['name'] for e in log]
    picks = pick_angles(all_places, posted_names)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out = OUTPUT_DIR / f"drafts_{today}.md"

    lines = [f"# Trovamo Draft Picks — {today}\n",
             f"Paste these into Claude to write the posts.\n"]

    for angle, place in picks:
        label = angle.replace('_', ' ').title()
        loc = f"{place['name']}, {place['state']}" if place['state'] else place['name']
        context = ANGLE_CONTEXT.get(angle, "Write about what makes this place worth knowing.")
        photo = PHOTO_SUGGESTIONS.get(angle, f"Neighborhood scene in {place['name']}")

        lines.append(f"## {loc} — {label}")
        lines.append(f"*Metro: {place['metro'].upper()} | County: {place['county']}*\n")
        lines.append(f"**Angle:** {context}\n")
        lines.append(f"**Photo rec:** {photo}\n")
        lines.append("---\n")

        log.append({
            'name': place['name'],
            'angle': angle,
            'date': today,
            'metro': place['metro'],
        })

    out.write_text('\n'.join(lines))
    save_log(log)
    print(f"\nPicks saved to {out}")


if __name__ == '__main__':
    main()
