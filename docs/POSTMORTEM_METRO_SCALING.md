# Postmortem: scaling to Austin, Chicago and Philadelphia (and re-checking the live metros)

Oct 7–15, 2026. Goal: roll the metro playbook out to three new metros without gaps, then audit the five live metros with the same standard. Standard set at the start: *people make decisions about where to move from this, so gaps are not acceptable.*

## Outcome

| Metro | State | Notes |
|---|---|---|
| Austin | Published | 4 crime places mapped to agencies; 6 transit gaps and 2 empty-walkable-area places accepted with reasons |
| Chicago | Published | All 103 places clean; 2024 political lean unavailable (IL/IN/DE precincts were redrawn), shown as 2020 and labelled |
| LA | Published | Porter Ranch transit accepted (service exists 2–5 km away, none in walking radius) |
| SF | Published | 4 pillar values withheld (shown as unknown) until Overpass lets them be rescored |
| NYC | Published | 5 pillar values withheld, same reason |
| Seattle | Not done | Ballard and Kirkland failed to score at all; needs Overpass |
| Philadelphia | Not done | Never scored; needs Overpass |

Tests went from about 190 to 232. One health command now audits every metro.

## Where the time went (root causes)

**1. The public Overpass servers (the biggest single cause).** Overpass supplies the map data for most pillars. Over the week the servers refused connections, returned 500/504 on heavy queries, and finally blocked this machine with 403. Worse, some outages came back as HTTP 200 with an error remark and an empty result, which the app treated as "no parks here." Effects: 39 of 58 Austin places scored 0 for active outdoors, healthcare and amenities results were wrong for hundreds of places in the live metros, and every retry during an outage either failed or hung.

**2. Pillars report failure as success.** A failed lookup was returned as `status=success` with a zero score. Nothing downstream could tell a genuinely empty area from a broken lookup, so each problem had to be found by hand. This is why we built independent validation (Census business counts, commuting, neighbours) instead of trusting the pillars.

**3. Failures that fixed themselves into the cache.** A failed healthcare result was cached and served back on every retry ("unchanged" 17 times in Chicago). A failure in only the clinics or pharmacies query was silently ignored, giving places like Wimberley a healthcare score of 2.1. Parallel pillar threads shared one cache temp file and corrupted it.

**4. Hand-built data for each new state or city.** Precinct files for six states, baselines for three metros, crime sources (Chicago, Philadelphia, Austin), a block-group file for Austin, place lists with corrected pins (Bastrop, Chester, Burlington), and a crime agency mapping. The automatic crime match chose park districts, forest preserves and neighbouring police departments for several suburbs.

**5. Code bugs that only appear with new geography.** Connecticut towns crashed social fabric (county subdivision, no "place"). Two places named Ridgewood collided in the retry step. The archetype script didn't know the new metros. The 2024 election join cannot work for states that redrew precincts.

**6. Tooling and process.** More than 50 admin scripts with no single status view; scoring depended on a laptop (Python 3.14 vs 3.12, a venv in the wrong folder, a missing proxy header, a duplicate `.env` line); long runs had no hard timeouts (15 minutes per place against a dead Overpass); and recomputing composites with live Census lookups moved scores by up to 17 points with no data change.

**7. Back-and-forth.** Several of the above were found only after a user paste, because there was no single place that said "here is exactly what is wrong and what to do." That is what the metro agent and the runbook were built to fix.

## What we built

- `scripts/metro_agent`: preflight, diagnose, resolve (retry), validate (independent cross-checks), probe (ask upstream directly), fbi (crime agency finder), run (whole launch), health (audit all metros, `--fix`), accept (sign off a real gap), withhold (show failed pillars as unknown).
- Data-driven fixes instead of code: `data/crime_agency_map.json`, accepted-gap files.
- Fixes at the source: remark-as-error handling in Overpass, no cached failures, healthcare category retries, empty-walkable-area rule, Connecticut towns, duplicate names, `--no-census` recomputes.
- `docs/METRO_RUNBOOK.md` (one page), a rewritten playbook, and 16 one-off scripts archived.

## Decisions made (for the record)

- Empty walkable areas score low, with confidence capped.
- Zero transit routes with 2–5% of commuters riding transit is accepted as low by design (service exists, outside the walking radius); above 5% it blocks as a likely failed lookup.
- County sheriff data used for unincorporated places is labelled lower precision.
- Political lean keeps the 2020 value where 2024 cannot be joined, labelled as such in the UI.
- A metro may publish with specific failed pillars shown as unknown; they stay on the rescore list.
- No private Overpass server for now.

## What would make the next metro fast

Ranked by how much time each would have saved.

1. **Decide the Overpass dependency.** It caused the majority of retries and all of the hangs. Options are a private instance (rejected for now), a scheduled overnight run with throttling, or caching raw OpenStreetMap responses per metro so a rescore never re-queries. Until one is chosen, expect every launch to stall on it.
2. **Make pillars fail honestly.** A failed lookup should return failed or degraded, never a successful zero. The validators then become a safety net instead of the only detector, and no cache should ever store a failure.
3. **Validate the place list before scoring.** Pins against Census town centres, duplicate (name, state) pairs, and the rule that a pin change invalidates the stored score. Most of this exists now in preflight; it should be mandatory.
4. **Generate the per-state data, don't hand-build it.** One command per state for precinct data, a probe that proposes crime agency mappings for approval, and a registry of crime sources. Today each is a separate manual step.
5. **Run scoring on a server, not a laptop.** Same Python, same environment variables, no sleeping machine, logs in one place.
6. **Keep a small recorded-response test metro.** Five places with saved upstream responses would catch bugs like the Connecticut crash and the duplicate-name collision without any live API.
7. **Treat "accept" and "withhold" as normal.** A launch should end with a short list of accepted gaps and withheld values, each with a reason, not with a hunt for perfection.

## Open items

- Seattle (Ballard, Kirkland) and Philadelphia need Overpass.
- Nine withheld values (SF 4, NYC 5) need a rescore when Overpass is back.
- Ridgewood (Queens) built environment fails repeatedly; cause unknown.
- 2024 political lean for IL, IN and DE (three options were laid out; the labelled 2020 value is the interim choice).
- The Overpass remark bug may have affected catalogs scored before it was fixed; the live metros were re-audited, but the full extent is unknown.
- Climate profiles, work-commute hubs and `cbd_transit_minutes` are missing for the new metros; Seattle has no incident-level crime source.
- Credentials were pasted into chat during the week and should be rotated.
