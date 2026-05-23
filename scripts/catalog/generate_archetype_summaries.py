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


def build_prompt(name: str, place_type: str, metro: str, ss: dict, pillars: dict) -> str:
    ci = ss.get("classifier_inputs", {})
    wealth    = ss.get("wealth") or 0
    home_cost = ss.get("home_cost") or 0
    education = ss.get("education") or 0
    occupation = ss.get("occupation") or 0
    stability = ci.get("stability") or 0
    diversity_pillar = pillars.get("diversity", {})
    diversity = diversity_pillar.get("score") or 0

    hv_summ = pillars.get("housing_value", {}).get("summary", {})
    income    = hv_summ.get("median_household_income")
    home_val  = hv_summ.get("median_home_value")
    rent      = hv_summ.get("median_gross_rent")
    renter_pct = hv_summ.get("renter_pct")

    income_str   = f"${int(income):,}"    if income   else "not available"
    home_val_str = f"${int(home_val):,}"  if home_val else "not available"
    rent_str     = f"${int(rent):,}/mo"   if rent     else "not available"
    renter_str   = f"{renter_pct:.0%}"    if renter_pct is not None else "not available"

    return f"""You are classifying a US neighborhood's socioeconomic archetype based on measured data.

LOCATION: {name}, {metro} metro area
PLACE TYPE: {place_type}

METRO-NORMALIZED SCORES (percentile 0–100 within the metro):
  Wealth:         {wealth:.0f}
  Home cost:      {home_cost:.0f}
  Education:      {education:.0f}
  Occupation mix: {occupation:.0f}
  Stability:      {stability:.0f}
  Diversity:      {diversity:.0f}

RAW CENSUS DATA:
  Median household income: {income_str}
  Median home value:       {home_val_str}
  Median gross rent:       {rent_str}
  Renter share:            {renter_str}

IMPORTANT: Census tract data is sometimes contaminated by adjacent areas. A very low Home cost score (< 20) for a neighborhood known to have expensive housing is a data quality issue — ignore it and classify based on Wealth + Education instead.
Use the metro-normalized Wealth score as the primary signal; treat raw income as secondary.

Pick exactly one archetype:
{ARCHETYPE_DEFINITIONS}
{GUARDRAIL_RULES}
Write a summary: exactly 2 sentences, present tense.
Sentence 1: who lives here and what defines the economic character.
Sentence 2: what makes this place distinctive — community culture, housing type, or notable traits.

Return ONLY valid JSON (no markdown, no explanation):
{{"archetype": "...", "summary": "..."}}"""


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


def _parse_response(raw: str) -> tuple[str, str] | None:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    result = json.loads(raw)
    archetype = result.get("archetype", "").strip()
    summary   = result.get("summary", "").strip()
    if archetype not in VALID_ARCHETYPES or not summary:
        return None
    return archetype, summary


def call_claude(client: anthropic.Anthropic, prompt: str, ss: dict) -> dict | None:
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(2):
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=messages,
            )
            raw = msg.content[0].text.strip()
            parsed = _parse_response(raw)
            if not parsed:
                print(f"    ⚠️  Bad JSON or empty summary (attempt {attempt+1})")
                continue
            archetype, summary = parsed
            violation = check_guardrails(archetype, ss)
            if violation:
                print(f"    ⚠️  Guardrail (attempt {attempt+1}): {violation} — retrying")
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"That violates a hard rule: {violation}. Pick a different archetype and rewrite the summary accordingly. Return only JSON."},
                ]
                continue
            return {"archetype": archetype, "summary": summary}
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

        # Skip already-classified entries unless forced
        if not force and ss.get("archetype_source") == "llm":
            skip += 1
            continue

        print(f"[{i+1}/{len(entries)}] {name} …", flush=True)

        # Resolve place FIPS key for fast catalog lookup
        place_fips_key = resolve_place_fips_key(lat, lon)

        # Check if the place FIPS resolves to a large city → record it but note it's a neighborhood
        if place_fips_key:
            # We store it regardless; the lookup layer decides whether to use it
            pass

        prompt = build_prompt(name, place_type, metro_label, ss, pillars)

        if dry_run:
            print(f"    [dry-run] would call Claude")
            print(f"    place_fips_key={place_fips_key}")
            ok += 1
            continue

        result = call_claude(client, prompt, ss)
        if result is None:
            err += 1
            continue

        llm_archetype = result["archetype"]
        llm_summary   = result["summary"]
        rule_archetype = ss.get("archetype")

        if llm_archetype != rule_archetype:
            print(f"    rule={rule_archetype} → llm={llm_archetype}")
        else:
            print(f"    archetype={llm_archetype} ✓")

        # Update status_signal_breakdown in-place
        ss["archetype"]        = llm_archetype
        ss["status_label"]     = llm_archetype
        ss["llm_summary"]      = llm_summary
        ss["archetype_source"] = "llm"
        ss["place_fips_key"]   = place_fips_key
        if rule_archetype and rule_archetype != llm_archetype:
            ss["rule_archetype"] = rule_archetype

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
