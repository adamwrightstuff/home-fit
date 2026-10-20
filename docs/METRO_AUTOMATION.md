# Metro automation

Adding a metro used to mean editing about eight files by hand and running a dozen scripts in the right order. It is now five commands, driven by one registry and one spec file per metro. Every automatic decision is a documented, data-driven rule that is the same for every place (DESIGN_PRINCIPLES.md: objective, reproducible, scalable, transparent). No code branches on a city name.

```bash
cd ~/Dev/home-fit && source .venv/bin/activate && export PYTHONPATH=.
export OVERPASS_URL=http://localhost:12346/api/interpreter        # tunnel to the private Overpass server (docs/PRIVATE_OVERPASS.md)

python -m scripts.metro_agent prereqs --state AZ                  # what each state still needs
python -m scripts.metro_agent init   --metro phoenix              # spec -> checked place list, pins, registry entry, baselines
python -m scripts.metro_agent run    --metro phoenix              # preflight, score, retries, gate (hours)
python -m scripts.metro_agent finish --metro phoenix              # education, crime agencies, retries, rule-based gap acceptance
python -m scripts.metro_agent ship   --metro phoenix              # gate, go live, stage only this metro, commit, push
```

Several metros back to back (one `run` at a time, because one local API serves the scorer):

```bash
bash scripts/catalog/run_metros_batch.sh phoenix san_antonio sacramento     # logs in /tmp/metro_batch_logs
```

## The registry (`data/metro_registry.json`)

The single list of metros. Each entry has a label, picker name, color, map bounds, `states`, `cbsa` (Census county definition), an `inference` rule (tags an untagged place with its metro), and a `status`:

- `building`: scored or being scored, not shown on the site.
- `live`: shown on the site.

`registry generate` rewrites the blocks between `BEGIN GENERATED` and `END GENERATED` in `frontend/lib/catalogMetros.ts`, `catalogServer.ts`, `catalogMapTypes.ts` and `frontend/next.config.js`, listing only live metros. The baseline builder, the education scripts and the preflight read the same file. Never edit a generated block by hand.

## Spec (`data/metro_specs/<slug>.json`)

```json
{"slug": "tucson", "label": "TUS", "long_label": "Tucson metro", "cbsa": "46060", "states": ["AZ"],
 "neighborhoods": {"Tucson": ["Downtown Tucson", {"name": "Midtown Tucson", "query": "Midtown"}]},
 "suburbs": ["Oro Valley", "Marana", "Sahuarita"]}
```

Specs for the metros built so far are in `data/metro_specs/`, so any of them can be rebuilt with `init`.

## Pins

A suburb is pinned at the OpenStreetMap place node (city, town, village, suburb) of that name within 25 miles of the Census gazetteer point. The Census internal point of a large or oddly shaped city can sit 5 to 15 miles from the built-up town (Scottsdale 13.6 miles, Peoria and Goodyear 14.8), which scores the place on empty land: no amenities, no healthcare, failed natural beauty. The preflight pin check cannot catch this because it compares against the same Census point. A moved pin is recorded in `data/pin_exceptions.json` with the distance.

A neighborhood is pinned by a Nominatim lookup of `<name>, <parent city>, <ST>`, rejected unless the result names the parent city. Its pin must fall inside the parent city's Census boundary, otherwise `init` stops: an enclave city listed as a neighborhood (Alamo Heights inside San Antonio) would be scored with the parent city's police department. List it under `suburbs`.

Every place must be in a county of the metro's Census CBSA; others are dropped with a note. Re-pinning a place changes almost every pillar (Galveston, moved 14 miles: 10 of 14 pillars changed), so a moved place is re-scored in full. `run` does that automatically.

## Rules applied by `finish`

Each decision is written to the output with the evidence that triggered it. A place that meets no rule stays flagged for a person.

| Rule | Condition | Action |
|---|---|---|
| C1 own agency | A police agency named for the place, within 15 miles of the pin, returns agency-level data | Map the place to it (`data/crime_agency_map.json`) |
| C2 neighborhood | The place is a neighborhood of city X and "X Police Department" returns data | Map city X to it |
| C3 unincorporated | A Census-designated place (CDP) with no agency of its own and a county sheriff with data | Map to the sheriff as a county proxy (lower confidence; the scorer labels it) |
| C4 otherwise | None of the above | Record the gap with the nearby agencies that were not borrowed. Never use a neighboring town's numbers |
| T transit | Transitland found no routes and a retry agrees | Accept; the reason states the OpenStreetMap bus stops within 1.9 miles |
| H healthcare | No clinics, pharmacies or hospitals found and OpenStreetMap shows none within 3 miles | Accept; the reason states the 7.5-mile count |
| P political lean | No precinct polygon within range of the pin | Accept (opt-in filter) |
| E education | No K-12 district covers the pin (Census "School District Not Defined") | Reviewed exception in `data/education_check_exceptions.json` |

Agencies for special purposes (university, school district, hospital, park rangers, constable, fire, transit, state police, campus) are never used for C1 to C3.

## Prerequisites per state (`prereqs`)

| Need | Source | Cost |
|---|---|---|
| Election precincts (political lean) | Harvard Dataverse: VEST 2020 precinct maps and 2024 results. File IDs are looked up through the Dataverse API and stored in `data/election/dataverse_ids.json` | Free; 5 to 210 MB |
| Census district and place outlines | census.gov TIGER/Line 2024 | Free; about 5 MB |
| School snapshot | SchoolDigger, 500 schools per call | About $0.008 per call; 2 to 14 calls per state |
| School geography bundle | Rebuilt from the files above; byte-different but identical gzip files are restored | Free |
| Overpass coverage | The private server's extract (`data/overpass_states.json`) | Not automated: adding states is a rebuild of a few hours (`scripts/overpass_server/add_states.sh`) |

Nothing is downloaded or paid for without `--yes`; the plan states what, from where, and how much first. Some states redrew precincts after 2020, so the 2024 results do not join; the lookup then shows the 2020 lean, labelled as such.

## What stays manual, on purpose

- Adding states to the Overpass server (provisioning and cost).
- An incident-level crime feed for a core city. Until one exists, neighborhoods in that city share one city-wide rate (the preflight warns).
- Current attendance-zone maps. Until added, schools use the labelled 2015-16 fallback zones.
- Anything a rule does not cover. `finish` leaves it flagged and says why.

## Operating rules

- One scoring `run` at a time per local API port. `finish` uses port 8010 so it can run next to a batch on 8000.
- `ship` stages only an allowlist: the metro's own place list and scores, the registry, the generated frontend blocks, and shared data (crime map, pin exceptions, baselines, climate rows, school and election data). Another metro's scores are never committed, and an unfinished metro is never shown (its status stays `building`).
- Delete or snapshot the Overpass server when the batch is done (it bills by the hour, powered off or not).
