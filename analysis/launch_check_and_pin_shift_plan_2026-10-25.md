# Launch check and pin-shift test: plan (2026-10-25)

Status: plan plus offline pilot results. No code, data, or catalog changed. Covers design principles v2 P10 (do places that
should differ actually differ) and P6 (how much does a score move when the pin moves).

## 1. Launch check (P10)

What it is: a script that runs on the stored catalog files in seconds, with no API calls, before a metro launches and
after any scoring change. It is a tripwire for data or logic problems. A failure means investigate the data or the code;
it is never a reason to tune a parameter until a place or a pair passes (design principles v1 forbid tuning to targets).

Four checks per pillar:
1. Spread and clumping: standard deviation, share of places at the maximum, share at the minimum, share in the single most
   common rounded value, number of distinct values, share of variance that is between metros.
2. Pre-registered contrasts: a file `data/launch_check_contrasts.json` written by the owner BEFORE looking at results: (pillar,
   group A, group B, expected sign, minimum gap, reason or source). Start with area-type contrasts where the direction is not
   in doubt (healthcare, air travel, transit, amenities, economic opportunity: urban above rural). Add a short list of named
   pairs only if the owner picks them in advance. Pillars where direction is a preference (diversity, natural beauty) get none.
3. Coverage: share of places that are no data or degraded per pillar and per metro, and any metro where 90% or more of places
   share one value for a sub-metric (this would have caught the IRS zeros in Chicago, Raleigh and Charlotte).
4. Report: `analysis/launch_check_<date>.md` plus a non-zero exit code on any failed gate, so `metro_agent health` can call it.

Proposed gates (judgment, to be set by the owner): fail if 25% or more of places sit at the maximum or the minimum; warn if the
most common rounded value holds more than 15%, or the standard deviation is below 5, or a metro is degenerate on a sub-metric.

### Pilot on the stored catalog (1,476 places)

| Pillar | sd | At max | At min | Most common value | Between-metro share of variance | Reading |
|---|---|---|---|---|---|---|
| healthcare_access | 20.3 | 39.2% | 0.8% | 41.9% | 14% | FAIL: 40% of places are at 100, so the pillar cannot tell them apart |
| active_outdoors | 18.1 | 15.2% | 0.1% | 16.5% | 20% | warn |
| air_travel_access | 15.7 | 6.8% | 0.1% | 17.2% | 14% | warn (18 distinct values) |
| public_transit_access | 25.6 | 2.3% | 11.4% | 11.4% | 25% | warn: 11% at 0 |
| economic_opportunity | 6.2 | 0.1% | 0.1% | 10.7% | 74% | warn: separates metros, not places (by design, tracker D8) |
| diversity, social_fabric, climate_risk, housing_value, natural_beauty, neighborhood_amenities, quality_education, community_safety | 8.6 to 28.4 | under 2.5% | under 0.5% | under 8% | 7% to 43% | pass |

Area-type contrasts that already point the expected way: healthcare 96 (urban core) vs 53 (rural), air travel 90 vs 70, economic
82 vs 67. Several pillars do not carry an area type in the stored pillar data, so the script must read it from the catalog row.
No contrast file exists yet; the owner writes it first.

## 2. Pin-shift sensitivity test (P6)

Protocol (judgment, to be approved): a fixed-seed sample of 80 places stratified by metro and area type; each pin shifted 8
bearings at 250 m and at 500 m (a 3 to 6 minute walk, about the error of a geocoded address); rescore each pillar at each point.
Per pillar report the median, 95th percentile and maximum absolute change, and a reliability ratio: the between-place variance
within a metro divided by that variance plus the pin-shift variance. Proposed gates (judgment): flag if the 95th percentile
change exceeds 5 points or reliability is below 0.8.

What can run how:

| Group | Pillars | Cost | Status |
|---|---|---|---|
| Offline now | economic job access (LODES grid), air travel (airport list), climate PM2.5 (stored table) | none | pilot run, see below |
| Free APIs with caching | housing value, diversity, social fabric stability and cohesion (Census, Atlas) | a few thousand cached Census calls | not run; the housing ring experiment already shows the problem |
| Heavy | neighborhood amenities, transit, active outdoors, healthcare, natural beauty (Overpass, Transitland, Google Earth Engine), community safety | about 7,000 Overpass-type queries; the public Overpass blocks scripts, so it needs the private server (billed hourly) | needs an owner decision; run on 30 places first |
| Economic market quality only | economic market quality (metro-level) | none | document as shift-proof by construction |
| Education (corrected 2026-10-26) | education (district and zone lookups) | none, offline | NOT shift-proof: measured on 1,472 places, median 5.8 points for a 0.5 mile shift (p95 42.7); 387 places flagged above 15 points (commit 21497d8) |

### Pilot results (80 places, 8 bearings)

| Component | Median change at 250 m / 500 m | 95th percentile at 500 m | Between-place spread within a metro | Reading |
|---|---|---|---|---|
| Job access (0 to 100) | 0.0 / 0.1 | 0.2 | sd 5.3 | very stable, high reliability |
| Climate PM2.5 air points (0 to 20) | 0.0 / 0.0 | 0.04 | sd 0.35 | stable, but the component barely differs between places within a metro |
| Share of shifted pins in a different census tract | 27% / 43% | | | tract-based pillars are exposed |
| Housing value (from the earlier neighbor-tract experiment, not this protocol) | | adjacent tracts differ by 20 to 40 points | | fails: Bronzeville 19 to 72, Westwood 5 to 53, Midtown 12 to 47 |

Expected finding when the free-API group runs: housing and diversity are the least reliable, because a pin shift of 500 m
changes the tract in 43% of cases. The fix candidate is pooling tracts within about 700 m, population-weighted, with the same test
rerun to show the improvement (tracker D14).

## 3. Build plan (nothing built yet)

1. `scripts/qa/launch_check.py` (reads the catalog JSONL, no network) and `tests/test_launch_check.py` on small fixtures.
2. `scripts/qa/pin_shift.py` with a pillar registry marking each pillar offline, cached-API, or heavy, a fixed sample file, and
   cached results so a rerun costs nothing.
3. Reports to `analysis/`, not committed by default; a short summary table added to the audit tracker (fills P6 and P10).
4. Order: launch check first (a day of work, no data cost), then pin shift for the offline and free-API groups, then the heavy
   group only after the owner approves the Overpass spend.

## 4. Decisions needed from the owner
1. Approve or change the launch-check gates (25% at an extreme, 15% in one value, sd below 5).
2. Write the contrast list before the check is run.
3. Approve the pin-shift protocol (250 m and 500 m, 8 bearings, 80 places, 5-point and 0.8 gates).
4. Decide whether to fund the Overpass server hours for the heavy pillars.
