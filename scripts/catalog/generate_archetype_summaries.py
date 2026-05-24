"""
Generate Claude-based archetype classifications and neighborhood summaries
for all catalog entries. Stores results back in the JSONL alongside the
existing rule-based breakdown.

For known locations the stored result is served directly. For new locations
the live API calls Claude fresh. This script populates the catalog.

Usage:
    python scripts/catalog/generate_archetype_summaries.py [--dry-run]
    python scripts/catalog/generate_archetype_summaries.py --metro nyc
    python scripts/catalog/generate_archetype_summaries.py --force-regenerate
"""

import argparse
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import anthropic
from dotenv import load_dotenv

load_dotenv()

from data_sources import census_api

CATALOGS = {
    "nyc": "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "la":  "data/la_metro_place_catalog_scores_merged.jsonl",
}

METRO_NAMES = {
    "nyc": "New York City",
    "la":  "Los Angeles",
}

PLACE_POPULATION_THRESHOLD = 300_000

VALID_ARCHETYPES = {
    "Established",
    "Upper Middle Class",
    "Middle Class",
    "Up-and-Coming",
    "Immigrant Community",
    "Working Class",
}

ARCHETYPE_DEFINITIONS = """- Established: legacy wealth, deep-rooted community, high home values, long-tenured residents. ONLY if Wealth ≥ 65 AND Education ≥ 50.
- Upper Middle Class: professional/credential households, educated, above-median wealth. Typically Wealth > 55 AND Education > 50.
- Middle Class: stable homeowning families, moderate wealth (Wealth 35–65), solid housing without elite credentials. The broad middle — not struggling, not elite.
- Up-and-Coming: home values rising faster than resident wealth — active gentrification or transition. ONLY if Home cost ≥ 20. Do not use if Home cost < 20 (signals bad census data, not gentrification).
- Immigrant Community: ONLY for places with a clearly identifiable, named ethnic enclave — a Chinatown, Koreatown, Little Dominican Republic, Arab community, South Asian enclave, Hasidic neighborhood, etc. Diverse areas without a dominant enclave identity → Working Class or Middle Class.
- Working Class: genuinely lower-income, price-sensitive, blue-collar character. Typically Wealth < 40 AND Education < 35. A place with Wealth 45–60 is NOT Working Class even if education is modest."""

GUARDRAIL_RULES = """
HARD RULES — these override your general judgment:
1. Established: requires Wealth ≥ 65 AND Education ≥ 50. High stability or home cost alone does not qualify.
2. Up-and-Coming: requires Home cost ≥ 20. Home cost < 20 is likely a census data quality issue, not a gentrification signal.
3. Immigrant Community: requires a named, culturally-identified ethnic enclave. Do not apply to African-American neighborhoods, generic diverse suburbs, or mixed urban areas without a dominant immigrant enclave character.
4. Working Class: requires Wealth < 50 AND Education < 40. If Wealth ≥ 50 or Education ≥ 40, use Middle Class or higher.
"""


def resolve_place_fips_key(lat: float, lon: float) -> str | None:
    place = census_api.get_place_fips_for_coordinates(lat, lon)
    if not place:
        return None
    return f"{place['state_fips']}/{place['place_fips']}"


def _pillar_score(pillars: dict, key: str) -> int | None:
    v = (pillars.get(key) or {}).get("score")
    return int(v) if v is not None else None


def _fmt(v: int | None) -> str:
    return f"{v}/100" if v is not None else "n/a"


def build_prompt(name: str, place_type: str, metro: str, ss: dict, pillars: dict) -> str:
    ci = ss.get("classifier_inputs", {}) or {}

    # Pillar scores
    transit   = _pillar_score(pillars, "public_transit")
    outdoors  = _pillar_score(pillars, "active_outdoors")
    amenities = _pillar_score(pillars, "neighborhood_amenities")
    schools   = _pillar_score(pillars, "education")
    social    = _pillar_score(pillars, "social_fabric")
    beauty    = _pillar_score(pillars, "built_beauty")
    nature    = _pillar_score(pillars, "natural_beauty")
    health    = _pillar_score(pillars, "healthcare")
    climate   = _pillar_score(pillars, "climate_risk")
    econ      = _pillar_score(pillars, "economic_security")
    diversity = _pillar_score(pillars, "diversity")
    air       = _pillar_score(pillars, "air_travel")

    hv = (pillars.get("housing_value") or {}).get("summary") or {}
    renter_pct = hv.get("renter_pct")
    home_val   = hv.get("median_home_value")
    rent       = hv.get("median_gross_rent")
    owner_str  = f"{1 - renter_pct:.0%} owners" if renter_pct is not None else "ownership mix unknown"
    home_str   = f"~${int(home_val):,} median home" if home_val else ""
    rent_str   = f"~${int(rent):,}/mo median rent" if rent else ""
    housing_ctx = ", ".join(x for x in [owner_str, home_str, rent_str] if x)

    archetype = ss.get("archetype", "")

    return f"""Describe what it feels like to live in {name}, {metro} metro area. Write 2–3 sentences as if telling a friend who is considering moving there. Be vivid and honest about both the appeal and the tradeoffs. Do NOT mention any numbers or scores — translate them into human experience.

ARCHETYPE: {archetype}
PLACE TYPE: {place_type}

SCORED DIMENSIONS (0–100, higher = better):
  Walkability / transit:    {_fmt(transit)}
  Parks & active outdoors:  {_fmt(outdoors)}
  Neighborhood amenities:   {_fmt(amenities)}
  Schools:                  {_fmt(schools)}
  Social fabric / community:{_fmt(social)}
  Built environment beauty: {_fmt(beauty)}
  Natural surroundings:     {_fmt(nature)}
  Healthcare access:        {_fmt(health)}
  Climate risk:             {_fmt(climate)}  (higher = lower risk)
  Economic opportunity:     {_fmt(econ)}
  Diversity:                {_fmt(diversity)}
  Airport access:           {_fmt(air)}

HOUSING CHARACTER: {housing_ctx}

Return ONLY valid JSON:
{{"summary": "..."}}"""


def check_guardrails(archetype: str, ss: dict) -> str | None:
    """Returns a violation message if the classification breaks a hard rule, else None."""
    ci = ss.get("classifier_inputs", {}) or {}
    wealth    = ss.get("wealth") or 0
    home_cost = ss.get("home_cost") or 0
    edu       = ci.get("education") or 0
    if archetype == "Established" and (wealth < 65 or edu < 50):
        return f"Established requires W≥65 and edu≥50, got W={wealth:.0f} edu={edu:.0f}"
    if archetype == "Up-and-Coming" and home_cost < 20:
        return f"Up-and-Coming requires HC≥20, got HC={home_cost:.0f}"
    if archetype == "Working Class" and (wealth >= 50 or edu >= 40):
        return f"Working Class requires W<50 and edu<40, got W={wealth:.0f} edu={edu:.0f}"
    return None


def _parse_response(raw: str) -> str | None:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    result = json.loads(raw)
    return result.get("summary", "").strip() or None


def call_claude(client: anthropic.Anthropic, prompt: str, ss: dict) -> dict | None:
    for attempt in range(2):
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            summary = _parse_response(raw)
            if not summary:
                print(f"    ⚠️  Bad JSON or empty summary (attempt {attempt+1})")
                continue
            return {"summary": summary}
        except Exception as e:
            print(f"    ⚠️  Claude call failed (attempt {attempt+1}): {e}")
    return None


def process_catalog(path: str, metro: str, dry_run: bool, force: bool) -> list:
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    client = anthropic.Anthropic()
    metro_label = METRO_NAMES[metro]

    ok = skip = err = 0

    for i, entry in enumerate(entries):
        name = entry.get("catalog", {}).get("name", f"entry_{i}")
        place_type = entry.get("catalog", {}).get("type", "neighborhood")
        score = entry.get("score", {})
        ss = score.get("status_signal_breakdown", {})
        pillars = score.get("livability_pillars", {})
        coords = score.get("coordinates", {})
        lat = coords.get("lat")
        lon = coords.get("lon")

        if not ss or not lat or not lon:
            skip += 1
            continue

        # Never overwrite manual overrides
        if ss.get("archetype_source") == "manual_override":
            skip += 1
            continue

        # Skip already-summarised entries unless forced
        if not force and ss.get("llm_summary"):
            skip += 1
            continue

        print(f"[{i+1}/{len(entries)}] {name} …", flush=True)

        place_fips_key = resolve_place_fips_key(lat, lon)
        prompt = build_prompt(name, place_type, metro_label, ss, pillars)

        if dry_run:
            print(f"    [dry-run] archetype={ss.get('archetype')}")
            ok += 1
            continue

        result = call_claude(client, prompt, ss)
        if result is None:
            err += 1
            continue

        print(f"    archetype={ss.get('archetype')} ✓")
        ss["llm_summary"]    = result["summary"]
        ss["place_fips_key"] = place_fips_key

        ok += 1
        time.sleep(0.15)  # stay well under Haiku rate limits

    print(f"\n  classified={ok}  skipped={skip}  errors={err}")
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-regenerate", action="store_true", help="Re-run even for already-classified entries")
    parser.add_argument("--metro", choices=["nyc", "la"], default=None)
    args = parser.parse_args()

    metros = [args.metro] if args.metro else list(CATALOGS.keys())

    for metro in metros:
        path = CATALOGS[metro]
        print(f"\n=== {metro.upper()} ({path}) ===")
        entries = process_catalog(path, metro, args.dry_run, args.force_regenerate)

        if not args.dry_run:
            ts = time.strftime("%Y%m%d-%H%M%S")
            shutil.copy(path, f"{path}.bak.{ts}")
            with open(path, "w") as f:
                for e in entries:
                    f.write(json.dumps(e, separators=(",", ":")) + "\n")
            print(f"  Wrote {len(entries)} lines to {path}")


if __name__ == "__main__":
    main()
