# Healthcare access: density-based baseline pilot (2026-10-28)

Status: PILOT, offline, proposal only. No code or catalog file was changed. Computed from stored catalog data (`data/*composites_recomputed.jsonl`, 1,458 places with stored healthcare counts) and the local density tables (people plus jobs per gross acre in the 1 km around the pin, the same factor active outdoors now uses).

## How healthcare scores today
Total 0 to 100 from five parts, each judged against an expected count that comes from the area-type table:
- Hospitals (35): count within the facility radius against expected hospitals (20), plus distance to the nearest hospital (15). Small bonus for extra hospitals.
- Primary care (25): clinics plus doctors within the facility radius against expected "urgent care" (the code reuses that table value).
- Specialized care (15): distinct specialty tags against a fixed 8.
- Emergency services (10): hospitals tagged as having an ER against expected hospitals.
- Pharmacies (15): count within the pharmacy radius against expected pharmacies.

The area type sets both the expected counts (hospitals 5, 1, 0, 0; urgent care 17, 3, 1, 0; pharmacies 3, 2, 1, 0 for urban residential, suburban, exurban, rural) and the search radius (facilities 5, 10, 15, 20 km; pharmacies 2, 3, 5, 8 km). The table comments cite small samples (n=10 to 19) from earlier pilots.

## Finding 1: facility density rises smoothly with activity density
Median stored counts divided by the area of the radius each place used, by people plus jobs per acre:

| Activity per acre | Places | Hospitals per km2 | Urgent care per km2 | Clinics per km2 | Pharmacies per km2 | Nearest hospital (km) | Nearest pharmacy (km) | Median score |
|---|---|---|---|---|---|---|---|---|
| 0 to 3 | 122 | 0.002 | 0.00 | 0.00 | 0.01 | 8.8 | 2.51 | 58 |
| 3 to 6 | 186 | 0.007 | 0.01 | 0.01 | 0.04 | 4.2 | 1.69 | 86 |
| 6 to 10 | 228 | 0.016 | 0.02 | 0.03 | 0.07 | 3.2 | 1.37 | 90 |
| 10 to 15 | 245 | 0.028 | 0.03 | 0.05 | 0.11 | 2.9 | 1.10 | 94 |
| 15 to 25 | 262 | 0.048 | 0.05 | 0.09 | 0.14 | 2.1 | 0.84 | 100 |
| 25 to 45 | 190 | 0.076 | 0.08 | 0.15 | 0.25 | 1.5 | 0.63 | 100 |
| 45 to 100 | 127 | 0.137 | 0.14 | 0.38 | 0.88 | 1.1 | 0.48 | 100 |
| 100 and up | 98 | 0.592 | 0.72 | 1.25 | 6.09 | 0.9 | 0.23 | 100 |

Counts rise by two to three orders of magnitude across the range, with no step at a type line, the same shape as parks.

## Finding 2: the score is capped at 100 for most of the catalog
The median score is 100 from 15 activity per acre upward, and 86 to 94 in the 3 to 15 range. Only the lowest-density places spread out (median 58). The ratio curve tops out at 95 percent of each part's maximum at 3 times the expected count, and the type-table expectations are low enough that dense places hit that easily. A density-peer baseline would not fix this by itself: it would recentre every place near 50, which is the wrong meaning for access to care.

## Why parks logic does not transfer directly
For parks the question was "how much green space does a place like this normally have". For healthcare the question a person cares about is closer to "how far am I from care", and that does not depend on what comparable neighbourhoods have. A peer baseline would score a dense place with one hospital nearby the same as a rural place with one hospital nearby, while their real access differs.

## Options
A. Peer baseline by density, as with parks (counts per area, judged against places at the same activity density). Fixes the type cliffs, but ranks places against peers rather than measuring access, and keeps the ceiling problem.
B. One absolute scale for every place, as with trails: distance to the nearest hospital, emergency department and pharmacy, plus counts within one fixed radius for all places. No area type, no density input. Needs published or survey evidence for the distance curve (TODO: source; candidates to look for are studies of travel time to emergency care and federal measures of healthcare shortage areas, none verified yet).
C. Hybrid: distances absolute (B), counts relative to density peers (A).

## What each option needs
- Distances: stored for every place (nearest hospital and nearest pharmacy), so B and C can be recomputed offline. Fallback hospital database distances are already mixed in for places with no OSM hospital in range.
- Counts at one common radius: NOT stored. The stored counts use four different radii, so they cannot be compared across types directly. A fixed-radius count needs a fresh read (the private Overpass server is up and covers 11 states; 7 states needed the extension that was just added).
- Specialties and doctors: the doctor count and the specialty tags are not stored, so those two parts (primary care partly, specialized care) cannot be re-fit offline. They would stay on their current logic until a fresh read.

## Caveats
- The stored nearest-hospital distance mixes OSM and fallback database results.
- The score ceiling affects the answer: any redesign should be tested for whether it separates places in the 15 and up range, where today almost everything is 100.
- Healthcare is regional more than local, so a 1 km density factor is a weak proxy for access; distance and drive time are the more direct measures.

## Decisions needed
1. Measure access with an absolute scale (B or C) or keep peer-relative scoring (A).
2. Whether a fresh fixed-radius read is acceptable for the count parts.

---

# Option B first look: distance-only scale (added 2026-10-28)

Status: proposal and sketch only. No code or catalog file changed.

## What the evidence gives us (all measured as drive time or road distance, not straight-line)
- Hospital emergency access: a national study of US emergency departments (Carr and colleagues, 2009, 2003 population data) found 71 percent of the population within 30 minutes of an emergency department and 98 percent within 60 minutes. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC2728684 and related summaries. Descriptive, dated.
- Outcomes: a Health Affairs study of emergency department closures (2001 to 2013, 3,720 hospitals) reports the largest mortality effects when driving time rises by 30 minutes or more. I could not verify the specific mortality figures quoted in secondary summaries. An NBER working paper (w32189) notes other studies of rural closures find mixed mortality effects.
- Pharmacy: a 2024 national study of pharmacy deserts used 1 mile for urban tracts, 5 miles for suburban and 10 miles for rural, 0.5 mile where few residents own a car. Other sources use 2 miles for suburban; the two do not agree. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC11034534/. Critics argue for travel time over distance.

These are thresholds for lacking access, not a scoring curve. The curve between them is a design judgment.

## What the stored catalog gives us
Nearest hospital and nearest pharmacy are stored as straight-line kilometres for 1,458 and 1,362 places (96 places have no pharmacy inside their search radius). The catalog median is 2.4 km to a hospital (90th percentile 7.2 km, 95th 27 km) and 0.9 km to a pharmacy. 67 percent of places have a pharmacy within 1 mile and 88 percent within 2 miles. Drive time is not stored, so any published time threshold needs a straight-line conversion (a road factor and a speed), which is itself unsourced (TODO).

## Finding: the existing hospital distance curve is already close to the published points
The current hospital distance part (15 points) is 15 x exp(-distance / 15 km). With an assumed 50 km/h and a 1.3 road factor (both unsourced), 30 minutes is about 19 km straight-line, where the curve gives about 28 percent of the points, and 60 minutes is about 38 km, where it gives about 12 percent. Under the published distribution, a person at 30 minutes is farther than 71 percent of the population (29 percent worse off) and at 60 minutes farther than 98 percent. The two readings are in the same range. So the hospital distance part may not need replacing; the open work is its source note and the road conversion, not the curve.

## Pilot: replace the pharmacy count with distance
Sketch only: pharmacy points = 15 x 2^(-distance / 1.609 km), so half credit at 1 mile (the urban desert line). Places with no pharmacy in their radius were scored at their radius distance (an upper bound).

| | Stored | Sketch |
|---|---|---|
| Mean pharmacy points (of 15) | 12.1 | 9.2 |
| Mean change in pillar score | | -2.9 (10th percentile -8.3, 90th +3.5) |
| Urban residential / suburban / exurban / rural | | -2.2 / -1.3 / -5.5 / -5.5 |

Do not read the drop as a finding: this sketch curve never reaches the full 15 points, so every place loses some. The shape and the full-credit point have to be chosen first (for example full credit inside a stated distance), and the choice would set the result. The sourced inputs are the three desert thresholds (1, 2 or 5, and 10 miles); the shape between them is judgment.

## What can and cannot be done offline
- Offline now: hospital distance part (source note and conversion only), pharmacy as a distance term.
- Needs a fresh read: hospital and emergency counts at one common radius, clinics and doctors, specialty tags (not stored, or stored at four different radii).

## Decisions needed
1. Keep the hospital distance curve and document the sources and the road conversion, or change it.
2. For pharmacies: pick the full-credit distance and the shape. Which suburban threshold (2 or 5 miles) do we cite?
3. Whether to run the fresh fixed-radius read for the count-based parts.

---

# Pharmacy distance term with full credit inside half a mile (added 2026-10-28)

Status: sketch only, offline, no code or catalog change. Full credit inside 0.5 mile (the carless-tract desert threshold). Two shapes beyond that, both using only published desert lines as anchors.

| Shape beyond 0.5 mile | Mean pharmacy points (stored 12.1) | Mean pillar change | 10th / 90th percentile | Places moving more than 5 |
|---|---|---|---|---|
| Straight line down to zero at 10 miles (rural desert line) | 14.2 | +2.1 | -1.0 / +9.5 | 23% |
| Half credit at 1 mile (urban desert line), then decay to 5 percent at 10 miles | 11.3 | -0.8 | -7.7 / +6.0 | 33% |

By area type (mean pillar change): straight line, urban residential +0.3, suburban +3.4, exurban +0.5, rural +1.3; half-credit shape, -0.2, +0.8, -3.6, -3.3.

Read this way: the straight line is lenient. A place 1.2 miles from a pharmacy still gets 92 percent of the points, even though the urban desert definition says access is lacking beyond 1 mile. The half-credit shape follows what the thresholds mean, and it is the one that moves exurban and rural places down about 3 to 4 points.

Data warning: 7 percent of places have no pharmacy stored inside their search radius, and several Chicago neighbourhoods (Berwyn, Edgewater, North Center, Ravenswood) show zero pharmacies within 2 km, which looks like an OpenStreetMap gap, not a real absence. They were scored at the radius distance, an upper bound, so their result is not reliable.

Decision needed: choose the shape (straight line, or half credit at 1 mile), then decide how places with no stored pharmacy are handled.

---

# Fresh fixed-radius read and the count-based parts (added 2026-10-28)

Status: pilot and proposal only. Source: a fresh read of 1,476 places at one radius (10 km), 1,460 with facilities, run on the private Overpass server (`analysis/hc_fresh_read/healthcare_fresh.json`). No code or catalog change.

## Check on the stored data
Fresh hospital counts equal the stored counts for 75 percent of suburban places (the type whose stored radius was also 10 km), with a median ratio of 1.00. The stored catalog is current.

## Finding 1: counts rise with density, as expected
Median counts within 10 km, by people plus jobs per acre: hospitals 2 (under 3) to 54 (100 and up), emergency-room hospitals 0 to 44, clinics 3 to 198, doctors 2 to 154, pharmacies 3 to 423. 41 percent of the lowest-density places have no hospital within 10 km, and 51 percent have no emergency room; from 15 per acre up, every place has both.

## Finding 2: per resident, the supply is flat across density
People within 10 km, estimated from the density tables (density x disk area, 2020 tracts; an approximation), against the fresh counts:

| Activity per acre | Places | People within 10 km | Hospitals per 100,000 | ER hospitals per 100,000 | Clinics + doctors per 1,000 | Pharmacies per 1,000 |
|---|---|---|---|---|---|---|
| 0 to 3 | 120 | 87,730 | 1.58 | 0.00 | 0.06 | 0.05 |
| 3 to 6 | 185 | 208,013 | 2.31 | 1.57 | 0.07 | 0.05 |
| 6 to 10 | 229 | 323,722 | 2.56 | 1.74 | 0.08 | 0.05 |
| 10 to 15 | 247 | 470,743 | 2.27 | 1.61 | 0.08 | 0.05 |
| 15 to 25 | 263 | 590,200 | 2.45 | 1.62 | 0.07 | 0.05 |
| 25 to 45 | 191 | 972,009 | 2.13 | 1.56 | 0.08 | 0.05 |
| 45 to 100 | 127 | 1,484,094 | 1.93 | 1.40 | 0.07 | 0.06 |
| 100 and up | 98 | 4,224,901 | 1.52 | 1.17 | 0.09 | 0.10 |

Across a 50-fold range of density the per-resident supply barely moves (hospitals 1.5 to 2.6 per 100,000). That means one scale, facilities per resident within a fixed 10 km, needs no area type and no density baseline. The catalog median of 2.2 hospitals per 100,000 is of the same order as the national figure from memory (about 6,000 hospitals for 330 million people); I have not verified that number.

## What per-resident supply misses
A small town with one hospital serving 50,000 people looks as well supplied as a city, even if the hospital is 15 km away. So supply per resident is not enough alone; distance to care has to be part of it.

## Proposed absolute design (no area type, no density input) for the remaining parts
- Emergency and hospital proximity: distance to the nearest emergency-room hospital on the same distance curve as the hospital distance part (already close to the published points, see above). Uses the fresh read for the ER tag.
- Hospital capacity (replaces the hospital count against an expected count): hospitals within 10 km per resident.
- Primary care capacity (replaces clinics plus doctors against an expected count): clinics plus doctors within 10 km per resident. A published benchmark exists for providers (the federal 3,500 residents per primary care provider shortage threshold, source to verify); OpenStreetMap lists facilities, not providers, so the equivalent threshold is a TODO and the scale would use catalog quantiles until sourced.
- Specialized care: distinct specialty tags within 10 km, against a fixed 8 today. Only 5 to 20 percent of facilities carry the tag, so this part measures OpenStreetMap tagging, not specialties. Recommend leaving it as is with a documented caveat, or dropping it and rescaling.

## Caveats
- 16 places have no facility of any kind within 10 km in OpenStreetMap, including towns such as Galt, CA and several near San Antonio; most look like data gaps and would be handled as unknown, as with pharmacies.
- Per-resident figures use an approximate population.
- Quantile scales are descriptive of the catalog, not external standards; they would carry the same note as the park baselines.

## Decisions needed
1. Approve the two-part design (distance to the nearest emergency room hospital plus facilities per resident within 10 km) for the count-based parts.
2. Specialized care: leave, or drop and rescale.
