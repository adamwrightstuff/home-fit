# Python Starter

Quickly get started with [Python](https://www.python.org/) using this starter! 

- If you want to upgrade Python, you can change the image in the [Dockerfile](./.devcontainer/Dockerfile).

## Radius behavior (defaults)

The API automatically adapts search radii per pillar based on detected area context (urban_core, suburban, exurban, rural) and location scope (neighborhood vs city). These defaults are centralized and consistent across pillars; no parameters are required.

Examples of defaults:
- Active Outdoors: local 1km (urban/suburban) or 2km (exurban/rural); regional 15km or 50km
- Neighborhood Amenities: query 1km (neighborhood) or 1.5km (city); walkability 800m/1000m
- Public Transit: nearby routes within ~1.5km
- Healthcare: facilities 5–20km and pharmacies 2–8km by area type
- Neighborhood Beauty (Tree canopy): 1km urban, 2km elsewhere (with city-only fallback expansion)
- Air Travel: airports within 100km

No public parameters are needed to control these; they follow sensible defaults derived from the location.