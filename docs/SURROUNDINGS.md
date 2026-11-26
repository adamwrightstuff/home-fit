# Surroundings ("Around here")

A description of the places around a catalog place, next to the place's own figures. Not a pillar: no score, no weight, not counted in any total. Shown in the Explorer side panel, the mobile sheet (expanded) and the neighborhood page.

## Why

What people live with comes partly from next door. Research supports two effects that our pillars do not already count by radius:

- **Relative standing and prices.** People report lower happiness when nearby incomes rise, holding their own income fixed (Luttmer, "Neighbors as Negatives", Quarterly Journal of Economics, 2005). Expensive neighbors push prices up next door.
- **Crime across the line.** Violence in an area tracks violence in the areas next to it, separately from its own conditions (Morenoff, Sampson and Raudenbush, Criminology, 2001).

Amenities, active outdoors, healthcare, transit and economic opportunity already measure by radius, so they include the neighbors and are left out here. Schools are left out because the assigned district is set by the town line: a better district next door does nothing for a family that does not move.

## What it shows

| Row | Source (stored in the catalog) |
|---|---|
| Household income | `housing_value.summary.median_household_income` (Census ACS 2022) |
| Home value | `housing_value.summary.median_home_value` (Census ACS 2022) |
| Safety score | `community_safety.score` (0 to 100, higher is safer) |

"Nearby" is a weighted average over the other catalog places within 8 miles, each weighted `exp(-(d / 3 mi)^2)`, so the closest count most. The three closest are named.

## Rules

- Only catalog places count as neighbors, not every town or tract. A place whose nearby weight is under 1.0 gets no figure (about 54% of places get one).
- Census caps: neighbors at the cap ($250,001 income, $2,000,001 home value) count at the cap, so the nearby figure is a floor. A place that is itself at the cap gets no comparison for that row.
- Safety uses only places whose rate is their own: a city incident-feed circle (`*_open_data`), or the yearly total of a police department that is not a sheriff or county force, is not shared by another catalog place, and does not cover a city neighborhood. Places on a city-wide, county, sheriff-station or state rate get no safety row and are not counted as anyone's neighbor for safety. In big cities without an incident feed (Houston, Phoenix, Atlanta and others), every neighborhood shares one city-wide rate, so a nearby figure there would only show where police reporting stops.
- A row scored at a pin the place list has since moved is left out entirely (no figure, not a neighbor).
- Missing data leaves the row or the whole card out; it is never shown as zero.

## Known limits (accepted, not validated)

- 8 miles, 3 miles and the 1.0 minimum weight are judgment calls (about a short drive), not fitted to any research.
- Straight-line distance, not drive time.
- No independent check that the nearby figure matches what residents experience.
- A neighbor's bad stored record flows into the nearby figure (for example North Miami's safety record, 0.14 violent crimes per 1,000, counts toward North Miami Beach).

## Build

Offline, from stored catalog numbers, no API calls:

```bash
cd ~/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/build_catalog_surroundings.py
```

Writes `data/catalog_surroundings.json`, joined into catalog places by `catalog_api.py` (list and detail) and `frontend/lib/catalogServer.ts` (neighborhood pages). Rebuild after any change to housing value, community safety or pins.
